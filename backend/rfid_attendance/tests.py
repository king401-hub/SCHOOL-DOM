"""Tests proving a shared dual-school kiosk device never leaks an
attendance record from one paired school into the other."""
import datetime

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from academic.models import AttendanceRecord
from core.tenant import SchoolGroup, SchoolTenant

from .models import CardAssignment, GateSettings

User = get_user_model()


class SharedDeviceTenantIsolationTestCase(TestCase):
    """Two schools in one group, one shared scanner_user (simulating a
    dual-school kiosk) - simulates a completed "switch" by flipping
    scanner_user.tenant directly, since that's exactly what
    device_switch_active_school does under the hood."""

    def setUp(self):
        owner = User.objects.create_user(email="owner@test.com", password="testpass123", role="school_superadmin")
        self.group = SchoolGroup.objects.create(name="Shared Kiosk Group", owner=owner)
        self.school_a = SchoolTenant.objects.create(name="School A", schema_name="school_a", school_group=self.group)
        self.school_b = SchoolTenant.objects.create(name="School B", schema_name="school_b", school_group=self.group)

        self.scanner_user = User.objects.create_user(
            email="scanner@test.com", password="testpass123", role="staff", tenant=self.school_a,
        )

        self.student_a = self._make_student(self.school_a, "Alice A", "STU-A-001", "ADM-A-001")
        self.student_b = self._make_student(self.school_b, "Bob B", "STU-B-001", "ADM-B-001")

        # Same physical card UID, independently assigned in each school -
        # CardAssignment's tenant-scoped uniqueness constraint allows this.
        CardAssignment.objects.create(tenant=self.school_a, holder=self.student_a, card_uid="1111")
        CardAssignment.objects.create(tenant=self.school_b, holder=self.student_b, card_uid="1111")

        GateSettings.objects.create(tenant=self.school_a, mode=GateSettings.MODE_ATTENDANCE_ONLY)
        GateSettings.objects.create(tenant=self.school_b, mode=GateSettings.MODE_FEE_TRACKER)

        self.client = APIClient()
        self.client.force_authenticate(user=self.scanner_user)

    def _make_student(self, tenant, name, student_id, admission_number):
        first, last = name.split(" ", 1)
        user = User.objects.create_user(
            email=f"{student_id.lower()}@test.com", password="testpass123", role="student",
            tenant=tenant, first_name=first, last_name=last,
        )
        from users.models import StudentProfile

        StudentProfile.objects.create(
            user=user,
            student_id=student_id,
            admission_number=admission_number,
            admission_date=datetime.date(2024, 9, 1),
            guardian_name="Test Guardian",
            guardian_phone="08010000000",
            guardian_relation="Parent",
        )
        return user

    def _scan(self, card_uid, idempotency_key):
        return self.client.post(
            "/api/rfid/attendance/scan/",
            {"card_uid": card_uid, "idempotency_key": idempotency_key},
            format="json",
        )

    def test_scan_while_school_a_active_resolves_school_a_holder(self):
        resp = self._scan("1111", "key-a-1")
        self.assertEqual(resp.status_code, 201)
        self.assertEqual(resp.data["person"]["name"], "Alice A")

        record = AttendanceRecord.objects.get(student=self.student_a)
        self.assertEqual(record.tenant.slug.lower(), "school_a")
        self.assertFalse(AttendanceRecord.objects.filter(student=self.student_b).exists())

    def test_scan_after_switch_resolves_school_b_holder_never_school_a(self):
        # Simulate a completed switch - exactly what device_switch_active_school does.
        self.scanner_user.tenant = self.school_b
        self.scanner_user.save(update_fields=["tenant"])

        resp = self._scan("1111", "key-b-1")
        self.assertEqual(resp.status_code, 201)
        self.assertEqual(resp.data["person"]["name"], "Bob B")

        record = AttendanceRecord.objects.get(student=self.student_b)
        self.assertEqual(record.tenant.slug.lower(), "school_b")
        self.assertFalse(AttendanceRecord.objects.filter(student=self.student_a).exists())

    def test_card_only_assigned_in_inactive_school_is_not_recognized(self):
        # A UID that's only ever been assigned inside School B must not be
        # reachable while School A is active - no cross-tenant fallback.
        CardAssignment.objects.create(tenant=self.school_b, holder=self.student_b, card_uid="2222")

        resp = self._scan("2222", "key-2222")
        self.assertEqual(resp.status_code, 404)
        self.assertTrue(resp.data["unregistered"])

    def test_gate_settings_mode_follows_the_active_school(self):
        from .views import get_or_create_gate_settings

        settings_a = get_or_create_gate_settings(self.school_a)
        self.assertEqual(settings_a.mode, GateSettings.MODE_ATTENDANCE_ONLY)

        self.scanner_user.tenant = self.school_b
        self.scanner_user.save(update_fields=["tenant"])
        settings_b = get_or_create_gate_settings(self.school_b)
        self.assertEqual(settings_b.mode, GateSettings.MODE_FEE_TRACKER)
