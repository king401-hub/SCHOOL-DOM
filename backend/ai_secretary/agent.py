"""
Schooldom Secretary — ReAct agent loop.

Uses Ollama's native tool-calling API (supported by llama3.1+, llama3.2, gemma3).
The loop: send message → if tool_calls, execute → feed result back → repeat → stream answer.
"""
import hashlib
import json
import logging
import re
import time

import requests
from django.conf import settings
from django.core.cache import cache
from django.utils import timezone

from ai_chat.services.openrouter_client import (
    OpenRouterClient,
    OpenRouterError,
    OpenRouterTimeout,
    build_multimodal_content,
)
from ai_chat.services.usage import AIUsageExhausted, check_quota, consume_usage, usage_dict

from .code_guard import CODE_REFUSAL_MESSAGE, TOOL_CALL_LEAK_MESSAGE, looks_like_code, looks_like_leaked_tool_call
from .prompts import SECRETARY_SYSTEM_PROMPT
from .tools import TOOL_SCHEMAS, SecretaryTools, resolve_navigation_page

logger = logging.getLogger(__name__)

_KNOWN_TOOL_NAMES = {schema["function"]["name"] for schema in TOOL_SCHEMAS}

OLLAMA_CHAT_URL = "http://localhost:11434/api/chat"
SECRETARY_MODEL = getattr(settings, "SECRETARY_OLLAMA_MODEL", "llama3.2:3b")
MAX_ITERATIONS = 6      # safety cap — prevents infinite tool-call loops
MAX_HISTORY = 20        # messages kept in context
MAX_MESSAGE_CHARS = 2000
# (connect, read) seconds for ONE Ollama call. Tightened from (5, 300): a
# single iteration legitimately taking longer than 90s is itself a sign
# something's wrong, and the old 300s read timeout didn't actually bound
# anything - run_agent can call this up to MAX_ITERATIONS times per request,
# so the real request-wide bound is AGENT_DEADLINE_SECONDS below.
OLLAMA_TIMEOUT = (10, 90)
# Wall-clock budget for the WHOLE run_agent() loop, independent of
# per-call/iteration limits - without this, a pathological run could take up
# to MAX_ITERATIONS x OLLAMA_TIMEOUT[1] before Django even returns. Must stay
# comfortably below gunicorn's --timeout, which must stay below nginx's
# proxy_read_timeout for /api/ - the same chain documented in
# ai_chat/views.py, which already caused one production incident when
# mismatched (a mid-reply 500 instead of a clean timeout response).
AGENT_DEADLINE_SECONDS = 50
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
        if any(keyword in cleaned.lower() for keyword in ["ss", "jss", "primary", "nursery", "grade", "year", "level"]):
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


def _find_prior_user_request(history: list | None) -> str | None:
    """Recover the original ask that preceded an 'I confirm...' reply - the
    confirmation turn itself carries no class/content information, so a bulk
    action must look back here instead of guessing or hardcoding a default."""
    for item in reversed(history or []):
        if item.get("role") != "user":
            continue
        content = str(item.get("content") or "").strip()
        if content and "confirm" not in content.lower():
            return content
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

    if any(phrase in lowered for phrase in ["how many student", "student count", "number of student", "count student", "total student"]):
        result = {
            "tool": "count_students",
            "params": {"class_name": class_name},
            "confidence": 0.95,
        }
        cache.set(cache_key, result, timeout=300)
        return result

    if any(phrase in lowered for phrase in ["how many class", "class count", "number of class", "count class", "total class"]):
        result = {
            "tool": "count_classes",
            "params": {},
            "confidence": 0.95,
        }
        cache.set(cache_key, result, timeout=300)
        return result

    if any(phrase in lowered for phrase in [
        "list classes", "list my classes", "list the classes", "name the classes", "name my classes",
        "what classes", "which classes", "show me the classes", "show the classes", "classes do i have",
        "class names", "name of classes", "names of classes",
    ]):
        result = {
            "tool": "list_classes",
            "params": {},
            "confidence": 0.95,
        }
        cache.set(cache_key, result, timeout=300)
        return result

    if class_name and any(phrase in lowered for phrase in ["roster", "list of student", "students in", "who is in", "who's in"]):
        result = {
            "tool": "get_class_roster",
            "params": {"class_name": class_name},
            "confidence": 0.92,
        }
        cache.set(cache_key, result, timeout=300)
        return result

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
        subject_match = re.search(r"for\s+([A-Za-z ]+?)(?:\s+with|\s+for|$)", lowered)
        # Only fast-path when a subject was actually extracted - guessing
        # "General" (almost never a real Subject) used to silently create a
        # fabricated exam shell; now it would just 404. Let the full agent
        # loop ask for the subject naturally instead when none was given.
        if subject_match:
            subject = subject_match.group(1).strip().title()
            result = {
                "tool": "create_cbt_exam",
                "params": {
                    "subject": subject,
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


def _extract_fake_tool_call(content: str):
    """Ollama's small tool-calling models (3B-class) sometimes fail to use
    the native `tool_calls` field at all and instead write out a hand-rolled
    imitation of their own TOOL_SCHEMAS definition as plain message content
    - e.g. {"type":"function","function":{"name": "create_cbt_exam",
    "parameters": {...}}} (note "parameters", the schema's own key name,
    rather than "arguments", what a real tool_calls entry uses). Recover a
    usable call out of that instead of discarding the admin's request or
    leaking the raw JSON to them. Returns a dict shaped like a real
    tool_calls entry, or None if nothing recognisable was found."""
    if not content or "{" not in content or "}" not in content:
        return None
    start, end = content.find("{"), content.rfind("}")
    if end <= start:
        return None
    try:
        parsed = json.loads(content[start:end + 1])
    except json.JSONDecodeError:
        return None

    fn = parsed.get("function") if isinstance(parsed.get("function"), dict) else parsed
    name = fn.get("name") if isinstance(fn, dict) else None
    if not name or name not in _KNOWN_TOOL_NAMES:
        return None

    args = fn.get("arguments")
    if not isinstance(args, dict):
        args = fn.get("parameters") if isinstance(fn.get("parameters"), dict) else {}
    return {"function": {"name": name, "arguments": args}}


def _call_ollama(messages: list, stream: bool = False, use_tools: bool = True) -> dict | requests.Response:
    """
    POST to Ollama. Returns parsed JSON dict (stream=False) or raw Response (stream=True).
    Raises requests.RequestException on network errors.
    """
    payload = {
        "model": SECRETARY_MODEL,
        "messages": messages,
        "stream": stream,
        "options": {
            "temperature": 0.3,
            # 400, not 100: a tool-call JSON payload or a warm multi-sentence
            # reply needs more than ~75 words - still well short of Phoenix's
            # 1024, since tool-call payloads are compact and the system
            # prompt already asks for concise replies.
            "num_predict": 400,
            # 8192, not 512: the system prompt + all 23 TOOL_SCHEMAS alone are
            # already ~3k tokens - at 512 the model's own tool definitions
            # were being truncated out of context on every call, before a
            # single history message or tool-result round-trip was even
            # added. This was almost certainly the dominant cause of
            # unreliable tool selection. KV-cache memory scales with this
            # value - watch actual RAM usage after raising it, don't assume
            # it's free.
            "num_ctx": 8192,
        },
    }
    if use_tools:
        payload["tools"] = TOOL_SCHEMAS
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


def _call_openrouter(messages: list, use_tools: bool = True) -> dict:
    """POST to OpenRouter via OpenRouterClient, normalized to the same
    {"message": {"content": ..., "tool_calls": [...]}} shape _call_ollama
    returns above, so the rest of run_agent's loop needs no provider
    branching. TOOL_SCHEMAS is already OpenAI-shaped (same "type":
    "function"/"parameters" structure OpenRouter expects), so it's passed
    through unchanged - no translation needed.

    A message carrying an attached image (run_agent's user_turn, when the
    admin attached one this turn) gets its content reshaped into
    OpenRouter's multimodal block format, and the call switches to
    OPENROUTER_VISION_MODEL - the default model is text-only and would
    otherwise ignore the image's content block entirely. Tool-calling is
    skipped for a vision call: TOOL_SCHEMAS was written/tested against the
    text-only model, and asking it to both look at an image and pick a
    tool in one call is untested territory - the admin can always follow up
    with a plain-text instruction once they've described what's in the image."""
    has_images = any(m.get("images") for m in messages)
    openrouter_messages = [
        {
            "role": m["role"],
            "content": build_multimodal_content(m["content"], m.get("images"), m.get("_image_mime_types")),
        }
        for m in messages
    ]
    client = OpenRouterClient(model=getattr(settings, "OPENROUTER_VISION_MODEL", None) if has_images else None)
    kwargs = {"max_tokens": 600, "temperature": 0.3}
    if use_tools and not has_images:
        kwargs["tools"] = TOOL_SCHEMAS
    result = client.chat(openrouter_messages, **kwargs)
    return {"message": {"content": result["content"], "tool_calls": result["tool_calls"]}}


def _call_model(messages: list, use_tools: bool = True) -> dict:
    """Routes to OpenRouter or Ollama per settings.AI_PROVIDER - the one
    place run_agent's loop needs to know a second provider exists."""
    if getattr(settings, "AI_PROVIDER", "ollama") == "openrouter":
        return _call_openrouter(messages, use_tools=use_tools)
    return _call_ollama(messages, stream=False, use_tools=use_tools)


def _friendly_openrouter_message(exc: OpenRouterError) -> str:
    if exc.status_code == 402:
        return "I can't reach the AI right now — the AI provider account is out of credits. Please contact Schooldom support."
    if exc.status_code == 403:
        return "I can't reach the AI right now — access was denied by the AI provider. Please contact Schooldom support."
    if exc.code == "MISSING_API_KEY":
        return "The AI isn't configured yet. Please contact Schooldom support."
    return "Something went wrong reaching the AI. Let's try again — or I'll flag it for your IT team."


def run_agent(user_message: str, history: list, tenant, requesting_user, images: list = None, image_mime_types: list = None) -> dict:
    """
    Run the full agent loop for one user turn.

    Args:
        user_message: The raw text the admin typed.
        history:      Previous conversation turns [{"role": ..., "content": ...}, ...]
        tenant:       The authenticated school tenant object.
        requesting_user: The authenticated User making the request.
        images:       Bare base64 strings attached to THIS turn only (already
                      cleaned by ai_chat.services.openrouter_client.clean_data_url_images)
                      - history entries never carry images back in, same as ai_chat.
        image_mime_types: Matching MIME types for `images`.

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
        if "decline" in lowered:
            return {"reply": "Okay — nothing was deleted.", "tools_called": [], "error": None}
        if "confirm" not in lowered:
            accept_phrase = "I confirm deletion of the targeted records."
            return {
                "reply": f"This is a sensitive operation and requires explicit confirmation. Please type: '{accept_phrase}'",
                "tools_called": [],
                "error": "Confirmation required",
                "confirm_action": {
                    "accept_message": accept_phrase,
                    "decline_message": "I decline — do not delete anything.",
                },
            }

    if "decline" in lowered and (
        ("parent reminder" in lowered or "bulk parent" in lowered or "bulk message" in lowered)
    ):
        return {"reply": "No problem — I won't send that. Let me know if you'd like to try again.", "tools_called": [], "error": None}

    if "confirm" not in lowered and "decline" not in lowered and (
        ("all " in lowered and "parents" in lowered) or
        ("bulk" in lowered and "message" in lowered) or
        ("reminder" in lowered and "parents" in lowered) or
        ("all " in lowered and "students" in lowered and "message" in lowered)
    ):
        pending_class = _extract_class_name(normalized_message) or _extract_context_class(history)
        if not pending_class:
            # Don't guess a class (that's exactly what causes "not found"
            # failures) - offer the real options instead, same free,
            # zero-AI-cost dispatch the phase 1 fast path below uses.
            classes_result = tools.dispatch("list_classes", {})
            class_list = classes_result.get("classes") or []
            if not class_list:
                return {
                    "reply": "I couldn't find any classes set up yet — please add a class first.",
                    "tools_called": ["list_classes"],
                    "error": "No classes found",
                }
            names = ", ".join(c["label"] for c in class_list)
            return {
                "reply": f"Which class should this go to? Your classes are: {names}.",
                "tools_called": ["list_classes"],
                "error": None,
            }
        accept_phrase = f"I confirm the bulk parent message for {pending_class}."
        decline_phrase = f"I decline the bulk parent message for {pending_class}."
        return {
            "reply": f"I’m about to send a bulk parent message for {pending_class}. Please confirm by replying: '{accept_phrase}'",
            "tools_called": [],
            "error": None,
            "confirm_action": {"accept_message": accept_phrase, "decline_message": decline_phrase},
        }

    if "confirm" in lowered and (
        ("parent reminder" in lowered or "bulk parent" in lowered or "bulk message" in lowered)
    ):
        # The confirmation turn itself ("I confirm...") carries no class/content
        # information - it was previously hardcoded to class_name="SS2" and a
        # canned "PTA meeting reminder" message regardless of what was actually
        # requested. Recover the real request (and its class) from the message
        # that triggered the confirmation prompt above, via history.
        original_request = _find_prior_user_request(history) or normalized_message
        class_name = _extract_class_name(original_request) or _extract_context_class(history)
        if not class_name:
            return {
                "reply": "Which class should this go out to? Please confirm again with the class name included.",
                "tools_called": [],
                "error": "Missing class",
            }
        original_lower = original_request.lower()
        if "fee" in original_lower or "payment" in original_lower:
            message_type = "fee_reminder"
        elif any(word in original_lower for word in ("pta", "meeting", "event")):
            message_type = "event"
        else:
            message_type = "reminder"
        result = tools.dispatch("send_bulk_parent_message", {
            "class_name": class_name,
            "message_type": message_type,
            "message": original_request,
        })
        return {
            "reply": result.get("message") or "Bulk message confirmed and sent.",
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

    # Usage quota check - only HERE, not before the deterministic Phase 1 /
    # bulk-confirmation branches above, since those never call an AI
    # provider at all and shouldn't be blocked by an AI time allowance.
    # This is also what starts the user's 3-hour reset timer on their first
    # AI request of a cycle (see ai_chat/services/usage.py).
    try:
        check_quota(requesting_user, tenant)
    except AIUsageExhausted as exc:
        reset_str = exc.cycle.cycle_resets_at.strftime("%H:%M")
        return {
            "reply": f"You've used up your AI time for now. It resets at {reset_str}.",
            "tools_called": [],
            "error": "AIUsageExhausted",
            "usage": usage_dict(exc.cycle),
        }

    # Build message list: system (+ the real current time, so the model can
    # greet appropriately and reason about "today"/"yesterday" correctly
    # instead of guessing, + the school's actual name, so it's never left
    # out of a drafted letter/SMS/reminder - the model has no other way to
    # know it) + trimmed history + new user turn
    now_local = timezone.localtime()
    time_context = f"Current date and time: {now_local.strftime('%A, %d %B %Y, %H:%M')} ({settings.TIME_ZONE})."
    school_name = (getattr(tenant, "name", "") or "").strip() or "the school"
    school_context = f"This school's name is: {school_name}. Always include it when drafting any letter, SMS, or reminder sent to parents/guardians, unless the admin says otherwise."
    messages = [{"role": "system", "content": f"{SECRETARY_SYSTEM_PROMPT}\n\n{time_context}\n{school_context}"}]
    messages += history[-MAX_HISTORY:]
    user_turn = {"role": "user", "content": user_message}
    if images:
        user_turn["images"] = images
        user_turn["_image_mime_types"] = image_mime_types or []
    messages.append(user_turn)

    tools_called = []
    deadline = time.monotonic() + AGENT_DEADLINE_SECONDS
    ai_time_spent = [0.0]  # mutable box - timed_call_model below accumulates into it

    def timed_call_model(msgs):
        start = time.monotonic()
        try:
            return _call_model(msgs)
        finally:
            ai_time_spent[0] += time.monotonic() - start

    try:
        for iteration in range(MAX_ITERATIONS):
            if time.monotonic() > deadline:
                logger.warning("Secretary agent hit its %ds wall-clock deadline before MAX_ITERATIONS", AGENT_DEADLINE_SECONDS)
                break
            try:
                data = timed_call_model(messages)
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
            except OpenRouterTimeout as exc:
                logger.error("OpenRouter timed out: %s", exc)
                return {
                    "reply": "The AI is taking too long to respond. Please try again in a moment.",
                    "tools_called": tools_called,
                    "error": f"Timeout: {exc}",
                }
            except OpenRouterError as exc:
                logger.error("OpenRouter error (status=%s, code=%s): %s", exc.status_code, exc.code, exc)
                return {
                    "reply": _friendly_openrouter_message(exc),
                    "tools_called": tools_called,
                    "error": f"OpenRouterError: {exc}",
                }

            message = data.get("message", {})
            tool_calls = message.get("tool_calls") or []

            if not tool_calls:
                content = message.get("content", "").strip()
                fake_call = _extract_fake_tool_call(content) if content else None
                if fake_call:
                    logger.warning(
                        "Secretary model emitted tool call as plain content instead of tool_calls; recovered %s",
                        fake_call["function"]["name"],
                    )
                    tool_calls = [fake_call]
                else:
                    # No more tool calls — return the final answer. This is raw
                    # model text (unlike every other return point in run_agent,
                    # which is built from deterministic tool results), so it's
                    # the one place Secretary needs the same code-signal backstop
                    # Phoenix already has - the model has zero guardrail of its
                    # own otherwise.
                    if not content:
                        reply = "Done ✅"
                    elif looks_like_code(content):
                        # Nothing has been sent to the client yet (unlike
                        # Phoenix's streaming path, which can only append a
                        # refusal after whatever already left the server) -
                        # replace outright rather than show the leak plus a
                        # refusal after it.
                        reply = CODE_REFUSAL_MESSAGE.strip()
                    elif looks_like_leaked_tool_call(content):
                        # A tool-call-shaped blob _extract_fake_tool_call couldn't
                        # recover (unknown tool name or malformed JSON) - still
                        # must not reach the user as raw JSON.
                        reply = TOOL_CALL_LEAK_MESSAGE.strip()
                    else:
                        reply = content
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

                # Feed the tool result back as a "tool" role message - OpenRouter
                # (unlike Ollama) requires tool_call_id to match it to the
                # assistant turn that requested it; only add it when the
                # provider actually gave one (Ollama's native tool_calls and the
                # Ollama-only fake-call recovery above don't have one).
                tool_message = {"role": "tool", "content": json.dumps(result)}
                if call.get("id"):
                    tool_message["tool_call_id"] = call["id"]
                messages.append(tool_message)

        # Exceeded iteration cap — ask Ollama for a plain summary of what happened
        logger.warning("Secretary exceeded MAX_ITERATIONS (%d)", MAX_ITERATIONS)
        messages.append({
            "role": "user",
            "content": "Please summarise what was completed so far in one short sentence.",
        })
        try:
            data = timed_call_model(messages)
            reply = data.get("message", {}).get("content", "").strip()
        except Exception:
            reply = "Something went wrong. Let's try again — or I can note it for your IT team."

        if reply and looks_like_code(reply):
            reply = CODE_REFUSAL_MESSAGE.strip()

        return {"reply": reply or "Task completed.", "tools_called": tools_called, "error": None}
    finally:
        # Charges real AI time regardless of which return path above fired -
        # success, every provider-error branch, and the iteration-cap
        # fallback all go through this one accumulator.
        consume_usage(requesting_user, ai_time_spent[0])
