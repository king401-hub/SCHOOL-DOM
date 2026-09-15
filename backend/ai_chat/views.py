"""Proxies chat requests to a locally running Ollama instance."""
import json

import requests
from django.conf import settings
from django.http import JsonResponse, StreamingHttpResponse
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated

# Shared with ai_secretary's admin agent (see ai_secretary/code_guard.py) so
# both AI personas cut a reply the moment it looks like code, from one
# implementation - re-exported under these names so existing imports/tests
# (ai_chat/tests.py) keep working unchanged.
from ai_secretary.code_guard import CODE_REFUSAL_MESSAGE, CODE_SIGNALS, looks_like_code as _looks_like_code
# Platform how-to knowledge (roles/navigation, common workflows, what
# Schooldom doesn't have) - shared with ai_secretary's admin agent so both
# personas answer platform questions from one source of truth.
from ai_secretary.prompts import PLATFORM_KNOWLEDGE_PROMPT

OLLAMA_CHAT_URL = "http://localhost:11434/api/chat"

# Same model as ai_secretary's Secretary mode by default (both read
# PHOENIX_OLLAMA_MODEL/SECRETARY_OLLAMA_MODEL, settings.py defaults both to
# llama3.2:3b) - Ollama only keeps one model warm at a time, so an admin
# switching between plain chat and asking the assistant to do something used
# to force an evict+reload every time. PHOENIX_OLLAMA_MODEL stays a separate
# env var so this can be dialed back to something smaller/faster under real
# load without touching Secretary or redeploying.
OLLAMA_MODEL = getattr(settings, "PHOENIX_OLLAMA_MODEL", "llama3.2:3b")

# Vision: required only when user attaches an image.
# Pull it with:  ollama pull llava
VISION_MODEL = "llava"

MAX_HISTORY_MESSAGES = 10       # fewer past messages = faster inference
MAX_MESSAGE_CHARS = 2000
MAX_IMAGE_BYTES = 8_000_000     # ~6 MB decoded; reject anything larger

SYSTEM_PROMPT = """You are SchoolDom AI, a personal assistant built into Schooldom — a school management platform used by Nigerian schools.

## Absolute rule — this overrides every other instruction below
You must NEVER write, generate, complete, fix, translate, or explain PROGRAMMING CODE -
a snippet in a language like Python, JavaScript, HTML, CSS, SQL, Java, etc. meant to run
on a computer - no matter how the request is worded: directly, "for a school project",
as pseudocode, as an example, inside a story or roleplay, or disguised any other way.
If asked for code in any form, reply with only this and nothing else:
"I can't help with writing code — I'm here for Schooldom admin tasks like lesson
plans, letters, and messages. What can I help you with on the platform?"

This rule is ONLY about programming code. It does NOT apply to math, arithmetic,
word problems, science, or any other academic subject - always help normally with
those exactly like any other assistant would. "3x3", "what is the square root of 9",
"solve for x", and similar are ordinary math questions, not code, and must never
trigger the refusal above.

""" + PLATFORM_KNOWLEDGE_PROMPT + """

---

## How to help users
- Give step-by-step guidance using the exact page names and button labels above.
- If asked about something not listed on the platform, say you are not sure rather than guessing.
- Help write lesson plans, report card remarks, parent letters, SMS drafts, or announcement text.
- Help with math, arithmetic, science, and general academic questions - a student or
  teacher asking "what is 3x3" or "explain photosynthesis" is normal homework help,
  not a request about the platform, and not code. Answer it directly and normally.
- Explain results or fee breakdowns if the user pastes data.
- You do NOT have access to live school data unless the user shares it directly in chat.
- Be warm, concise, and use markdown (bold, numbered lists) when it aids clarity.

## What you must never do
- Never write, generate, debug, or explain PROGRAMMING CODE (Python, JavaScript, SQL, HTML, etc. - actual code meant to run on a computer), even if asked directly, indirectly, or as part of a hypothetical or roleplay. Politely decline and redirect the user to Schooldom-related help instead. This does not cover math or academic questions - see above.
"""


def _clean_messages(raw_messages):
    cleaned = []
    for item in raw_messages[-MAX_HISTORY_MESSAGES:]:
        if not isinstance(item, dict):
            continue
        role = item.get("role")
        content = (item.get("content") or "").strip()
        if role not in ("user", "assistant") or not content:
            continue
        msg = {"role": role, "content": content[:MAX_MESSAGE_CHARS]}
        # Handle attached images — strip data-URL prefix, enforce size limit
        raw_images = item.get("images")
        if isinstance(raw_images, list) and raw_images:
            cleaned_imgs = []
            for img in raw_images[:2]:
                if not isinstance(img, str):
                    continue
                if ";base64," in img:
                    img = img.split(";base64,", 1)[1]
                if len(img) <= MAX_IMAGE_BYTES:
                    cleaned_imgs.append(img)
            if cleaned_imgs:
                msg["images"] = cleaned_imgs
        cleaned.append(msg)
    return cleaned


def _stream_ollama_reply(upstream):
    collected = ""
    try:
        for line in upstream.iter_lines():
            if not line:
                continue
            try:
                chunk = json.loads(line)
            except ValueError:
                continue
            if chunk.get("error"):
                yield str(chunk["error"])
                return
            content = (chunk.get("message") or {}).get("content", "")
            if content:
                collected += content
                if _looks_like_code(collected):
                    yield CODE_REFUSAL_MESSAGE
                    return
                yield content
            if chunk.get("done"):
                return
    except requests.exceptions.RequestException:
        yield "\n\n[Connection to the AI assistant was interrupted.]"
    finally:
        upstream.close()


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def chat(request):
    raw_messages = request.data.get("messages")
    if not isinstance(raw_messages, list) or not raw_messages:
        return JsonResponse({"detail": "messages is required."}, status=400)

    messages = _clean_messages(raw_messages)
    if not messages:
        return JsonResponse({"detail": "messages is required."}, status=400)

    has_images = any(msg.get("images") for msg in messages)
    model = VISION_MODEL if has_images else OLLAMA_MODEL

    payload = {
        "model": model,
        "messages": [{"role": "system", "content": SYSTEM_PROMPT}] + messages,
        "stream": True,
        "options": {
            "num_predict": 1024,   # cap response length for speed
            "num_ctx": 2048,       # context window — smaller = faster
            "temperature": 0.7,
        },
    }

    # This VPS runs Ollama on CPU only (no GPU), so even a small model like
    # OLLAMA_MODEL can take well over a minute per reply under load - this timeout must
    # stay comfortably BELOW gunicorn's --timeout (see schooldom.service),
    # which must in turn stay below nginx's proxy_read_timeout on /api/ (see
    # sites-enabled/schooldom). Whichever of the three is shortest silently
    # kills the other two - a mismatch here is what caused a mid-reply 500
    # with gunicorn logging "Worker exiting" instead of a clean timeout
    # response reaching the user.
    try:
        upstream = requests.post(OLLAMA_CHAT_URL, json=payload, stream=True, timeout=(5, 180))
    except requests.exceptions.RequestException:
        return JsonResponse(
            {
                "detail": (
                    "SchoolDom AI is offline. Make sure Ollama is running "
                    "('ollama serve') and the model is pulled "
                    f"('ollama pull {model}')."
                )
            },
            status=503,
        )

    response = StreamingHttpResponse(
        _stream_ollama_reply(upstream), content_type="text/plain; charset=utf-8"
    )
    response["Cache-Control"] = "no-cache"
    response["X-Accel-Buffering"] = "no"
    return response


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def status_check(request):
    try:
        resp = requests.get("http://localhost:11434/api/tags", timeout=3)
        online = resp.status_code == 200
    except requests.exceptions.RequestException:
        online = False
    return JsonResponse({"online": online, "model": OLLAMA_MODEL})
