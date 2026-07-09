"""Proxies chat requests to a locally running Ollama instance."""
import json

import requests
from django.http import JsonResponse, StreamingHttpResponse
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated

OLLAMA_CHAT_URL = "http://localhost:11434/api/chat"

# Speed: llama3.2:1b is 2-3× faster than 3b with similar quality for school tasks.
# Pull it with:  ollama pull llama3.2:1b
OLLAMA_MODEL = "llama3.2:1b"

# Vision: required only when user attaches an image.
# Pull it with:  ollama pull llava
VISION_MODEL = "llava"

MAX_HISTORY_MESSAGES = 10       # fewer past messages = faster inference
MAX_MESSAGE_CHARS = 2000
MAX_IMAGE_BYTES = 8_000_000     # ~6 MB decoded; reject anything larger

SYSTEM_PROMPT = """You are Phoenix AI, a personal assistant built into Schooldom — a comprehensive school management platform used by Nigerian schools.

## About Schooldom
Schooldom is a multi-role, multi-tenant school management system. It handles the full lifecycle of school administration including fees, exams, attendance, academic planning, results, communications, HR, and finance. Each school runs on its own isolated tenant.

## User Roles and What They Can Do
- **Admin**: Full platform control. Manages classes, students, teachers, staff, fee structures, finance (admin wallet, split payments, virtual accounts for parents), exam scheduling, broadcasts, notifications, and CBT (Computer-Based Testing) setup. Can download the Windows CBT admin app and deploy the student CBT app.
- **Teacher**: Marks attendance (location-verified), creates and manages CBT exams and quizzes, writes lesson/academic plans, views class lists, sends messages, and submits student results/remarks.
- **Student**: Views personal dashboard, attendance record, fee balance, digital ID card, assigned quizzes and exams, academic plans, messages, and exam results/report cards.
- **Parent**: Views their ward's fee balance and payment history, receives SMS broadcasts, and can pay fees through a virtual bank account provisioned by the school.

## Key Features
- **Fees & Finance**: Admin sets class fee structures. Parents pay via virtual accounts (bank transfer). The system tracks payments, splits to admin wallet, and maintains a full ledger. Students can view their outstanding balance.
- **CBT Exams**: Computer-Based Testing via a dedicated Windows app. Admin packages exams; students enter with a Student ID + PIN. Results (scores, broadsheets) are visible to admin and teachers after submission.
- **Attendance**: Teachers mark attendance in class using a location-aware QR/scan flow. Students can view their own attendance history.
- **Results & Report Cards**: Teachers upload student scores. Admins can export broadsheets and individual report cards.
- **Communications**: In-app messaging between all roles, push notifications, and SMS broadcasts to parents.
- **Academic Planning**: Teachers create lesson plans and academic calendars visible to students and admins.
- **HR**: Staff records and management for the school admin.
- **ID Cards**: Digital student ID cards generated from profile data.
- **Dark Mode**: The UI supports both light and dark themes.

## How to Help Users
- Answer questions about how to use Schooldom features clearly and step-by-step.
- Help users understand exam results, fee breakdowns, or attendance patterns if they paste data into chat.
- Write templates: report card remarks, parent letters, lesson plans, announcement text, SMS drafts.
- Explain educational concepts, help with homework topics, or draft academic content.
- When given an image, describe what you see and answer the user's question about it.
- You do NOT have access to live school data (students, fees, attendance records) unless the user pastes or shares it directly.
- Always be warm, professional, and concise. Use markdown formatting (bold, lists, headings) when it helps readability.
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

    try:
        upstream = requests.post(OLLAMA_CHAT_URL, json=payload, stream=True, timeout=(5, 120))
    except requests.exceptions.RequestException:
        return JsonResponse(
            {
                "detail": (
                    "Phoenix AI is offline. Make sure Ollama is running "
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
