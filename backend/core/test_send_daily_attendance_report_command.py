from io import StringIO

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase
from django.utils import timezone

from academic.models import AttendanceRecord
from core.models import SchoolTenant
from users.models import User


class SendDailyAttendanceReportCommandTests(TestCase):
    """Smoke test for the cron-callable wrapper around core.tasks.send_daily_attendance_report."""

    def test_runs_cleanly_with_no_schools(self):
        out = StringIO()
        call_command("send_daily_attendance_report", stdout=out)
        self.assertIn("No active schools", out.getvalue())

    def test_rejects_an_invalid_date(self):
        with self.assertRaises(CommandError):
            call_command("send_daily_attendance_report", "--date", "not-a-date", stdout=StringIO())

    def test_show_message_prints_the_full_whatsapp_text(self):
        school = SchoolTenant.objects.create(name="Command Test School", schema_name="command_test_school", is_active=True)
        student = User.objects.create_user(
            email="student@commandtest.edu", password="StudentPass123", role="student", tenant=school, is_active=True,
        )
        AttendanceRecord.objects.create(student=student, date=timezone.localdate(), status="present")
        out = StringIO()

        call_command("send_daily_attendance_report", "--school", "command_test_school", "--show-message", stdout=out)

        output = out.getvalue()
        self.assertIn("--- message ---", output)
        self.assertIn("Command Test School", output)
        self.assertIn("Attendance report", output)
