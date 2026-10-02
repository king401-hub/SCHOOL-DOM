from io import StringIO

from django.core.management import call_command
from django.test import TestCase


class SendComplianceRemindersCommandTests(TestCase):
    """Smoke test for the cron-callable wrapper around core.tasks.send_compliance_reminders."""

    def test_runs_cleanly_with_no_schools(self):
        out = StringIO()
        call_command("send_compliance_reminders", stdout=out)
        self.assertIn("reminders_sent=0", out.getvalue())
