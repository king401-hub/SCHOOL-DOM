from io import StringIO

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase


class SendDailyAttendanceReportCommandTests(TestCase):
    """Smoke test for the cron-callable wrapper around core.tasks.send_daily_attendance_report."""

    def test_runs_cleanly_with_no_schools(self):
        out = StringIO()
        call_command("send_daily_attendance_report", stdout=out)
        self.assertIn("No active schools", out.getvalue())

    def test_rejects_an_invalid_date(self):
        with self.assertRaises(CommandError):
            call_command("send_daily_attendance_report", "--date", "not-a-date", stdout=StringIO())
