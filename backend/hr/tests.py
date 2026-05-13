from decimal import Decimal

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from rest_framework.test import APIClient

from core.models import SchoolTenant
from attendance.models import AttendanceQRCode
from hr.models import LeaveRequest, PayrollRecord, SalaryAdvanceRequest, StaffAttendance, StaffProfile
from users.models import TeacherProfile, User


class HRManagementAPITests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.school = SchoolTenant.objects.create(name="HR School", schema_name="hr_school", is_active=True)
        self.admin = User.objects.create_user(
            email="hr.admin@school.edu",
            password="AdminPass123",
            first_name="HR",
            last_name="Admin",
            role="school_admin",
            tenant=self.school,
            is_active=True,
            is_verified=True,
        )
        self.client.force_authenticate(user=self.admin)

    def test_admin_can_manage_staff_payroll_attendance_leave_and_advances(self):
        staff_response = self.client.post(
            "/api/hr/staff/create/",
            data={
                "first_name": "Ada",
                "last_name": "Okafor",
                "staff_type": "non_teaching",
                "role": "Accountant",
                "department": "Finance",
                "base_salary": "150000",
            },
            format="json",
        )
        self.assertEqual(staff_response.status_code, 201)
        staff_id = staff_response.data["staff"]["id"]
        staff = StaffProfile.objects.get(id=staff_id)
        self.assertEqual(len(staff.staff_code), 7)
        self.assertRegex(staff.staff_code, r"^NSHS\d{3}$")
        qr_code, _created = AttendanceQRCode.get_or_create_for_tenant(self.school)

        attendance_response = self.client.post(
            "/api/hr/attendance/mark/",
            data={"staff_id": staff_id, "qr_token": qr_code.token},
            format="json",
        )
        self.assertEqual(attendance_response.status_code, 200)
        self.assertEqual(StaffAttendance.objects.filter(staff=staff).count(), 1)

        leave_response = self.client.post(
            "/api/hr/leave/create/",
            data={"staff_id": staff_id, "leave_type": "Annual", "start_date": "2026-05-10", "end_date": "2026-05-12"},
            format="json",
        )
        self.assertEqual(leave_response.status_code, 201)
        review_response = self.client.post(
            f"/api/hr/leave/{leave_response.data['leave']['id']}/review/",
            data={"status": "approved"},
            format="json",
        )
        self.assertEqual(review_response.status_code, 200)
        self.assertEqual(LeaveRequest.objects.get(staff=staff).status, "approved")

        advance_response = self.client.post(
            "/api/hr/advances/create/",
            data={"staff_id": staff_id, "amount": "10000", "reason": "Transport"},
            format="json",
        )
        self.assertEqual(advance_response.status_code, 201)
        paid_advance_response = self.client.post(
            f"/api/hr/advances/{advance_response.data['advance']['id']}/review/",
            data={"status": "paid"},
            format="json",
        )
        self.assertEqual(paid_advance_response.status_code, 200)
        self.assertEqual(SalaryAdvanceRequest.objects.get(staff=staff).status, "paid")

        payroll_response = self.client.post(
            "/api/hr/payroll/create/",
            data={"staff_id": staff_id, "year": 2026, "month": 5, "allowances": "5000", "deductions": "2000", "amount_paid": "140000"},
            format="json",
        )
        self.assertEqual(payroll_response.status_code, 201)
        payroll = PayrollRecord.objects.get(staff=staff, year=2026, month=5)
        self.assertEqual(payroll.net_salary, Decimal("143000.00"))
        self.assertEqual(payroll.balance_after_payment, Decimal("3000.00"))

        snapshot = self.client.get("/api/hr/overview/")
        self.assertEqual(snapshot.status_code, 200)
        self.assertEqual(snapshot.data["summary"]["total_staff"], 1)
        self.assertEqual(snapshot.data["summary"]["pending_leaves"], 0)

        download = self.client.get("/api/hr/staff/download/?type=non_teaching")
        self.assertEqual(download.status_code, 200)
        self.assertIn("text/csv", download["Content-Type"])

        qr_download = self.client.get("/api/attendance/qr-code/download/")
        self.assertEqual(qr_download.status_code, 200)
        self.assertEqual(qr_download["Content-Type"], "image/png")

    def test_staff_can_request_own_leave_and_salary_advance(self):
        staff_user = User.objects.create_user(
            email="staff.self@school.edu",
            password="StaffPass123",
            first_name="Solomon",
            last_name="Enoch",
            role="staff",
            tenant=self.school,
            is_active=True,
            is_verified=True,
        )
        staff = StaffProfile.objects.create(
            tenant=self.school,
            user=staff_user,
            staff_code="NST001",
            first_name="Solomon",
            last_name="Enoch",
            email=staff_user.email,
            staff_type=StaffProfile.NON_TEACHING,
            role="Admin Officer",
            base_salary=Decimal("75000.00"),
        )
        self.client.force_authenticate(user=self.admin)
        update_response = self.client.patch(
            f"/api/hr/staff/{staff.id}/",
            data={
                "email": "staff.updated@school.edu",
                "staff_password": "NewStaff123",
                "confirm_staff_password": "NewStaff123",
            },
            format="json",
        )
        self.assertEqual(update_response.status_code, 200)
        staff.refresh_from_db()
        staff_user.refresh_from_db()
        self.assertEqual(staff.email, "staff.updated@school.edu")
        self.assertEqual(staff_user.email, "staff.updated@school.edu")
        self.assertTrue(staff_user.check_password("NewStaff123"))

        self.client.force_authenticate(user=staff_user)
        qr_code, _created = AttendanceQRCode.get_or_create_for_tenant(self.school)
        attendance_response = self.client.post(
            "/api/hr/attendance/mark/",
            data={"qr_token": qr_code.token},
            format="json",
        )
        self.assertEqual(attendance_response.status_code, 200)
        self.assertEqual(StaffAttendance.objects.filter(staff=staff).count(), 1)

        leave_response = self.client.post(
            "/api/hr/leave/create/",
            data={"leave_type": "Annual", "start_date": "2026-05-10", "end_date": "2026-05-12", "reason": "Family"},
            format="json",
        )
        self.assertEqual(leave_response.status_code, 201)
        self.assertEqual(LeaveRequest.objects.get(staff=staff).requested_by, staff_user)

        advance_response = self.client.post(
            "/api/hr/advances/create/",
            data={"amount": "12000", "reason": "Transport"},
            format="json",
        )
        self.assertEqual(advance_response.status_code, 201)
        self.assertEqual(SalaryAdvanceRequest.objects.get(staff=staff).amount, Decimal("12000.00"))

        snapshot = self.client.get("/api/hr/me/")
        self.assertEqual(snapshot.status_code, 200)
        self.assertEqual(snapshot.data["staff"]["id"], str(staff.id))
        self.assertEqual(len(snapshot.data["leaves"]), 1)
        self.assertEqual(len(snapshot.data["advances"]), 1)

    def test_staff_can_update_own_biodata_and_cv(self):
        staff_user = User.objects.create_user(
            email="staff.bio@school.edu",
            password="StaffPass123",
            first_name="Bisi",
            last_name="Adeniyi",
            role="staff",
            tenant=self.school,
            is_active=True,
            is_verified=True,
        )
        staff = StaffProfile.objects.create(
            tenant=self.school,
            user=staff_user,
            staff_code="NSHS123",
            first_name="Bisi",
            last_name="Adeniyi",
            email=staff_user.email,
            staff_type=StaffProfile.NON_TEACHING,
            role="Bursar",
            base_salary=Decimal("80000.00"),
        )
        self.client.force_authenticate(user=staff_user)
        response = self.client.patch(
            "/api/hr/me/",
            data={
                "phone": "+234800000001",
                "gender": "F",
                "date_of_birth": "1992-04-11",
                "address": "12 Admin Road",
                "emergency_contact_name": "Next Kin",
                "emergency_contact_phone": "+234800000002",
                "emergency_contact_relation": "Sibling",
                "cv": SimpleUploadedFile("bisi-cv.pdf", b"cv", content_type="application/pdf"),
            },
            format="multipart",
        )
        self.assertEqual(response.status_code, 200)
        staff.refresh_from_db()
        staff_user.refresh_from_db()
        self.assertEqual(staff.gender, "F")
        self.assertEqual(str(staff.date_of_birth), "1992-04-11")
        self.assertEqual(staff.emergency_contact_relation, "Sibling")
        self.assertTrue(staff.cv.name.endswith(".pdf"))
        self.assertEqual(staff_user.phone, "+234800000001")
        self.assertEqual(staff_user.gender, "F")

    def test_teacher_can_update_own_biodata_and_cv(self):
        teacher_user = User.objects.create_user(
            email="teacher.bio@school.edu",
            password="TeacherPass123",
            first_name="Tomi",
            last_name="Bello",
            role="teacher",
            tenant=self.school,
            is_active=True,
            is_verified=True,
        )
        teacher = TeacherProfile.objects.create(
            user=teacher_user,
            employee_id="TCH901",
            qualification="B.Ed",
            specialization="English",
            years_of_experience=5,
            hire_date="2025-09-01",
            employment_type="full_time",
            emergency_contact_name="Old Kin",
            emergency_contact_phone="+2348012345678",
            emergency_contact_relation="Sibling",
        )
        self.client.force_authenticate(user=teacher_user)
        response = self.client.patch(
            "/api/hr/me/",
            data={
                "gender": "M",
                "date_of_birth": "1989-02-03",
                "emergency_contact_name": "New Kin",
                "emergency_contact_phone": "+234800000003",
                "emergency_contact_relation": "Spouse",
                "cv": SimpleUploadedFile("teacher-cv.pdf", b"teacher cv", content_type="application/pdf"),
            },
            format="multipart",
        )
        self.assertEqual(response.status_code, 200)
        teacher.refresh_from_db()
        teacher_user.refresh_from_db()
        staff = StaffProfile.objects.get(user=teacher_user)
        self.assertEqual(teacher.emergency_contact_name, "New Kin")
        self.assertEqual(teacher.emergency_contact_relation, "Spouse")
        self.assertTrue(teacher.resume.name.endswith(".pdf"))
        self.assertEqual(staff.emergency_contact_relation, "Spouse")
        self.assertEqual(str(teacher_user.date_of_birth), "1989-02-03")

    def test_teacher_can_request_leave_and_auto_link_hr_profile(self):
        teacher_user = User.objects.create_user(
            email="teacher.self@school.edu",
            password="TeacherPass123",
            first_name="Tola",
            last_name="Ade",
            role="teacher",
            tenant=self.school,
            is_active=True,
            is_verified=True,
        )
        TeacherProfile.objects.create(
            user=teacher_user,
            employee_id="TCH900",
            qualification="B.Ed",
            specialization="Mathematics",
            years_of_experience=4,
            hire_date="2025-09-01",
            employment_type="full_time",
            emergency_contact_name="Next Kin",
            emergency_contact_phone="+2348012345678",
            emergency_contact_relation="Sibling",
        )
        self.client.force_authenticate(user=teacher_user)

        leave_response = self.client.post(
            "/api/hr/leave/create/",
            data={"leave_type": "Sick", "start_date": "2026-06-01", "end_date": "2026-06-02"},
            format="json",
        )
        self.assertEqual(leave_response.status_code, 201)
        staff = StaffProfile.objects.get(user=teacher_user)
        self.assertEqual(staff.staff_type, StaffProfile.TEACHING)
        self.assertEqual(staff.staff_code, "TCH900")

        advance_response = self.client.post(
            "/api/hr/advances/create/",
            data={"amount": "5000", "reason": "Medical"},
            format="json",
        )
        self.assertEqual(advance_response.status_code, 201)
        self.assertEqual(SalaryAdvanceRequest.objects.filter(staff=staff).count(), 1)
