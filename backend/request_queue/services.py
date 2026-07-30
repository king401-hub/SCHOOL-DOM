"""Enqueue, dedupe, retry-schedule, and resolve QueuedRequests.

This is the only module that should touch QueuedRequest's lifecycle fields
directly - views and Celery tasks call into these functions rather than
mutating the model inline, so every transition is logged and transactional.
"""
import hashlib
import json

from django.db import IntegrityError, transaction
from django.utils import timezone

from .models import QueuedRequest, QueuedRequestEvent
from .registry import get_defaults

BACKOFF_BASE_SECONDS = 30
BACKOFF_CAP_SECONDS = 3600


def _canonical_json(payload):
    return json.dumps(payload, sort_keys=True, default=str)


def compute_dedupe_key(tenant_id, requester_id, request_type, payload):
    raw = f"{tenant_id}:{requester_id}:{request_type}:{_canonical_json(payload)}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def backoff_seconds(retry_count):
    return min(BACKOFF_BASE_SECONDS * (2 ** retry_count), BACKOFF_CAP_SECONDS)


def _dispatch(request_id):
    from .tasks import process_queued_request

    process_queued_request.delay(str(request_id))


def _create_duplicate(original, *, tenant, requester, request_type, payload, dedupe_key, max_retries, expires_at):
    duplicate = QueuedRequest.objects.create(
        tenant=tenant,
        requester=requester,
        request_type=request_type,
        status=QueuedRequest.STATUS_CANCELLED,
        payload=payload,
        dedupe_key=dedupe_key,
        linked_request=original,
        is_archived=True,
        max_retries=max_retries,
        expires_at=expires_at,
    )
    duplicate.log(
        QueuedRequestEvent.EVENT_DUPLICATE_DETECTED,
        f"Duplicate of request {original.id}; not queued for processing.",
        actor=requester,
    )
    original.log(
        QueuedRequestEvent.EVENT_DUPLICATE_DETECTED,
        f"Duplicate submission {duplicate.id} received while this request is still active.",
        actor=requester,
    )
    return duplicate


def enqueue_request(tenant, requester, request_type, payload, max_retries=None, expiry_hours=None, dedupe_payload=None):
    """Create (or dedupe against) a QueuedRequest and schedule processing.

    `dedupe_payload` is what's hashed to detect "the same request" - pass it
    explicitly whenever `payload` contains a freshly-generated unique value
    (an idempotency reference, a timestamp, etc.) that would otherwise make
    every submission hash differently and silently defeat deduplication.
    Defaults to `payload` itself when every field is meaningful content
    (e.g. no generated reference embedded in it).

    Returns (request, created). created=False means an identical request
    from this user/tenant is already active - `request` is the ORIGINAL, and
    the new submission was recorded as an archived, linked duplicate that
    never enters the processing pipeline.
    """
    defaults = get_defaults(request_type)
    max_retries = max_retries if max_retries is not None else defaults.get("max_retries", 5)
    expiry_hours = expiry_hours if expiry_hours is not None else defaults.get("expiry_hours", 24)

    tenant_id = getattr(tenant, "id", tenant)
    requester_id = getattr(requester, "id", requester)
    dedupe_key = compute_dedupe_key(tenant_id, requester_id, request_type, dedupe_payload if dedupe_payload is not None else payload)
    expires_at = timezone.now() + timezone.timedelta(hours=expiry_hours)

    with transaction.atomic():
        existing = (
            QueuedRequest.objects.select_for_update()
            .filter(dedupe_key=dedupe_key, status__in=QueuedRequest.ACTIVE_STATUSES)
            .first()
        )
        if existing:
            _create_duplicate(
                existing, tenant=tenant, requester=requester, request_type=request_type,
                payload=payload, dedupe_key=dedupe_key, max_retries=max_retries, expires_at=expires_at,
            )
            return existing, False

        try:
            with transaction.atomic():  # savepoint: isolate a possible race-loss IntegrityError
                request = QueuedRequest.objects.create(
                    tenant=tenant,
                    requester=requester,
                    request_type=request_type,
                    status=QueuedRequest.STATUS_QUEUED,
                    payload=payload,
                    dedupe_key=dedupe_key,
                    max_retries=max_retries,
                    expires_at=expires_at,
                )
        except IntegrityError:
            # Lost a race to a concurrent submission with the same dedupe key -
            # the winner now exists; link this submission to it instead.
            existing = QueuedRequest.objects.select_for_update().get(
                dedupe_key=dedupe_key, status__in=QueuedRequest.ACTIVE_STATUSES
            )
            _create_duplicate(
                existing, tenant=tenant, requester=requester, request_type=request_type,
                payload=payload, dedupe_key=dedupe_key, max_retries=max_retries, expires_at=expires_at,
            )
            return existing, False

        request.log(QueuedRequestEvent.EVENT_CREATED, "Request created.", actor=requester)
        request.log(QueuedRequestEvent.EVENT_QUEUED, "Request queued for processing.")

    transaction.on_commit(lambda: _dispatch(request.id))
    return request, True


def _notify_requester(request, title, message):
    if not request.requester_id:
        return
    from notifications.models import Notification

    Notification.objects.create(
        tenant=request.tenant,
        user=request.requester,
        title=title,
        message=message,
        notification_type="success" if request.status == QueuedRequest.STATUS_APPROVED else "alert",
        priority=3,
        channel="in_app",
        event_type=f"request_queue.{request.request_type}",
        reference_id=request.id,
        reference_model="request_queue.QueuedRequest",
        is_delivered=True,
        delivered_at=timezone.now(),
    )


def _archive_duplicates(request):
    for duplicate in request.duplicates.filter(is_archived=False):
        duplicate.is_archived = True
        duplicate.save(update_fields=["is_archived", "updated_at"])
        duplicate.log(QueuedRequestEvent.EVENT_ARCHIVED, f"Archived - original request {request.id} resolved.")


def finalize_terminal(request, status, *, description="", metadata=None, notify=True):
    """Move a request into a terminal status and clean up duplicates/notify.
    Call only from inside the row-locking transaction that owns `request`."""
    request.status = status
    if status == QueuedRequest.STATUS_APPROVED:
        request.error_message = ""
    request.save(update_fields=["status", "updated_at"])

    event_map = {
        QueuedRequest.STATUS_APPROVED: QueuedRequestEvent.EVENT_SUCCEEDED,
        QueuedRequest.STATUS_REJECTED: QueuedRequestEvent.EVENT_REJECTED,
        QueuedRequest.STATUS_FAILED: QueuedRequestEvent.EVENT_FAILED,
        QueuedRequest.STATUS_CANCELLED: QueuedRequestEvent.EVENT_CANCELLED,
        QueuedRequest.STATUS_EXPIRED: QueuedRequestEvent.EVENT_EXPIRED,
    }
    request.log(event_map.get(status, QueuedRequestEvent.EVENT_FAILED), description, metadata=metadata)

    _archive_duplicates(request)

    if notify and status in (QueuedRequest.STATUS_APPROVED, QueuedRequest.STATUS_FAILED, QueuedRequest.STATUS_REJECTED):
        titles = {
            QueuedRequest.STATUS_APPROVED: "Request completed",
            QueuedRequest.STATUS_FAILED: "Request failed",
            QueuedRequest.STATUS_REJECTED: "Request rejected",
        }
        messages = {
            QueuedRequest.STATUS_APPROVED: "Your request has been processed successfully.",
            QueuedRequest.STATUS_FAILED: f"Your request could not be completed: {request.error_message or 'an error occurred'}.",
            QueuedRequest.STATUS_REJECTED: f"Your request was rejected: {request.error_message or 'see details'}.",
        }
        _notify_requester(request, titles[status], messages[status])


def manual_retry(request, actor):
    """Admin-triggered retry of a failed request."""
    if request.status not in (QueuedRequest.STATUS_FAILED,):
        raise ValueError("Only failed requests can be manually retried.")
    request.status = QueuedRequest.STATUS_QUEUED
    request.error_message = ""
    request.save(update_fields=["status", "error_message", "updated_at"])
    request.log(QueuedRequestEvent.EVENT_MANUAL_RETRY, "Manually retried by administrator.", actor=actor)
    transaction.on_commit(lambda: _dispatch(request.id))


def cancel_request(request, actor):
    """Admin-triggered cancellation of a non-terminal request."""
    if request.is_terminal:
        raise ValueError("Cannot cancel a request that has already reached a terminal state.")
    request.status = QueuedRequest.STATUS_CANCELLED
    request.save(update_fields=["status", "updated_at"])
    request.log(QueuedRequestEvent.EVENT_CANCELLED, "Cancelled by administrator.", actor=actor)
