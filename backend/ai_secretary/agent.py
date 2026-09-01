"""
Schooldom Secretary — ReAct agent loop.

Uses Ollama's native tool-calling API (supported by llama3.1+, llama3.2, gemma3).
The loop: send message → if tool_calls, execute → feed result back → repeat → stream answer.
"""
import hashlib
import json
import logging
import re

import requests
from django.conf import settings
from django.core.cache import cache

from .prompts import SECRETARY_SYSTEM_PROMPT
from .tools import TOOL_SCHEMAS, SecretaryTools, resolve_navigation_page

logger = logging.getLogger(__name__)

OLLAMA_CHAT_URL = "http://localhost:11434/api/chat"
SECRETARY_MODEL = getattr(settings, "SECRETARY_OLLAMA_MODEL", "llama3.2:3b")
MAX_ITERATIONS = 6      # safety cap — prevents infinite tool-call loops
MAX_HISTORY = 20        # messages kept in context
MAX_MESSAGE_CHARS = 2000
OLLAMA_TIMEOUT = (5, 120)  # (connect, read) seconds
ADMIN_ROLES = {"school_admin", "principal", "accountant", "school_superadmin", "super_admin"}


def _cache_key_for_command(text: str, history: list | None = None) -> str:
    message = (text or "").strip()
    history_text = json.dumps(history or [], sort_keys=True)
    digest = hashlib.sha256(f"{message.lower()}::{history_text}".encode("utf-8")).hexdigest()
    return f"ai_secretary:phase1:{digest}"


def _extract_class_name(text: str):
    matches = re.findall(r"\b(?:[A-Z]{2,5}\d?[A-Z]?|[A-Za-z]+\s?\d+[A-Za-z]?)\b", text)
    for item in matches:
        cleaned = str(item).strip()
        if cleaned.lower() in {"the", "for", "all", "of", "and", "school", "students", "class", "page"}:
            continue
        if any(keyword in cleaned.lower() for keyword in ["ss", "jss", "primary", "nursery"]):
            return cleaned
    return None


def _extract_context_class(history: list | None):
    if not history:
        return None
    for item in reversed(history):
        content = str(item.get("content", "") or "")
        candidate = _extract_class_name(content)
        if candidate:
            return candidate
    return None


def _extract_term(text: str):
    lowered = text.lower()
    if "first term" in lowered or "term 1" in lowered:
        return "First Term"
    if "second term" in lowered or "term 2" in lowered:
        return "Second Term"
    if "third term" in lowered or "term 3" in lowered:
        return "Third Term"
    return "First Term"


def parse_phase_one_command(text: str, history: list | None = None) -> dict:
    """Map short admin requests to the five Phase 1 agent actions."""
    message = (text or "").strip()
    if not message:
        return {"tool": "general_chat", "params": {}, "confidence": 0.0}

    if len(message) > MAX_MESSAGE_CHARS:
        return {"tool": "general_chat", "params": {}, "confidence": 0.0}

    cache_key = _cache_key_for_command(message, history)
    cached = cache.get(cache_key)
    if cached is not None:
        return cached

    lowered = message.lower()
    class_name = _extract_class_name(message) or _extract_context_class(history)
    term = _extract_term(message)
    question_count = None
    match = re.search(r"(\d+)\s+questions?", lowered)
    if match:
        question_count = int(match.group(1))

    if "timetable" in lowered:
        result = {
            "tool": "generate_timetable",
            "params": {"class_name": class_name or "SS2A", "term": term},
            "confidence": 0.96,
        }
        cache.set(cache_key, result, timeout=300)
        return result

    if "report card" in lowered or "report cards" in lowered:
        result = {
            "tool": "generate_report_cards",
            "params": {"class_name": class_name or "all", "term": term},
            "confidence": 0.93,
        }
        cache.set(cache_key, result, timeout=300)
        return result

    if "fee status" in lowered or "fee" in lowered and "status" in lowered:
        result = {
            "tool": "get_fee_status",
            "params": {"class_name": class_name, "scope": "school"},
            "confidence": 0.95,
        }
        cache.set(cache_key, result, timeout=300)
        return result

    if "cbt" in lowered or "computer-based" in lowered or "computer based" in lowered:
        subject = ""
        subject_match = re.search(r"for\s+([A-Za-z ]+?)(?:\s+with|\s+for|$)", lowered)
        if subject_match:
            subject = subject_match.group(1).strip().title()
        result = {
            "tool": "create_cbt_exam",
            "params": {
                "subject": subject or "General",
                "class_name": class_name or "SS2",
                "question_count": question_count or 50,
                "time_limit_minutes": 60,
            },
            "confidence": 0.94,
        }
        cache.set(cache_key, result, timeout=300)
        return result

    if "take me to" in lowered or "open" in lowered or "navigate" in lowered or "page" in lowered:
        page, _route = resolve_navigation_page(message)
        result = {"tool": "navigate_to_page", "params": {"page": page}, "confidence": 0.89}
        cache.set(cache_key, result, timeout=300)
        return result

    result = {"tool": "general_chat", "params": {}, "confidence": 0.1}
    cache.set(cache_key, result, timeout=300)
    return result


def _call_ollama(messages: list, stream: bool = False) -> dict | requests.Response:
    """
    POST to Ollama. Returns parsed JSON dict (stream=False) or raw Response (stream=True).
    Raises requests.RequestException on network errors.
    """
    payload = {
        "model": SECRETARY_MODEL,
        "messages": messages,
        "tools": TOOL_SCHEMAS,
        "stream": stream,
        "options": {
            "temperature": 0.3,
            "num_predict": 400,
            "num_ctx": 2048,   # prompt ~1200 tokens; smaller KV cache = faster CPU inference
        },
    }
    response = requests.post(
        OLLAMA_CHAT_URL,
        json=payload,
        stream=stream,
        timeout=OLLAMA_TIMEOUT,
    )
    response.raise_for_status()
    if stream:
        return response
    return response.json()


def run_agent(user_message: str, history: list, tenant, requesting_user) -> dict:
    """
    Run the full agent loop for one user turn.

    Args:
        user_message: The raw text the admin typed.
        history:      Previous conversation turns [{"role": ..., "content": ...}, ...]
        tenant:       The authenticated school tenant object.
        requesting_user: The authenticated User making the request.

    Returns:
        {
          "reply": str,           # final text to show the user
          "tools_called": list,   # names of tools that were invoked
          "error": str | None     # set only on hard failures
        }
    """
    if not requesting_user or not getattr(requesting_user, "tenant", None):
        return {"reply": "Your session is not linked to a valid school. Please sign in again.", "tools_called": [], "error": "Unauthenticated"}

    if getattr(requesting_user, "role", "") not in ADMIN_ROLES:
        return {"reply": "This assistant is restricted to admin users only.", "tools_called": [], "error": "Forbidden"}

    tools = SecretaryTools(tenant=tenant, requesting_user=requesting_user)
    normalized_message = (user_message or "").strip()
    lowered = normalized_message.lower()

    if len(normalized_message) > MAX_MESSAGE_CHARS:
        return {"reply": f"Message exceeds the allowed length of {MAX_MESSAGE_CHARS} characters.", "tools_called": [], "error": "Message too long"}

    if any(token in lowered for token in ["delete all", "delete student", "drop database", "purge school", "remove all students"]):
        if "confirm" not in lowered:
            return {
                "reply": "This is a sensitive operation and requires explicit confirmation. Please type: 'I confirm deletion of the targeted records'.",
                "tools_called": [],
                "error": "Confirmation required",
            }

    if "confirm" not in lowered and (
        ("all " in lowered and "parents" in lowered) or
        ("bulk" in lowered and "message" in lowered) or
        ("reminder" in lowered and "parents" in lowered) or
        ("all " in lowered and "students" in lowered and "message" in lowered)
    ):
        return {
            "reply": "I’m about to send a bulk parent reminder. Please confirm by replying: 'I confirm the bulk parent reminder for SS2.'",
            "tools_called": [],
            "error": None,
        }

    if "confirm" in lowered and (
        ("parent reminder" in lowered or "bulk parent" in lowered or "bulk message" in lowered)
    ):
        result = tools.dispatch("send_bulk_parent_message", {"class_name": "SS2", "message_type": "reminder", "message": "PTA meeting reminder"})
        return {
            "reply": result.get("message") or "Bulk reminder confirmed and sent.",
            "tools_called": ["send_bulk_parent_message"],
            "error": None if result.get("status") == "success" else result.get("message"),
        }

    phase_one = parse_phase_one_command(user_message, history=history)
    if phase_one["tool"] != "general_chat":
        result = tools.dispatch(phase_one["tool"], phase_one["params"])
        route = result.get("route")
        payload = {
            "reply": result.get("message") or result.get("summary") or "Done ✅",
            "tools_called": [phase_one["tool"]],
            "error": None if result.get("status") == "success" else result.get("message"),
        }
        if route:
            payload["route"] = route
        return payload

    # Build message list: system + trimmed history + new user turn
    messages = [{"role": "system", "content": SECRETARY_SYSTEM_PROMPT}]
    messages += history[-MAX_HISTORY:]
    messages.append({"role": "user", "content": user_message})

    tools_called = []

    for iteration in range(MAX_ITERATIONS):
        try:
            data = _call_ollama(messages, stream=False)
        except requests.exceptions.ConnectionError as exc:
            logger.error("Ollama connection refused: %s", exc)
            return {
                "reply": "Network issue — might be light problem 😅. I'll retry when you're back online.",
                "tools_called": tools_called,
                "error": f"ConnectionError: {exc}",
            }
        except requests.exceptions.Timeout as exc:
            logger.error("Ollama timed out (model may be overloaded): %s", exc)
            return {
                "reply": "The AI is taking too long to respond. Please try again in a moment.",
                "tools_called": tools_called,
                "error": f"Timeout: {exc}",
            }
        except requests.exceptions.HTTPError as exc:
            logger.error("Ollama HTTP error: %s — response: %s", exc, getattr(exc.response, 'text', ''))
            return {
                "reply": "Something went wrong communicating with the AI. Let's try again.",
                "tools_called": tools_called,
                "error": f"HTTPError: {exc}",
            }
        except requests.exceptions.RequestException as exc:
            logger.error("Ollama request failed: %s", exc)
            return {
                "reply": "Network issue — might be light problem 😅. I'll retry when you're back online.",
                "tools_called": tools_called,
                "error": str(exc),
            }

        message = data.get("message", {})
        tool_calls = message.get("tool_calls") or []

        if not tool_calls:
            # No more tool calls — return the final answer
            reply = message.get("content", "").strip()
            if not reply:
                reply = "Done ✅"
            return {"reply": reply, "tools_called": tools_called, "error": None}

        # ── Execute each requested tool call ─────────────────────────────
        # Add the assistant's tool-call message to history first
        messages.append({
            "role": "assistant",
            "content": message.get("content") or "",
            "tool_calls": tool_calls,
        })

        for call in tool_calls:
            fn = call.get("function", {})
            tool_name = fn.get("name", "")
            raw_args = fn.get("arguments", {})

            # Ollama sometimes passes arguments as a JSON string
            if isinstance(raw_args, str):
                try:
                    raw_args = json.loads(raw_args)
                except json.JSONDecodeError:
                    raw_args = {}

            tools_called.append(tool_name)
            logger.info("Secretary calling tool: %s(%s)", tool_name, list(raw_args.keys()))

            result = tools.dispatch(tool_name, raw_args)

            # Feed the tool result back as a "tool" role message
            messages.append({
                "role": "tool",
                "content": json.dumps(result),
            })

    # Exceeded iteration cap — ask Ollama for a plain summary of what happened
    logger.warning("Secretary exceeded MAX_ITERATIONS (%d)", MAX_ITERATIONS)
    messages.append({
        "role": "user",
        "content": "Please summarise what was completed so far in one short sentence.",
    })
    try:
        data = _call_ollama(messages, stream=False)
        reply = data.get("message", {}).get("content", "").strip()
    except Exception:
        reply = "Something went wrong. Let's try again — or I can note it for your IT team."

    return {"reply": reply or "Task completed.", "tools_called": tools_called, "error": None}
