"""Celery processing for QueuedRequest - retry with exponential backoff,
row-locked to prevent races, self-healing after a worker restart."""
from celery import shared_task
from celery.utils.log import get_task_logger
from django.db import transaction
from django.utils import timezone

from .exceptions import RequestRejectedError, RetriableRequestError
from .models import QueuedRequest, QueuedRequestEvent
from .registry import get_handler
from .services import backoff_seconds, finalize_terminal

logger = get_task_logger(__name__)


@shared_task(bind=True, acks_late=True, reject_on_worker_lost=True)
def process_queued_request(self, request_id):
    # Set only when a RetriableRequestError needs a Celery-level retry. The
    # actual self.retry() call happens AFTER the atomic block below commits -
    # raising it from inside that block would roll back the very
    # status="retrying"/retry_count/log writes we just made.
    retry_info = None

    with transaction.atomic():
        try:
            request = QueuedRequest.objects.select_for_update().get(id=request_id)
        except QueuedRequest.DoesNotExist:
            logger.warning("process_queued_request: request %s no longer exists", request_id)
            return {"status": "skipped", "reason": "not_found"}

        if request.is_terminal:
            # Already resolved (e.g. redelivered after a worker restart, or a
            # manual admin action beat us to it) - nothing to do.
            return {"status": "skipped", "reason": "already_terminal", "current_status": request.status}

        if timezone.now() > request.expires_at:
            finalize_terminal(request, QueuedRequest.STATUS_EXPIRED, description="Request expired before it could be completed.")
            return {"status": "expired"}

        request.status = QueuedRequest.STATUS_PROCESSING
        request.last_attempt_at = timezone.now()
        request.save(update_fields=["status", "last_attempt_at", "updated_at"])
        request.log(QueuedRequestEvent.EVENT_PROCESSING_STARTED, f"Attempt #{request.retry_count + 1} started.")

        try:
            handler = get_handler(request.request_type)
        except KeyError as exc:
            finalize_terminal(request, QueuedRequest.STATUS_FAILED, description=str(exc))
            logger.error("process_queued_request: %s", exc)
            return {"status": "failed", "reason": "no_handler"}

        try:
            result = handler(request)
        except RetriableRequestError as exc:
            request.retry_count += 1
            request.error_message = str(exc)
            if request.retry_count >= request.max_retries:
                request.save(update_fields=["retry_count", "error_message", "updated_at"])
                finalize_terminal(
                    request, QueuedRequest.STATUS_FAILED,
                    description=f"Exhausted {request.max_retries} retries: {exc}",
                )
                return {"status": "failed", "reason": "max_retries_exhausted"}

            countdown = backoff_seconds(request.retry_count)
            request.status = QueuedRequest.STATUS_RETRYING
            request.next_retry_at = timezone.now() + timezone.timedelta(seconds=countdown)
            request.save(update_fields=["status", "retry_count", "error_message", "next_retry_at", "updated_at"])
            request.log(
                QueuedRequestEvent.EVENT_RETRY_SCHEDULED,
                f"Retry {request.retry_count}/{request.max_retries} scheduled in {countdown}s after: {exc}",
            )
            retry_info = (exc, countdown)
        except RequestRejectedError as exc:
            request.error_message = str(exc)
            request.save(update_fields=["error_message", "updated_at"])
            finalize_terminal(request, QueuedRequest.STATUS_REJECTED, description=str(exc))
            return {"status": "rejected", "reason": str(exc)}
        except Exception as exc:  # noqa: BLE001 - unexpected handler error, treat as terminal failure
            logger.exception("process_queued_request: unexpected error handling %s", request_id)
            request.error_message = str(exc)
            request.save(update_fields=["error_message", "updated_at"])
            finalize_terminal(request, QueuedRequest.STATUS_FAILED, description=f"Unexpected error: {exc}")
            return {"status": "failed", "reason": "unexpected_error"}
        else:
            request.result = result if isinstance(result, dict) else {"value": result}
            request.save(update_fields=["result", "updated_at"])
            finalize_terminal(request, QueuedRequest.STATUS_APPROVED, description="Completed successfully.")

    # Outside the atomic block: the retry-scheduled state above is already
    # committed, so it's now safe to raise Celery's Retry.
    if retry_info is not None:
        exc, countdown = retry_info
        raise self.retry(exc=exc, countdown=countdown)

    return {"status": "approved"}


@shared_task
def reconcile_stuck_requests():
    """Safety net beyond acks_late: re-dispatch any request that's been
    active for too long with no sign of an in-flight Celery task (e.g. Redis
    itself was restarted and lost in-flight task state). QueuedRequest rows
    live in Postgres, so nothing is lost even if broker state is."""
    stuck_cutoff = timezone.now() - timezone.timedelta(minutes=10)
    stuck = QueuedRequest.objects.filter(
        status__in=[QueuedRequest.STATUS_QUEUED, QueuedRequest.STATUS_PROCESSING],
        updated_at__lt=stuck_cutoff,
    )
    requeued = 0
    for request in stuck:
        request.log(QueuedRequestEvent.EVENT_QUEUED, "Re-dispatched by queue health check after appearing stuck.")
        process_queued_request.delay(str(request.id))
        requeued += 1

    due_retries = QueuedRequest.objects.filter(
        status=QueuedRequest.STATUS_RETRYING,
        next_retry_at__lt=timezone.now() - timezone.timedelta(minutes=5),
    )
    for request in due_retries:
        request.log(QueuedRequestEvent.EVENT_QUEUED, "Re-dispatched by queue health check - overdue retry.")
        process_queued_request.delay(str(request.id))
        requeued += 1

    if requeued:
        logger.info("reconcile_stuck_requests: re-dispatched %d request(s)", requeued)
    return {"requeued": requeued}
