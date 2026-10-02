from django.core.management.base import BaseCommand
from django.utils import timezone

from request_queue.models import QueuedRequest, QueuedRequestEvent
from request_queue.tasks import process_queued_request


class Command(BaseCommand):
    help = (
        "Re-dispatch any queued request stuck too long with no sign of progress. "
        "Intended to run every 5 minutes via cron."
    )

    def handle(self, *args, **options):
        # Does the same lookup as request_queue.tasks.reconcile_stuck_requests, but
        # calls process_queued_request(...) directly instead of .delay(...): that
        # task needs a live Celery worker to actually run, and without one the
        # requeue would just vanish into a broker nobody is listening on.
        now = timezone.now()
        stuck_cutoff = now - timezone.timedelta(minutes=10)
        stuck = QueuedRequest.objects.filter(
            status__in=[QueuedRequest.STATUS_QUEUED, QueuedRequest.STATUS_PROCESSING],
            updated_at__lt=stuck_cutoff,
        )
        due_retries = QueuedRequest.objects.filter(
            status=QueuedRequest.STATUS_RETRYING,
            next_retry_at__lt=now - timezone.timedelta(minutes=5),
        )

        requeued = 0
        for request in list(stuck):
            request.log(QueuedRequestEvent.EVENT_QUEUED, "Re-dispatched by queue health check after appearing stuck.")
            process_queued_request(str(request.id))
            requeued += 1
        for request in list(due_retries):
            request.log(QueuedRequestEvent.EVENT_QUEUED, "Re-dispatched by queue health check - overdue retry.")
            process_queued_request(str(request.id))
            requeued += 1

        self.stdout.write(f"requeued={requeued}")
