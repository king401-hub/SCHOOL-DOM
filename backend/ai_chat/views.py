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

SYSTEM_PROMPT = """You are Phoenix AI, a personal assistant built into Schooldom — a school management platform used by Nigerian schools.

## Roles and their navigation menus

**Admin** sees these pages in the sidebar:
Dashboard · Performance Analytics · Finance · Expenses · Attendance · HR Management · Students · Parent Directory · ID Cards · Transcripts & Testimonials · Staff (Teachers / Non-Teaching Staff) · Classes · Exams · Results · Database Import · Messages · Loan Application · Settings

**Accountant** sees: Finance · Expenses · Payroll & Leave · Messages

**Teacher** sees: Dashboard · Attendance (scan flow) · Exams · Quizzes · Academic Planning · Messages · Results

**Student** sees: Dashboard · Attendance · ID Card · School Fees · Exams · Quizzes · Academic Planning · Messages · Results

**Parent** sees: Dashboard · School Fees · Payment History

---

## Exact workflows for common tasks

### Add a student (Admin only)
1. Go to **Students** in the sidebar.
2. Click **Add Student** (top-right of the page).
3. Fill in: Student Email, First Name, Last Name, Gender, Admission Date, Class, Guardian Name, Guardian Phone, Guardian Email, Guardian Relation (e.g. Father/Mother/Uncle), and optionally a Second Guardian.
4. Click **Create Student**.
The student is added immediately. No documents are uploaded here.

### Add a class (Admin only)
1. Go to **Classes**.
2. Click **Add Class**, enter the class name and arm (e.g. JSS 1, Arm A), then save.
You can also add subjects to a class and do bulk promotions from this page.

### Set up school fees (Admin only)
1. Go to **Finance**.
2. Under **Class Fees**, click **Add Fee**, pick the class, enter the fee title and amount, then save.
3. To generate individual fee bills for students, click **Generate Bills** for that class fee.
Parents pay via a Paystack virtual bank account (bank transfer) assigned to them — no cash handling in the app.

### Provision a parent virtual account (Admin only)
1. Go to **Finance** → scroll to **Virtual Accounts** section.
2. Find the parent row and click **Provision via Paystack**.
The parent is given a unique bank account number. When they transfer money to it, the payment is automatically recorded and split to the school wallet.

### Record or view attendance (Teacher)
1. Go to **Attendance**.
2. Click **Start Scan** to begin marking attendance for a class.
Students can view their own attendance history from their **Attendance** page.

### Create an exam (Admin / Teacher)
1. Go to **Exams**.
2. Click **Create Exam**, fill in the exam details and add questions.
For Computer-Based Testing (CBT), the Admin downloads the Windows CBT Admin App from **Settings → Downloads**, packages the exam, and students sit it on the offline Student CBT app.

### Upload results (Teacher)
1. Go to **Results**.
2. Select the class and upload/enter scores. Admins can then export broadsheets or individual report cards.

### Send a message or broadcast (Admin)
1. Go to **Messages**.
2. Compose and send to individual users or broadcast to all parents/students via SMS.

### Add a teacher or staff member (Admin)
1. Go to **Staff → Teachers** or **Staff → Non-Teaching Staff**.
2. Click **Add**, fill in their details, and save.

### Generate ID cards (Admin)
1. Go to **ID Cards**.
2. Select students and click **Generate** to produce digital ID cards.

### Import students in bulk (Admin)
1. Go to **Database Import**.
2. Upload a CSV file following the required template.

### School settings (Admin)
Go to **Settings** to update school name, logo, contact info, academic session, grading system, SMS configuration, and to download the CBT apps.

---

## What Schooldom does NOT have
- No document uploads during student registration (passport photos, birth certificates are not part of the add-student form).
- No "New Student" button at the top of the dashboard — it is inside the Students page.
- No separate "parent portal" login — parents log in through the same sign-in page and see their own restricted dashboard.
- No built-in video conferencing or timetable builder.

---

## How to help users
- Give step-by-step guidance using the exact page names and button labels above.
- If asked about something not listed, say you are not sure rather than guessing.
- Help write lesson plans, report card remarks, parent letters, SMS drafts, or announcement text.
- Explain results or fee breakdowns if the user pastes data.
- You do NOT have access to live school data unless the user shares it directly in chat.
- Be warm, concise, and use markdown (bold, numbered lists) when it aids clarity.

## What you must never do
- Never write, generate, debug, or explain programming code (Python, JavaScript, SQL, HTML, etc.), even if asked directly, indirectly, or as part of a hypothetical or roleplay. Politely decline and redirect the user to Schooldom-related help instead.
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
