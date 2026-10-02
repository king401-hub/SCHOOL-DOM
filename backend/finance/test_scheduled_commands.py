from io import StringIO

from django.core.management import call_command
from django.test import TestCase


class ScheduledFinanceCommandsTests(TestCase):
    """Smoke tests for the cron-callable wrappers around finance.tasks/services
    that used to only run under Celery beat (no broker/worker is confirmed
    running in production, so these give the same jobs a plain cron path)."""

    def test_send_fee_reminders_runs_cleanly_with_no_fees(self):
        out = StringIO()
        call_command("send_fee_reminders", stdout=out)
        self.assertIn("sent=0", out.getvalue())

    def test_process_token_allocations_runs_cleanly_with_no_allocations(self):
        out = StringIO()
        call_command("process_token_allocations", stdout=out)
        self.assertIn("expired=0 notified_7d=0 notified_1d=0", out.getvalue())

    def test_retry_payment_receipts_runs_cleanly_with_no_payments(self):
        out = StringIO()
        call_command("retry_payment_receipts", stdout=out)
        self.assertIn("'retried': 0, 'delivered': 0", out.getvalue())
