"""Tests for attendance app."""
from django.test import TestCase
from django.utils import timezone
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from core.models import SchoolTenant
from .models import AttendanceQRCode, TeacherAttendance

User = get_user_model()


class AttendanceQRCodeTestCase(TestCase):
    """Test QR code generation and verification."""
    
    def setUp(self):
        """Set up test data."""
        self.tenant = SchoolTenant.objects.create(
            name="Test School",
            schema_name="test_school"
        )
        self.admin = User.objects.create_user(
            email="admin@test.com",
            password="testpass123",
            role="school_admin",
            tenant=self.tenant
        )
    
    def test_qr_code_creation(self):
        """Test QR code creation."""
        qr_code, created = AttendanceQRCode.get_or_create_for_tenant(self.tenant)
        self.assertTrue(created)
        self.assertEqual(qr_code.tenant, self.tenant)
        self.assertEqual(qr_code.token, AttendanceQRCode.static_token_for_tenant(self.tenant))
    
    def test_qr_code_verification(self):
        """Test QR code token verification."""
        qr_code, _ = AttendanceQRCode.get_or_create_for_tenant(self.tenant)
        
        # Valid token
        verified = AttendanceQRCode.verify_token(qr_code.token)
        self.assertEqual(verified, qr_code)
        
        # Invalid token
        verified = AttendanceQRCode.verify_token("invalid_token")
        self.assertIsNone(verified)


class TeacherAttendanceTestCase(TestCase):
    """Test teacher attendance marking."""
    
    def setUp(self):
        """Set up test data."""
        self.tenant = SchoolTenant.objects.create(
            name="Test School",
            schema_name="test_school"
        )
        self.teacher = User.objects.create_user(
            email="teacher@test.com",
            password="testpass123",
            role="teacher",
            tenant=self.tenant
        )
        self.qr_code, _ = AttendanceQRCode.get_or_create_for_tenant(self.tenant)
        self.client = APIClient()
        self.location_payload = {
            "latitude": 6.5243793,
            "longitude": 3.3792057,
            "accuracy": 12.5,
            "address": "Lagos, Nigeria",
            "device_info": "Test browser | platform=test",
        }
    
    def test_attendance_creation(self):
        """Test creating attendance record."""
        attendance = TeacherAttendance.objects.create(
            teacher=self.teacher,
            tenant=self.tenant,
            qr_code=self.qr_code,
            status='present'
        )
        self.assertEqual(attendance.teacher, self.teacher)
        self.assertEqual(attendance.status, 'present')
        self.assertIsNotNone(attendance.check_in_time)
    
    def test_one_attendance_per_day(self):
        """Test that only one attendance per day is allowed."""
        today = timezone.localdate()
        
        # First attendance
        TeacherAttendance.objects.create(
            teacher=self.teacher,
            tenant=self.tenant,
            qr_code=self.qr_code,
            status='present'
        )
        
        # Check if already marked
        has_checked_in = TeacherAttendance.has_checked_in_today(self.teacher, today)
        self.assertTrue(has_checked_in)
    
    def test_get_today_attendance(self):
        """Test retrieving today's attendance."""
        # Create multiple attendance records
        for i in range(3):
            User.objects.create_user(
                email=f"teacher{i}@test.com",
                password="testpass123",
                role="teacher",
                tenant=self.tenant
            )
        
        teachers = User.objects.filter(role="teacher", tenant=self.tenant)
        for teacher in teachers:
            TeacherAttendance.objects.create(
                teacher=teacher,
                tenant=self.tenant,
                qr_code=self.qr_code,
                status='present'
            )
        
        # Get today's attendance
        attendance_list = TeacherAttendance.get_today_attendance(self.tenant)
        self.assertEqual(attendance_list.count(), teachers.count())

    def test_staff_role_can_mark_qr_attendance(self):
        staff_user = User.objects.create_user(
            email="nonteaching@test.com",
            password="testpass123",
            role="staff",
            tenant=self.tenant,
        )
        response = self.client.post(
            f"/api/attendance/scan/{self.qr_code.token}/",
            {"user_id": str(staff_user.id), "location": self.location_payload},
            format="json",
        )

        self.assertEqual(response.status_code, 201)
        self.assertTrue(response.data["success"])
        attendance = TeacherAttendance.objects.get(teacher=staff_user)
        self.assertEqual(str(attendance.check_in_latitude), "6.5243793")
        self.assertEqual(str(attendance.check_in_longitude), "3.3792057")
        self.assertEqual(attendance.check_in_address, "Lagos, Nigeria")

    def test_invalid_bearer_header_does_not_block_attendance(self):
        response = self.client.post(
            f"/api/attendance/scan/{self.qr_code.token}/",
            {"user_id": str(self.teacher.id), "location": self.location_payload},
            format="json",
            HTTP_AUTHORIZATION="Bearer expired-or-bad-token",
        )

        self.assertEqual(response.status_code, 201)
        self.assertTrue(response.data["success"])

    def test_qr_attendance_requires_location(self):
        response = self.client.post(
            f"/api/attendance/scan/{self.qr_code.token}/",
            {"user_id": str(self.teacher.id)},
            format="json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertFalse(response.data["success"])
        self.assertFalse(TeacherAttendance.objects.filter(teacher=self.teacher).exists())

    def test_clock_out_requires_location_and_stores_location(self):
        self.client.post(
            f"/api/attendance/scan/{self.qr_code.token}/",
            {"user_id": str(self.teacher.id), "location": self.location_payload},
            format="json",
        )

        missing_location = self.client.post(
            "/api/attendance/clock-out/",
            {"user_id": str(self.teacher.id)},
            format="json",
        )
        self.assertEqual(missing_location.status_code, 400)

        response = self.client.post(
            "/api/attendance/clock-out/",
            {
                "user_id": str(self.teacher.id),
                "location": {
                    **self.location_payload,
                    "latitude": 6.45,
                    "longitude": 3.40,
                    "address": "School gate",
                },
            },
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        attendance = TeacherAttendance.objects.get(teacher=self.teacher)
        self.assertIsNotNone(attendance.check_out_time)
        self.assertEqual(str(attendance.check_out_latitude), "6.4500000")
        self.assertEqual(attendance.check_out_address, "School gate")
