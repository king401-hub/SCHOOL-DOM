import re
from datetime import timedelta
from pathlib import Path

from django.conf import settings
from django.test import TestCase
from django.utils import timezone

from core.models import SchoolTenant
from core.tasks import send_compliance_reminders
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
