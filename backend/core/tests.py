from datetime import timedelta

from django.test import TestCase
from django.utils import timezone

from core.models import SchoolTenant
from core.tasks import send_compliance_reminders
from notifications.models import Notification
from users.models import User


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
