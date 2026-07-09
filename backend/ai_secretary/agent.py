"""
Schooldom Secretary — ReAct agent loop.

Uses Ollama's native tool-calling API (supported by llama3.1+, llama3.2, gemma3).
The loop: send message → if tool_calls, execute → feed result back → repeat → stream answer.
"""
import json
import logging

import requests
from django.conf import settings

from .prompts import SECRETARY_SYSTEM_PROMPT
from .tools import TOOL_SCHEMAS, SecretaryTools

logger = logging.getLogger(__name__)

OLLAMA_CHAT_URL = "http://localhost:11434/api/chat"
SECRETARY_MODEL = getattr(settings, "SECRETARY_OLLAMA_MODEL", "llama3.2:3b")
MAX_ITERATIONS = 6      # safety cap — prevents infinite tool-call loops
MAX_HISTORY = 20        # messages kept in context
OLLAMA_TIMEOUT = (5, 120)  # (connect, read) seconds


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
    tools = SecretaryTools(tenant=tenant, requesting_user=requesting_user)

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
