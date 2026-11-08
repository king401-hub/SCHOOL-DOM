import re
from datetime import timedelta
from pathlib import Path
from unittest.mock import patch

from django.conf import settings
from django.test import TestCase
from django.utils import timezone

from academic.models import AttendanceRecord
from core.models import SchoolGroup, SchoolTenant, primary_school_tenants
from core.tasks import send_compliance_reminders, send_daily_attendance_report
from hr.models import StaffAttendance, StaffProfile
from notifications.models import Notification
from users.models import User


class NoInterpolatedSqlTests(TestCase):
    """Guard against SQL injection by keeping interpolated SQL out of the codebase.

    Nothing here reaches the database. The ORM already parameterizes every query
    this platform makes, so injection can only appear if someone reintroduces
    raw SQL built by string formatting. This test is what stops that landing
    unnoticed - it fails the build instead of leaving it for a security review.

    Static and parameterized raw SQL are fine and deliberately not flagged; the
    danger is only ever the value pasted straight into the string.
    """

    # f-string, %-format, .format(), or concatenation feeding a raw-SQL entry point.
    DANGEROUS = re.compile(
        r"""(?:\.raw\(|cursor\.execute\()\s*(?:f["']|["'][^"']*["']\s*(?:%|\+|\.format\())""",
        re.IGNORECASE,
    )
    # A second net, for SQL assembled into a variable before being executed
    # somewhere else. DANGEROUS above already covers every f-string handed
    # straight to .raw()/cursor.execute() whatever it contains, so this one is
    # deliberately conservative: it demands a full statement shape, because a
    # bare keyword match turns ordinary English into a build failure
    # ("{prefix} update: {status}" is an email subject; "Select a class from the
    # list" is a form hint). A guard that cries wolf gets deleted.
    FSTRING_SQL = re.compile(
        r"""f["'][^"']*(?:"""
        r"""\bSELECT\b.*\bFROM\b.*\b(?:WHERE|JOIN|GROUP\s+BY|ORDER\s+BY|LIMIT|HAVING)\b"""
        r"""|\bINSERT\s+INTO\b.*\b(?:VALUES|SELECT)\b"""
        r"""|\bDELETE\s+FROM\b.*\bWHERE\b"""
        r"""|\bUPDATE\b.*\bSET\b"""
        r""")[^"']*\{""",
        re.IGNORECASE,
    )
    # .extra() and RawSQL() splice a fragment into the query with no parameter
    # binding of their own, so their safety depends entirely on the caller.
    # Django's own docs steer away from .extra(); nothing here uses either, so
    # any appearance is worth a deliberate decision rather than a silent merge.
    ESCAPE_HATCH = re.compile(r"\.extra\(|RawSQL\(")

    SKIP_DIRS = {"migrations", "node_modules", "venv", ".venv", "__pycache__", "frontend", "landing-page"}

    def _python_sources(self):
        root = Path(settings.BASE_DIR)
        for path in root.rglob("*.py"):
            if any(part in self.SKIP_DIRS for part in path.parts):
                continue
            if path.name == "tests.py" or path.name == Path(__file__).name:
                continue
            yield path

    def test_no_sql_is_built_by_string_interpolation(self):
        offenders = []
        for path in self._python_sources():
            try:
                source = path.read_text(encoding="utf-8")
            except (OSError, UnicodeDecodeError):
                continue
            for number, line in enumerate(source.splitlines(), start=1):
                if (
                    self.DANGEROUS.search(line)
                    or self.FSTRING_SQL.search(line)
                    or self.ESCAPE_HATCH.search(line)
                ):
                    offenders.append(f"{path}:{number}: {line.strip()}")

        self.assertEqual(
            offenders,
            [],
            "SQL built by string interpolation is an injection risk. Use the ORM, or "
            "pass values as parameters (cursor.execute(sql, [value])) instead of "
            "formatting them into the query:\n" + "\n".join(offenders),
        )


class PrimarySchoolTenantsTests(TestCase):
    """A branch (users.branch_views.create_branch) is another SchoolTenant
    row sharing school_group with its parent, not a new school - anything
    that counts/lists "schools" platform-wide (superadmin dashboards,
    device fleet stats) must collapse those branches down to one entry per
    real school via primary_school_tenants, or creating a branch would look
    exactly like a brand new signup."""

    def test_a_standalone_school_with_no_group_passes_through_unchanged(self):
        standalone = SchoolTenant.objects.create(name="Lone School", schema_name="lone_school", is_active=True)
        ids = set(primary_school_tenants().values_list("id", flat=True))
        self.assertIn(standalone.id, ids)

    def test_only_the_earliest_branch_in_a_group_survives(self):
        owner = User.objects.create_user(
            email="owner@group.test", password="OwnerPass123", role="school_admin", is_active=True,
        )
        group = SchoolGroup.objects.create(name="Grouped School", owner=owner)
        main = SchoolTenant.objects.create(
            name="Grouped School", schema_name="grouped_main", school_group=group, branch_label="Main", is_active=True,
        )
        secondary = SchoolTenant.objects.create(
            name="Grouped School", schema_name="grouped_secondary", school_group=group, branch_label="Secondary", is_active=True,
        )

        ids = list(primary_school_tenants(SchoolTenant.objects.filter(school_group=group)).values_list("id", flat=True))
        self.assertEqual(ids, [main.id])
        self.assertNotIn(secondary.id, ids)

    def test_two_separate_groups_each_keep_their_own_primary_row(self):
        owner_one = User.objects.create_user(
            email="owner1@group.test", password="OwnerPass123", role="school_admin", is_active=True,
        )
        owner_two = User.objects.create_user(
            email="owner2@group.test", password="OwnerPass123", role="school_admin", is_active=True,
        )
        group_one = SchoolGroup.objects.create(name="School One", owner=owner_one)
        group_two = SchoolGroup.objects.create(name="School Two", owner=owner_two)
        main_one = SchoolTenant.objects.create(name="School One", schema_name="school_one_main", school_group=group_one, is_active=True)
        SchoolTenant.objects.create(name="School One", schema_name="school_one_branch", school_group=group_one, is_active=True)
        main_two = SchoolTenant.objects.create(name="School Two", schema_name="school_two_main", school_group=group_two, is_active=True)

        ids = set(primary_school_tenants(SchoolTenant.objects.filter(school_group__in=[group_one, group_two])).values_list("id", flat=True))
        self.assertEqual(ids, {main_one.id, main_two.id})


class ComplianceReminderTaskTests(TestCase):
    """Schools that haven't finished compliance get a weekly email nudge -
    this also has to reach whoever logs in first, via an in-app notification
    for every admin at the school, not just the one email recipient."""

    def _make_school(self, days_since_signup, **extra):
        fields = {
            "name": "Reminder School",
            "schema_name": f"reminder_school_{days_since_signup}d",
            "is_active": True,
            "compliance_status": "not_submitted",
            "compliance_deadline_reference_at": timezone.now() - timedelta(days=days_since_signup),
        }
        fields.update(extra)
        return SchoolTenant.objects.create(**fields)

    def test_reminder_stage_creates_in_app_notification_for_every_admin(self):
        school = self._make_school(8)
        admin_one = User.objects.create_user(
            email="admin1@reminder.edu", password="AdminPass123", role="school_admin",
            tenant=school, is_active=True, is_verified=True,
        )
        admin_two = User.objects.create_user(
            email="admin2@reminder.edu", password="AdminPass123", role="school_superadmin",
            tenant=school, is_active=True, is_verified=True,
        )

        send_compliance_reminders()

        school.refresh_from_db()
        self.assertEqual(school.compliance_reminder_stage, 1)
        self.assertTrue(school.is_active)

        for admin in (admin_one, admin_two):
            notification = Notification.objects.get(tenant=school, user=admin, event_type="compliance_reminder")
            self.assertEqual(notification.deep_link, "/settings")
            self.assertIn("day(s) left", notification.message)

    def test_reminder_not_resent_for_same_stage_twice(self):
        school = self._make_school(8)
        User.objects.create_user(
            email="admin@reminder.edu", password="AdminPass123", role="school_admin",
            tenant=school, is_active=True, is_verified=True,
        )

        send_compliance_reminders()
        send_compliance_reminders()

        self.assertEqual(
            Notification.objects.filter(tenant=school, event_type="compliance_reminder").count(), 1
        )

    def test_school_past_30_days_is_suspended_with_no_extra_in_app_notification(self):
        school = self._make_school(31)
        User.objects.create_user(
            email="admin@suspend.edu", password="AdminPass123", role="school_admin",
            tenant=school, is_active=True, is_verified=True,
        )

        send_compliance_reminders()

        school.refresh_from_db()
        self.assertFalse(school.is_active)
        self.assertIsNotNone(school.compliance_suspended_at)
        self.assertFalse(Notification.objects.filter(tenant=school, event_type="compliance_reminder").exists())

    def test_schools_with_submitted_compliance_are_skipped(self):
        school = self._make_school(31, compliance_status="submitted")
        User.objects.create_user(
            email="admin@submitted.edu", password="AdminPass123", role="school_admin",
            tenant=school, is_active=True, is_verified=True,
        )

        send_compliance_reminders()

        school.refresh_from_db()
        self.assertTrue(school.is_active)
        self.assertFalse(Notification.objects.filter(tenant=school).exists())


class DailyAttendanceReportTests(TestCase):
    """The daily WhatsApp attendance report: present/absent/late counts for
    students and staff, folding anyone excused/half-day/never-marked into
    "absent" (the 3-bucket report that was asked for), sent to every
    school_admin/principal's own phone via send_whatsapp_message (Bahasha
    first, Termii only as its own fallback when Bahasha isn't configured)."""

    def setUp(self):
        self.school = SchoolTenant.objects.create(name="Roll Call School", schema_name="roll_call_school", is_active=True)
        self.admin = User.objects.create_user(
            email="admin@rollcall.edu", password="AdminPass123", role="school_admin",
            tenant=self.school, is_active=True, is_verified=True, phone="+2348012345678",
        )
        self.today = timezone.localdate()

    def _student(self, email, status=None):
        student = User.objects.create_user(
            email=email, password="StudentPass123", role="student",
            tenant=self.school, is_active=True, is_verified=True,
        )
        if status:
            AttendanceRecord.objects.create(student=student, date=self.today, status=status)
        return student

    def _staff(self, code, status=None):
        staff = StaffProfile.objects.create(
            tenant=self.school, staff_code=code, first_name="Staff", last_name=code, role="Teacher",
        )
        if status:
            StaffAttendance.objects.create(staff=staff, date=self.today, status=status)
        return staff

    @patch("finance.services.send_whatsapp_message")
    def test_counts_fold_unmarked_excused_and_half_day_into_absent_and_sends_whatsapp(self, mock_send):
        mock_send.return_value = {"status": "success", "message_id": "abc"}
        self._student("present@rollcall.edu", "present")
        self._student("late@rollcall.edu", "late")
        self._student("excused@rollcall.edu", "excused")
        self._student("unmarked@rollcall.edu")  # no AttendanceRecord at all
        self._staff("ST1", StaffAttendance.PRESENT)
        self._staff("ST2", StaffAttendance.LATE)
        self._staff("ST3", StaffAttendance.HALF_DAY)
        self._staff("ST4")  # no StaffAttendance row at all

        results = send_daily_attendance_report()

        result = results[self.school.schema_name]
        self.assertEqual(result["students"], {"total": 4, "present": 1, "late": 1, "absent": 2})
        self.assertEqual(result["staff"], {"total": 4, "present": 1, "late": 1, "absent": 2})
        self.assertIn("Present: 1", result["message"])
        self.assertIn("Absent: 2", result["message"])

        mock_send.assert_called_once_with("+2348012345678", result["message"])
        self.assertEqual(result["rows"], [{"admin": self.admin, "outcome": "sent", "phone": "+2348012345678"}])

    @patch("finance.services.send_whatsapp_message")
    def test_dry_run_sends_nothing(self, mock_send):
        self._student("present@rollcall.edu", "present")

        results = send_daily_attendance_report(dry_run=True)

        mock_send.assert_not_called()
        self.assertEqual(results[self.school.schema_name]["rows"], [{"admin": self.admin, "outcome": "dry_run", "phone": "+2348012345678"}])

    @patch("finance.services.send_whatsapp_message")
    def test_admin_with_no_phone_is_skipped_not_crashed(self, mock_send):
        self.admin.phone = ""
        self.admin.save(update_fields=["phone"])
        self._student("present@rollcall.edu", "present")

        results = send_daily_attendance_report()

        mock_send.assert_not_called()
        self.assertEqual(results[self.school.schema_name]["rows"], [{"admin": self.admin, "outcome": "skipped_no_phone"}])

    @patch("finance.services.send_whatsapp_message")
    def test_a_closed_whatsapp_window_is_reported_per_admin_not_raised(self, mock_send):
        # send_whatsapp_message raises RuntimeError on failure (e.g. Bahasha's
        # 24-hour customer-service window being closed for this admin) -
        # one admin's failure must not blow up the whole run.
        mock_send.side_effect = RuntimeError("Customer service window is closed, no message was sent in the last 24 hours.")
        self._student("present@rollcall.edu", "present")

        results = send_daily_attendance_report()

        row = results[self.school.schema_name]["rows"][0]
        self.assertEqual(row["outcome"], "failed: Customer service window is closed, no message was sent in the last 24 hours.")

    @patch("finance.services.send_whatsapp_message")
    def test_school_with_no_students_or_staff_is_excluded(self, mock_send):
        results = send_daily_attendance_report()

        self.assertNotIn(self.school.schema_name, results)
        mock_send.assert_not_called()

    @patch("finance.services.send_whatsapp_message")
    def test_school_filter_limits_to_one_school(self, mock_send):
        mock_send.return_value = {"status": "success", "message_id": "abc"}
        other_school = SchoolTenant.objects.create(name="Other School", schema_name="other_roll_call_school", is_active=True)
        User.objects.create_user(
            email="admin@other.edu", password="AdminPass123", role="school_admin",
            tenant=other_school, is_active=True, is_verified=True, phone="+2348099999999",
        )
        self._student("present@rollcall.edu", "present")
        User.objects.create_user(
            email="student@other.edu", password="StudentPass123", role="student",
            tenant=other_school, is_active=True, is_verified=True,
        )

        results = send_daily_attendance_report(school_code="roll_call_school")

        self.assertEqual(list(results.keys()), [self.school.schema_name])
        mock_send.assert_called_once()

    @patch("finance.services.send_whatsapp_message")
    def test_report_date_can_be_overridden(self, mock_send):
        mock_send.return_value = {"status": "success", "message_id": "abc"}
        yesterday = self.today - timedelta(days=1)
        student = self._student("present@rollcall.edu")
        AttendanceRecord.objects.create(student=student, date=yesterday, status="present")

        today_results = send_daily_attendance_report()
        yesterday_results = send_daily_attendance_report(today=yesterday)

        self.assertEqual(today_results[self.school.schema_name]["students"]["present"], 0)
        self.assertEqual(yesterday_results[self.school.schema_name]["students"]["present"], 1)
