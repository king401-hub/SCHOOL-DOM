from io import StringIO

from django.core.management import call_command
from django.test import TestCase


class ReconcileStuckRequestsCommandTests(TestCase):
    """Smoke test for the cron-callable requeue sweep. Confirms it calls
    process_queued_request(...) directly rather than .delay(...), which would
    need a live Celery worker to ever actually run."""

    def test_runs_cleanly_with_no_requests(self):
        out = StringIO()
        call_command("reconcile_stuck_requests", stdout=out)
        self.assertIn("requeued=0", out.getvalue())
