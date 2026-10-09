"""Schooldom Secretary AI — REST endpoint."""
import json
import logging

from django.http import JsonResponse
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated

from ai_chat.services.usage import usage_snapshot

from .agent import run_agent
from .tools import SecretaryTools

logger = logging.getLogger(__name__)

ADMIN_ROLES = {"school_admin", "principal", "accountant", "school_superadmin", "super_admin"}
MAX_MESSAGE_CHARS = 2000
MAX_HISTORY_TURNS = 20  # pairs


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def secretary_chat(request):
    """
    POST /api/secretary/chat/
    Body: { "message": "...", "history": [...] }

    Restricted to admin-level roles. Returns:
    { "reply": "...", "tools_called": [...] }
    """
    user = request.user

    # Role guard
    role = getattr(user, "role", "")
    if role not in ADMIN_ROLES:
        return JsonResponse(
            {"detail": "The Schooldom Secretary is only available to school admins and bursars."},
            status=403,
        )

    # Resolve tenant
    tenant = getattr(user, "tenant", None)
    if tenant is None:
        return JsonResponse(
            {"detail": "Your account is not linked to a school. Please contact support."},
            status=400,
        )

    # Parse body
    message = (request.data.get("message") or "").strip()[:MAX_MESSAGE_CHARS]
    if not message:
        return JsonResponse({"detail": "message is required."}, status=400)

    from ai_chat.services.openrouter_client import clean_data_url_images

    images, image_mime_types = clean_data_url_images(request.data.get("images"))

    raw_history = request.data.get("history")
    if not isinstance(raw_history, list):
        raw_history = []

    # Sanitise history — keep only role+content string pairs, trim to limit
    history = []
    for item in raw_history[-MAX_HISTORY_TURNS * 2:]:
        if not isinstance(item, dict):
            continue
        r = item.get("role")
        c = str(item.get("content") or "").strip()
        if r in ("user", "assistant") and c:
            history.append({"role": r, "content": c[:MAX_MESSAGE_CHARS]})

    # Run the agent
    result = run_agent(
        user_message=message,
        history=history,
        tenant=tenant,
        requesting_user=user,
        images=images,
        image_mime_types=image_mime_types,
    )

    if result.get("error") == "AIUsageExhausted":
        return JsonResponse({"detail": result["reply"], "usage": result.get("usage")}, status=429)

    if result.get("error") and not result.get("reply"):
        return JsonResponse({"detail": result["error"]}, status=503)

    response = {
        "reply": result["reply"],
        "tools_called": result.get("tools_called", []),
    }
    if result.get("route"):
        response["route"] = result["route"]
    if result.get("confirm_action"):
        response["confirm_action"] = result["confirm_action"]
    return JsonResponse(response)


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def secretary_status(request):
    """GET /api/secretary/status/ — check Ollama availability and role access."""
    import requests as req
    role = getattr(request.user, "role", "")
    has_access = role in ADMIN_ROLES
    try:
        r = req.get("http://localhost:11434/api/tags", timeout=3)
        online = r.status_code == 200
    except Exception:
        online = False
    return JsonResponse({
        "online": online, "has_access": has_access, "role": role, "usage": usage_snapshot(request.user),
    })


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def secretary_briefing(request):
    """GET /api/secretary/briefing/ - deterministic, zero-AI-cost daily
    briefing (fee defaulters, yesterday's payments) for the admin dashboard.
    No AI provider is called here - pure DB queries, safe to fetch on every
    login without touching anyone's AI usage quota."""
    user = request.user
    role = getattr(user, "role", "")
    if role not in ADMIN_ROLES:
        return JsonResponse({"detail": "Not available for this role."}, status=403)

    tenant = getattr(user, "tenant", None)
    if tenant is None:
        return JsonResponse({"detail": "Your account is not linked to a school."}, status=400)

    tools = SecretaryTools(tenant=tenant, requesting_user=user)
    data = tools.get_daily_briefing()
    if data.get("status") != "success":
        return JsonResponse({"detail": data.get("message", "Could not build the briefing.")}, status=500)
    return JsonResponse(data)
