"""Admin-facing Request Queue Management API."""
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .models import QueuedRequest
from .services import cancel_request, manual_retry

ADMIN_ROLES = {"school_admin", "principal", "super_admin", "school_superadmin"}

LIST_CAP = 200


def _actor_name(user):
    if not user:
        return "System"
    return user.get_full_name() or user.email


def _event_payload(event):
    return {
        "id": str(event.id),
        "event_type": event.event_type,
        "description": event.description,
        "actor": _actor_name(event.actor),
        "metadata": event.metadata,
        "created_at": event.created_at,
    }


def _request_payload(request_obj, *, include_history=True):
    data = {
        "id": str(request_obj.id),
        "request_type": request_obj.request_type,
        "status": request_obj.status,
        "requester": _actor_name(request_obj.requester),
        "requester_email": getattr(request_obj.requester, "email", ""),
        "retry_count": request_obj.retry_count,
        "max_retries": request_obj.max_retries,
        "last_attempt_at": request_obj.last_attempt_at,
        "next_retry_at": request_obj.next_retry_at,
        "expires_at": request_obj.expires_at,
        "error_message": request_obj.error_message,
        "result": request_obj.result,
        "is_duplicate": request_obj.linked_request_id is not None,
        "linked_request_id": str(request_obj.linked_request_id) if request_obj.linked_request_id else None,
        "is_archived": request_obj.is_archived,
        "created_at": request_obj.created_at,
        "updated_at": request_obj.updated_at,
    }
    if include_history:
        data["history"] = [_event_payload(event) for event in request_obj.history.select_related("actor").all()]
    return data


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def request_queue_list(request):
    """List queued requests for this tenant, with filters + queue-health stats."""
    user = request.user
    if user.role not in ADMIN_ROLES:
        return Response({"success": False, "message": "Admin access required."}, status=status.HTTP_403_FORBIDDEN)

    queryset = QueuedRequest.objects.select_related("requester").filter(tenant=user.tenant)

    include_archived = str(request.query_params.get("include_archived", "")).lower() in {"1", "true", "yes"}
    if not include_archived:
        queryset = queryset.filter(is_archived=False)

    status_filter = request.query_params.get("status")
    if status_filter:
        queryset = queryset.filter(status=status_filter)

    type_filter = request.query_params.get("request_type")
    if type_filter:
        queryset = queryset.filter(request_type=type_filter)

    search = request.query_params.get("search", "").strip()
    if search:
        from django.db.models import Q

        queryset = queryset.filter(
            Q(requester__first_name__icontains=search)
            | Q(requester__last_name__icontains=search)
            | Q(requester__email__icontains=search)
            | Q(id__icontains=search)
        )

    date_from = request.query_params.get("date_from")
    if date_from:
        queryset = queryset.filter(created_at__date__gte=date_from)
    date_to = request.query_params.get("date_to")
    if date_to:
        queryset = queryset.filter(created_at__date__lte=date_to)

    rows = list(queryset[:LIST_CAP])

    all_active = QueuedRequest.objects.filter(tenant=user.tenant, is_archived=False)
    by_status = {
        choice_value: all_active.filter(status=choice_value).count()
        for choice_value, _label in QueuedRequest.STATUS_CHOICES
    }
    active_count = sum(by_status.get(s, 0) for s in QueuedRequest.ACTIVE_STATUSES)
    oldest_active = all_active.filter(status__in=QueuedRequest.ACTIVE_STATUSES).order_by("created_at").first()
    retrying = all_active.filter(status=QueuedRequest.STATUS_RETRYING)
    avg_retry_count = 0
    if retrying.exists():
        avg_retry_count = sum(r.retry_count for r in retrying) / retrying.count()

    return Response(
        {
            "success": True,
            "requests": [_request_payload(r) for r in rows],
            "stats": {
                "by_status": by_status,
                "active_count": active_count,
                "avg_retry_count": round(avg_retry_count, 2),
                "oldest_active_age_seconds": (
                    int((timezone.now() - oldest_active.created_at).total_seconds()) if oldest_active else 0
                ),
            },
        }
    )


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def request_queue_retry(request, request_id):
    user = request.user
    if user.role not in ADMIN_ROLES:
        return Response({"success": False, "message": "Admin access required."}, status=status.HTTP_403_FORBIDDEN)

    queued_request = get_object_or_404(QueuedRequest, id=request_id, tenant=user.tenant)
    try:
        manual_retry(queued_request, actor=user)
    except ValueError as exc:
        return Response({"success": False, "message": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

    queued_request.refresh_from_db()
    return Response({"success": True, "request": _request_payload(queued_request)})


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def request_queue_cancel(request, request_id):
    user = request.user
    if user.role not in ADMIN_ROLES:
        return Response({"success": False, "message": "Admin access required."}, status=status.HTTP_403_FORBIDDEN)

    queued_request = get_object_or_404(QueuedRequest, id=request_id, tenant=user.tenant)
    try:
        cancel_request(queued_request, actor=user)
    except ValueError as exc:
        return Response({"success": False, "message": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

    queued_request.refresh_from_db()
    return Response({"success": True, "request": _request_payload(queued_request)})
