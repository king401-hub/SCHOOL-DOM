"""Tests for the vendor face-recognition SchoolGate terminal HTTP
integration (the "cloud solution" cmd/sn protocol). There is no real
AT3003F unit to test against, so these simulate the device side of each
vendor-documented command with plain HTTP calls to the single device_api/
endpoint - exactly the requests a real terminal would send."""
import datetime
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from rest_framework.test import APIClient

from academic.models import AttendanceRecord
from core.models import SchoolTenant

from .models import FaceGateDevice, FaceGateEnrollment
from .services import enroll_user_on_device

User = get_user_model()

DEVICE_API = "/api/facegate/device_api/"


class _ImmediateThread:
    """Stands in for threading.Thread so a gate SMS (fired on a background
    thread, see rfid_attendance.views._send_gate_sms/_send_gate_sms_from_wallet)
    runs synchronously within the test instead of racing the assertions -
    same helper rfid_attendance/tests.py uses for the same reason."""

    def __init__(self, target=None, args=(), kwargs=None, daemon=None):
        self._target, self._args, self._kwargs = target, args, kwargs or {}

    def start(self):
        self._target(*self._args, **self._kwargs)


def _make_student(tenant, first, last, student_id, phone="08010000000", with_photo=False):
    from users.models import StudentProfile

    user = User.objects.create_user(
        email=f"{student_id.lower()}@facegate.test", password="testpass123", role="student",
        tenant=tenant, first_name=first, last_name=last,
    )
    if with_photo:
        user.profile_picture = SimpleUploadedFile(f"{student_id}.jpg", b"fake-photo-bytes", content_type="image/jpeg")
        user.save(update_fields=["profile_picture"])
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
            {"device_id": "AT3003-0001", "label": "Front Gate"},
            format="json",
        )
        self.assertEqual(resp.status_code, 201, resp.data)
        self.assertTrue(FaceGateDevice.objects.filter(tenant=self.school, device_id="AT3003-0001").exists())

    def test_registering_the_same_device_id_for_another_school_is_rejected(self):
        other_school = SchoolTenant.objects.create(name="Other School", schema_name="facegate_other_school")
        FaceGateDevice.objects.create(tenant=other_school, device_id="AT3003-SHARED", label="Theirs")

        resp = self.client.post(
            "/api/facegate/admin/devices/register",
            {"device_id": "AT3003-SHARED", "label": "Mine"},
            format="json",
        )
        self.assertEqual(resp.status_code, 400, resp.data)

    def test_a_non_admin_cannot_register_a_device(self):
        teacher = User.objects.create_user(
            email="teacher@facegate.test", password="testpass123", role="teacher", tenant=self.school,
        )
        self.client.force_authenticate(user=teacher)

        resp = self.client.post(
            "/api/facegate/admin/devices/register", {"device_id": "AT3003-0002"}, format="json",
        )
        self.assertEqual(resp.status_code, 403)

    def test_an_admin_only_sees_devices_from_their_own_school(self):
        other_school = SchoolTenant.objects.create(name="Other School 2", schema_name="facegate_other_school_2")
        FaceGateDevice.objects.create(tenant=other_school, device_id="AT3003-NOT-MINE")
        FaceGateDevice.objects.create(tenant=self.school, device_id="AT3003-MINE")

        resp = self.client.get("/api/facegate/admin/devices")

        self.assertEqual(resp.status_code, 200)
        device_ids = [d["device_id"] for d in resp.data["devices"]]
        self.assertEqual(device_ids, ["AT3003-MINE"])


class FaceGateRegAndHeartbeatTests(TestCase):
    def setUp(self):
        self.school = SchoolTenant.objects.create(name="Heartbeat School", schema_name="facegate_heartbeat_school")
        self.device = FaceGateDevice.objects.create(tenant=self.school, device_id="AT3003-HB-1")
        self.client = APIClient()

    def test_reg_for_a_known_sn_updates_devinfo_and_last_seen(self):
        self.assertIsNone(self.device.last_seen_at)

        resp = self.client.post(DEVICE_API, {
            "cmd": "reg", "sn": "AT3003-HB-1",
            "devinfo": {"modelname": "AT3003F", "firmware": "6.1.0", "mac": "AA:BB:CC"},
        }, format="json")

        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.data["result"])
        self.device.refresh_from_db()
        self.assertIsNotNone(self.device.last_seen_at)
        self.assertEqual(self.device.firmware_version, "6.1.0")
        self.assertEqual(self.device.mac_address, "AA:BB:CC")

    def test_reg_for_an_unregistered_sn_fails_safely(self):
        resp = self.client.post(DEVICE_API, {"cmd": "reg", "sn": "NOT-REGISTERED"}, format="json")
        self.assertEqual(resp.status_code, 200)
        self.assertFalse(resp.data["result"])

    def test_checklive_with_nothing_pending_returns_a_plain_ack(self):
        resp = self.client.post(DEVICE_API, {"cmd": "checklive", "sn": "AT3003-HB-1"}, format="json")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data["ret"], "checklive")
        self.assertTrue(resp.data["result"])
        self.device.refresh_from_db()
        self.assertIsNotNone(self.device.last_seen_at)

    def test_an_unknown_command_gets_a_safe_failure_reply(self):
        resp = self.client.post(DEVICE_API, {"cmd": "somethingunexpected", "sn": "AT3003-HB-1"}, format="json")
        self.assertEqual(resp.status_code, 200)
        self.assertFalse(resp.data["result"])


class FaceGateEnrollmentPushTests(TestCase):
    def setUp(self):
        self.school = SchoolTenant.objects.create(name="Push School", schema_name="facegate_push_school")
        self.device = FaceGateDevice.objects.create(tenant=self.school, device_id="AT3003-PUSH-1")
        self.client = APIClient()

    def test_a_pending_enrollment_with_a_photo_is_pushed_on_the_next_checklive(self):
        student = _make_student(self.school, "Has", "Photo", "PHOTO001", with_photo=True)
        enrollment = enroll_user_on_device(self.device, student)

        resp = self.client.post(DEVICE_API, {"cmd": "checklive", "sn": "AT3003-PUSH-1"}, format="json")

        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data["cmd"], "setuserinfo")
        self.assertEqual(resp.data["enrollid"], enrollment.device_employee_number)
        self.assertEqual(resp.data["backupnum"], 50)
        self.assertTrue(resp.data["record"])  # base64 photo bytes
        enrollment.refresh_from_db()
        self.assertEqual(enrollment.status, FaceGateEnrollment.STATUS_PENDING_ADD)  # synced only once acked

    def test_a_pending_enrollment_with_no_photo_is_skipped_not_pushed(self):
        student = _make_student(self.school, "No", "Photo", "NOPHOTO001", with_photo=False)
        enroll_user_on_device(self.device, student)

        resp = self.client.post(DEVICE_API, {"cmd": "checklive", "sn": "AT3003-PUSH-1"}, format="json")

        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data.get("ret"), "checklive")  # plain ack, nothing to push

    def test_device_ack_of_setuserinfo_marks_the_enrollment_synced(self):
        student = _make_student(self.school, "Will", "Sync", "SYNC001", with_photo=True)
        enrollment = enroll_user_on_device(self.device, student)

        resp = self.client.post(DEVICE_API, {
            "ret": "setuserinfo", "sn": "AT3003-PUSH-1",
            "enrollid": enrollment.device_employee_number, "result": True,
        }, format="json")

        self.assertEqual(resp.status_code, 200)
        enrollment.refresh_from_db()
        self.assertEqual(enrollment.status, FaceGateEnrollment.STATUS_SYNCED)

    def test_a_failed_ack_leaves_the_enrollment_pending_for_retry(self):
        student = _make_student(self.school, "Will", "Fail", "FAIL001", with_photo=True)
        enrollment = enroll_user_on_device(self.device, student)

        resp = self.client.post(DEVICE_API, {
            "ret": "setuserinfo", "sn": "AT3003-PUSH-1", "result": False, "reason": 1,
        }, format="json")

        self.assertEqual(resp.status_code, 200)
        enrollment.refresh_from_db()
        self.assertEqual(enrollment.status, FaceGateEnrollment.STATUS_PENDING_ADD)


class FaceGateLocalFingerprintTests(TestCase):
    """A fingerprint can only ever be captured locally on the terminal's own
    sensor (see facegate.views._handle_senduser's docstring) - these
    simulate the device reporting that capture back via `senduser`, using
    the exact field shape confirmed from both the vendor's protocol doc
    and its own reference server (FlaskProject/app.py's get_enroll_info)."""

    def setUp(self):
        self.school = SchoolTenant.objects.create(name="Fingerprint School", schema_name="facegate_fingerprint_school")
        self.device = FaceGateDevice.objects.create(tenant=self.school, device_id="AT3003-FP-1")
        self.student = _make_student(self.school, "Finger", "Student", "FP001")
        self.enrollment = enroll_user_on_device(self.device, self.student)
        self.client = APIClient()

    def test_a_locally_captured_fingerprint_is_recorded_for_the_preallocated_enrollid(self):
        self.assertIsNone(self.enrollment.fingerprint_enrolled_at)

        resp = self.client.post(DEVICE_API, {
            "cmd": "senduser", "sn": "AT3003-FP-1",
            "enrollid": self.enrollment.device_employee_number, "name": "Finger Student",
            "backupnum": 0, "admin": 0, "record": "opaque-thbio-template-bytes",
        }, format="json")

        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.data["result"])
        self.enrollment.refresh_from_db()
        self.assertIsNotNone(self.enrollment.fingerprint_enrolled_at)

    def test_a_password_or_card_local_add_is_acked_but_not_recorded_as_a_fingerprint(self):
        resp = self.client.post(DEVICE_API, {
            "cmd": "senduser", "sn": "AT3003-FP-1",
            "enrollid": self.enrollment.device_employee_number, "name": "Finger Student",
            "backupnum": 11, "admin": 0, "record": 2352253,
        }, format="json")

        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.data["result"])
        self.enrollment.refresh_from_db()
        self.assertIsNone(self.enrollment.fingerprint_enrolled_at)

    def test_a_fingerprint_for_an_enrollid_we_never_allocated_is_safely_ignored(self):
        resp = self.client.post(DEVICE_API, {
            "cmd": "senduser", "sn": "AT3003-FP-1",
            "enrollid": 99999, "name": "Nobody", "backupnum": 0, "admin": 0, "record": "x",
        }, format="json")

        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.data["result"])
        self.assertFalse(FaceGateEnrollment.objects.filter(fingerprint_enrolled_at__isnull=False).exists())

    def test_an_unregistered_device_still_gets_a_safe_ack(self):
        resp = self.client.post(DEVICE_API, {
            "cmd": "senduser", "sn": "GHOST", "enrollid": 1, "backupnum": 0, "record": "x",
        }, format="json")

        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.data["result"])

    def test_admin_device_list_surfaces_the_fingerprint_enrolled_count(self):
        admin = User.objects.create_user(
            email="admin@fingerprint.test", password="testpass123", role="school_admin", tenant=self.school,
        )
        self.enrollment.fingerprint_enrolled_at = datetime.datetime.now(datetime.timezone.utc)
        self.enrollment.save(update_fields=["fingerprint_enrolled_at"])
        client = APIClient()
        client.force_authenticate(user=admin)

        resp = client.get("/api/facegate/admin/devices")

        self.assertEqual(resp.status_code, 200)
        device_row = next(d for d in resp.data["devices"] if d["device_id"] == "AT3003-FP-1")
        self.assertEqual(device_row["fingerprint_enrolled_count"], 1)


class FaceGateUnenrollTests(TestCase):
    def setUp(self):
        self.school = SchoolTenant.objects.create(name="Unenroll School", schema_name="facegate_unenroll_school")
        self.admin = User.objects.create_user(
            email="admin@unenroll.test", password="testpass123", role="school_admin", tenant=self.school,
        )
        self.device = FaceGateDevice.objects.create(tenant=self.school, device_id="AT3003-UNENROLL-1")
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
        other_device = FaceGateDevice.objects.create(tenant=other_school, device_id="AT3003-ELSEWHERE-1")

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
        self.device = FaceGateDevice.objects.create(tenant=self.school, device_id="AT3003-CHECKIN-1")
        self.student = _make_student(self.school, "Tap", "Student", "TAP001", phone="08010000099")
        self.enrollment = enroll_user_on_device(self.device, self.student)
        self.client = APIClient()

    def _sendlog(self, note_time, enrollid=None):
        return self.client.post(DEVICE_API, {
            "cmd": "sendlog", "sn": "AT3003-CHECKIN-1", "count": 1,
            "record": [{
                "enrollid": enrollid if enrollid is not None else self.enrollment.device_employee_number,
                "time": note_time, "mode": 8, "inout": 0, "event": 0,
            }],
        }, format="json")

    def test_a_tap_in_the_early_window_clocks_in_and_bills_the_wallet(self):
        from finance.models import SmsMessageLog
        from finance.services import get_or_create_sms_wallet

        wallet = get_or_create_sms_wallet(self.school)
        wallet.balance = 10
        wallet.save(update_fields=["balance", "updated_at"])

        with patch("finance.services._dispatch_wallet_sms") as mock_send, \
                patch("rfid_attendance.views.threading.Thread", _ImmediateThread):
            mock_send.return_value = {"response": {"status": "SUCCESS", "totalsent": 1, "cost": 4}}
            resp = self._sendlog("2026-01-15 08:00:00")

        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.data["result"])
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
            resp = self._sendlog("2026-01-15 13:30:00")

        self.assertEqual(resp.status_code, 200)
        record = AttendanceRecord.objects.get(student=self.student)
        self.assertIsNotNone(record.clock_out_at)

    def test_a_tap_before_the_clockin_window_opens_is_rejected_as_too_early(self):
        resp = self._sendlog("2026-01-15 06:00:00")

        self.assertEqual(resp.status_code, 200)
        self.assertFalse(AttendanceRecord.objects.filter(student=self.student).exists())

    def test_repeating_the_exact_same_note_time_does_not_record_twice(self):
        with patch("rfid_attendance.views.threading.Thread", _ImmediateThread), \
                patch(
                    "finance.services._dispatch_wallet_sms",
                    return_value={"response": {"status": "SUCCESS", "totalsent": 1, "cost": 4}},
                ) as mock_send:
            self._sendlog("2026-01-15 08:00:00")
            self._sendlog("2026-01-15 08:00:00")  # the device's own documented retry behavior

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
            resp = self._sendlog("2026-01-15 08:00:00")

        self.assertEqual(resp.status_code, 200)
        mock_thread.assert_called_once()
        _call_args, call_kwargs = mock_thread.call_args
        self.assertEqual(call_kwargs["args"][1], "kudisms")
        wallet.refresh_from_db()
        self.assertEqual(wallet.balance, 10)
        self.assertFalse(SmsMessageLog.objects.filter(category=SmsMessageLog.ATTENDANCE).exists())

    def test_a_tap_for_an_unknown_enrollid_is_ignored(self):
        resp = self._sendlog("2026-01-15 08:00:00", enrollid=99999)
        self.assertEqual(resp.status_code, 200)
        self.assertFalse(AttendanceRecord.objects.filter(student=self.student).exists())

    def test_an_unregistered_device_fails_safely(self):
        resp = self.client.post(DEVICE_API, {"cmd": "sendlog", "sn": "GHOST", "count": 0, "record": []}, format="json")
        self.assertEqual(resp.status_code, 200)
        self.assertFalse(resp.data["result"])


class FaceGateDeviceCommandTests(TestCase):
    """Pop semantics for the one-shot restart/opendoor flags, delivered on
    the device's next checklive poll - a queued command must fire exactly
    once, not on every subsequent heartbeat."""

    def setUp(self):
        self.school = SchoolTenant.objects.create(name="Command School", schema_name="facegate_command_school")
        self.admin = User.objects.create_user(
            email="admin@command.test", password="testpass123", role="school_admin", tenant=self.school,
        )
        self.device = FaceGateDevice.objects.create(tenant=self.school, device_id="AT3003-CMD-1")
        self.client = APIClient()

    def test_a_queued_opendoor_command_is_served_once_on_checklive_then_cleared(self):
        self.client.force_authenticate(user=self.admin)
        queue_resp = self.client.post(f"/api/facegate/admin/devices/{self.device.pk}/opendoor")
        self.assertEqual(queue_resp.status_code, 200, queue_resp.data)
        self.client.force_authenticate(user=None)

        first_poll = self.client.post(DEVICE_API, {"cmd": "checklive", "sn": "AT3003-CMD-1"}, format="json")
        self.assertEqual(first_poll.data, {"cmd": "opendoor"})

        second_poll = self.client.post(DEVICE_API, {"cmd": "checklive", "sn": "AT3003-CMD-1"}, format="json")
        self.assertEqual(second_poll.data["ret"], "checklive")

    def test_a_queued_restart_command_is_served_as_reboot_then_cleared(self):
        self.client.force_authenticate(user=self.admin)
        self.client.post(f"/api/facegate/admin/devices/{self.device.pk}/restart")
        self.client.force_authenticate(user=None)

        first_poll = self.client.post(DEVICE_API, {"cmd": "checklive", "sn": "AT3003-CMD-1"}, format="json")
        self.assertEqual(first_poll.data, {"cmd": "reboot"})

        second_poll = self.client.post(DEVICE_API, {"cmd": "checklive", "sn": "AT3003-CMD-1"}, format="json")
        self.assertEqual(second_poll.data["ret"], "checklive")
