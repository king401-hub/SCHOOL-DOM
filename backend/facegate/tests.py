"""Tests for the vendor face-recognition SchoolGate terminal HTTP
integration. There is no real F45 unit to test against, so these simulate
the device side of each vendor-documented endpoint with plain HTTP calls -
exactly the requests a real terminal would send."""
import datetime
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from academic.models import AttendanceRecord
from core.tenant import SchoolTenant

from .models import FaceGateDevice, FaceGateEnrollment
from .services import enroll_user_on_device

User = get_user_model()


class _ImmediateThread:
    """Stands in for threading.Thread so a gate SMS (fired on a background
    thread, see rfid_attendance.views._send_gate_sms/_send_gate_sms_from_wallet)
    runs synchronously within the test instead of racing the assertions -
    same helper rfid_attendance/tests.py uses for the same reason."""

    def __init__(self, target=None, args=(), kwargs=None, daemon=None):
        self._target, self._args, self._kwargs = target, args, kwargs or {}

    def start(self):
        self._target(*self._args, **self._kwargs)


def _make_student(tenant, first, last, student_id, phone="08010000000"):
    from users.models import StudentProfile

    user = User.objects.create_user(
        email=f"{student_id.lower()}@facegate.test", password="testpass123", role="student",
        tenant=tenant, first_name=first, last_name=last,
    )
    StudentProfile.objects.create(
        user=user, student_id=student_id, admission_number=f"ADM-{student_id}",
        admission_date=datetime.date(2024, 9, 1), guardian_name="Guardian",
        guardian_phone=phone, guardian_relation="Parent",
    )
    return user


class FaceGateAdminDeviceTests(TestCase):
    def setUp(self):
        self.school = SchoolTenant.objects.create(name="Gate School", schema_name="facegate_admin_school")
        self.admin = User.objects.create_user(
            email="admin@facegate.test", password="testpass123", role="school_admin", tenant=self.school,
        )
        self.client = APIClient()
        self.client.force_authenticate(user=self.admin)

    def test_admin_can_register_a_new_device(self):
        resp = self.client.post(
            "/api/facegate/admin/devices/register",
            {"device_id": "F45-0001", "label": "Front Gate"},
            format="json",
        )
        self.assertEqual(resp.status_code, 201, resp.data)
        self.assertTrue(FaceGateDevice.objects.filter(tenant=self.school, device_id="F45-0001").exists())

    def test_registering_the_same_device_id_for_another_school_is_rejected(self):
        other_school = SchoolTenant.objects.create(name="Other School", schema_name="facegate_other_school")
        FaceGateDevice.objects.create(tenant=other_school, device_id="F45-SHARED", label="Theirs")

        resp = self.client.post(
            "/api/facegate/admin/devices/register",
            {"device_id": "F45-SHARED", "label": "Mine"},
            format="json",
        )
        self.assertEqual(resp.status_code, 400, resp.data)

    def test_a_non_admin_cannot_register_a_device(self):
        teacher = User.objects.create_user(
            email="teacher@facegate.test", password="testpass123", role="teacher", tenant=self.school,
        )
        self.client.force_authenticate(user=teacher)

        resp = self.client.post(
            "/api/facegate/admin/devices/register", {"device_id": "F45-0002"}, format="json",
        )
        self.assertEqual(resp.status_code, 403)

    def test_an_admin_only_sees_devices_from_their_own_school(self):
        other_school = SchoolTenant.objects.create(name="Other School 2", schema_name="facegate_other_school_2")
        FaceGateDevice.objects.create(tenant=other_school, device_id="F45-NOT-MINE")
        FaceGateDevice.objects.create(tenant=self.school, device_id="F45-MINE")

        resp = self.client.get("/api/facegate/admin/devices")

        self.assertEqual(resp.status_code, 200)
        device_ids = [d["device_id"] for d in resp.data["devices"]]
        self.assertEqual(device_ids, ["F45-MINE"])


class FaceGateHeartbeatTests(TestCase):
    def setUp(self):
        self.school = SchoolTenant.objects.create(name="Heartbeat School", schema_name="facegate_heartbeat_school")
        self.device = FaceGateDevice.objects.create(tenant=self.school, device_id="F45-HB-1")
        self.client = APIClient()

    def test_update_state_for_a_known_device_updates_firmware_and_last_seen(self):
        self.assertIsNone(self.device.last_seen_at)

        resp = self.client.post(
            "/api/facegate/device/updateStateDevice",
            {"deviceId": "F45-HB-1", "data": {
                "deviceType": "faceid", "parameterVersion": "6.1.0", "parameterMAC": "AA:BB:CC",
            }},
            format="json",
        )

        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data["success"], 0)
        self.device.refresh_from_db()
        self.assertIsNotNone(self.device.last_seen_at)
        self.assertEqual(self.device.firmware_version, "6.1.0")
        self.assertEqual(self.device.mac_address, "AA:BB:CC")

    def test_update_state_for_an_unknown_device_is_a_quiet_success(self):
        resp = self.client.post(
            "/api/facegate/device/updateStateDevice", {"deviceId": "NOT-REGISTERED"}, format="json",
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data["success"], 0)


class FaceGatePassInfoCursorTests(TestCase):
    def setUp(self):
        self.school = SchoolTenant.objects.create(name="Cursor School", schema_name="facegate_cursor_school")
        self.device = FaceGateDevice.objects.create(tenant=self.school, device_id="F45-CURSOR-1")
        self.client = APIClient()

    def test_only_pending_enrollments_past_the_cursor_are_returned_in_order(self):
        s1 = _make_student(self.school, "One", "Student", "CUR001")
        s2 = _make_student(self.school, "Two", "Student", "CUR002")
        s3 = _make_student(self.school, "Three", "Student", "CUR003")
        e1 = enroll_user_on_device(self.device, s1)
        e2 = enroll_user_on_device(self.device, s2)
        e3 = enroll_user_on_device(self.device, s3)
        # e2 is already synced - selectPassInfo must skip it even though its
        # number is past the cursor, and never hand it back a second time.
        FaceGateEnrollment.objects.filter(pk=e2.pk).update(status=FaceGateEnrollment.STATUS_SYNCED)

        resp = self.client.post(
            "/api/facegate/devicePass/selectPassInfo",
            {"deviceId": "F45-CURSOR-1", "last_employee_number": e1.device_employee_number},
            format="json",
        )

        self.assertEqual(resp.status_code, 200)
        numbers = [row["employeeNumberId"] for row in resp.data["passinfo"]]
        self.assertEqual(numbers, [str(e3.device_employee_number)])

    def test_an_unknown_device_gets_an_empty_list_not_an_error(self):
        resp = self.client.post(
            "/api/facegate/devicePass/selectPassInfo", {"deviceId": "GHOST", "last_employee_number": 0}, format="json",
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data["passinfo"], [])


class FaceGateSetPassResultTests(TestCase):
    def setUp(self):
        self.school = SchoolTenant.objects.create(name="Result School", schema_name="facegate_result_school")
        self.device = FaceGateDevice.objects.create(tenant=self.school, device_id="F45-RESULT-1")
        self.student = _make_student(self.school, "Result", "Student", "RES001")
        self.enrollment = enroll_user_on_device(self.device, self.student)
        self.client = APIClient()

    def test_a_reported_success_marks_the_enrollment_synced(self):
        resp = self.client.post(
            "/api/facegate/devicePass/setPassResult",
            {
                "deviceId": "F45-RESULT-1",
                "successEmployeeId": [{"employeeId": str(self.enrollment.device_employee_number)}],
            },
            format="json",
        )
        self.assertEqual(resp.status_code, 200)
        self.enrollment.refresh_from_db()
        self.assertEqual(self.enrollment.status, FaceGateEnrollment.STATUS_SYNCED)

    def test_a_reported_failure_marks_the_enrollment_failed_with_its_error_code(self):
        resp = self.client.post(
            "/api/facegate/devicePass/setPassResult",
            {
                "deviceId": "F45-RESULT-1",
                "failEmployeeId": [{"employeeId": str(self.enrollment.device_employee_number), "errorCode": "1001"}],
            },
            format="json",
        )
        self.assertEqual(resp.status_code, 200)
        self.enrollment.refresh_from_db()
        self.assertEqual(self.enrollment.status, FaceGateEnrollment.STATUS_FAILED)
        self.assertEqual(self.enrollment.error_message, "1001")


class FaceGateUnenrollTests(TestCase):
    def setUp(self):
        self.school = SchoolTenant.objects.create(name="Unenroll School", schema_name="facegate_unenroll_school")
        self.admin = User.objects.create_user(
            email="admin@unenroll.test", password="testpass123", role="school_admin", tenant=self.school,
        )
        self.device = FaceGateDevice.objects.create(tenant=self.school, device_id="F45-UNENROLL-1")
        self.student = _make_student(self.school, "Gone", "Student", "GONE001")
        from users.models import StudentProfile
        self.student_profile = StudentProfile.objects.get(user=self.student)
        self.enrollment = enroll_user_on_device(self.device, self.student)
        self.client = APIClient()
        self.client.force_authenticate(user=self.admin)

    def test_unenrolling_a_student_deletes_their_enrollment_row(self):
        resp = self.client.post(
            f"/api/facegate/admin/devices/{self.device.pk}/unenroll",
            {"student_ids": [str(self.student_profile.id)]},
            format="json",
        )
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertFalse(FaceGateEnrollment.objects.filter(pk=self.enrollment.pk).exists())

    def test_an_admin_cannot_unenroll_from_another_schools_device(self):
        other_school = SchoolTenant.objects.create(name="Elsewhere", schema_name="facegate_elsewhere_school")
        other_device = FaceGateDevice.objects.create(tenant=other_school, device_id="F45-ELSEWHERE-1")

        resp = self.client.post(
            f"/api/facegate/admin/devices/{other_device.pk}/unenroll",
            {"student_ids": [str(self.student_profile.id)]},
            format="json",
        )
        self.assertEqual(resp.status_code, 404)
        self.assertTrue(FaceGateEnrollment.objects.filter(pk=self.enrollment.pk).exists())


class FaceGateCheckinTests(TestCase):
    def setUp(self):
        self.school = SchoolTenant.objects.create(name="Checkin School", schema_name="facegate_checkin_school")
        self.device = FaceGateDevice.objects.create(tenant=self.school, device_id="F45-CHECKIN-1")
        self.student = _make_student(self.school, "Tap", "Student", "TAP001", phone="08010000099")
        self.enrollment = enroll_user_on_device(self.device, self.student)
        self.client = APIClient()

    def _tap(self, note_time):
        return self.client.post(
            "/api/facegate/note/insertNoteFace",
            {
                "deviceId": "F45-CHECKIN-1",
                "data": {"employeeNumberId": str(self.enrollment.device_employee_number), "noteTime": note_time},
            },
            format="json",
        )

    def test_a_tap_in_the_early_window_clocks_in_and_bills_the_wallet(self):
        from finance.models import SmsMessageLog
        from finance.services import get_or_create_sms_wallet

        wallet = get_or_create_sms_wallet(self.school)
        wallet.balance = 10
        wallet.save(update_fields=["balance", "updated_at"])

        with patch("finance.services._dispatch_wallet_sms") as mock_send, \
                patch("rfid_attendance.views.threading.Thread", _ImmediateThread):
            mock_send.return_value = {"response": {"status": "SUCCESS", "totalsent": 1, "cost": 4}}
            resp = self._tap("2026-01-15 08:00:00")

        self.assertEqual(resp.status_code, 200)
        record = AttendanceRecord.objects.get(student=self.student)
        self.assertIsNotNone(record.clock_in_at)
        self.assertIsNone(record.clock_out_at)
        wallet.refresh_from_db()
        self.assertEqual(wallet.balance, 9)
        self.assertTrue(SmsMessageLog.objects.filter(category=SmsMessageLog.ATTENDANCE).exists())

    def test_a_tap_in_the_clockout_window_with_no_prior_clockin_clocks_out(self):
        with patch("rfid_attendance.views.threading.Thread", _ImmediateThread), \
                patch(
                    "finance.services._dispatch_wallet_sms",
                    return_value={"response": {"status": "SUCCESS", "totalsent": 1, "cost": 4}},
                ):
            resp = self._tap("2026-01-15 13:30:00")

        self.assertEqual(resp.status_code, 200)
        record = AttendanceRecord.objects.get(student=self.student)
        self.assertIsNotNone(record.clock_out_at)

    def test_a_tap_before_the_clockin_window_opens_is_rejected_as_too_early(self):
        resp = self._tap("2026-01-15 06:00:00")

        self.assertEqual(resp.status_code, 200)
        self.assertFalse(AttendanceRecord.objects.filter(student=self.student).exists())

    def test_repeating_the_exact_same_note_time_does_not_record_twice(self):
        with patch("rfid_attendance.views.threading.Thread", _ImmediateThread), \
                patch(
                    "finance.services._dispatch_wallet_sms",
                    return_value={"response": {"status": "SUCCESS", "totalsent": 1, "cost": 4}},
                ) as mock_send:
            self._tap("2026-01-15 08:00:00")
            self._tap("2026-01-15 08:00:00")  # the device's own documented retry behavior

        self.assertEqual(AttendanceRecord.objects.filter(student=self.student).count(), 1)
        mock_send.assert_called_once()

    def test_a_premium_schoolgate_school_sends_the_sms_free_via_kudisms_not_the_wallet(self):
        from finance.models import SmsMessageLog
        from finance.services import get_or_create_sms_wallet

        self.school.product = SchoolTenant.PRODUCT_SCHOOLGATE
        self.school.subscription_tier = "premium"
        self.school.save(update_fields=["product", "subscription_tier"])
        wallet = get_or_create_sms_wallet(self.school)
        wallet.balance = 10
        wallet.save(update_fields=["balance", "updated_at"])

        with patch("rfid_attendance.views.threading.Thread") as mock_thread:
            resp = self._tap("2026-01-15 08:00:00")

        self.assertEqual(resp.status_code, 200)
        mock_thread.assert_called_once()
        _call_args, call_kwargs = mock_thread.call_args
        self.assertEqual(call_kwargs["args"][1], "kudisms")
        wallet.refresh_from_db()
        self.assertEqual(wallet.balance, 10)
        self.assertFalse(SmsMessageLog.objects.filter(category=SmsMessageLog.ATTENDANCE).exists())

    def test_a_tap_for_an_unknown_employee_number_is_ignored(self):
        resp = self.client.post(
            "/api/facegate/note/insertNoteFace",
            {"deviceId": "F45-CHECKIN-1", "data": {"employeeNumberId": "99999", "noteTime": "2026-01-15 08:00:00"}},
            format="json",
        )
        self.assertEqual(resp.status_code, 200)
        self.assertFalse(AttendanceRecord.objects.filter(student=self.student).exists())


class FaceGateDeviceCommandTests(TestCase):
    """Pop semantics for the one-shot restart/shutdown/opendoor flags - a
    queued command must fire exactly once, not on every subsequent poll."""

    def setUp(self):
        self.school = SchoolTenant.objects.create(name="Command School", schema_name="facegate_command_school")
        self.admin = User.objects.create_user(
            email="admin@command.test", password="testpass123", role="school_admin", tenant=self.school,
        )
        self.device = FaceGateDevice.objects.create(tenant=self.school, device_id="F45-CMD-1")
        self.client = APIClient()

    def test_no_pending_command_returns_all_zero(self):
        resp = self.client.post("/api/facegate/device/selectRestart", {"deviceId": "F45-CMD-1"}, format="json")

        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data, {"restart": 0, "shutdown": 0, "opendoor": 0})

    def test_a_queued_opendoor_command_is_served_once_then_cleared(self):
        self.client.force_authenticate(user=self.admin)
        queue_resp = self.client.post(f"/api/facegate/admin/devices/{self.device.pk}/opendoor")
        self.assertEqual(queue_resp.status_code, 200, queue_resp.data)

        first_poll = self.client.post("/api/facegate/device/selectRestart", {"deviceId": "F45-CMD-1"}, format="json")
        self.assertEqual(first_poll.data["opendoor"], 1)

        second_poll = self.client.post("/api/facegate/device/selectRestart", {"deviceId": "F45-CMD-1"}, format="json")
        self.assertEqual(second_poll.data["opendoor"], 0)
