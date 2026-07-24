from datetime import date, timedelta
from decimal import Decimal
from unittest.mock import patch

from django.core import mail, signing
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework.test import APIClient

from academic.models import (
    AttendanceRecord,
    Class,
    GradeScale,
    QuestionPrompt,
    QuestionResponse,
    ResultBatch,
    SchoolActivityCalendar,
    StudentClassPromotion,
    StudentSubjectScore,
    Subject,
    Term,
)
from core.models import Domain, SchoolGroup, SchoolTenant
from exams.models import Exam, ExamAttempt, ExamPin, Question, QuestionBank
from finance.models import ActivationCreditPool, ActivationCreditTransaction, PaymentReceiptLink, SmsMessageLog, StudentPaymentReference
from finance.services import (
    activate_kids_monitor_subscription,
    get_or_create_activation_credit_pool,
    get_or_create_student_activation_credit,
)
from hr.models import StaffProfile
from notifications.models import Announcement, InAppMessage, MessageGroup, Notification
from tenants.models import Tenant
from users.models import KidsMonitorSubscription, ParentProfile, StudentActivityTitle, StudentEnrollment, StudentProfile, SupportTicket, TeacherProfile, User
from users.app_views import ID_CARD_SIGNING_SALT, _class_broadsheet, _resolve_school_signature_url


class SchoolRegistrationCreditTests(TestCase):
    def setUp(self):
        # This class calls create-school many times across its methods, all
        # sharing the same per-IP 'auth' throttle scope (see
        # users.views.AuthRateThrottle) - clear it so one method's calls
        # don't push a later method over the limit.
        from django.core.cache import cache as django_cache
        django_cache.clear()
        self.client = APIClient()

    def test_create_school_receives_fifty_free_activation_credits(self):
        response = self.client.post(
            "/api/auth/create-school/",
            data={
                "school_name": "Credit Gift Academy",
                "school_code": "credit_gift_academy",
                "email": "admin@creditgift.test",
                "phone": "08012345678",
                "address": "12 School Road",
            },
            format="json",
        )

        self.assertEqual(response.status_code, 201)
        self.assertTrue(response.data["success"])
        self.assertEqual(response.data["school"]["free_credits"], 50)

        school = SchoolTenant.objects.get(schema_name=response.data["school"]["school_code"])
        pool = ActivationCreditPool.objects.get(tenant=school)
        self.assertEqual(pool.balance, 50)
        self.assertTrue(
            ActivationCreditTransaction.objects.filter(
                pool=pool,
                tx_type=ActivationCreditTransaction.ADJUSTMENT,
                credits=50,
                amount=0,
                metadata__bonus="school_registration",
            ).exists()
        )

    def test_create_school_with_non_k12_tier_is_never_mixed_up_with_k12(self):
        """Selecting Non-K12 at signup must persist as Non-K12 end-to-end — the
        tier drives pricing (activation_credit_price_for_tenant) and downstream
        gating (attendance, Child Monitor), so a mix-up here breaks everything."""
        response = self.client.post(
            "/api/auth/create-school/",
            data={
                "school_name": "Precision Vocational Institute",
                "school_code": "precision_vocational",
                "email": "admin@precisionvoc.test",
                "school_type": "non_k12",
            },
            format="json",
        )

        self.assertEqual(response.status_code, 201, response.data)
        self.assertEqual(response.data["school"]["school_type"], "non_k12")

        school = SchoolTenant.objects.get(schema_name=response.data["school"]["school_code"])
        self.assertEqual(school.school_type, SchoolTenant.NON_K12)

        pool = get_or_create_activation_credit_pool(school)
        self.assertEqual(pool.price_per_credit, Decimal("200.00"))

    def test_create_school_with_k12_tier_is_never_mixed_up_with_non_k12(self):
        response = self.client.post(
            "/api/auth/create-school/",
            data={
                "school_name": "Precision Primary School",
                "school_code": "precision_primary",
                "email": "admin@precisionprimary.test",
                "school_type": "k12",
            },
            format="json",
        )

        self.assertEqual(response.status_code, 201, response.data)
        self.assertEqual(response.data["school"]["school_type"], "k12")

        school = SchoolTenant.objects.get(schema_name=response.data["school"]["school_code"])
        self.assertEqual(school.school_type, SchoolTenant.K12)

        pool = get_or_create_activation_credit_pool(school)
        self.assertEqual(pool.price_per_credit, Decimal("500.00"))

    def test_create_school_omitting_tier_defaults_to_k12_not_non_k12(self):
        response = self.client.post(
            "/api/auth/create-school/",
            data={
                "school_name": "Default Tier Academy",
                "school_code": "default_tier_academy",
            },
            format="json",
        )

        self.assertEqual(response.status_code, 201, response.data)
        self.assertEqual(response.data["school"]["school_type"], "k12")
        school = SchoolTenant.objects.get(schema_name=response.data["school"]["school_code"])
        self.assertEqual(school.school_type, SchoolTenant.K12)

    def test_create_school_rejects_invalid_tier_instead_of_silently_defaulting(self):
        response = self.client.post(
            "/api/auth/create-school/",
            data={
                "school_name": "Bogus Tier Academy",
                "school_code": "bogus_tier_academy",
                "school_type": "high_school",
            },
            format="json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertFalse(response.data["success"])
        self.assertIn("school_type", response.data["errors"])
        self.assertFalse(SchoolTenant.objects.filter(schema_name="bogus_tier_academy").exists())

    def test_retrying_create_school_with_same_email_does_not_create_a_duplicate_school(self):
        """Regression: the sign-up wizard retries create-school if the
        follow-up /register/ call fails - this used to create a brand new
        SchoolTenant every retry."""
        first = self.client.post(
            "/api/auth/create-school/",
            data={"school_name": "Retry Academy", "email": "retry.parent@school.test", "address": "1 First Street"},
            format="json",
        )
        self.assertEqual(first.status_code, 201, first.data)
        first_code = first.data["school"]["school_code"]

        # Different body (not an exact duplicate) so this exercises the
        # view's own email-based dedup, not just the IdempotencyMiddleware
        # replaying an identical cached response.
        second = self.client.post(
            "/api/auth/create-school/",
            data={"school_name": "Retry Academy Retry", "email": "retry.parent@school.test", "address": "2 Second Street"},
            format="json",
        )
        self.assertEqual(second.status_code, 201, second.data)
        self.assertEqual(second.data["school"]["school_code"], first_code)
        self.assertEqual(SchoolTenant.objects.filter(email__iexact="retry.parent@school.test").count(), 1)

    def test_retry_does_not_grant_free_activation_credits_twice(self):
        self.client.post(
            "/api/auth/create-school/",
            data={"school_name": "Credit Retry Academy", "email": "credit.retry@school.test"},
            format="json",
        )
        self.client.post(
            "/api/auth/create-school/",
            data={"school_name": "Credit Retry Academy", "email": "credit.retry@school.test", "address": "Second try"},
            format="json",
        )
        school = SchoolTenant.objects.get(email__iexact="credit.retry@school.test")
        pool = ActivationCreditPool.objects.get(tenant=school)
        self.assertEqual(pool.balance, 50)

    def test_new_school_allowed_for_email_once_previous_signup_actually_completed(self):
        """A school with a real admin user already means that sign-up
        finished - a later create-school call for the same email (e.g. a
        proprietor genuinely registering a second school) must not be
        merged into the first one."""
        first = self.client.post(
            "/api/auth/create-school/",
            data={"school_name": "Completed Academy", "email": "completed.admin@school.test"},
            format="json",
        )
        self.assertEqual(first.status_code, 201, first.data)
        completed_school = SchoolTenant.objects.get(schema_name=first.data["school"]["school_code"])
        User.objects.create_user(
            email="completed.admin@school.test",
            password="AdminPass123",
            first_name="Completed",
            last_name="Admin",
            role="school_admin",
            tenant=completed_school,
            is_active=True,
            is_verified=True,
        )

        second = self.client.post(
            "/api/auth/create-school/",
            data={"school_name": "Second Genuine School", "email": "completed.admin@school.test"},
            format="json",
        )
        self.assertEqual(second.status_code, 201, second.data)
        self.assertNotEqual(second.data["school"]["school_code"], completed_school.schema_name)
        self.assertEqual(SchoolTenant.objects.filter(email__iexact="completed.admin@school.test").count(), 2)


class StudentEnrollmentTests(TestCase):
    def setUp(self):
        self.school = SchoolTenant.objects.create(
            name="Blue Ridge Academy",
            schema_name="blue_ridge",
            is_active=True,
        )
        self.legacy_tenant = Tenant.objects.create(
            name="Blue Ridge Academy Legacy",
            slug="blue_ridge",
        )

        self.admin_user = User.objects.create_user(
            email="admin@blueridge.edu",
            password="AdminPass123",
            first_name="Alice",
            last_name="Admin",
            role="school_admin",
            tenant=self.school,
            is_active=True,
        )

        self.student_user = User.objects.create_user(
            email="student@blueridge.edu",
            password="StudentPass123",
            first_name="Sam",
            last_name="Student",
            role="student",
            tenant=self.school,
            is_active=True,
        )

        self.student_profile = StudentProfile.objects.create(
            user=self.student_user,
            student_id="STU-BR-001",
            admission_number="ADM-BR-001",
            admission_date=timezone.now().date(),
            guardian_name="Jordan Student",
            guardian_phone="+15550001111",
            guardian_relation="Parent",
        )

        self.classroom = Class.objects.create(
            name="Grade 9",
            section="A",
            tenant=self.legacy_tenant,
        )

        start_date = timezone.now() + timedelta(days=1)
        self.exam = Exam.objects.create(
            title="Mathematics Midterm",
            class_group=self.classroom,
            teacher=self.admin_user,
            start_date=start_date,
            end_date=start_date + timedelta(hours=2),
            duration_minutes=120,
            tenant=self.legacy_tenant,
            is_published=True,
        )

    def test_apply_links_assigns_class_creates_exam_attempt_and_message(self):
        enrollment = StudentEnrollment.objects.create(
            school=self.school,
            student=self.student_profile,
            assigned_class=self.classroom,
            created_by=self.admin_user,
            welcome_subject="Welcome to Grade 9",
            welcome_message="You are now enrolled. Please check your timetable.",
        )
        enrollment.exams.add(self.exam)

        enrollment.apply_links()
        enrollment.refresh_from_db()
        self.student_profile.refresh_from_db()

        self.assertEqual(self.student_profile.current_class, self.classroom)

        attempt = ExamAttempt.objects.filter(exam=self.exam, student=self.student_user).first()
        self.assertIsNotNone(attempt)
        self.assertEqual(attempt.tenant, self.legacy_tenant)

        self.assertIsNotNone(enrollment.enrollment_message)
        message = enrollment.enrollment_message
        self.assertEqual(message.sender, self.admin_user)
        self.assertEqual(message.recipient, self.student_user)
        self.assertEqual(message.tenant, self.school)
        self.assertIn("enrolled", message.body.lower())

        # Running the linker twice should not duplicate exam attempts or messages.
        enrollment.apply_links()
        self.assertEqual(ExamAttempt.objects.filter(exam=self.exam, student=self.student_user).count(), 1)
        self.assertEqual(InAppMessage.objects.filter(recipient=self.student_user, subject="Welcome to Grade 9").count(), 1)

    def test_enrollment_rejects_class_from_different_school(self):
        SchoolTenant.objects.create(
            name="Red River High",
            schema_name="red_river",
            is_active=True,
        )
        other_legacy_tenant = Tenant.objects.create(
            name="Red River Legacy",
            slug="red_river",
        )
        foreign_class = Class.objects.create(
            name="Grade 10",
            section="B",
            tenant=other_legacy_tenant,
        )

        enrollment = StudentEnrollment(
            school=self.school,
            student=self.student_profile,
            assigned_class=foreign_class,
            created_by=self.admin_user,
        )

        with self.assertRaises(ValidationError):
            enrollment.full_clean()


class EnrollmentsAPITests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.school = SchoolTenant.objects.create(
            name="Smoke School",
            schema_name="smoke_20260306072129",
            is_active=True,
        )
        self.legacy_tenant = Tenant.objects.create(
            name="Smoke School Legacy",
            slug="smoke_20260306072129",
        )
        self.admin_user = User.objects.create_user(
            email="admin@smoke.edu",
            password="AdminPass123",
            first_name="Casey",
            last_name="Admin",
            role="school_admin",
            tenant=self.school,
            is_active=True,
            is_verified=True,
        )
        self.client.force_authenticate(user=self.admin_user)

        self.classroom = Class.objects.create(
            name="Grade 9",
            section="A",
            tenant=self.legacy_tenant,
        )
        now = timezone.now() + timedelta(days=1)
        self.exam = Exam.objects.create(
            title="Biology Test",
            class_group=self.classroom,
            teacher=self.admin_user,
            start_date=now,
            end_date=now + timedelta(hours=1),
            duration_minutes=60,
            tenant=self.legacy_tenant,
            is_published=True,
        )

    def test_create_enrollment_api_creates_student_and_links(self):
        response = self.client.post(
            "/api/app/enrollments/create/",
            data={
                "student_email": "newstudent@smoke.edu",
                "first_name": "Nia",
                "last_name": "Student",
                "guardian_name": "Dana Guardian",
                "guardian_phone": "+15550002222",
                "student_password": "StudentPass123",
                "confirm_student_password": "StudentPass123",
                "class_id": self.classroom.id,
                "exam_ids": [self.exam.id],
                "welcome_subject": "Welcome aboard",
                "welcome_message": "You have been enrolled.",
            },
            format="json",
        )
        self.assertEqual(response.status_code, 201)
        self.assertTrue(response.data["success"])

        student_profile = StudentProfile.objects.get(user__email="newstudent@smoke.edu")
        self.assertEqual(student_profile.current_class, self.classroom)
        self.assertTrue(student_profile.user.check_password("StudentPass123"))
        self.assertTrue(
            ExamAttempt.objects.filter(
                exam=self.exam,
                student=student_profile.user,
                tenant=self.legacy_tenant,
            ).exists()
        )
        self.assertTrue(
            InAppMessage.objects.filter(
                recipient=student_profile.user,
                sender=self.admin_user,
                tenant=self.school,
            ).exists()
        )

    def test_create_enrollment_api_accepts_student_profile_picture(self):
        photo = SimpleUploadedFile("student.jpg", b"student-photo-bytes", content_type="image/jpeg")
        response = self.client.post(
            "/api/app/enrollments/create/",
            data={
                "student_email": "photo.student@smoke.edu",
                "first_name": "Photo",
                "last_name": "Student",
                "guardian_name": "Photo Guardian",
                "guardian_phone": "+15550006666",
                "student_password": "StudentPass123",
                "confirm_student_password": "StudentPass123",
                "profile_picture": photo,
            },
            format="multipart",
        )

        self.assertEqual(response.status_code, 201)
        self.assertTrue(response.data["success"])
        student_profile = StudentProfile.objects.get(user__email="photo.student@smoke.edu")
        self.assertTrue(bool(student_profile.user.profile_picture))
        self.assertIn("profiles/", student_profile.user.profile_picture.name)
        self.assertTrue(student_profile.user.check_password("StudentPass123"))

    def test_create_enrollment_api_requires_password_for_new_student(self):
        response = self.client.post(
            "/api/app/enrollments/create/",
            data={
                "student_email": "nopassword@smoke.edu",
                "first_name": "No",
                "last_name": "Password",
                "guardian_name": "Guardian",
            },
            format="json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertFalse(response.data["success"])
        self.assertIn("student_password is required", response.data["message"])
        self.assertFalse(User.objects.filter(email="nopassword@smoke.edu").exists())

    def test_enrollments_snapshot_returns_summary_and_options(self):
        student_user = User.objects.create_user(
            email="existing@smoke.edu",
            password="StudentPass123",
            first_name="Existing",
            last_name="Learner",
            role="student",
            tenant=self.school,
            is_active=True,
            is_verified=True,
        )
        student_profile = StudentProfile.objects.create(
            user=student_user,
            student_id="STU-SMOKE-1",
            admission_number="ADM-SMOKE-1",
            admission_date=timezone.now().date(),
            guardian_name="Guardian One",
            guardian_phone="+15550003333",
            guardian_relation="Parent",
        )
        enrollment = StudentEnrollment.objects.create(
            school=self.school,
            student=student_profile,
            assigned_class=self.classroom,
            created_by=self.admin_user,
            welcome_message="Welcome",
        )
        enrollment.exams.add(self.exam)
        enrollment.apply_links()

        response = self.client.get("/api/app/enrollments/")
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.data["success"])
        self.assertGreaterEqual(response.data["summary"]["total_enrollments"], 1)
        self.assertGreaterEqual(len(response.data["options"]["classes"]), 1)
        self.assertGreaterEqual(len(response.data["options"]["exams"]), 1)

    def test_enrollment_full_clean_without_student_returns_field_error(self):
        enrollment = StudentEnrollment(
            school=self.school,
            created_by=self.admin_user,
        )

        with self.assertRaises(ValidationError) as exc:
            enrollment.full_clean()

        self.assertIn("student", exc.exception.message_dict)

    def test_dashboard_snapshot_includes_recent_registered_students(self):
        student_user = User.objects.create_user(
            email="recent@smoke.edu",
            password="StudentPass123",
            first_name="Recent",
            last_name="Learner",
            role="student",
            tenant=self.school,
            is_active=True,
            is_verified=True,
        )
        StudentProfile.objects.create(
            user=student_user,
            student_id="STU-SMOKE-RECENT",
            admission_number="ADM-SMOKE-RECENT",
            admission_date=timezone.now().date(),
            guardian_name="Guardian Recent",
            guardian_phone="+15550005555",
            guardian_relation="Parent",
        )

        response = self.client.get("/api/app/dashboard/")
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.data["success"])
        self.assertGreaterEqual(len(response.data["recent_students"]), 1)
        self.assertIn("profile_picture", response.data["recent_students"][0])

    def test_messages_snapshot_includes_recipient_directory(self):
        teacher_user = User.objects.create_user(
            email="teacher.msg@smoke.edu",
            password="TeacherPass123",
            first_name="Mia",
            last_name="Teacher",
            role="teacher",
            tenant=self.school,
            is_active=True,
            is_verified=True,
        )
        InAppMessage.objects.create(
            tenant=self.school,
            sender=teacher_user,
            recipient=self.admin_user,
            subject="Attendance follow-up",
            body="Could we confirm the updated attendance list?",
        )

        response = self.client.get("/api/app/messages/")
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.data["success"])
        self.assertIn("recipients", response.data)
        self.assertTrue(any(item["email"] == "teacher.msg@smoke.edu" for item in response.data["recipients"]))
        self.assertGreaterEqual(len(response.data["inbox"]), 1)
        first_message = response.data["inbox"][0]
        self.assertIn("from_email", first_message)
        self.assertIn("body", first_message)
        self.assertIn("attachments", first_message)

    def test_messages_snapshot_never_lists_parents_as_recipients(self):
        """In-app messaging is staff and students only - a newly created parent
        account must never show up as someone an admin (or anyone else) can
        message."""
        User.objects.create_user(
            email="parent.msg@smoke.edu",
            password="ParentPass123",
            first_name="Priya",
            last_name="Parent",
            role="parent",
            tenant=self.school,
            is_active=True,
            is_verified=True,
        )

        response = self.client.get("/api/app/messages/")
        self.assertEqual(response.status_code, 200)
        self.assertFalse(any(item["email"] == "parent.msg@smoke.edu" for item in response.data["recipients"]))

    def test_parent_gets_no_message_recipients_and_cannot_send(self):
        parent_user = User.objects.create_user(
            email="parent.sender@smoke.edu",
            password="ParentPass123",
            first_name="Priya",
            last_name="Parent",
            role="parent",
            tenant=self.school,
            is_active=True,
            is_verified=True,
        )
        self.client.force_authenticate(user=parent_user)

        response = self.client.get("/api/app/messages/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["recipients"], [])

        send_response = self.client.post(
            "/api/app/messages/send/",
            data={"recipient_email": self.admin_user.email, "body": "Hello"},
            format="json",
        )
        self.assertEqual(send_response.status_code, 403)

    def test_admin_cannot_message_a_parent_directly(self):
        """Even an admin's elevated messaging permission must not let them
        target a parent account - parents are outside the messaging system
        entirely, not just outside the default recipient list."""
        parent_user = User.objects.create_user(
            email="parent.target@smoke.edu",
            password="ParentPass123",
            first_name="Priya",
            last_name="Parent",
            role="parent",
            tenant=self.school,
            is_active=True,
            is_verified=True,
        )

        response = self.client.post(
            "/api/app/messages/send/",
            data={"recipient_email": parent_user.email, "body": "Hello parent"},
            format="json",
        )
        self.assertEqual(response.status_code, 403)
        self.assertFalse(InAppMessage.objects.filter(recipient=parent_user).exists())

    def test_messages_snapshot_hides_cross_tenant_rows_even_for_same_user(self):
        other_school = SchoolTenant.objects.create(name="Other School", schema_name="other_school", is_active=True)
        other_sender = User.objects.create_user(
            email="other.sender@smoke.edu",
            password="TeacherPass123",
            first_name="Other",
            last_name="Sender",
            role="teacher",
            tenant=other_school,
            is_active=True,
            is_verified=True,
        )
        InAppMessage.objects.bulk_create(
            [
                InAppMessage(
                    tenant=other_school,
                    sender=other_sender,
                    recipient=self.admin_user,
                    subject="Wrong tenant message",
                    body="This should not appear.",
                )
            ]
        )
        Notification.objects.bulk_create(
            [
                Notification(
                    tenant=other_school,
                    user=self.admin_user,
                    title="Wrong tenant notification",
                    message="This should not appear.",
                    notification_type="info",
                    priority=2,
                    channel="in_app",
                    is_delivered=True,
                    delivered_at=timezone.now(),
                )
            ]
        )

        response = self.client.get("/api/app/messages/")

        self.assertEqual(response.status_code, 200)
        self.assertFalse(any(item["subject"] == "Wrong tenant message" for item in response.data["inbox"]))
        self.assertFalse(any(item["title"] == "Wrong tenant notification" for item in response.data["notifications"]))
        self.assertEqual(response.data["summary"]["unread_inbox"], 0)
        self.assertEqual(response.data["summary"]["unread_notifications"], 0)

    def test_cross_tenant_notification_and_message_writes_are_rejected(self):
        other_school = SchoolTenant.objects.create(name="Other Guard School", schema_name="other_guard", is_active=True)
        other_user = User.objects.create_user(
            email="other.guard@smoke.edu",
            password="TeacherPass123",
            role="teacher",
            tenant=other_school,
            is_active=True,
            is_verified=True,
        )

        with self.assertRaises(ValidationError):
            Notification.objects.create(
                tenant=other_school,
                user=self.admin_user,
                title="Wrong tenant notification",
                message="Blocked",
                notification_type="info",
                priority=2,
                channel="in_app",
            )

        with self.assertRaises(ValidationError):
            InAppMessage.objects.create(
                tenant=self.school,
                sender=self.admin_user,
                recipient=other_user,
                subject="Wrong tenant message",
                body="Blocked",
            )

    def test_message_send_accepts_attachments(self):
        teacher_user = User.objects.create_user(
            email="teacher.attachment@smoke.edu",
            password="TeacherPass123",
            first_name="File",
            last_name="Teacher",
            role="teacher",
            tenant=self.school,
            is_active=True,
            is_verified=True,
        )
        upload = SimpleUploadedFile("notice.txt", b"Bring your notebook.", content_type="text/plain")

        response = self.client.post(
            "/api/app/messages/send/",
            data={
                "recipient_email": teacher_user.email,
                "subject": "Attached note",
                "body": "Please check the file.",
                "attachments": [upload],
            },
            format="multipart",
        )

        self.assertEqual(response.status_code, 201)
        self.assertTrue(response.data["success"])
        message = InAppMessage.objects.get(recipient=teacher_user)
        self.assertEqual(len(message.attachments), 1)
        self.assertEqual(message.attachments[0]["name"], "notice.txt")

        self.client.force_authenticate(user=teacher_user)
        inbox_response = self.client.get("/api/app/messages/")
        self.assertEqual(inbox_response.status_code, 200)
        self.assertEqual(inbox_response.data["inbox"][0]["attachments"][0]["name"], "notice.txt")

    def test_messages_snapshot_includes_guardian_sms_contacts_for_admins(self):
        student_user = User.objects.create_user(
            email="guardian.snapshot@smoke.edu",
            password="StudentPass123",
            first_name="Guardian",
            last_name="Snapshot",
            role="student",
            tenant=self.school,
            is_active=True,
            is_verified=True,
        )
        StudentProfile.objects.create(
            user=student_user,
            student_id="STU-SMOKE-SMS",
            admission_number="ADM-SMOKE-SMS",
            admission_date=timezone.now().date(),
            guardian_name="First Guardian",
            guardian_phone="09036425748",
            guardian_relation="Parent",
            second_guardian_name="Second Guardian",
            second_guardian_phone="+2348153197053",
            second_guardian_relation="Mother",
        )

        response = self.client.get("/api/app/messages/")

        self.assertEqual(response.status_code, 200)
        phones = {item["phone"] for item in response.data["guardian_sms_recipients"]}
        self.assertIn("2349036425748", phones)
        self.assertIn("2348153197053", phones)

    @override_settings(KUDISMS_TOKEN="test-token", KUDISMS_SENDER_ID="neo", KUDISMS_GATEWAY="2")
    @patch("users.app_views.requests.get")
    def test_admin_can_send_guardian_bulk_sms(self, mock_get):
        mock_get.return_value.status_code = 200
        mock_get.return_value.text = "OK"

        response = self.client.post(
            "/api/app/messages/send/",
            data={
                "target": "guardian_sms",
                "body": "School closes by 2 PM today.",
                "recipients": ["09036425748", "+2348153197053", "09036425748"],
            },
            format="json",
        )

        self.assertEqual(response.status_code, 201)
        self.assertTrue(response.data["success"])
        self.assertEqual(response.data["sms_data"]["recipient_count"], 2)
        _, kwargs = mock_get.call_args
        self.assertEqual(kwargs["params"]["token"], "test-token")
        self.assertEqual(kwargs["params"]["senderID"], "neo")
        self.assertEqual(kwargs["params"]["recipients"], "2349036425748,2348153197053")
        self.assertEqual(kwargs["params"]["gateway"], "2")

    def test_admin_can_publish_announcement_for_students_and_teachers(self):
        student_user = User.objects.create_user(
            email="student.msg@smoke.edu",
            password="StudentPass123",
            first_name="Stu",
            last_name="Dent",
            role="student",
            tenant=self.school,
            is_active=True,
            is_verified=True,
        )
        teacher_user = User.objects.create_user(
            email="teacher.broadcast@smoke.edu",
            password="TeacherPass123",
            first_name="Teach",
            last_name="Er",
            role="teacher",
            tenant=self.school,
            is_active=True,
            is_verified=True,
        )

        response = self.client.post(
            "/api/app/messages/send/",
            data={
                "target": "students_teachers_announcement",
                "subject": "Schedule update",
                "body": "Classes start at 9 AM tomorrow.",
            },
            format="json",
        )

        self.assertEqual(response.status_code, 201)
        self.assertTrue(response.data["success"])
        self.assertIn("Announcement published", response.data["message"])
        self.assertEqual(InAppMessage.objects.count(), 0)

        announcement = Announcement.objects.filter(tenant=self.school, title="Schedule update").first()
        self.assertIsNotNone(announcement)
        self.assertEqual(announcement.audience_type, "role")
        self.assertCountEqual(announcement.target_roles, ["student", "teacher", "staff"])
        self.assertEqual(announcement.author, self.admin_user)

        self.client.force_authenticate(user=student_user)
        student_feed = self.client.get("/api/app/messages/")
        self.assertEqual(student_feed.status_code, 200)
        self.assertTrue(any(item["title"] == "Schedule update" for item in student_feed.data["announcements"]))

        self.client.force_authenticate(user=teacher_user)
        teacher_feed = self.client.get("/api/app/messages/")
        self.assertEqual(teacher_feed.status_code, 200)
        self.assertTrue(any(item["title"] == "Schedule update" for item in teacher_feed.data["announcements"]))

    def test_non_admin_cannot_publish_students_teachers_announcement(self):
        teacher_user = User.objects.create_user(
            email="teacher.only@smoke.edu",
            password="TeacherPass123",
            first_name="Nina",
            last_name="Teach",
            role="teacher",
            tenant=self.school,
            is_active=True,
            is_verified=True,
        )
        self.client.force_authenticate(user=teacher_user)

        response = self.client.post(
            "/api/app/messages/send/",
            data={
                "target": "students_teachers_announcement",
                "subject": "Unauthorized",
                "body": "This should be blocked.",
            },
            format="json",
        )

        self.assertEqual(response.status_code, 403)
        self.assertFalse(response.data["success"])
        self.assertEqual(Announcement.objects.filter(tenant=self.school, title="Unauthorized").count(), 0)


class StudentDashboardAPITests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.school = SchoolTenant.objects.create(
            name="Student Dashboard School",
            schema_name="student_dashboard_20260306",
            is_active=True,
        )
        self.legacy_tenant = Tenant.objects.create(
            name="Student Dashboard Legacy",
            slug="student_dashboard_20260306",
        )
        self.classroom = Class.objects.create(
            name="Grade 10",
            section="C",
            tenant=self.legacy_tenant,
        )
        self.subject = Subject.objects.create(
            name="Mathematics",
            code="MATH",
            tenant=self.legacy_tenant,
        )
        self.admin_user = User.objects.create_user(
            email="admin@student-dashboard.edu",
            password="AdminPass123",
            first_name="Dashboard",
            last_name="Admin",
            role="school_admin",
            tenant=self.school,
            is_active=True,
            is_verified=True,
        )
        self.student_user = User.objects.create_user(
            email="student@student-dashboard.edu",
            password="StudentPass123",
            first_name="Dash",
            last_name="Student",
            role="student",
            tenant=self.school,
            is_active=True,
            is_verified=True,
        )
        StudentProfile.objects.create(
            user=self.student_user,
            student_id="STU-DASH-1",
            admission_number="ADM-DASH-1",
            admission_date=timezone.now().date(),
            guardian_name="Guardian Dash",
            guardian_phone="+15550001234",
            guardian_relation="Parent",
            current_class=self.classroom,
        )
        start = timezone.now() + timedelta(days=1)
        self.exam = Exam.objects.create(
            title="Student Dashboard Exam",
            subject=self.subject,
            class_group=self.classroom,
            teacher=self.admin_user,
            start_date=start,
            end_date=start + timedelta(hours=1),
            duration_minutes=60,
            tenant=self.legacy_tenant,
            is_published=True,
        )
        ExamAttempt.objects.create(
            exam=self.exam,
            student=self.student_user,
            tenant=self.legacy_tenant,
            is_submitted=False,
            is_completed=False,
        )
        past_start = timezone.now() - timedelta(days=5)
        self.completed_exam = Exam.objects.create(
            title="Completed Dashboard Exam",
            subject=self.subject,
            class_group=self.classroom,
            teacher=self.admin_user,
            start_date=past_start,
            end_date=past_start + timedelta(hours=1),
            duration_minutes=60,
            tenant=self.legacy_tenant,
            is_published=True,
        )
        ExamAttempt.objects.create(
            exam=self.completed_exam,
            student=self.student_user,
            tenant=self.legacy_tenant,
            is_submitted=True,
            is_completed=True,
            end_time=timezone.now() - timedelta(days=4),
        )
        InAppMessage.objects.create(
            tenant=self.school,
            sender=self.admin_user,
            recipient=self.student_user,
            subject="Welcome",
            body="Dashboard message",
        )

    def test_student_dashboard_returns_student_payload(self):
        self.client.force_authenticate(user=self.student_user)
        response = self.client.get("/api/app/student/dashboard/")

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.data["success"])
        self.assertEqual(response.data["student"]["email"], "student@student-dashboard.edu")
        self.assertGreaterEqual(response.data["metrics"]["upcoming_exams"], 1)
        self.assertGreaterEqual(len(response.data["upcoming_exams"]), 1)
        self.assertGreaterEqual(len(response.data["inbox"]), 1)
        self.assertGreaterEqual(len(response.data["recent_results"]), 1)
        self.assertGreaterEqual(response.data["metrics"]["available_results"], 1)
        self.assertEqual(response.data["metrics"]["subjects_offered"], 1)
        self.assertEqual(response.data["subjects"][0]["name"], "Mathematics")
        self.assertTrue(any(item["email"] == "admin@student-dashboard.edu" for item in response.data["admin_contacts"]))
        self.assertIn("from_email", response.data["inbox"][0])
        self.assertIn("body", response.data["inbox"][0])

    def test_non_student_cannot_access_student_dashboard(self):
        self.client.force_authenticate(user=self.admin_user)
        response = self.client.get("/api/app/student/dashboard/")

        self.assertEqual(response.status_code, 403)
        self.assertFalse(response.data["success"])

    def test_student_can_reply_to_school_admin(self):
        self.client.force_authenticate(user=self.student_user)
        response = self.client.post(
            "/api/app/messages/send/",
            data={
                "recipient_email": "admin@student-dashboard.edu",
                "subject": "Re: Welcome",
                "body": "Thanks admin, I have a follow up question.",
            },
            format="json",
        )

        self.assertEqual(response.status_code, 201)
        self.assertTrue(response.data["success"])
        self.assertTrue(
            InAppMessage.objects.filter(
                sender=self.student_user,
                recipient=self.admin_user,
                subject__iexact="Re: Welcome",
            ).exists()
        )

    def test_student_can_message_teacher(self):
        teacher_user = User.objects.create_user(
            email="teacher.student-message@student-dashboard.edu",
            password="TeacherPass123",
            first_name="Message",
            last_name="Teacher",
            role="teacher",
            tenant=self.school,
            is_active=True,
            is_verified=True,
        )

        self.client.force_authenticate(user=self.student_user)
        response = self.client.post(
            "/api/app/messages/send/",
            data={
                "recipient_email": teacher_user.email,
                "subject": "Question",
                "body": "Please I need help with the assignment.",
            },
            format="json",
        )

        self.assertEqual(response.status_code, 201)
        self.assertTrue(response.data["success"])
        self.assertTrue(
            InAppMessage.objects.filter(
                sender=self.student_user,
                recipient=teacher_user,
                subject="Question",
            ).exists()
        )


class TeacherDashboardAPITests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.school = SchoolTenant.objects.create(
            name="Teacher Dashboard School",
            schema_name="teacher_dashboard_20260307",
            is_active=True,
        )
        self.legacy_tenant = Tenant.objects.create(
            name="Teacher Dashboard Legacy",
            slug="teacher_dashboard_20260307",
        )
        self.classroom = Class.objects.create(
            name="Grade 8",
            section="B",
            tenant=self.legacy_tenant,
        )
        self.subject = Subject.objects.create(
            tenant=self.legacy_tenant,
            name="Mathematics",
            code="MATH-8",
        )
        self.teacher_user = User.objects.create_user(
            email="teacher@teacher-dashboard.edu",
            password="TeacherPass123",
            first_name="Taylor",
            last_name="Teacher",
            role="teacher",
            tenant=self.school,
            is_active=True,
            is_verified=True,
        )
        self.admin_user = User.objects.create_user(
            email="admin@teacher-dashboard.edu",
            password="AdminPass123",
            first_name="Alex",
            last_name="Admin",
            role="school_admin",
            tenant=self.school,
            is_active=True,
            is_verified=True,
        )
        teacher_profile = TeacherProfile.objects.create(
            user=self.teacher_user,
            employee_id="TCH-DASH-1",
            qualification="B.Ed",
            specialization="Mathematics",
            years_of_experience=6,
            hire_date=timezone.now().date(),
            employment_type="full_time",
            emergency_contact_name="Guardian Contact",
            emergency_contact_phone="+15554443333",
            emergency_contact_relation="Sibling",
        )
        teacher_profile.assigned_classes.add(self.classroom)
        teacher_profile.subjects.add(self.subject)
        start = timezone.now() + timedelta(days=2)
        Exam.objects.create(
            title="Teacher Dashboard Midterm",
            subject=self.subject,
            class_group=self.classroom,
            teacher=self.teacher_user,
            start_date=start,
            end_date=start + timedelta(hours=2),
            duration_minutes=120,
            tenant=self.legacy_tenant,
            is_published=True,
        )

    def test_teacher_dashboard_returns_profile_subjects_and_options(self):
        self.client.force_authenticate(user=self.teacher_user)
        response = self.client.get("/api/app/teacher/dashboard/")

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.data["success"])
        self.assertEqual(response.data["profile"]["email"], "teacher@teacher-dashboard.edu")
        self.assertIn("Mathematics", response.data["profile"]["subjects_taught"])
        self.assertGreaterEqual(response.data["metrics"]["total_assessments"], 1)
        self.assertGreaterEqual(len(response.data["upcoming_assessments"]), 1)
        self.assertTrue(any(item["id"] == self.classroom.id for item in response.data["options"]["classes"]))
        self.assertTrue(any(item["id"] == self.subject.id for item in response.data["options"]["subjects"]))

    def test_non_teacher_cannot_access_teacher_dashboard(self):
        self.client.force_authenticate(user=self.admin_user)
        response = self.client.get("/api/app/teacher/dashboard/")

        self.assertEqual(response.status_code, 403)
        self.assertFalse(response.data["success"])

    def test_teacher_can_message_students_in_assigned_class(self):
        student_user = User.objects.create_user(
            email="student.class-message@teacher-dashboard.edu",
            password="StudentPass123",
            first_name="Class",
            last_name="Student",
            role="student",
            tenant=self.school,
            is_active=True,
            is_verified=True,
        )
        StudentProfile.objects.create(
            user=student_user,
            student_id="STD-MSG-1",
            admission_number="ADM-MSG-1",
            admission_date=timezone.now().date(),
            current_class=self.classroom,
            guardian_name="Parent",
            guardian_phone="+15550001111",
            guardian_relation="Parent",
        )

        self.client.force_authenticate(user=self.teacher_user)
        response = self.client.post(
            "/api/app/messages/send/",
            data={
                "target": "class",
                "class_id": self.classroom.id,
                "subject": "Class update",
                "body": "Bring your workbook tomorrow.",
            },
            format="json",
        )

        self.assertEqual(response.status_code, 201)
        self.assertTrue(response.data["success"])
        self.assertEqual(response.data["message_data"]["recipient_count"], 1)
        self.assertTrue(
            InAppMessage.objects.filter(
                sender=self.teacher_user,
                recipient=student_user,
                subject="Class update",
                body="Bring your workbook tomorrow.",
            ).exists()
        )

    def test_teacher_can_message_admin_and_assigned_student_directly(self):
        student_user = User.objects.create_user(
            email="direct.student@teacher-dashboard.edu",
            password="StudentPass123",
            first_name="Direct",
            last_name="Student",
            role="student",
            tenant=self.school,
            is_active=True,
            is_verified=True,
        )
        StudentProfile.objects.create(
            user=student_user,
            student_id="STD-DIRECT-1",
            admission_number="ADM-DIRECT-1",
            admission_date=timezone.now().date(),
            current_class=self.classroom,
            guardian_name="Parent",
            guardian_phone="+15550002222",
            guardian_relation="Parent",
        )

        self.client.force_authenticate(user=self.teacher_user)
        admin_response = self.client.post(
            "/api/app/messages/send/",
            data={
                "recipient_email": self.admin_user.email,
                "subject": "Admin note",
                "body": "Please review this request.",
            },
            format="json",
        )
        student_response = self.client.post(
            "/api/app/messages/send/",
            data={
                "recipient_email": student_user.email,
                "subject": "Student note",
                "body": "Please submit your classwork.",
            },
            format="json",
        )

        self.assertEqual(admin_response.status_code, 201)
        self.assertEqual(student_response.status_code, 201)
        self.assertTrue(InAppMessage.objects.filter(sender=self.teacher_user, recipient=self.admin_user).exists())
        self.assertTrue(InAppMessage.objects.filter(sender=self.teacher_user, recipient=student_user).exists())

    def test_teacher_can_create_test_for_all_classes(self):
        self.client.force_authenticate(user=self.teacher_user)
        start = timezone.now() + timedelta(days=4)
        end = start + timedelta(hours=2)

        response = self.client.post(
            "/api/app/exams/create/",
            data={
                "title": "Weekly Quiz",
                "assessment_type": "test",
                "subject_id": self.subject.id,
                "start_date": start.isoformat(),
                "end_date": end.isoformat(),
                "duration_minutes": 45,
                "is_published": True,
                "questions": [
                    {
                        "text": "What is 2 + 2?",
                        "options": ["3", "4", "5", "6"],
                        "correct_answer": "4",
                        "points": 1,
                    }
                ],
            },
            format="json",
        )

        self.assertEqual(response.status_code, 201)
        self.assertTrue(response.data["success"])
        self.assertEqual(response.data["exam"]["assessment_type"], "test")
        self.assertEqual(response.data["exam"]["class_name"], "All classes")

        created = Exam.objects.get(id=response.data["exam"]["id"])
        self.assertIsNone(created.class_group)
        self.assertIsNotNone(created.exam_type)
        self.assertEqual(created.exam_type.name.lower(), "test")
        self.assertEqual(created.duration_minutes, 45)

        exams_response = self.client.get("/api/app/exams/")
        self.assertEqual(exams_response.status_code, 200)
        self.assertTrue(exams_response.data["success"])
        self.assertGreaterEqual(exams_response.data["summary"]["tests_count"], 1)
        self.assertIn("assessment_type", exams_response.data["exams"][0])

    def test_only_admin_can_generate_cbt_pin_and_pin_is_numeric(self):
        exam = Exam.objects.filter(teacher=self.teacher_user).first()

        self.client.force_authenticate(user=self.teacher_user)
        teacher_response = self.client.post(
            "/api/app/exams/pins/",
            data={"exam_id": exam.id, "length": 12},
            format="json",
        )
        self.assertEqual(teacher_response.status_code, 403)

        self.client.force_authenticate(user=self.admin_user)
        admin_response = self.client.post(
            "/api/app/exams/pins/",
            data={"exam_id": exam.id, "length": 12},
            format="json",
        )

        self.assertEqual(admin_response.status_code, 201)
        self.assertTrue(admin_response.data["success"])
        plain_pin = admin_response.data["plain_pin"]
        self.assertRegex(plain_pin, r"^\d{6}$")

    def test_teacher_exam_list_does_not_expose_pin_status(self):
        exam = Exam.objects.filter(teacher=self.teacher_user).first()
        plain_pin = ExamPin.generate_plain_pin()
        pin = ExamPin(
            tenant=exam.tenant,
            exam=exam,
            usage_policy=ExamPin.USE_REUSABLE,
            created_by=self.admin_user,
        )
        pin.set_pin(plain_pin)
        pin.save()

        self.client.force_authenticate(user=self.teacher_user)
        teacher_response = self.client.get("/api/app/exams/")
        self.assertEqual(teacher_response.status_code, 200)
        teacher_exam = next(item for item in teacher_response.data["exams"] if item["id"] == exam.id)
        self.assertFalse(teacher_exam["pin_required"])
        self.assertEqual(teacher_exam["active_pin_count"], 0)

        self.client.force_authenticate(user=self.admin_user)
        admin_response = self.client.get("/api/app/exams/")
        self.assertEqual(admin_response.status_code, 200)
        admin_exam = next(item for item in admin_response.data["exams"] if item["id"] == exam.id)
        self.assertTrue(admin_exam["pin_required"])
        self.assertEqual(admin_exam["active_pin_count"], 1)

    def test_teacher_cbt_bank_only_includes_assigned_subjects(self):
        chemistry = Subject.objects.create(
            tenant=self.legacy_tenant,
            name="Chemistry",
            code="CHEM",
        )
        math_question = Question.objects.create(
            tenant=self.legacy_tenant,
            question_type="mcq",
            text="Mathematics bank question?",
            options=["A", "B"],
            correct_answer="A",
            points=1,
        )
        chemistry_question = Question.objects.create(
            tenant=self.legacy_tenant,
            question_type="mcq",
            text="Chemistry quiz bank question?",
            options=["Atom", "Cell"],
            correct_answer="Atom",
            points=1,
        )
        math_bank = QuestionBank.objects.create(
            tenant=self.legacy_tenant,
            name="Shared Mathematics Bank",
            subject=self.subject,
            teacher=self.admin_user,
            is_shared=True,
        )
        chemistry_bank = QuestionBank.objects.create(
            tenant=self.legacy_tenant,
            name="Shared Chemistry Quiz Bank",
            subject=chemistry,
            teacher=self.admin_user,
            is_shared=True,
        )
        math_bank.questions.add(math_question)
        chemistry_bank.questions.add(chemistry_question)

        self.client.force_authenticate(user=self.teacher_user)
        response = self.client.get("/api/app/exams/question-bank/")

        self.assertEqual(response.status_code, 200)
        question_texts = [item["text"] for item in response.data["questions"]]
        self.assertIn("Mathematics bank question?", question_texts)
        self.assertNotIn("Chemistry quiz bank question?", question_texts)

    def test_admin_cbt_bank_hides_chemistry_subject_pool(self):
        chemistry = Subject.objects.create(
            tenant=self.legacy_tenant,
            name="Chemistry",
            code="CHEM",
        )
        chemistry_question = Question.objects.create(
            tenant=self.legacy_tenant,
            question_type="mcq",
            text="Chemistry personal quiz pool question?",
            options=["Atom", "Cell"],
            correct_answer="Atom",
            points=1,
        )
        chemistry_bank = QuestionBank.objects.create(
            tenant=self.legacy_tenant,
            name="Chemistry Quiz Question Bank",
            subject=chemistry,
            teacher=self.teacher_user,
            is_shared=True,
        )
        chemistry_bank.questions.add(chemistry_question)

        self.client.force_authenticate(user=self.admin_user)
        response = self.client.get("/api/app/exams/question-bank/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["questions"], [])
        self.assertEqual(response.data["banks"], [])

    def test_teacher_can_view_and_edit_own_exam_questions(self):
        self.client.force_authenticate(user=self.teacher_user)
        start = timezone.now() - timedelta(days=3)
        exam = Exam.objects.create(
            title="Past Algebra Exam",
            subject=self.subject,
            class_group=self.classroom,
            teacher=self.teacher_user,
            start_date=start,
            end_date=start + timedelta(hours=1),
            duration_minutes=60,
            tenant=self.legacy_tenant,
            is_published=False,
        )
        question = Question.objects.create(
            tenant=self.legacy_tenant,
            question_type="mcq",
            text="Original question?",
            options=["A", "B"],
            correct_answer="A",
            points=1,
        )
        exam.questions.add(question)

        detail_response = self.client.get(f"/api/app/exams/{exam.id}/")
        self.assertEqual(detail_response.status_code, 200)
        self.assertTrue(detail_response.data["success"])
        self.assertEqual(detail_response.data["exam"]["id"], exam.id)
        self.assertEqual(len(detail_response.data["exam"]["questions"]), 1)

        publish_response = self.client.patch(
            f"/api/app/exams/{exam.id}/",
            data={
                "title": "Edited Algebra Exam",
                "is_published": True,
                "questions": [
                    {
                        "text": "Edited question?",
                        "options": ["True", "False"],
                        "correct_answer": "True",
                        "points": 2,
                    }
                ],
            },
            format="json",
        )
        self.assertEqual(publish_response.status_code, 403)

        patch_response = self.client.patch(
            f"/api/app/exams/{exam.id}/",
            data={
                "title": "Edited Algebra Exam",
                "start_date": start.isoformat(),
                "end_date": (start + timedelta(hours=3)).isoformat(),
                "duration_minutes": 45,
                "questions": [
                    {
                        "text": "Edited question?",
                        "options": ["True", "False"],
                        "correct_answer": "True",
                        "points": 2,
                    }
                ],
            },
            format="json",
        )

        self.assertEqual(patch_response.status_code, 200)
        self.assertTrue(patch_response.data["success"])
        exam.refresh_from_db()
        self.assertEqual(exam.title, "Edited Algebra Exam")
        self.assertFalse(exam.is_published)
        self.assertEqual(exam.questions.count(), 1)
        self.assertEqual(exam.questions.first().text, "Edited question?")
        self.assertEqual(exam.duration_minutes, 45)

    def test_teacher_can_set_grade_scale_and_push_regraded_results(self):
        self.client.force_authenticate(user=self.teacher_user)
        student_user = User.objects.create_user(
            email="grade.student@teacher-dashboard.edu",
            password="StudentPass123",
            first_name="Grade",
            last_name="Student",
            role="student",
            tenant=self.school,
            is_active=True,
            is_verified=True,
        )
        student = StudentProfile.objects.create(
            user=student_user,
            student_id="STU-GRADE-1",
            admission_number="ADM-GRADE-1",
            admission_date=timezone.now().date(),
            current_class=self.classroom,
            guardian_name="Guardian",
            guardian_phone="+15550001111",
            guardian_relation="Parent",
        )
        TeacherProfile.objects.filter(user=self.teacher_user).first().subjects.add(self.subject)

        grade_response = self.client.post(
            "/api/app/results/grades/",
            data={"letter": "A", "min_percentage": "80", "max_percentage": "100", "remark": "Distinction"},
            format="json",
        )
        self.assertEqual(grade_response.status_code, 200)
        self.client.post(
            "/api/app/results/grades/",
            data={"letter": "B", "min_percentage": "70", "max_percentage": "79.99", "remark": "Very good"},
            format="json",
        )
        self.assertTrue(GradeScale.objects.filter(tenant=self.legacy_tenant, letter="A", min_percentage=80).exists())

        score_response = self.client.post(
            "/api/app/results/submit/",
            data={
                "student_id": student.student_id,
                "subject_id": self.subject.id,
                "class_id": self.classroom.id,
                "score": 75,
                "max_score": 100,
            },
            format="json",
        )
        self.assertEqual(score_response.status_code, 201)
        score = StudentSubjectScore.objects.get(student=student, subject=self.subject)
        self.assertEqual(score.grade, "B")

        self.client.post(
            "/api/app/results/grades/",
            data={"letter": "A", "min_percentage": "70", "max_percentage": "100", "remark": "Excellent"},
            format="json",
        )
        push_response = self.client.post(
            "/api/app/results/push/",
            data={"class_id": self.classroom.id, "title": "Teacher compiled results"},
            format="json",
        )
        self.assertEqual(push_response.status_code, 200)
        score.refresh_from_db()
        self.assertEqual(score.grade, "A")
        self.assertEqual(score.approval_status, ResultBatch.PENDING)

    def test_teacher_can_submit_score_for_subject_student_outside_assigned_class(self):
        other_class = Class.objects.create(
            name="Grade 9",
            section="A",
            tenant=self.legacy_tenant,
        )
        student_user = User.objects.create_user(
            email="subject.student@teacher-dashboard.edu",
            password="StudentPass123",
            first_name="Subject",
            last_name="Student",
            role="student",
            tenant=self.school,
            is_active=True,
            is_verified=True,
        )
        student = StudentProfile.objects.create(
            user=student_user,
            student_id="STU-SUBJECT-1",
            admission_number="ADM-SUBJECT-1",
            admission_date=timezone.now().date(),
            current_class=other_class,
            guardian_name="Guardian",
            guardian_phone="+15550001111",
            guardian_relation="Parent",
        )

        self.client.force_authenticate(user=self.teacher_user)
        response = self.client.post(
            "/api/app/results/submit/",
            data={
                "student_id": student.student_id,
                "subject_id": self.subject.id,
                "class_id": other_class.id,
                "score": 68,
                "max_score": 100,
            },
            format="json",
        )

        self.assertEqual(response.status_code, 201)
        self.assertTrue(response.data["success"])
        score = StudentSubjectScore.objects.get(student=student, subject=self.subject)
        self.assertEqual(score.class_group, other_class)
        self.assertEqual(score.teacher, self.teacher_user)

    def test_admin_can_delete_result_batch_and_scores(self):
        self.client.force_authenticate(user=self.teacher_user)
        student_user = User.objects.create_user(
            email="delete.batch.student@teacher-dashboard.edu",
            password="StudentPass123",
            first_name="Delete",
            last_name="Batch",
            role="student",
            tenant=self.school,
            is_active=True,
            is_verified=True,
        )
        student = StudentProfile.objects.create(
            user=student_user,
            student_id="STU-DEL-1",
            admission_number="ADM-DEL-1",
            admission_date=timezone.now().date(),
            current_class=self.classroom,
            guardian_name="Guardian",
            guardian_phone="+15550001111",
            guardian_relation="Parent",
        )
        score_response = self.client.post(
            "/api/app/results/submit/",
            data={
                "student_id": student.student_id,
                "subject_id": self.subject.id,
                "class_id": self.classroom.id,
                "score": 82,
                "max_score": 100,
            },
            format="json",
        )
        self.assertEqual(score_response.status_code, 201)
        push_response = self.client.post(
            "/api/app/results/push/",
            data={"class_id": self.classroom.id, "title": "Delete me"},
            format="json",
        )
        self.assertEqual(push_response.status_code, 200)
        batch_id = push_response.data["batch_id"]

        self.client.force_authenticate(user=self.admin_user)
        delete_response = self.client.delete(f"/api/app/results/batches/{batch_id}/")
        self.assertEqual(delete_response.status_code, 200)
        self.assertFalse(ResultBatch.objects.filter(id=batch_id).exists())
        self.assertFalse(StudentSubjectScore.objects.filter(student=student, subject=self.subject).exists())


class DocumentSignatureResolutionTests(TestCase):
    """The signature shown on report cards/transcripts/testimonials/ID cards
    must resolve to whichever admin actually uploaded one - even when other
    users in the tenant have director_signature stored as NULL rather than
    an empty string (exactly what AddField backfills existing rows to), and
    even when that admin isn't the first user row in the tenant."""

    def test_resolves_admin_signature_even_when_later_user_has_null_signature(self):
        school = SchoolTenant.objects.create(
            name="Signature School", schema_name="signature_school_test", is_active=True,
        )

        # User.Meta.ordering is ["-created_at"] (most recent first), so the
        # admin must be created FIRST here to prove the query doesn't just
        # get lucky from default ordering - the decoy (created after, with
        # director_signature forced to NULL rather than "" to match what a
        # migration's AddField backfill actually produces for existing rows)
        # would otherwise sort ahead of the real signer.
        admin_user = User.objects.create_user(
            email="admin@signature.edu", password="AdminPass123", role="school_admin",
            tenant=school, is_active=True, is_verified=True,
        )
        admin_user.director_signature = SimpleUploadedFile("sig.png", b"fake-image-bytes", content_type="image/png")
        admin_user.save(update_fields=["director_signature"])

        decoy_student = User.objects.create_user(
            email="decoy@signature.edu", password="StudentPass123", role="student",
            tenant=school, is_active=True, is_verified=True,
        )
        User.objects.filter(pk=decoy_student.pk).update(director_signature=None)

        resolved_url = _resolve_school_signature_url(school)
        self.assertTrue(resolved_url)
        self.assertIn("sig", resolved_url)

    def test_returns_empty_string_when_nobody_has_uploaded_a_signature(self):
        school = SchoolTenant.objects.create(
            name="No Signature School", schema_name="no_signature_school_test", is_active=True,
        )
        admin_user = User.objects.create_user(
            email="admin@nosignature.edu", password="AdminPass123", role="school_admin",
            tenant=school, is_active=True, is_verified=True,
        )
        User.objects.filter(pk=admin_user.pk).update(director_signature=None)

        self.assertEqual(_resolve_school_signature_url(school), "")


class SchoolSettingsAPITests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.school = SchoolTenant.objects.create(
            name="Settings School",
            schema_name="settings_school_20260306",
            is_active=True,
        )
        self.admin_user = User.objects.create_user(
            email="admin@settings.edu",
            password="AdminPass123",
            first_name="Admin",
            last_name="User",
            role="school_admin",
            tenant=self.school,
            is_active=True,
            is_verified=True,
        )
        self.student_user = User.objects.create_user(
            email="student@settings.edu",
            password="StudentPass123",
            first_name="Student",
            last_name="User",
            role="student",
            tenant=self.school,
            is_active=True,
            is_verified=True,
        )

    def test_get_school_settings_returns_current_tenant_profile(self):
        self.client.force_authenticate(user=self.admin_user)
        response = self.client.get("/api/app/school/settings/")

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.data["success"])
        self.assertEqual(response.data["school"]["name"], "Settings School")
        self.assertEqual(response.data["school"]["school_code"], "settings_school_20260306")
        self.assertTrue(response.data["can_edit"])

    def test_school_admin_can_update_school_name(self):
        self.client.force_authenticate(user=self.admin_user)
        response = self.client.patch(
            "/api/app/school/settings/",
            data={"name": "Updated Settings School"},
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.data["success"])
        self.school.refresh_from_db()
        self.assertEqual(self.school.name, "Updated Settings School")

    def test_school_rename_updates_code_domain_and_linked_ids(self):
        Tenant.objects.create(slug=self.school.schema_name, name=self.school.name)
        Domain.objects.create(tenant=self.school, domain="settings_school_20260306.school.local", is_primary=True)
        student = StudentProfile.objects.create(
            user=self.student_user,
            student_id="STOLD001",
            admission_number="ADM-OLD-001",
            admission_date=timezone.localdate(),
            guardian_name="Guardian",
            guardian_relation="Parent",
        )
        StudentPaymentReference.objects.create(student=student, tenant=self.school, code="STOLD001")
        teacher_user = User.objects.create_user(
            email="teacher@settings.edu",
            password="TeacherPass123",
            first_name="Teacher",
            last_name="User",
            role="teacher",
            tenant=self.school,
            is_active=True,
            is_verified=True,
        )
        teacher = TeacherProfile.objects.create(
            user=teacher_user,
            employee_id="TCOLD001",
            qualification="B.Ed",
            specialization="Science",
            years_of_experience=2,
            hire_date=timezone.localdate(),
            emergency_contact_name="Guardian",
            emergency_contact_phone="+100000000",
            emergency_contact_relation="Parent",
        )
        teacher_staff = StaffProfile.objects.create(
            tenant=self.school,
            user=teacher_user,
            staff_code="TCOLD001",
            first_name="Teacher",
            last_name="User",
            staff_type=StaffProfile.TEACHING,
            role="Teacher",
        )
        non_teaching = StaffProfile.objects.create(
            tenant=self.school,
            staff_code="NSOLD001",
            first_name="Admin",
            last_name="Staff",
            staff_type=StaffProfile.NON_TEACHING,
            role="Accountant",
        )

        self.client.force_authenticate(user=self.admin_user)
        response = self.client.patch(
            "/api/app/school/settings/",
            data={"name": "Icon Tutor"},
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.data["renamed"])
        self.school.refresh_from_db()
        student.refresh_from_db()
        teacher.refresh_from_db()
        teacher_staff.refresh_from_db()
        non_teaching.refresh_from_db()
        self.assertEqual(self.school.name, "Icon Tutor")
        self.assertEqual(self.school.schema_name, "icon_tutor")
        self.assertTrue(Tenant.objects.filter(slug="icon_tutor", name="Icon Tutor").exists())
        self.assertTrue(Domain.objects.filter(tenant=self.school, domain="icon_tutor.school.local", is_primary=True).exists())
        self.assertRegex(student.student_id, r"^STIT\d{3}$")
        self.assertRegex(teacher.employee_id, r"^TCIT\d{3}$")
        self.assertEqual(teacher_staff.staff_code, teacher.employee_id)
        self.assertRegex(non_teaching.staff_code, r"^NSIT\d{3}$")
        self.assertEqual(student.payment_reference.code, student.student_id)

    def test_school_admin_can_upload_school_logo(self):
        self.client.force_authenticate(user=self.admin_user)
        logo = SimpleUploadedFile(
            "logo.gif",
            b"GIF87a\x01\x00\x01\x00\x80\x01\x00\x00\x00\x00ccc,\x00\x00\x00\x00\x01\x00\x01\x00\x00\x02\x02D\x01\x00;",
            content_type="image/gif",
        )
        response = self.client.patch(
            "/api/app/school/settings/",
            data={
                "name": "Settings School",
                "logo": logo,
                "currency": "NGN",
                "timezone": "Africa/Lagos",
            },
            format="multipart",
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.data["success"])
        self.assertIn("logo", response.data["school"])
        self.assertTrue(response.data["school"]["logo"])
        self.school.refresh_from_db()
        self.assertTrue(self.school.logo.name)
        self.assertEqual(self.school.currency, "NGN")

    def test_school_admin_can_upload_one_megabyte_school_logo(self):
        self.client.force_authenticate(user=self.admin_user)
        logo = SimpleUploadedFile(
            "logo.png",
            b"\x89PNG\r\n\x1a\n" + (b"0" * (1024 * 1024)),
            content_type="image/png",
        )
        response = self.client.patch(
            "/api/app/school/settings/",
            data={
                "name": "Settings School",
                "logo": logo,
            },
            format="multipart",
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.data["success"])
        self.school.refresh_from_db()
        self.assertTrue(self.school.logo.name.endswith(".png"))

    def test_non_admin_cannot_update_school_name(self):
        self.client.force_authenticate(user=self.student_user)
        response = self.client.patch(
            "/api/app/school/settings/",
            data={"name": "Student Should Not Update"},
            format="json",
        )

        self.assertEqual(response.status_code, 403)
        self.school.refresh_from_db()
        self.assertEqual(self.school.name, "Settings School")

    @patch("users.app_views.send_mail", return_value=1)
    def test_school_admin_can_submit_support_ticket(self, send_mail_mock):
        self.client.force_authenticate(user=self.admin_user)
        attachment = SimpleUploadedFile("error.txt", b"Traceback details", content_type="text/plain")

        response = self.client.post(
            "/api/app/support-tickets/",
            data={
                "category": "technical_issue",
                "subject": "CBT page is not loading",
                "description": "Students receive a blank CBT screen after signing in.",
                "attachment": attachment,
            },
            format="multipart",
        )

        self.assertEqual(response.status_code, 201)
        self.assertTrue(response.data["success"])
        ticket = SupportTicket.objects.get()
        self.assertEqual(ticket.school, self.school)
        self.assertEqual(ticket.submitted_by, self.admin_user)
        self.assertEqual(ticket.status, "open")
        self.assertTrue(ticket.attachment.name)
        send_mail_mock.assert_called_once()

    @patch("users.app_views.send_mail", return_value=1)
    def test_public_contact_form_sends_email_to_support_inbox(self, send_mail_mock):
        response = self.client.post(
            "/api/auth/contact/",
            data={
                "name": "Jordan Smith",
                "email": "jordan@example.com",
                "message": "Please call me back about onboarding and migration.",
            },
            format="json",
        )

        self.assertEqual(response.status_code, 201)
        self.assertTrue(response.data["success"])
        send_mail_mock.assert_called_once()
        args, kwargs = send_mail_mock.call_args
        self.assertIn("Schooldom contact from Jordan Smith", args[0])
        self.assertIn("jordan@example.com", args[1])
        self.assertIn("enquiry@schooldom.academy", args[3])

    def test_school_settings_includes_support_tickets(self):
        SupportTicket.objects.create(
            school=self.school,
            submitted_by=self.admin_user,
            category="billing_issue",
            subject="Token balance question",
            description="We need help reconciling our activation token balance.",
            requester_email=self.admin_user.email,
        )

        self.client.force_authenticate(user=self.admin_user)
        response = self.client.get("/api/app/school/settings/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data["support_tickets"]), 1)
        self.assertEqual(response.data["support_tickets"][0]["status"], "open")

    def test_non_admin_cannot_submit_support_ticket(self):
        self.client.force_authenticate(user=self.student_user)
        response = self.client.post(
            "/api/app/support-tickets/",
            data={
                "category": "general_inquiry",
                "subject": "Need help",
                "description": "I need help with the platform.",
            },
            format="json",
        )

        self.assertEqual(response.status_code, 403)


class StudentsAPITests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.school = SchoolTenant.objects.create(
            name="Student Upload School",
            schema_name="student_upload_school_20260306",
            is_active=True,
        )
        self.legacy_tenant = Tenant.objects.create(
            name="Student Upload School Legacy",
            slug="student_upload_school_20260306",
        )
        self.classroom = Class.objects.create(
            name="Grade 7",
            section="B",
            tenant=self.legacy_tenant,
        )
        self.admin_user = User.objects.create_user(
            email="admin@student-upload.edu",
            password="AdminPass123",
            first_name="Admin",
            last_name="Uploader",
            role="school_admin",
            tenant=self.school,
            is_active=True,
            is_verified=True,
        )
        self.client.force_authenticate(user=self.admin_user)

    def test_create_student_accepts_profile_picture_and_returns_visible_media_url(self):
        image_content = (
            b"GIF89a\x01\x00\x01\x00\x80\x00\x00\x00\x00\x00\xff\xff\xff!"
            b"\xf9\x04\x01\x00\x00\x00\x00,\x00\x00\x00\x00\x01\x00\x01\x00"
            b"\x00\x02\x02D\x01\x00;"
        )
        image = SimpleUploadedFile("student.gif", image_content, content_type="image/gif")

        response = self.client.post(
            "/api/app/students/create/",
            data={
                "student_email": "photo.student@student-upload.edu",
                "first_name": "Photo",
                "last_name": "Student",
                "guardian_name": "Guardian Photo",
                "guardian_phone": "+15550006666",
                "student_password": "StudentPass123",
                "confirm_student_password": "StudentPass123",
                "class_id": self.classroom.id,
                "profile_picture": image,
            },
            format="multipart",
        )

        self.assertEqual(response.status_code, 201)
        self.assertTrue(response.data["success"])
        self.assertIn("/media/profiles/", response.data["student"]["profile_picture"])

        profile = StudentProfile.objects.get(user__email="photo.student@student-upload.edu")
        self.assertEqual(profile.current_class, self.classroom)
        self.assertTrue(bool(profile.user.profile_picture))
        self.assertTrue(profile.user.profile_picture.storage.exists(profile.user.profile_picture.name))
        self.assertTrue(profile.user.check_password("StudentPass123"))

    def test_database_import_image_creates_student_from_filename(self):
        image_content = (
            b"GIF89a\x01\x00\x01\x00\x80\x00\x00\x00\x00\x00\xff\xff\xff!"
            b"\xf9\x04\x01\x00\x00\x00\x00,\x00\x00\x00\x00\x01\x00\x01\x00"
            b"\x00\x02\x02D\x01\x00;"
        )
        image = SimpleUploadedFile("Janet Jackson.gif", image_content, content_type="image/gif")

        response = self.client.post(
            "/api/app/database-imports/",
            data={
                "import_type": "students",
                "link_key": "filename",
                "file": image,
            },
            format="multipart",
        )

        self.assertEqual(response.status_code, 201)
        self.assertTrue(response.data["success"], response.data)
        self.assertIn("1 student image import", response.data["message"])

        profile = StudentProfile.objects.get(user__email__iexact="janet-jackson@student-upload-school-20260306.imported.local")
        self.assertEqual(profile.user.first_name, "Janet")
        self.assertEqual(profile.user.last_name, "Jackson")
        self.assertTrue(bool(profile.user.profile_picture))
        self.assertTrue(profile.user.check_password("StudentPass123"))

    def test_database_import_accepts_multiple_student_image_files(self):
        image_content = (
            b"GIF89a\x01\x00\x01\x00\x80\x00\x00\x00\x00\x00\xff\xff\xff!"
            b"\xf9\x04\x01\x00\x00\x00\x00,\x00\x00\x00\x00\x01\x00\x01\x00"
            b"\x00\x02\x02D\x01\x00;"
        )
        first = SimpleUploadedFile("Mary Stone.gif", image_content, content_type="image/gif")
        second = SimpleUploadedFile("Paul Green.gif", image_content, content_type="image/gif")

        response = self.client.post(
            "/api/app/database-imports/",
            data={
                "import_type": "students",
                "link_key": "filename",
                "file": [first, second],
            },
            format="multipart",
        )

        self.assertEqual(response.status_code, 201)
        self.assertTrue(response.data["success"], response.data)
        self.assertEqual(len(response.data["jobs"]), 2)
        self.assertTrue(StudentProfile.objects.filter(user__first_name="Mary", user__last_name="Stone").exists())
        self.assertTrue(StudentProfile.objects.filter(user__first_name="Paul", user__last_name="Green").exists())

    def test_update_student_profile_api_updates_user_and_profile(self):
        student_user = User.objects.create_user(
            email="update.student@student-upload.edu",
            password="StudentPass123",
            first_name="Old",
            last_name="Name",
            role="student",
            tenant=self.school,
            is_active=True,
            is_verified=True,
        )
        profile = StudentProfile.objects.create(
            user=student_user,
            student_id="STU-UPD-1",
            admission_number="ADM-UPD-1",
            admission_date=timezone.now().date(),
            guardian_name="Old Guardian",
            guardian_phone="+15550001111",
            guardian_relation="Parent",
        )

        response = self.client.patch(
            f"/api/app/students/{profile.id}/",
            data={
                "first_name": "Updated",
                "last_name": "Student",
                "phone": "+15551112222",
                "guardian_name": "Updated Guardian",
                "guardian_phone": "+15553334444",
                "class_id": self.classroom.id,
            },
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.data["success"])
        profile.refresh_from_db()
        student_user.refresh_from_db()
        self.assertEqual(student_user.first_name, "Updated")
        self.assertEqual(student_user.last_name, "Student")
        self.assertEqual(student_user.phone, "+15551112222")
        self.assertEqual(profile.guardian_name, "Updated Guardian")
        self.assertEqual(profile.guardian_phone, "+15553334444")
        self.assertEqual(profile.current_class, self.classroom)

    def test_delete_student_api_removes_profile_and_user(self):
        student_user = User.objects.create_user(
            email="delete.student@student-upload.edu",
            password="StudentPass123",
            first_name="Delete",
            last_name="Me",
            role="student",
            tenant=self.school,
            is_active=True,
            is_verified=True,
        )
        profile = StudentProfile.objects.create(
            user=student_user,
            student_id="STU-DEL-1",
            admission_number="ADM-DEL-1",
            admission_date=timezone.now().date(),
            guardian_name="Delete Guardian",
            guardian_phone="+15556667777",
            guardian_relation="Parent",
        )

        response = self.client.delete(f"/api/app/students/{profile.id}/")
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.data["success"])
        self.assertFalse(StudentProfile.objects.filter(id=profile.id).exists())
        self.assertFalse(User.objects.filter(id=student_user.id).exists())

    def test_create_student_requires_password_for_new_student(self):
        response = self.client.post(
            "/api/app/students/create/",
            data={
                "student_email": "nopassword@student-upload.edu",
                "first_name": "No",
                "last_name": "Password",
                "guardian_name": "Guardian",
            },
            format="json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertFalse(response.data["success"])
        self.assertIn("student_password is required", response.data["message"])
        self.assertFalse(User.objects.filter(email="nopassword@student-upload.edu").exists())


class AttendanceAndPromptTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.school = SchoolTenant.objects.create(
            name="Attendance School",
            schema_name="attendance_school_20260307",
            is_active=True,
        )
        self.legacy_tenant = Tenant.objects.create(
            name="Attendance School Legacy",
            slug="attendance_school_20260307",
        )
        self.classroom = Class.objects.create(
            name="Grade 8",
            section="C",
            tenant=self.legacy_tenant,
        )
        self.student_user = User.objects.create_user(
            email="attendance@student.edu",
            password="StudentPass123",
            first_name="Learner",
            last_name="Student",
            role="student",
            tenant=self.school,
            is_active=True,
            is_verified=True,
        )
        StudentProfile.objects.create(
            user=self.student_user,
            student_id="STU-ATT-1",
            admission_number="ADM-ATT-1",
            admission_date=timezone.now().date(),
            guardian_name="Guardian Lead",
            guardian_phone="+15550009999",
            guardian_relation="Parent",
            current_class=self.classroom,
        )
        self.teacher_user = User.objects.create_user(
            email="teacher@attendance.edu",
            password="TeacherPass123",
            first_name="Casey",
            last_name="Teacher",
            role="teacher",
            tenant=self.school,
            is_active=True,
            is_verified=True,
        )
        self.teacher_profile = TeacherProfile.objects.create(
            user=self.teacher_user,
            employee_id="TCH-ATT-1",
            qualification="M.Ed",
            specialization="General Studies",
            years_of_experience=5,
            hire_date=timezone.now().date(),
            employment_type="full_time",
            emergency_contact_name="Assistant Lead",
            emergency_contact_phone="+15550008888",
            emergency_contact_relation="Sibling",
        )
        self.teacher_profile.assigned_classes.add(self.classroom)
        self.subject = Subject.objects.create(
            name="Science",
            code="SCI",
            tenant=self.legacy_tenant,
        )
        start = timezone.now() + timedelta(days=2)
        self.exam = Exam.objects.create(
            title="Attendance Lesson Quiz",
            subject=self.subject,
            class_group=self.classroom,
            teacher=self.teacher_user,
            start_date=start,
            end_date=start + timedelta(hours=1),
            duration_minutes=45,
            tenant=self.legacy_tenant,
            is_published=True,
        )

    def test_teacher_class_students_only_returns_assigned_class_students(self):
        other_class = Class.objects.create(name="Grade 9", section="A", tenant=self.legacy_tenant)
        other_student_user = User.objects.create_user(
            email="other.attendance@student.edu",
            password="StudentPass123",
            first_name="Other",
            last_name="Student",
            role="student",
            tenant=self.school,
            is_active=True,
            is_verified=True,
        )
        StudentProfile.objects.create(
            user=other_student_user,
            student_id="STU-ATT-2",
            admission_number="ADM-ATT-2",
            admission_date=timezone.now().date(),
            guardian_name="Guardian Two",
            guardian_phone="+15550007777",
            guardian_relation="Parent",
            current_class=other_class,
        )

        self.client.force_authenticate(user=self.teacher_user)
        response = self.client.get("/api/app/attendance/class-students/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual([item["student_id"] for item in response.data["students"]], ["STU-ATT-1"])
        self.assertEqual([item["id"] for item in response.data["classes"]], [self.classroom.id])

    def test_teacher_cannot_mark_unassigned_class_attendance(self):
        other_class = Class.objects.create(name="Grade 9", section="B", tenant=self.legacy_tenant)
        other_student_user = User.objects.create_user(
            email="blocked.attendance@student.edu",
            password="StudentPass123",
            first_name="Blocked",
            last_name="Student",
            role="student",
            tenant=self.school,
            is_active=True,
            is_verified=True,
        )
        StudentProfile.objects.create(
            user=other_student_user,
            student_id="STU-ATT-3",
            admission_number="ADM-ATT-3",
            admission_date=timezone.now().date(),
            guardian_name="Guardian Three",
            guardian_phone="+15550006666",
            guardian_relation="Parent",
            current_class=other_class,
        )

        self.client.force_authenticate(user=self.teacher_user)
        response = self.client.post(
            "/api/app/attendance/teacher-mark/",
            data={
                "student_id": "STU-ATT-3",
                "class_id": other_class.id,
                "status": "present",
                "location": {"latitude": 6.5243793, "longitude": 3.3792057, "accuracy": 12.5},
            },
            format="json",
        )

        self.assertEqual(response.status_code, 403)
        self.assertFalse(AttendanceRecord.objects.filter(student=other_student_user).exists())

    def test_teacher_can_mark_attendance_without_geo_location(self):
        self.client.force_authenticate(user=self.teacher_user)
        response = self.client.post(
            "/api/app/attendance/teacher-mark/",
            data={"student_id": "STU-ATT-1", "class_id": self.classroom.id, "status": "present"},
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        record = AttendanceRecord.objects.get(student=self.student_user, date=timezone.localdate())
        self.assertEqual(record.status, "present")
        self.assertIsNone(record.latitude)
        self.assertIsNone(record.longitude)

    def test_teacher_can_mark_assigned_class_attendance(self):
        self.client.force_authenticate(user=self.teacher_user)
        response = self.client.post(
            "/api/app/attendance/teacher-mark/",
            data={
                "student_id": "STU-ATT-1",
                "class_id": self.classroom.id,
                "status": "present",
                "location": {
                    "latitude": 6.5243793,
                    "longitude": 3.3792057,
                    "accuracy": 12.5,
                    "address": "Lagos, Nigeria",
                    "device_info": "Test browser",
                },
            },
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        record = AttendanceRecord.objects.get(student=self.student_user, date=timezone.localdate())
        self.assertEqual(record.status, "present")
        self.assertEqual(record.class_group, self.classroom)
        self.assertEqual(record.noted_by, self.teacher_user)
        self.assertEqual(str(record.latitude), "6.5243793")
        self.assertEqual(str(record.longitude), "3.3792057")
        self.assertEqual(record.location_address, "Lagos, Nigeria")

    def test_teacher_id_card_scan_attendance_does_not_require_geo_location(self):
        student_profile = StudentProfile.objects.get(user=self.student_user)
        token = signing.dumps(
            {
                "tenant_id": str(self.school.id),
                "person_type": "student",
                "person_id": str(student_profile.id),
                "unique_id": student_profile.student_id,
            },
            salt=ID_CARD_SIGNING_SALT,
            compress=True,
        )

        self.client.force_authenticate(user=self.teacher_user)
        response = self.client.post(
            "/api/app/id-cards/scan-attendance/",
            data={"token": token},
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        record = AttendanceRecord.objects.get(student=self.student_user, date=timezone.localdate())
        self.assertEqual(record.status, "present")
        self.assertEqual(record.noted_by, self.teacher_user)
        self.assertIsNone(record.latitude)
        self.assertIsNone(record.longitude)

    def test_document_endpoints_do_not_consume_tokens(self):
        admin_user = User.objects.create_user(
            email="admin@attendance.edu",
            password="AdminPass123",
            first_name="Avery",
            last_name="Admin",
            role="school_admin",
            tenant=self.school,
            is_active=True,
            is_verified=True,
        )
        transcript_student = StudentProfile.objects.create(
            user=User.objects.create_user(
                email="transcript@student.edu",
                password="StudentPass123",
                first_name="Transcript",
                last_name="Student",
                role="student",
                tenant=self.school,
                is_active=True,
                is_verified=True,
            ),
            student_id="STU-ATT-2",
            admission_number="ADM-ATT-2",
            admission_date=timezone.now().date(),
            guardian_name="Guardian Two",
            guardian_phone="+15550007777",
            guardian_relation="Parent",
            current_class=self.classroom,
        )
        testimonial_class = Class.objects.create(name="SSS3", section="A", tenant=self.legacy_tenant)
        testimonial_student = StudentProfile.objects.create(
            user=User.objects.create_user(
                email="testimonial@student.edu",
                password="StudentPass123",
                first_name="Testimonial",
                last_name="Student",
                role="student",
                tenant=self.school,
                is_active=True,
                is_verified=True,
            ),
            student_id="STU-ATT-3",
            admission_number="ADM-ATT-3",
            admission_date=timezone.now().date(),
            guardian_name="Guardian Three",
            guardian_phone="+15550006666",
            guardian_relation="Parent",
            current_class=testimonial_class,
        )

        self.client.force_authenticate(user=admin_user)

        transcript_response = self.client.get(
            f"/api/app/documents/transcripts/{transcript_student.id}/?generate=true"
        )
        self.assertEqual(transcript_response.status_code, 200)
        self.assertFalse(transcript_response.data["token_used"])
        self.assertEqual(transcript_response.data["tokens_used"], 0)

        testimonial_response = self.client.get(
            f"/api/app/documents/testimonials/{testimonial_student.id}/?generate=true"
        )
        self.assertEqual(testimonial_response.status_code, 200)
        self.assertFalse(testimonial_response.data["token_used"])
        self.assertEqual(testimonial_response.data["tokens_used"], 0)

        qr_response = self.client.get(
            f"/api/app/id-cards/qr/?person_type=student&person_id={transcript_student.id}&download=true"
        )
        self.assertEqual(qr_response.status_code, 200)
        self.assertEqual(qr_response.headers.get("X-Token-Used"), "0")
        self.assertEqual(qr_response.headers.get("X-Token-Message"), "ID card generated.")

    def test_student_cannot_mark_own_attendance(self):
        self.client.force_authenticate(user=self.student_user)
        response = self.client.post(
            "/api/app/attendance/mark/",
            data={"status": "present"},
            format="json",
        )
        self.assertEqual(response.status_code, 403)
        self.assertFalse(response.data["success"])
        self.assertEqual(
            AttendanceRecord.objects.filter(student=self.student_user, date=timezone.localdate()).count(),
            0,
        )

    def test_student_can_answer_prompt(self):
        prompt = QuestionPrompt.objects.create(
            title="Daily Reflection",
            body="Share one highlight from today's lesson.",
            class_group=self.classroom,
            created_by=self.teacher_user,
            tenant=self.legacy_tenant,
        )
        self.client.force_authenticate(user=self.student_user)
        response = self.client.post(
            "/api/app/questions/answer/",
            data={"prompt_id": str(prompt.id), "response_text": "Learned about ecosystems."},
            format="json",
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.data["success"])
        self.assertTrue(
            QuestionResponse.objects.filter(prompt=prompt, student=self.student_user).exists()
        )

    def test_teacher_can_create_prompt_and_notify(self):
        self.client.force_authenticate(user=self.teacher_user)
        create_response = self.client.post(
            "/api/app/questions/create/",
            data={
                "title": "Weekly Poll",
                "body": "What topic should we revisit?",
                "class_id": self.classroom.id,
            },
            format="json",
        )
        self.assertEqual(create_response.status_code, 201)
        self.assertTrue(create_response.data["success"])
        self.assertEqual(create_response.data["prompt"]["class_name"], "Grade 8 - C")

        notify_response = self.client.post(
            f"/api/app/exams/{self.exam.id}/notify/",
            data={"message": "Don't forget the quiz tomorrow.", "subject": "Quiz reminder"},
            format="json",
        )
        self.assertEqual(notify_response.status_code, 200)
        self.assertTrue(notify_response.data["success"])
        self.assertEqual(notify_response.data["sent"], 1)
        self.assertTrue(
            InAppMessage.objects.filter(sender=self.teacher_user, recipient=self.student_user).exists()
        )


class TeachersAPITests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.school = SchoolTenant.objects.create(
            name="Teacher Smoke School",
            schema_name="teacher_smoke_202603060812",
            is_active=True,
        )
        self.admin_user = User.objects.create_user(
            email="admin@teacher-smoke.edu",
            password="AdminPass123",
            first_name="Taylor",
            last_name="Admin",
            role="school_admin",
            tenant=self.school,
            is_active=True,
            is_verified=True,
        )
        self.client.force_authenticate(user=self.admin_user)

    def test_create_teacher_api_creates_user_and_profile(self):
        response = self.client.post(
            "/api/app/teachers/create/",
            data={
                "teacher_email": "new.teacher@teacher-smoke.edu",
                "first_name": "Nora",
                "last_name": "Teacher",
                "employee_id": "TCH-SMOKE-001",
                "specialization": "Mathematics",
                "qualification": "B.Ed",
                "employment_type": "full_time",
                "years_of_experience": 4,
            },
            format="json",
        )

        self.assertEqual(response.status_code, 201)
        self.assertTrue(response.data["success"])

        profile = TeacherProfile.objects.get(user__email="new.teacher@teacher-smoke.edu")
        self.assertEqual(profile.employee_id, "TCH-SMOKE-001")
        self.assertEqual(profile.specialization, "Mathematics")
        self.assertEqual(profile.qualification, "B.Ed")
        self.assertEqual(profile.years_of_experience, 4)
        self.assertEqual(profile.user.tenant, self.school)

    def test_create_teacher_api_auto_generates_employee_id(self):
        response = self.client.post(
            "/api/app/teachers/create/",
            data={
                "teacher_email": "autogen.teacher@teacher-smoke.edu",
                "first_name": "Auto",
                "last_name": "Generate",
                "specialization": "English",
                "qualification": "B.A",
                "employment_type": "full_time",
                "years_of_experience": 2,
            },
            format="json",
        )

        self.assertEqual(response.status_code, 201)
        self.assertTrue(response.data["success"])

        profile = TeacherProfile.objects.get(user__email="autogen.teacher@teacher-smoke.edu")
        self.assertTrue(profile.employee_id)
        self.assertRegex(profile.employee_id, r"^TC[A-Z]{2}\d{3}$")
        self.assertEqual(profile.user.tenant, self.school)

    def test_teachers_snapshot_returns_summary_and_options(self):
        teacher_user = User.objects.create_user(
            email="existing.teacher@teacher-smoke.edu",
            password="TeacherPass123",
            first_name="Existing",
            last_name="Teacher",
            role="teacher",
            tenant=self.school,
            is_active=True,
            is_verified=True,
        )
        TeacherProfile.objects.create(
            user=teacher_user,
            employee_id="TCH-SMOKE-EXISTING",
            qualification="M.Ed",
            specialization="Science",
            years_of_experience=7,
            hire_date=timezone.now().date(),
            emergency_contact_name="Emergency Contact",
            emergency_contact_phone="+15550004444",
            emergency_contact_relation="Sibling",
        )

        response = self.client.get("/api/app/teachers/")
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.data["success"])
        self.assertGreaterEqual(response.data["summary"]["total_teachers"], 1)
        self.assertGreaterEqual(len(response.data["teachers"]), 1)
        employment_values = [item["value"] for item in response.data["options"]["employment_types"]]
        self.assertIn("full_time", employment_values)

    def test_create_teacher_api_accepts_profile_picture(self):
        photo = SimpleUploadedFile("teacher.jpg", b"teacher-photo-bytes", content_type="image/jpeg")
        response = self.client.post(
            "/api/app/teachers/create/",
            data={
                "teacher_email": "photo.teacher@teacher-smoke.edu",
                "first_name": "Photo",
                "last_name": "Teacher",
                "profile_picture": photo,
            },
            format="multipart",
        )

        self.assertEqual(response.status_code, 201)
        self.assertTrue(response.data["success"])
        profile = TeacherProfile.objects.get(user__email="photo.teacher@teacher-smoke.edu")
        self.assertTrue(bool(profile.user.profile_picture))
        self.assertIn("profiles/", profile.user.profile_picture.name)

    def test_update_teacher_profile_api_updates_user_and_profile(self):
        teacher_user = User.objects.create_user(
            email="update.teacher@teacher-smoke.edu",
            password="TeacherPass123",
            first_name="Old",
            last_name="Teacher",
            role="teacher",
            tenant=self.school,
            is_active=True,
            is_verified=True,
        )
        profile = TeacherProfile.objects.create(
            user=teacher_user,
            employee_id="TCH-UPD-1",
            qualification="Old Qual",
            specialization="Old Spec",
            years_of_experience=1,
            hire_date=timezone.now().date(),
            employment_type="full_time",
            emergency_contact_name="Old Contact",
            emergency_contact_phone="+15550009999",
            emergency_contact_relation="Sibling",
        )

        response = self.client.patch(
            f"/api/app/teachers/{profile.id}/",
            data={
                "first_name": "Updated",
                "last_name": "Teacher",
                "phone": "+15558889999",
                "employee_id": "TCH-UPD-2",
                "specialization": "Mathematics",
                "qualification": "B.Ed",
                "employment_type": "part_time",
                "years_of_experience": 6,
            },
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.data["success"])
        profile.refresh_from_db()
        teacher_user.refresh_from_db()
        self.assertEqual(teacher_user.first_name, "Updated")
        self.assertEqual(teacher_user.last_name, "Teacher")
        self.assertEqual(teacher_user.phone, "+15558889999")
        self.assertEqual(profile.employee_id, "TCH-UPD-2")
        self.assertEqual(profile.specialization, "Mathematics")
        self.assertEqual(profile.qualification, "B.Ed")
        self.assertEqual(profile.employment_type, "part_time")
        self.assertEqual(profile.years_of_experience, 6)

    def test_update_teacher_profile_api_can_reset_password(self):
        teacher_user = User.objects.create_user(
            email="password.teacher@teacher-smoke.edu",
            password="OldPass123",
            first_name="Password",
            last_name="Teacher",
            role="teacher",
            tenant=self.school,
            is_active=True,
            is_verified=True,
        )
        profile = TeacherProfile.objects.create(
            user=teacher_user,
            employee_id="TCH-PASS-1",
            qualification="M.Ed",
            specialization="Science",
            years_of_experience=3,
            hire_date=timezone.now().date(),
            employment_type="full_time",
            emergency_contact_name="Password Contact",
            emergency_contact_phone="+15557770000",
            emergency_contact_relation="Sibling",
        )

        response = self.client.patch(
            f"/api/app/teachers/{profile.id}/",
            data={
                "teacher_password": "NewPass123",
                "confirm_teacher_password": "NewPass123",
            },
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.data["success"])
        teacher_user.refresh_from_db()
        self.assertTrue(teacher_user.check_password("NewPass123"))

    def test_id_card_verify_requires_email_and_id_challenge(self):
        student_user = User.objects.create_user(
            email="privacy.student@teacher-smoke.edu",
            password="StudentPass123",
            first_name="Private",
            last_name="Student",
            role="student",
            tenant=self.school,
            phone="+15551112222",
            is_active=True,
            is_verified=True,
        )
        profile = StudentProfile.objects.create(
            user=student_user,
            student_id="STU-PRIVATE-1",
            admission_number="ADM-PRIVATE-1",
            admission_date=timezone.now().date(),
            guardian_name="Private Guardian",
            guardian_phone="+15553334444",
            guardian_relation="Parent",
        )
        token = signing.dumps(
            {
                "tenant_id": str(self.school.id),
                "person_type": "student",
                "person_id": str(profile.id),
                "unique_id": profile.student_id,
            },
            salt=ID_CARD_SIGNING_SALT,
            compress=True,
        )

        response = self.client.get(f"/api/app/id-cards/verify/?token={token}")

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.data["challenge_required"])
        self.assertNotIn("person", response.data)

        blocked = self.client.post(
            "/api/app/id-cards/verify/",
            data={"token": token, "email": "wrong@student.edu", "unique_id": "STU-PRIVATE-1"},
            format="json",
        )
        self.assertEqual(blocked.status_code, 403)

        response = self.client.post(
            "/api/app/id-cards/verify/",
            data={"token": token, "email": "privacy.student@teacher-smoke.edu", "unique_id": "STU-PRIVATE-1"},
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.data["verified"])
        person = response.data["person"]
        self.assertEqual(person["name"], "Private Student")
        self.assertEqual(person["unique_id"], "STU-PRIVATE-1")
        self.assertEqual(person["email"], "privacy.student@teacher-smoke.edu")
        self.assertNotIn("guardian_name", person)
        self.assertNotIn("phone", person)
        self.assertNotIn("date_of_birth", person)

    def test_delete_teacher_api_removes_profile_and_user(self):
        teacher_user = User.objects.create_user(
            email="delete.teacher@teacher-smoke.edu",
            password="TeacherPass123",
            first_name="Delete",
            last_name="Teacher",
            role="teacher",
            tenant=self.school,
            is_active=True,
            is_verified=True,
        )
        profile = TeacherProfile.objects.create(
            user=teacher_user,
            employee_id="TCH-DEL-1",
            qualification="M.Ed",
            specialization="Science",
            years_of_experience=3,
            hire_date=timezone.now().date(),
            employment_type="full_time",
            emergency_contact_name="Delete Contact",
            emergency_contact_phone="+15557776666",
            emergency_contact_relation="Sibling",
        )

        response = self.client.delete(f"/api/app/teachers/{profile.id}/")
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.data["success"])
        self.assertFalse(TeacherProfile.objects.filter(id=profile.id).exists())
        self.assertFalse(User.objects.filter(id=teacher_user.id).exists())


class AuthSchoolScopeTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.school = SchoolTenant.objects.create(
            name="Scope School",
            schema_name="scope_school_20260306",
            is_active=True,
        )
        self.other_school = SchoolTenant.objects.create(
            name="Other Scope School",
            schema_name="other_scope_20260306",
            is_active=True,
        )

    def test_register_student_requires_school_code(self):
        response = self.client.post(
            "/api/auth/register/",
            data={
                "first_name": "Scope",
                "last_name": "Student",
                "email": "scope.student@school.edu",
                "password": "StudentPass123",
                "confirm_password": "StudentPass123",
                "role": "student",
                "guardian_name": "Guardian One",
                "terms_accepted": True,
            },
            format="json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertFalse(response.data["success"])
        self.assertIn("school_code", response.data["errors"])

    def test_register_teacher_requires_school_code(self):
        response = self.client.post(
            "/api/auth/register/",
            data={
                "first_name": "Scope",
                "last_name": "Teacher",
                "email": "scope.teacher@school.edu",
                "password": "TeacherPass123",
                "confirm_password": "TeacherPass123",
                "role": "teacher",
                "terms_accepted": True,
            },
            format="json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertFalse(response.data["success"])
        self.assertIn("school_code", response.data["errors"])

    def test_register_school_admin_requires_school_code(self):
        response = self.client.post(
            "/api/auth/register/",
            data={
                "first_name": "Scope",
                "last_name": "Admin",
                "email": "scope.admin@school.edu",
                "password": "AdminPass123",
                "confirm_password": "AdminPass123",
                "role": "school_admin",
                "terms_accepted": True,
            },
            format="json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertFalse(response.data["success"])
        self.assertIn("school_code", response.data["errors"])

    def test_register_student_with_school_code_is_allowed(self):
        # Student self-registration is Non-K12-only (see NonK12StudentSelfRegistrationTests);
        # self.school defaults to K12, so this needs its own Non-K12 tenant with credits.
        non_k12_school = SchoolTenant.objects.create(
            name="Scoped Non-K12 School",
            schema_name="scoped_non_k12_20260306",
            school_type=SchoolTenant.NON_K12,
            is_active=True,
        )
        pool = get_or_create_activation_credit_pool(non_k12_school)
        pool.balance = 5
        pool.save(update_fields=["balance", "updated_at"])

        response = self.client.post(
            "/api/auth/register/",
            data={
                "first_name": "Scoped",
                "last_name": "Learner",
                "email": "scoped.learner@school.edu",
                "password": "StudentPass123",
                "confirm_password": "StudentPass123",
                "role": "student",
                "guardian_name": "Guardian Scoped",
                "school_code": non_k12_school.schema_name,
                "terms_accepted": True,
            },
            format="json",
        )

        self.assertEqual(response.status_code, 201)
        self.assertTrue(response.data["success"])
        user = User.objects.get(email="scoped.learner@school.edu")
        self.assertEqual(user.tenant_id, non_k12_school.id)

    def test_student_login_requires_school_code(self):
        student = User.objects.create_user(
            email="login.student@school.edu",
            password="StudentPass123",
            first_name="Login",
            last_name="Student",
            role="student",
            tenant=self.school,
            is_active=True,
            is_verified=True,
        )
        StudentProfile.objects.create(
            user=student,
            student_id="STU-LOGIN-1",
            admission_number="ADM-LOGIN-1",
            admission_date=timezone.now().date(),
            guardian_name="Guardian Login",
            guardian_phone="+15550007777",
            guardian_relation="Parent",
        )

        response = self.client.post(
            "/api/auth/login/",
            data={
                "email": "login.student@school.edu",
                "password": "StudentPass123",
            },
            format="json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertFalse(response.data["success"])
        self.assertIn("school code is required", str(response.data["errors"]).lower())

    def test_teacher_login_requires_matching_school_code(self):
        teacher = User.objects.create_user(
            email="login.teacher@school.edu",
            password="TeacherPass123",
            first_name="Login",
            last_name="Teacher",
            role="teacher",
            tenant=self.school,
            is_active=True,
            is_verified=True,
        )
        TeacherProfile.objects.create(
            user=teacher,
            employee_id="TCH-LOGIN-1",
            qualification="M.Ed",
            specialization="Science",
            years_of_experience=5,
            hire_date=timezone.now().date(),
            emergency_contact_name="Emergency",
            emergency_contact_phone="+15550008888",
            emergency_contact_relation="Sibling",
        )

        wrong_response = self.client.post(
            "/api/auth/login/",
            data={
                "email": "login.teacher@school.edu",
                "password": "TeacherPass123",
                "school_code": self.other_school.schema_name,
            },
            format="json",
        )
        self.assertEqual(wrong_response.status_code, 400)
        self.assertFalse(wrong_response.data["success"])

        ok_response = self.client.post(
            "/api/auth/login/",
            data={
                "email": "login.teacher@school.edu",
                "password": "TeacherPass123",
                "school_code": self.school.schema_name,
            },
            format="json",
        )
        self.assertEqual(ok_response.status_code, 200)
        self.assertTrue(ok_response.data["success"])

    def test_school_admin_without_tenant_must_provide_school_code(self):
        User.objects.create_user(
            email="orphan.admin@school.edu",
            password="AdminPass123",
            first_name="Orphan",
            last_name="Admin",
            role="school_admin",
            tenant=None,
            is_active=True,
            is_verified=True,
        )

        response = self.client.post(
            "/api/auth/login/",
            data={
                "email": "orphan.admin@school.edu",
                "password": "AdminPass123",
            },
            format="json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertFalse(response.data["success"])
        self.assertIn("school code is required", str(response.data["errors"]).lower())

    @patch("users.views.ADMIN_OTP_ENABLED", False)
    def test_school_admin_login_with_school_code_backfills_tenant(self):
        user = User.objects.create_user(
            email="backfill.admin@school.edu",
            password="AdminPass123",
            first_name="Backfill",
            last_name="Admin",
            role="school_admin",
            tenant=None,
            is_active=True,
            is_verified=True,
        )

        response = self.client.post(
            "/api/auth/login/",
            data={
                "email": "backfill.admin@school.edu",
                "password": "AdminPass123",
                "school_code": self.school.schema_name,
            },
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.data["success"])
        user.refresh_from_db()
        self.assertEqual(user.tenant_id, self.school.id)

    @override_settings(DEBUG=True, ADMIN_OTP_EMAIL_FAILURE_CONSOLE_FALLBACK=True)
    @patch("users.views.ADMIN_OTP_ENABLED", True)
    @patch("users.views.send_mail", side_effect=Exception("SMTP rejected credentials"))
    @patch("users.views.render_to_string", return_value="<p>OTP</p>")
    def test_admin_otp_login_uses_console_fallback_when_email_fails_in_debug(self, _render_to_string, _send_mail):
        user = User.objects.create_user(
            email="otp.fallback.admin@school.edu",
            password="AdminPass123",
            first_name="Otp",
            last_name="Fallback",
            role="school_admin",
            tenant=self.school,
            is_active=True,
            is_verified=True,
        )

        response = self.client.post(
            "/api/auth/login/",
            data={
                "email": user.email,
                "password": "AdminPass123",
                "school_code": self.school.schema_name,
            },
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.data["success"])
        self.assertTrue(response.data["requires_otp"])
        self.assertTrue(response.data["otp_challenge"])

    @override_settings(DEBUG=True, ADMIN_OTP_EMAIL_FAILURE_CONSOLE_FALLBACK=True)
    @patch("users.views.ADMIN_OTP_ENABLED", True)
    @patch("users.views.send_mail", return_value=1)
    @patch("users.views.render_to_string", return_value="<p>OTP</p>")
    def test_admin_otp_resend_accepts_matching_expired_challenge(self, _render_to_string, _send_mail):
        user = User.objects.create_user(
            email="otp.expired.admin@school.edu",
            password="AdminPass123",
            first_name="Otp",
            last_name="Expired",
            role="school_admin",
            tenant=self.school,
            is_active=True,
            is_verified=False,
        )
        user.admin_otp_hash = "old-hash"
        user.admin_otp_challenge = "expired-challenge"
        user.admin_otp_sent_at = timezone.now() - timedelta(minutes=30)
        user.admin_otp_purpose = "signup"
        user.save(update_fields=[
            "admin_otp_hash",
            "admin_otp_challenge",
            "admin_otp_sent_at",
            "admin_otp_purpose",
        ])

        response = self.client.post(
            "/api/auth/admin/resend-otp/",
            data={
                "email": user.email,
                "challenge": "expired-challenge",
            },
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.data["success"])
        self.assertEqual(response.data["otp_purpose"], "signup")
        self.assertTrue(response.data["otp_challenge"])
        self.assertNotEqual(response.data["otp_challenge"], "expired-challenge")

    def test_create_class_accepts_school_code_when_user_tenant_missing(self):
        user = User.objects.create_user(
            email="class.admin@school.edu",
            password="AdminPass123",
            first_name="Class",
            last_name="Admin",
            role="school_admin",
            tenant=None,
            is_active=True,
            is_verified=True,
        )
        self.client.force_authenticate(user=user)

        response = self.client.post(
            "/api/app/classes/create/",
            data={
                "name": "Grade 11",
                "section": "A",
                "school_code": self.school.schema_name,
            },
            format="json",
        )

        self.assertEqual(response.status_code, 201)
        self.assertTrue(response.data["success"])
        user.refresh_from_db()
        self.assertEqual(user.tenant_id, self.school.id)
        self.assertTrue(Tenant.objects.filter(slug=self.school.schema_name).exists())

    def test_create_class_assigns_selected_subjects(self):
        user = User.objects.create_user(
            email="subject.class.admin@school.edu",
            password="AdminPass123",
            first_name="Subject",
            last_name="Admin",
            role="school_admin",
            tenant=self.school,
            is_active=True,
            is_verified=True,
        )
        legacy_tenant = Tenant.objects.create(slug=self.school.schema_name, name=self.school.name)
        math = Subject.objects.create(name="Mathematics", code="MATH", tenant=legacy_tenant)
        physics = Subject.objects.create(name="Physics", code="PHY", tenant=legacy_tenant)
        self.client.force_authenticate(user=user)

        response = self.client.post(
            "/api/app/classes/create/",
            data={
                "name": "Science Department",
                "section": "Senior",
                "subject_ids": [math.id, physics.id],
            },
            format="json",
        )

        self.assertEqual(response.status_code, 201)
        self.assertTrue(response.data["success"])
        self.assertEqual({item["id"] for item in response.data["class"]["subjects"]}, {math.id, physics.id})
        class_obj = Class.objects.get(name="Science Department")
        self.assertEqual(set(class_obj.subjects.values_list("id", flat=True)), {math.id, physics.id})

    def test_bulk_class_promotion_preview_and_apply_updates_students(self):
        user = User.objects.create_user(
            email="promotion.admin@school.edu",
            password="AdminPass123",
            first_name="Promotion",
            last_name="Admin",
            role="school_admin",
            tenant=self.school,
            is_active=True,
            is_verified=True,
        )
        legacy_tenant = Tenant.objects.create(slug=self.school.schema_name, name=self.school.name)
        term_one = Term.objects.create(
            name="2026 Term 1",
            start_date=timezone.now().date(),
            end_date=timezone.now().date() + timedelta(days=90),
            is_active=True,
            tenant=legacy_tenant,
        )
        source_class = Class.objects.create(name="Grade 9", section="A", tenant=legacy_tenant)
        target_class = Class.objects.create(name="Grade 10", section="A", tenant=legacy_tenant)
        student_user = User.objects.create_user(
            email="promote.student@school.edu",
            password="StudentPass123",
            first_name="Promote",
            last_name="Student",
            role="student",
            tenant=self.school,
            is_active=True,
            is_verified=True,
        )
        student = StudentProfile.objects.create(
            user=student_user,
            student_id="ST-PROMO-1",
            admission_number="ADM-PROMO-1",
            admission_date=timezone.now().date(),
            guardian_name="Guardian",
            guardian_phone="08000000000",
            guardian_relation="Parent",
            current_class=source_class,
            current_term=term_one,
        )
        self.client.force_authenticate(user=user)

        preview_response = self.client.post(
            "/api/app/classes/promotions/",
            data={
                "action": "preview",
                "scope": "class",
                "source_class_id": source_class.id,
                "source_term_id": term_one.id,
                "target_class_id": target_class.id,
                "target_term_id": term_one.id,
            },
            format="json",
        )

        self.assertEqual(preview_response.status_code, 200)
        self.assertEqual(preview_response.data["preview"]["summary"]["eligible_students"], 1)

        apply_response = self.client.post(
            "/api/app/classes/promotions/",
            data={
                "action": "apply",
                "scope": "class",
                "source_class_id": source_class.id,
                "source_term_id": term_one.id,
                "target_class_id": target_class.id,
                "target_term_id": term_one.id,
                "confirm": True,
            },
            format="json",
        )

        self.assertEqual(apply_response.status_code, 200)
        student.refresh_from_db()
        self.assertEqual(student.current_class, target_class)
        self.assertEqual(StudentClassPromotion.objects.filter(student=student, to_class=target_class).count(), 1)

    def test_bulk_class_promotion_blocks_duplicate_preview(self):
        user = User.objects.create_user(
            email="promotion.duplicate.admin@school.edu",
            password="AdminPass123",
            first_name="Promotion",
            last_name="Duplicate",
            role="school_admin",
            tenant=self.school,
            is_active=True,
            is_verified=True,
        )
        legacy_tenant = Tenant.objects.create(slug=self.school.schema_name, name=self.school.name)
        source_class = Class.objects.create(name="Grade 8", section="B", tenant=legacy_tenant)
        target_class = Class.objects.create(name="Grade 9", section="B", tenant=legacy_tenant)
        student_user = User.objects.create_user(
            email="duplicate.promotion.student@school.edu",
            password="StudentPass123",
            first_name="Duplicate",
            last_name="Student",
            role="student",
            tenant=self.school,
            is_active=True,
            is_verified=True,
        )
        student = StudentProfile.objects.create(
            user=student_user,
            student_id="ST-PROMO-2",
            admission_number="ADM-PROMO-2",
            admission_date=timezone.now().date(),
            guardian_name="Guardian",
            guardian_phone="08000000001",
            guardian_relation="Parent",
            current_class=source_class,
        )
        StudentClassPromotion.objects.create(
            tenant=legacy_tenant,
            student=student,
            from_class=source_class,
            to_class=target_class,
            scope="class",
            scope_value="Grade 8 - B",
            batch_reference="TEST-BATCH",
            promoted_by=user,
        )
        self.client.force_authenticate(user=user)

        response = self.client.post(
            "/api/app/classes/promotions/",
            data={
                "action": "preview",
                "scope": "class",
                "source_class_id": source_class.id,
                "target_class_id": target_class.id,
            },
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["preview"]["summary"]["eligible_students"], 0)
        self.assertEqual(response.data["preview"]["summary"]["duplicate_promotions"], 1)

    @patch("users.views.ADMIN_OTP_ENABLED", False)
    def test_refresh_token_endpoint_allows_refresh_without_access_token(self):
        user = User.objects.create_user(
            email="refresh.admin@school.edu",
            password="AdminPass123",
            first_name="Refresh",
            last_name="Admin",
            role="school_admin",
            tenant=self.school,
            is_active=True,
            is_verified=True,
        )

        login_response = self.client.post(
            "/api/auth/login/",
            data={
                "email": user.email,
                "password": "AdminPass123",
            },
            format="json",
        )
        self.assertEqual(login_response.status_code, 200)
        self.assertTrue(login_response.data["success"])
        self.assertIn("refresh", login_response.data)

        # Simulate browser state after access token expiry by omitting Authorization header.
        self.client.credentials()
        refresh_response = self.client.post(
            "/api/auth/refresh/",
            data={"refresh": login_response.data["refresh"]},
            format="json",
        )

        self.assertEqual(refresh_response.status_code, 200)
        self.assertIn("access", refresh_response.data)

    @patch("users.views.ADMIN_OTP_ENABLED", False)
    def test_refresh_token_rejected_once_school_is_suspended(self):
        """Suspension must end an already-open session too, not just block
        new logins - a user signed in before their school got suspended
        shouldn't be able to keep refreshing forever."""
        user = User.objects.create_user(
            email="suspend.admin@school.edu",
            password="AdminPass123",
            first_name="Suspend",
            last_name="Admin",
            role="school_admin",
            tenant=self.school,
            is_active=True,
            is_verified=True,
        )

        login_response = self.client.post(
            "/api/auth/login/",
            data={"email": user.email, "password": "AdminPass123"},
            format="json",
        )
        self.assertEqual(login_response.status_code, 200)
        refresh_value = login_response.data["refresh"]

        self.school.is_active = False
        self.school.save(update_fields=["is_active"])

        self.client.credentials()
        refresh_response = self.client.post(
            "/api/auth/refresh/",
            data={"refresh": refresh_value},
            format="json",
        )

        self.assertEqual(refresh_response.status_code, 401)
        self.assertFalse(refresh_response.data["success"])
        self.assertIn("suspended", refresh_response.data["message"].lower())


class NonK12StudentSelfRegistrationTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.non_k12_school = SchoolTenant.objects.create(
            name="Vocational Academy",
            schema_name="vocational_academy_20260306",
            school_type=SchoolTenant.NON_K12,
            is_active=True,
        )
        self.k12_school = SchoolTenant.objects.create(
            name="Primary School",
            schema_name="primary_school_20260306",
            school_type=SchoolTenant.K12,
            is_active=True,
        )
        self.inactive_non_k12_school = SchoolTenant.objects.create(
            name="Closed Vocational Academy",
            schema_name="closed_vocational_20260306",
            school_type=SchoolTenant.NON_K12,
            is_active=False,
        )

    def _register_payload(self, school_code, email=None):
        # Unique-per-test email: the IdempotencyMiddleware dedupes identical
        # (anon user, method, path, body) requests for 10s, so a fixed email
        # + fixed school_code across test methods would replay a stale response.
        return {
            "first_name": "New",
            "last_name": "Student",
            "email": email or f"{self._testMethodName}@school.edu",
            "password": "StudentPass123",
            "confirm_password": "StudentPass123",
            "role": "student",
            "guardian_name": "Guardian Person",
            "phone": "+15550001111",
            "school_code": school_code,
            "terms_accepted": True,
        }

    def test_self_registration_succeeds_for_active_non_k12_school_with_credits(self):
        pool = get_or_create_activation_credit_pool(self.non_k12_school)
        pool.balance = 3
        pool.save(update_fields=["balance", "updated_at"])

        response = self.client.post(
            "/api/auth/register/",
            data=self._register_payload(self.non_k12_school.schema_name),
            format="json",
        )

        self.assertEqual(response.status_code, 201, response.data)
        self.assertTrue(response.data["success"])
        self.assertIn("access", response.data)

        user = User.objects.get(email=f"{self._testMethodName}@school.edu")
        self.assertEqual(user.role, "student")
        self.assertEqual(user.tenant_id, self.non_k12_school.id)

        profile = StudentProfile.objects.get(user=user)
        self.assertTrue(profile.student_id)
        self.assertTrue(profile.admission_number)
        self.assertTrue(hasattr(user, "wallet"))

        # One credit was actually consumed from the school's pool, and the
        # student can log in immediately (mirrors an admin manually assigning one).
        pool.refresh_from_db()
        self.assertEqual(pool.balance, 2)
        credit = get_or_create_student_activation_credit(profile)
        self.assertTrue(credit.has_login_credit)

    def test_self_registration_rejected_for_k12_school(self):
        response = self.client.post(
            "/api/auth/register/",
            data=self._register_payload(self.k12_school.schema_name),
            format="json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertFalse(response.data["success"])
        self.assertIn("school_code", response.data["errors"])
        self.assertIn("non-k12", str(response.data["errors"]).lower())
        self.assertFalse(User.objects.filter(email=f"{self._testMethodName}@school.edu").exists())

    def test_self_registration_rejected_when_pool_has_no_credits(self):
        # Fresh pool defaults to a zero balance.
        response = self.client.post(
            "/api/auth/register/",
            data=self._register_payload(self.non_k12_school.schema_name),
            format="json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertFalse(response.data["success"])
        self.assertIn("school_code", response.data["errors"])
        self.assertIn("activation credit", str(response.data["errors"]).lower())
        # No half-created account left behind.
        self.assertFalse(User.objects.filter(email=f"{self._testMethodName}@school.edu").exists())

    def test_self_registration_rejected_for_inactive_non_k12_school(self):
        response = self.client.post(
            "/api/auth/register/",
            data=self._register_payload(self.inactive_non_k12_school.schema_name),
            format="json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertFalse(response.data["success"])
        self.assertIn("school_code", response.data["errors"])
        self.assertFalse(User.objects.filter(email=f"{self._testMethodName}@school.edu").exists())

    def test_self_registration_rejected_for_nonexistent_school_code(self):
        response = self.client.post(
            "/api/auth/register/",
            data=self._register_payload("does_not_exist_anywhere"),
            format="json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertFalse(response.data["success"])
        self.assertIn("school_code", response.data["errors"])
        self.assertFalse(User.objects.filter(email=f"{self._testMethodName}@school.edu").exists())

    def test_self_registration_never_links_to_a_different_school_via_race(self):
        """A student can never end up linked to a school other than the one whose code they supplied."""
        pool = get_or_create_activation_credit_pool(self.non_k12_school)
        pool.balance = 1
        pool.save(update_fields=["balance", "updated_at"])
        other_pool = get_or_create_activation_credit_pool(self.k12_school)
        other_pool.balance = 10
        other_pool.save(update_fields=["balance", "updated_at"])

        response = self.client.post(
            "/api/auth/register/",
            data=self._register_payload(self.non_k12_school.schema_name),
            format="json",
        )

        self.assertEqual(response.status_code, 201, response.data)
        user = User.objects.get(email=f"{self._testMethodName}@school.edu")
        self.assertEqual(user.tenant_id, self.non_k12_school.id)
        self.assertNotEqual(user.tenant_id, self.k12_school.id)


class MessageGroupChatTests(TestCase):
    """Non-K12 students can create group chats with their classmates; K12
    students and cross-tenant students must never be able to join or see them."""

    def setUp(self):
        self.client = APIClient()
        self.non_k12_school = SchoolTenant.objects.create(
            name="Vocational Academy",
            schema_name="msggroup_non_k12",
            school_type=SchoolTenant.NON_K12,
            is_active=True,
        )
        self.k12_school = SchoolTenant.objects.create(
            name="Primary Academy",
            schema_name="msggroup_k12",
            school_type=SchoolTenant.K12,
            is_active=True,
        )
        self.other_non_k12_school = SchoolTenant.objects.create(
            name="Other Vocational Academy",
            schema_name="msggroup_other_non_k12",
            school_type=SchoolTenant.NON_K12,
            is_active=True,
        )

        def make_student(email, tenant, first_name="Student"):
            return User.objects.create_user(
                email=email,
                password="StudentPass123",
                first_name=first_name,
                last_name="Learner",
                role="student",
                tenant=tenant,
                is_active=True,
                is_verified=True,
            )

        self.alice = make_student("alice@msggroup.edu", self.non_k12_school, "Alice")
        self.bob = make_student("bob@msggroup.edu", self.non_k12_school, "Bob")
        self.carol = make_student("carol@msggroup.edu", self.non_k12_school, "Carol")
        self.teacher = User.objects.create_user(
            email="teacher@msggroup.edu",
            password="TeacherPass123",
            first_name="Teacher",
            last_name="Staff",
            role="teacher",
            tenant=self.non_k12_school,
            is_active=True,
            is_verified=True,
        )
        self.k12_student = make_student("k12student@msggroup.edu", self.k12_school, "K12")
        self.outsider = make_student("outsider@msggroup.edu", self.other_non_k12_school, "Outsider")

    def _create_group(self, user, name="Study Squad", member_emails=None):
        self.client.force_authenticate(user=user)
        return self.client.post(
            "/api/app/messages/groups/",
            data={"name": f"{name} [{self._testMethodName}]", "member_emails": member_emails or []},
            format="json",
        )

    def test_non_k12_student_can_create_group_with_classmates(self):
        response = self._create_group(self.alice, member_emails=[self.bob.email, self.carol.email])

        self.assertEqual(response.status_code, 201, response.data)
        self.assertTrue(response.data["success"])
        group = response.data["group"]
        self.assertTrue(group["name"].startswith("Study Squad"))
        self.assertEqual(group["member_count"], 3)
        member_emails = {m["email"] for m in group["members"]}
        self.assertEqual(member_emails, {self.alice.email, self.bob.email, self.carol.email})

    def test_k12_student_cannot_create_group(self):
        response = self._create_group(self.k12_student, member_emails=[self.bob.email])

        self.assertEqual(response.status_code, 403)
        self.assertFalse(response.data["success"])
        self.assertFalse(MessageGroup.objects.exists())

    def test_teacher_cannot_create_group(self):
        response = self._create_group(self.teacher, member_emails=[self.bob.email])

        self.assertEqual(response.status_code, 403)
        self.assertFalse(MessageGroup.objects.exists())

    def test_cannot_add_student_from_another_tenant(self):
        response = self._create_group(self.alice, member_emails=[self.outsider.email])

        self.assertEqual(response.status_code, 400)
        self.assertFalse(response.data["success"])
        self.assertFalse(MessageGroup.objects.exists())

    def test_group_requires_at_least_one_valid_member(self):
        response = self._create_group(self.alice, member_emails=[])

        self.assertEqual(response.status_code, 400)
        self.assertFalse(MessageGroup.objects.exists())

    def test_member_can_send_and_read_group_messages(self):
        create_response = self._create_group(self.alice, member_emails=[self.bob.email])
        group_id = create_response.data["group"]["id"]

        self.client.force_authenticate(user=self.alice)
        send_response = self.client.post(
            f"/api/app/messages/groups/{group_id}/messages/",
            data={"body": "Anyone free to study tonight?"},
            format="json",
        )
        self.assertEqual(send_response.status_code, 201, send_response.data)
        self.assertTrue(send_response.data["group_message"]["outgoing"])

        self.client.force_authenticate(user=self.bob)
        detail_response = self.client.get(f"/api/app/messages/groups/{group_id}/")
        self.assertEqual(detail_response.status_code, 200)
        messages = detail_response.data["group"]["messages"]
        self.assertEqual(len(messages), 1)
        self.assertEqual(messages[0]["body"], "Anyone free to study tonight?")
        self.assertFalse(messages[0]["outgoing"])
        self.assertEqual(detail_response.data["group"]["unread"], 1)

        mark_read_response = self.client.post(f"/api/app/messages/groups/{group_id}/read/")
        self.assertEqual(mark_read_response.status_code, 200)
        detail_after_read = self.client.get(f"/api/app/messages/groups/{group_id}/")
        self.assertEqual(detail_after_read.data["group"]["unread"], 0)

    def test_non_member_cannot_view_or_message_group(self):
        create_response = self._create_group(self.alice, member_emails=[self.bob.email])
        group_id = create_response.data["group"]["id"]

        self.client.force_authenticate(user=self.carol)
        detail_response = self.client.get(f"/api/app/messages/groups/{group_id}/")
        self.assertEqual(detail_response.status_code, 404)

        send_response = self.client.post(
            f"/api/app/messages/groups/{group_id}/messages/",
            data={"body": "I shouldn't be able to post this."},
            format="json",
        )
        self.assertEqual(send_response.status_code, 404)

    def test_cross_tenant_student_cannot_access_group_even_with_id(self):
        create_response = self._create_group(self.alice, member_emails=[self.bob.email])
        group_id = create_response.data["group"]["id"]

        self.client.force_authenticate(user=self.outsider)
        response = self.client.get(f"/api/app/messages/groups/{group_id}/")
        self.assertEqual(response.status_code, 404)

    def test_member_can_add_new_classmate(self):
        create_response = self._create_group(self.alice, member_emails=[self.bob.email])
        group_id = create_response.data["group"]["id"]

        self.client.force_authenticate(user=self.bob)
        response = self.client.post(
            f"/api/app/messages/groups/{group_id}/members/",
            data={"member_emails": [self.carol.email]},
            format="json",
        )
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data["group"]["member_count"], 3)

    def test_member_can_leave_group_and_group_survives_with_remaining_members(self):
        create_response = self._create_group(self.alice, member_emails=[self.bob.email, self.carol.email])
        group_id = create_response.data["group"]["id"]

        self.client.force_authenticate(user=self.carol)
        response = self.client.post(f"/api/app/messages/groups/{group_id}/leave/")
        self.assertEqual(response.status_code, 200)

        group = MessageGroup.objects.get(id=group_id)
        self.assertEqual(group.memberships.count(), 2)
        self.assertFalse(group.memberships.filter(user=self.carol).exists())

    def test_group_is_deleted_once_last_member_leaves(self):
        create_response = self._create_group(self.alice, member_emails=[self.bob.email])
        group_id = create_response.data["group"]["id"]

        # Both leave calls hit the identical (method, path, body) tuple, and the
        # idempotency middleware can't see the real user under force_authenticate
        # (DRF auth resolves after this middleware runs) — clear the cache between
        # them so the second call isn't served a replayed response from the first.
        self.client.force_authenticate(user=self.bob)
        self.client.post(f"/api/app/messages/groups/{group_id}/leave/")
        from django.core.cache import cache as django_cache
        django_cache.clear()
        self.client.force_authenticate(user=self.alice)
        self.client.post(f"/api/app/messages/groups/{group_id}/leave/")

        self.assertFalse(MessageGroup.objects.filter(id=group_id).exists())

    def test_groups_list_only_shows_own_tenant_groups(self):
        self._create_group(self.alice, member_emails=[self.bob.email])

        self.client.force_authenticate(user=self.outsider)
        response = self.client.get("/api/app/messages/groups/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["groups"], [])

    def test_messages_snapshot_reports_can_create_groups_flag(self):
        self.client.force_authenticate(user=self.alice)
        non_k12_response = self.client.get("/api/app/messages/")
        self.assertTrue(non_k12_response.data["can_create_groups"])

        self.client.force_authenticate(user=self.k12_student)
        k12_response = self.client.get("/api/app/messages/")
        self.assertFalse(k12_response.data["can_create_groups"])


class KidsMonitorExpiryTests(TestCase):
    """Non-K12 Child Monitor subscriptions renew monthly, like activation credits;
    K12 stays indefinite until an admin manually deactivates it."""

    def setUp(self):
        self.non_k12_school = SchoolTenant.objects.create(
            name="Vocational Academy",
            schema_name="km_non_k12_20260306",
            school_type=SchoolTenant.NON_K12,
            is_active=True,
        )
        self.k12_school = SchoolTenant.objects.create(
            name="Primary School",
            schema_name="km_k12_20260306",
            school_type=SchoolTenant.K12,
            is_active=True,
        )
        self.admin = User.objects.create_user(
            email="km.admin@school.edu",
            password="AdminPass123",
            first_name="KM",
            last_name="Admin",
            role="school_admin",
            tenant=self.non_k12_school,
            is_active=True,
            is_verified=True,
        )
        parent_user = User.objects.create_user(
            email="km.parent@school.edu",
            password="ParentPass123",
            first_name="KM",
            last_name="Parent",
            role="parent",
            tenant=self.non_k12_school,
            is_active=True,
            is_verified=True,
        )
        self.parent_profile = ParentProfile.objects.create(user=parent_user)
        self.client = APIClient()

    def test_activation_sets_one_month_expiry_for_non_k12(self):
        sub = activate_kids_monitor_subscription(self.parent_profile, self.non_k12_school, reference="km-test-1")
        self.assertTrue(sub.is_active)
        self.assertIsNotNone(sub.expires_at)
        self.assertTrue(sub.is_currently_active)
        self.assertLess(sub.expires_at, timezone.now() + timedelta(days=32))
        self.assertGreater(sub.expires_at, timezone.now() + timedelta(days=27))

    def test_activation_leaves_no_expiry_for_k12(self):
        k12_parent_user = User.objects.create_user(
            email="km.k12.parent@school.edu",
            password="ParentPass123",
            first_name="KM",
            last_name="K12Parent",
            role="parent",
            tenant=self.k12_school,
            is_active=True,
            is_verified=True,
        )
        k12_parent_profile = ParentProfile.objects.create(user=k12_parent_user)
        sub = activate_kids_monitor_subscription(k12_parent_profile, self.k12_school, reference="km-test-2")
        self.assertTrue(sub.is_active)
        self.assertIsNone(sub.expires_at)
        self.assertTrue(sub.is_currently_active)

    def test_is_currently_active_respects_expiry(self):
        sub = KidsMonitorSubscription.objects.create(
            parent=self.parent_profile,
            school=self.non_k12_school,
            is_active=True,
            activated_at=timezone.now(),
            expires_at=timezone.now() - timedelta(days=1),
        )
        self.assertFalse(sub.is_currently_active)

    def test_kids_monitor_verify_endpoint_sets_expiry_for_non_k12(self):
        self.client.force_authenticate(user=self.admin)
        with patch("finance.services.verify_paystack_transaction", return_value={"status": "success"}):
            response = self.client.post(
                f"/api/app/kids-monitor/{self.parent_profile.id}/verify/",
                data={"reference": "km-endpoint-test"},
                format="json",
            )
        self.assertEqual(response.status_code, 200, response.data)
        self.assertTrue(response.data["success"])
        self.assertIsNotNone(response.data.get("expires_at"))
        sub = KidsMonitorSubscription.objects.get(parent=self.parent_profile)
        self.assertTrue(sub.is_active)
        self.assertIsNotNone(sub.expires_at)

    def test_kids_monitor_initiate_blocks_active_but_allows_renewal_after_expiry(self):
        self.client.force_authenticate(user=self.admin)
        activate_kids_monitor_subscription(self.parent_profile, self.non_k12_school, reference="km-active")

        blocked = self.client.post(f"/api/app/kids-monitor/{self.parent_profile.id}/initiate/", format="json")
        self.assertEqual(blocked.status_code, 400)
        self.assertFalse(blocked.data["success"])

        sub = self.parent_profile.kids_monitor
        sub.expires_at = timezone.now() - timedelta(days=1)
        sub.save(update_fields=["expires_at"])

        with patch("finance.services.verify_paystack_transaction", return_value={"status": "success"}):
            renewed = self.client.post(f"/api/app/kids-monitor/{self.parent_profile.id}/initiate/", format="json")
        self.assertEqual(renewed.status_code, 200, renewed.data)
        self.assertTrue(renewed.data["success"])
        self.assertTrue(renewed.data.get("already_paid"))
        sub.refresh_from_db()
        self.assertTrue(sub.is_currently_active)

    @patch("requests.post")
    def test_fresh_initiate_does_not_call_paystack_initialize_itself(self, mock_post):
        """Regression: kids_monitor_initiate used to call Paystack's
        /transaction/initialize server-side, then hand the same reference to
        the frontend's PaystackPop.setup({ref, ...}), which performs its own
        initialize/charge - Paystack rejects re-initializing the same
        reference, so the popup failed with "Duplicate transaction
        reference" on every attempt."""
        self.client.force_authenticate(user=self.admin)

        response = self.client.post(f"/api/app/kids-monitor/{self.parent_profile.id}/initiate/", format="json")

        self.assertEqual(response.status_code, 200, response.data)
        self.assertTrue(response.data["success"])
        self.assertTrue(response.data["reference"].startswith("km-"))
        mock_post.assert_not_called()

        sub = KidsMonitorSubscription.objects.get(parent=self.parent_profile)
        self.assertFalse(sub.is_active)
        self.assertEqual(sub.paystack_ref, response.data["reference"])


@override_settings(ADMIN_OTP_DEBUG_CODE_ENABLED=True)
class PasswordResetOtpTests(TestCase):
    def setUp(self):
        # This class calls password-reset endpoints many times across its
        # methods, all sharing the same per-IP 'auth' throttle scope (see
        # users.views.AuthRateThrottle) - clear it so one method's calls
        # don't push a later method over the limit.
        from django.core.cache import cache as django_cache
        django_cache.clear()
        self.client = APIClient()
        # Unique-per-test email: the IdempotencyMiddleware dedupes identical
        # (anon user, method, path, body) requests for 10s, so reusing the
        # same email across test methods would replay a stale cached response.
        # role="parent" avoids the strict school_code-at-login requirement that
        # applies to teacher/student/staff/accountant roles — irrelevant here
        # since password reset itself is role-agnostic.
        self.user = User.objects.create_user(
            email=f"reset.{self._testMethodName}@school.edu",
            password="OldPass123",
            first_name="Reset",
            last_name="Me",
            role="parent",
            is_active=True,
            is_verified=True,
        )

    @patch("users.views.send_mail", return_value=1)
    @patch("users.views.render_to_string", return_value="<p>code</p>")
    def _request_otp(self, _render_to_string, _send_mail):
        response = self.client.post(
            "/api/auth/password-reset/",
            data={"email": self.user.email},
            format="json",
        )
        return response

    def test_request_reset_sends_otp_and_matches_shape_for_unknown_email(self):
        real_response = self._request_otp()
        self.assertEqual(real_response.status_code, 200)
        self.assertTrue(real_response.data["success"])
        self.assertTrue(real_response.data["requires_otp"])
        self.assertTrue(real_response.data["otp_challenge"])
        self.assertIn("debug_otp", real_response.data)

        fake_response = self.client.post(
            "/api/auth/password-reset/",
            data={"email": "no.such.user@school.edu"},
            format="json",
        )
        self.assertEqual(fake_response.status_code, 200)
        self.assertTrue(fake_response.data["success"])
        self.assertTrue(fake_response.data["requires_otp"])
        self.assertTrue(fake_response.data["otp_challenge"])
        # Anti-enumeration: identical message regardless of whether the account exists.
        self.assertEqual(fake_response.data["message"], real_response.data["message"])
        self.assertNotIn("debug_otp", fake_response.data)

    def test_confirm_with_correct_code_resets_password(self):
        otp_response = self._request_otp()
        code = otp_response.data["debug_otp"]
        challenge = otp_response.data["otp_challenge"]

        confirm_response = self.client.post(
            "/api/auth/password-reset/confirm/",
            data={
                "email": self.user.email,
                "code": code,
                "challenge": challenge,
                "password": "BrandNewPass123",
                "confirm_password": "BrandNewPass123",
            },
            format="json",
        )
        self.assertEqual(confirm_response.status_code, 200)
        self.assertTrue(confirm_response.data["success"])

        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password("BrandNewPass123"))
        self.assertIsNone(self.user.password_reset_token)
        self.assertIsNone(self.user.password_reset_challenge)

    def test_confirm_with_wrong_code_decrements_attempts_and_eventually_locks_code(self):
        otp_response = self._request_otp()
        challenge = otp_response.data["otp_challenge"]

        last_response = None
        for _ in range(5):
            last_response = self.client.post(
                "/api/auth/password-reset/confirm/",
                data={
                    "email": self.user.email,
                    "code": "000000",
                    "challenge": challenge,
                    "password": "BrandNewPass123",
                    "confirm_password": "BrandNewPass123",
                },
                format="json",
            )
            self.assertEqual(last_response.status_code, 400)
            self.assertFalse(last_response.data["success"])

        self.assertIn("too many", last_response.data["message"].lower())

        self.user.refresh_from_db()
        self.assertIsNone(self.user.password_reset_token)

        # Old password must still work — nothing was actually reset.
        self.assertTrue(self.user.check_password("OldPass123"))

    def test_confirm_rejects_expired_code(self):
        otp_response = self._request_otp()
        code = otp_response.data["debug_otp"]
        challenge = otp_response.data["otp_challenge"]

        self.user.refresh_from_db()
        self.user.password_reset_sent_at = timezone.now() - timedelta(minutes=11)
        self.user.save(update_fields=["password_reset_sent_at"])

        response = self.client.post(
            "/api/auth/password-reset/confirm/",
            data={
                "email": self.user.email,
                "code": code,
                "challenge": challenge,
                "password": "BrandNewPass123",
                "confirm_password": "BrandNewPass123",
            },
            format="json",
        )
        self.assertEqual(response.status_code, 400)
        self.assertFalse(response.data["success"])
        self.assertIn("expired", response.data["message"].lower())

    def test_confirm_rejects_mismatched_challenge(self):
        otp_response = self._request_otp()
        code = otp_response.data["debug_otp"]

        response = self.client.post(
            "/api/auth/password-reset/confirm/",
            data={
                "email": self.user.email,
                "code": code,
                "challenge": "not-the-right-challenge",
                "password": "BrandNewPass123",
                "confirm_password": "BrandNewPass123",
            },
            format="json",
        )
        self.assertEqual(response.status_code, 400)
        self.assertFalse(response.data["success"])

    @patch("users.views.send_mail", return_value=1)
    @patch("users.views.render_to_string", return_value="<p>code</p>")
    def test_resend_issues_a_new_challenge(self, _render_to_string, _send_mail):
        otp_response = self._request_otp()
        first_challenge = otp_response.data["otp_challenge"]

        resend_response = self.client.post(
            "/api/auth/password-reset/resend/",
            data={"email": self.user.email, "challenge": first_challenge},
            format="json",
        )
        self.assertEqual(resend_response.status_code, 200)
        self.assertTrue(resend_response.data["success"])
        self.assertTrue(resend_response.data["otp_challenge"])
        self.assertNotEqual(resend_response.data["otp_challenge"], first_challenge)


class SchoolActivitiesOnTimetableTests(TestCase):
    """Admin-set school activities should surface to students, teachers, and
    non-teaching staff via the shared timetables endpoint."""

    def setUp(self):
        self.client = APIClient()
        self.school = SchoolTenant.objects.create(
            name="Activities School",
            schema_name="activities_school_20260716",
            is_active=True,
        )
        self.tenant = Tenant.objects.create(slug=self.school.schema_name, name=self.school.name)
        self.student_user = User.objects.create_user(
            email="student@activities.edu",
            password="StudentPass123",
            first_name="Stu",
            last_name="Dent",
            role="student",
            tenant=self.school,
            is_active=True,
            is_verified=True,
        )
        self.teacher_user = User.objects.create_user(
            email="teacher@activities.edu",
            password="TeacherPass123",
            first_name="Tea",
            last_name="Cher",
            role="teacher",
            tenant=self.school,
            is_active=True,
            is_verified=True,
        )
        self.staff_user = User.objects.create_user(
            email="staff@activities.edu",
            password="StaffPass123",
            first_name="Non",
            last_name="Teaching",
            role="staff",
            tenant=self.school,
            is_active=True,
            is_verified=True,
        )
        today = timezone.localdate()
        self.upcoming_activity = SchoolActivityCalendar.objects.create(
            tenant=self.tenant,
            month=today.month,
            year=today.year,
            title="Inter-House Sports",
            activity_date=today + timedelta(days=5),
            description="Annual sports day",
            color="#22C55E",
        )
        self.past_activity = SchoolActivityCalendar.objects.create(
            tenant=self.tenant,
            month=1,
            year=2020,
            title="Old Assembly",
            activity_date=date(2020, 1, 10),
        )

    def _activity_titles(self, response):
        return [item["title"] for item in response.data["school_activities"]]

    def test_student_sees_upcoming_school_activity_not_past_one(self):
        self.client.force_authenticate(user=self.student_user)
        response = self.client.get("/api/app/timetables/")

        self.assertEqual(response.status_code, 200)
        titles = self._activity_titles(response)
        self.assertIn("Inter-House Sports", titles)
        self.assertNotIn("Old Assembly", titles)

    def test_teacher_sees_upcoming_school_activity(self):
        self.client.force_authenticate(user=self.teacher_user)
        response = self.client.get("/api/app/timetables/")

        self.assertEqual(response.status_code, 200)
        self.assertIn("Inter-House Sports", self._activity_titles(response))

    def test_non_teaching_staff_sees_upcoming_school_activity(self):
        self.client.force_authenticate(user=self.staff_user)
        response = self.client.get("/api/app/timetables/")

        self.assertEqual(response.status_code, 200)
        # Staff have no class assigned, so no timetable entries - but they
        # should still see tenant-wide school activities.
        self.assertEqual(response.data["entries"], [])
        self.assertIn("Inter-House Sports", self._activity_titles(response))


class AuthRateThrottleTests(TestCase):
    """Login/register/create-school/password-reset used to have zero rate
    limiting - a script could brute-force credentials with no server-side
    slowdown at all."""

    def setUp(self):
        from django.core.cache import cache as django_cache
        django_cache.clear()
        self.client = APIClient()

    def tearDown(self):
        from django.core.cache import cache as django_cache
        django_cache.clear()

    def test_login_gets_throttled_after_too_many_attempts_from_same_ip(self):
        for _ in range(20):
            response = self.client.post(
                "/api/auth/login/",
                {"email": "nobody@nowhere.test", "password": "wrong"},
                format="json",
            )
            self.assertNotEqual(response.status_code, 429)

        throttled = self.client.post(
            "/api/auth/login/",
            {"email": "nobody@nowhere.test", "password": "wrong"},
            format="json",
        )
        self.assertEqual(throttled.status_code, 429)

    def test_throttle_bucket_is_shared_across_the_auth_endpoints(self):
        """login and create-school share the same 'auth' scope/IP bucket -
        a script can't dodge the limit by rotating which endpoint it hits."""
        for _ in range(20):
            self.client.post(
                "/api/auth/login/",
                {"email": "nobody@nowhere.test", "password": "wrong"},
                format="json",
            )

        throttled = self.client.post(
            "/api/auth/create-school/",
            {"school_name": "Throttle Test Academy", "email": "throttle@test.edu"},
            format="json",
        )
        self.assertEqual(throttled.status_code, 429)


class StudentActivityTitleNonK12Tests(TestCase):
    """Student activity titles (leadership/extracurricular roles) are a
    K-12-only feature - Non-K12 schools must not be able to see, manage, or
    assign them at all."""

    def setUp(self):
        self.client = APIClient()
        self.k12_school = SchoolTenant.objects.create(
            name="K12 Activity School", schema_name="k12_activity_school", school_type=SchoolTenant.K12, is_active=True,
        )
        self.non_k12_school = SchoolTenant.objects.create(
            name="Non-K12 Activity School", schema_name="non_k12_activity_school", school_type=SchoolTenant.NON_K12, is_active=True,
        )
        self.k12_admin = User.objects.create_user(
            email="k12.admin@activity.edu", password="AdminPass123", first_name="K12", last_name="Admin",
            role="school_admin", tenant=self.k12_school, is_active=True, is_verified=True,
        )
        self.non_k12_admin = User.objects.create_user(
            email="nonk12.admin@activity.edu", password="AdminPass123", first_name="NonK12", last_name="Admin",
            role="school_admin", tenant=self.non_k12_school, is_active=True, is_verified=True,
        )
        self.k12_legacy_tenant = Tenant.objects.create(name=self.k12_school.name, slug=self.k12_school.schema_name)
        self.non_k12_legacy_tenant = Tenant.objects.create(name=self.non_k12_school.name, slug=self.non_k12_school.schema_name)
        self.k12_class = Class.objects.create(name="Grade 5", section="A", tenant=self.k12_legacy_tenant)
        self.non_k12_class = Class.objects.create(name="Cohort 1", section="A", tenant=self.non_k12_legacy_tenant)

    def test_k12_admin_can_list_and_create_activity_titles(self):
        self.client.force_authenticate(user=self.k12_admin)

        listed = self.client.get("/api/app/students/activity-titles/")
        self.assertEqual(listed.status_code, 200)

        created = self.client.post(
            "/api/app/students/activity-titles/",
            {"name": "Head Boy", "star_rating": "5"},
            format="json",
        )
        self.assertEqual(created.status_code, 201, created.data)

    def test_non_k12_admin_cannot_list_activity_titles(self):
        self.client.force_authenticate(user=self.non_k12_admin)
        response = self.client.get("/api/app/students/activity-titles/")
        self.assertEqual(response.status_code, 403)

    def test_non_k12_admin_cannot_create_activity_title(self):
        self.client.force_authenticate(user=self.non_k12_admin)
        response = self.client.post(
            "/api/app/students/activity-titles/",
            {"name": "Cohort Lead", "star_rating": "3"},
            format="json",
        )
        self.assertEqual(response.status_code, 403)
        self.assertFalse(StudentActivityTitle.objects.filter(tenant=self.non_k12_school, name="Cohort Lead").exists())

    def test_non_k12_admin_cannot_update_or_delete_existing_activity_title(self):
        title = StudentActivityTitle.objects.create(tenant=self.non_k12_school, name="Leftover Title", star_rating=2)
        self.client.force_authenticate(user=self.non_k12_admin)

        patched = self.client.patch(
            f"/api/app/students/activity-titles/{title.id}/",
            {"name": "Renamed"},
            format="json",
        )
        self.assertEqual(patched.status_code, 403)

        deleted = self.client.delete(f"/api/app/students/activity-titles/{title.id}/")
        self.assertEqual(deleted.status_code, 403)

    def test_creating_student_with_activity_title_id_is_ignored_for_non_k12(self):
        title = StudentActivityTitle.objects.create(tenant=self.non_k12_school, name="Ignored Title", star_rating=1)
        self.client.force_authenticate(user=self.non_k12_admin)

        response = self.client.post(
            "/api/app/students/create/",
            {
                "student_email": "nonk12.student@activity.edu",
                "first_name": "NonK12",
                "last_name": "Student",
                "guardian_name": "Guardian",
                "guardian_phone": "+15550001111",
                "student_password": "StudentPass123",
                "confirm_student_password": "StudentPass123",
                "class_id": self.non_k12_class.id,
                "extra_curricular_activity_title_id": str(title.id),
            },
        )

        self.assertEqual(response.status_code, 201, response.data)
        profile = StudentProfile.objects.get(user__email="nonk12.student@activity.edu")
        self.assertIsNone(profile.extra_curricular_activity_title)

    def test_creating_student_with_activity_title_id_still_works_for_k12(self):
        title = StudentActivityTitle.objects.create(tenant=self.k12_school, name="Class Prefect", star_rating=4)
        self.client.force_authenticate(user=self.k12_admin)

        response = self.client.post(
            "/api/app/students/create/",
            {
                "student_email": "k12.student@activity.edu",
                "first_name": "K12",
                "last_name": "Student",
                "guardian_name": "Guardian",
                "guardian_phone": "+15550002222",
                "student_password": "StudentPass123",
                "confirm_student_password": "StudentPass123",
                "class_id": self.k12_class.id,
                "extra_curricular_activity_title_id": str(title.id),
            },
        )

        self.assertEqual(response.status_code, 201, response.data)
        profile = StudentProfile.objects.get(user__email="k12.student@activity.edu")
        self.assertEqual(profile.extra_curricular_activity_title_id, title.id)

    def test_editing_student_with_activity_title_id_is_ignored_for_non_k12(self):
        title = StudentActivityTitle.objects.create(tenant=self.non_k12_school, name="Ignored Edit Title", star_rating=1)
        self.client.force_authenticate(user=self.non_k12_admin)

        created = self.client.post(
            "/api/app/students/create/",
            {
                "student_email": "nonk12.edit@activity.edu",
                "first_name": "NonK12",
                "last_name": "Edit",
                "guardian_name": "Guardian",
                "guardian_phone": "+15550003333",
                "student_password": "StudentPass123",
                "confirm_student_password": "StudentPass123",
                "class_id": self.non_k12_class.id,
            },
        )
        self.assertEqual(created.status_code, 201, created.data)
        student_id = created.data["student"]["id"]

        response = self.client.patch(
            f"/api/app/students/{student_id}/",
            {"extra_curricular_activity_title_id": str(title.id)},
            format="json",
        )

        self.assertEqual(response.status_code, 200, response.data)
        profile = StudentProfile.objects.get(user__email="nonk12.edit@activity.edu")
        self.assertIsNone(profile.extra_curricular_activity_title)


class ProprietorDashboardAPITests(TestCase):
    """school_superadmin (proprietor) accounts have no single tenant - they
    manage several schools under one SchoolGroup instead. See
    users/proprietor_views.py."""

    def setUp(self):
        self.client = APIClient()
        self.proprietor = User.objects.create_user(
            email="owner@xcelgroup.edu",
            password="OwnerPass123",
            first_name="Xcel",
            last_name="Owner",
            role="school_superadmin",
            is_active=True,
            is_verified=True,
        )
        self.group = SchoolGroup.objects.create(name="Xcel Schools Group", owner=self.proprietor)
        self.proprietor.school_group = self.group
        self.proprietor.save(update_fields=["school_group"])
        self.client.force_authenticate(user=self.proprietor)

    def test_overview_returns_group_name_and_empty_schools_list(self):
        response = self.client.get("/api/app/proprietor/overview/")
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data["school_group"]["name"], "Xcel Schools Group")
        self.assertEqual(response.data["schools"], [])
        self.assertEqual(response.data["totals"]["students"], 0)

    def test_create_school_creates_real_tenant_linked_to_group(self):
        response = self.client.post(
            "/api/app/proprietor/schools/",
            {"name": "Xcel Academy - Lekki", "address": "12 Admiralty Way", "email": "lekki@xcelgroup.edu"},
            format="json",
        )
        self.assertEqual(response.status_code, 201, response.data)
        school = SchoolTenant.objects.get(name="Xcel Academy - Lekki")
        self.assertEqual(school.school_group_id, self.group.id)
        self.assertTrue(school.schema_name)

        overview = self.client.get("/api/app/proprietor/overview/")
        self.assertEqual(len(overview.data["schools"]), 1)
        self.assertEqual(overview.data["schools"][0]["name"], "Xcel Academy - Lekki")

    def test_create_school_requires_a_name(self):
        response = self.client.post("/api/app/proprietor/schools/", {"name": "  "}, format="json")
        self.assertEqual(response.status_code, 400)

    def test_add_school_admin_creates_user_sends_email_and_hides_password(self):
        school = SchoolTenant.objects.create(
            name="Xcel Academy - Ikeja",
            schema_name="xcel_ikeja",
            school_group=self.group,
        )
        mail.outbox = []
        response = self.client.post(
            f"/api/app/proprietor/schools/{school.id}/admins/",
            {"name": "Jane Doe", "email": "jane@xcelgroup.edu", "role": "principal"},
            format="json",
        )
        self.assertEqual(response.status_code, 201, response.data)
        self.assertTrue(response.data["invited"])
        self.assertNotIn("password", str(response.data).lower())

        new_admin = User.objects.get(email="jane@xcelgroup.edu")
        self.assertEqual(new_admin.role, "principal")
        self.assertEqual(new_admin.tenant_id, school.id)
        self.assertEqual(new_admin.school_group_id, self.group.id)

        self.assertEqual(len(mail.outbox), 1)
        self.assertIn("jane@xcelgroup.edu", mail.outbox[0].to)
        self.assertIn(school.schema_name, mail.outbox[0].body)

    def test_add_school_admin_rejects_school_outside_group(self):
        other_school = SchoolTenant.objects.create(name="Rival School", schema_name="rival_school")
        response = self.client.post(
            f"/api/app/proprietor/schools/{other_school.id}/admins/",
            {"name": "Jane Doe", "email": "jane@rival.edu", "role": "school_admin"},
            format="json",
        )
        self.assertEqual(response.status_code, 404)
        self.assertFalse(User.objects.filter(email="jane@rival.edu").exists())

    def test_add_school_admin_rejects_duplicate_email(self):
        school = SchoolTenant.objects.create(name="Xcel Academy - Yaba", schema_name="xcel_yaba", school_group=self.group)
        User.objects.create_user(email="taken@xcelgroup.edu", password="Pass1234", role="teacher", is_active=True)
        response = self.client.post(
            f"/api/app/proprietor/schools/{school.id}/admins/",
            {"name": "Jane Doe", "email": "taken@xcelgroup.edu", "role": "school_admin"},
            format="json",
        )
        self.assertEqual(response.status_code, 400)

    def test_finance_rollup_aggregates_across_schools(self):
        SchoolTenant.objects.create(name="Xcel A", schema_name="xcel_a", school_group=self.group)
        SchoolTenant.objects.create(name="Xcel B", schema_name="xcel_b", school_group=self.group)
        response = self.client.get("/api/app/proprietor/finance/")
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(len(response.data["schools"]), 2)
        self.assertIn("top_defaulters", response.data)

    def test_finance_export_returns_csv(self):
        response = self.client.get("/api/app/proprietor/finance/export/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "text/csv")

    def test_non_proprietor_gets_403_on_proprietor_routes(self):
        school = SchoolTenant.objects.create(name="Some School", schema_name="some_school")
        admin_user = User.objects.create_user(
            email="admin@someschool.edu",
            password="AdminPass123",
            role="school_admin",
            tenant=school,
            is_active=True,
            is_verified=True,
        )
        self.client.force_authenticate(user=admin_user)

        self.assertEqual(self.client.get("/api/app/proprietor/overview/").status_code, 403)
        self.assertEqual(self.client.post("/api/app/proprietor/schools/", {"name": "X"}, format="json").status_code, 403)
        self.assertEqual(self.client.get("/api/app/proprietor/finance/").status_code, 403)

    def test_registration_creates_group_but_no_tenant(self):
        """Regression test for the original bug report: signing up as
        school_superadmin must create a SchoolGroup and leave tenant unset -
        schools are added afterwards from the dashboard, not at signup."""
        response = self.client.post(
            "/api/auth/register/",
            {
                "first_name": "New",
                "last_name": "Owner",
                "email": "newowner@group.edu",
                "password": "OwnerPass123",
                "confirm_password": "OwnerPass123",
                "role": "school_superadmin",
                "school_group_name": "New Owner Group",
                "phone": "+15550009999",
                "terms_accepted": True,
            },
            format="json",
        )
        self.assertEqual(response.status_code, 201, response.data)
        new_user = User.objects.get(email="newowner@group.edu")
        self.assertIsNone(new_user.tenant)
        self.assertIsNotNone(new_user.school_group)
        self.assertEqual(new_user.school_group.name, "New Owner Group")


class ClassBroadsheetFeatureTests(TestCase):
    """Student search + class broadsheet aggregation + parent resolution +
    SMS-sharing, all sharing one rich fixture: two classes, a term, students
    with/without scores, and parents covering every edge case the feature
    needs to get right (sibling in another class, twins in the same class,
    a parent with no child in the class at all, a parent with no phone)."""

    def setUp(self):
        self.client = APIClient()
        self.school = SchoolTenant.objects.create(name="Broadsheet School", schema_name="broadsheet_school", is_active=True)
        self.legacy_tenant = Tenant.objects.create(name=self.school.name, slug=self.school.schema_name)

        self.admin = User.objects.create_user(
            email="admin@broadsheet.edu", password="AdminPass123", first_name="Ada", last_name="Min",
            role="school_admin", tenant=self.school, is_active=True, is_verified=True,
        )

        self.class_a = Class.objects.create(tenant=self.legacy_tenant, name="Basic 1", section="A")
        self.class_b = Class.objects.create(tenant=self.legacy_tenant, name="Basic 2", section="A")
        self.term = Term.objects.create(
            tenant=self.legacy_tenant, name="First Term",
            start_date=timezone.localdate(), end_date=timezone.localdate() + timedelta(days=90),
        )
        self.other_term = Term.objects.create(
            tenant=self.legacy_tenant, name="Second Term",
            start_date=timezone.localdate() + timedelta(days=91), end_date=timezone.localdate() + timedelta(days=180),
        )

        self.math = Subject.objects.create(tenant=self.legacy_tenant, name="Mathematics", code="MATH")
        self.english = Subject.objects.create(tenant=self.legacy_tenant, name="English Language", code="ENG")
        self.science = Subject.objects.create(tenant=self.legacy_tenant, name="Basic Science", code="SCI")

        def make_student(email, first, last, student_id, class_group):
            user = User.objects.create_user(
                email=email, password="StudentPass123", first_name=first, last_name=last,
                role="student", tenant=self.school, is_active=True, is_verified=True,
            )
            return StudentProfile.objects.create(
                user=user, student_id=student_id, admission_number=f"ADM-{student_id}",
                admission_date=timezone.localdate(), guardian_name="Guardian", guardian_relation="Parent",
                current_class=class_group,
            )

        self.student1 = make_student("s1@broadsheet.edu", "Ada", "Okoro", "BS001", self.class_a)
        self.student2 = make_student("s2@broadsheet.edu", "Bola", "Okoro", "BS002", self.class_a)
        self.student3 = make_student("s3@broadsheet.edu", "Chidi", "Eze", "BS003", self.class_a)  # no scores
        self.twin1 = make_student("twin1@broadsheet.edu", "Tayo", "Twin", "BS004", self.class_a)
        self.twin2 = make_student("twin2@broadsheet.edu", "Kehinde", "Twin", "BS005", self.class_a)
        self.student_b = make_student("sb@broadsheet.edu", "Dami", "Lawal", "BS010", self.class_b)

        StudentSubjectScore.objects.create(student=self.student1, subject=self.math, class_group=self.class_a, term=self.term, score=Decimal("90"), max_score=Decimal("100"), grade="A", approval_status=ResultBatch.PUBLISHED)
        StudentSubjectScore.objects.create(student=self.student1, subject=self.english, class_group=self.class_a, term=self.term, score=Decimal("80"), max_score=Decimal("100"), grade="B", approval_status=ResultBatch.PUBLISHED)
        StudentSubjectScore.objects.create(student=self.student2, subject=self.math, class_group=self.class_a, term=self.term, score=Decimal("60"), max_score=Decimal("100"), grade="C", approval_status=ResultBatch.PUBLISHED)
        StudentSubjectScore.objects.create(student=self.student2, subject=self.english, class_group=self.class_a, term=self.term, score=Decimal("55"), max_score=Decimal("100"), grade="C", approval_status=ResultBatch.PUBLISHED)
        # Unpublished - must not count unless include_unpublished=True.
        StudentSubjectScore.objects.create(student=self.student1, subject=self.science, class_group=self.class_a, term=self.term, score=Decimal("100"), max_score=Decimal("100"), grade="A", approval_status=ResultBatch.PENDING)
        # A different term entirely - must never leak into this term's broadsheet.
        StudentSubjectScore.objects.create(student=self.student1, subject=self.math, class_group=self.class_a, term=self.other_term, score=Decimal("1"), max_score=Decimal("100"), grade="F", approval_status=ResultBatch.PUBLISHED)

        def make_parent(email, phone=""):
            user = User.objects.create_user(
                email=email, password="ParentPass123", role="parent",
                tenant=self.school, is_active=True, is_verified=True, phone=phone,
            )
            return ParentProfile.objects.create(user=user)

        self.parent1 = make_parent("parent1@broadsheet.edu", "08010000001")  # student1 only
        self.parent1.children.add(self.student1)

        self.parent2 = make_parent("parent2@broadsheet.edu", "08010000002")  # student2 (class_a) + student_b (class_b)
        self.parent2.children.add(self.student2, self.student_b)

        self.parent3 = make_parent("parent3@broadsheet.edu", "08010000003")  # student_b only - not in class_a at all
        self.parent3.children.add(self.student_b)

        self.parent4 = make_parent("parent4@broadsheet.edu", "08010000004")  # twins, both in class_a
        self.parent4.children.add(self.twin1, self.twin2)

        self.parent5 = make_parent("parent5@broadsheet.edu", "")  # student3, but no phone on file
        self.parent5.children.add(self.student3)

    # ── Student search ──────────────────────────────────────────────────────

    def test_search_ranks_exact_match_first(self):
        self.client.force_authenticate(user=self.admin)
        response = self.client.get("/api/app/students/search/?q=Okoro")
        self.assertEqual(response.status_code, 200)
        names = [row["name"] for row in response.data["results"]]
        self.assertIn("Ada Okoro", names)
        self.assertIn("Bola Okoro", names)

    def test_search_matches_exact_student_id(self):
        self.client.force_authenticate(user=self.admin)
        response = self.client.get("/api/app/students/search/?q=BS002")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["results"][0]["student_id"], "BS002")

    def test_search_filters_by_class(self):
        self.client.force_authenticate(user=self.admin)
        response = self.client.get(f"/api/app/students/search/?q=BS&class_id={self.class_b.id}")
        self.assertEqual(response.status_code, 200)
        student_ids = {row["student_id"] for row in response.data["results"]}
        self.assertEqual(student_ids, {"BS010"})

    def test_search_short_query_returns_empty(self):
        self.client.force_authenticate(user=self.admin)
        response = self.client.get("/api/app/students/search/?q=B")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["results"], [])

    def test_search_requires_admin_role(self):
        teacher = User.objects.create_user(email="teacher@broadsheet.edu", password="TeacherPass123", role="teacher", tenant=self.school, is_active=True, is_verified=True)
        self.client.force_authenticate(user=teacher)
        response = self.client.get("/api/app/students/search/?q=Okoro")
        self.assertEqual(response.status_code, 403)

    # ── Broadsheet aggregation ──────────────────────────────────────────────

    def test_broadsheet_is_roster_complete_and_ranked(self):
        sheet = _class_broadsheet(self.class_a, self.term, self.admin, include_unpublished=False)
        self.assertEqual(sheet["class_size"], 5)
        self.assertEqual(sheet["subjects"], ["Basic Science", "English Language", "Mathematics"])

        by_id = {row["student_id"]: row for row in sheet["rows"]}
        self.assertEqual(by_id["BS001"]["total_score"], 170.0)
        self.assertEqual(by_id["BS001"]["rank"], 1)
        self.assertEqual(by_id["BS002"]["total_score"], 115.0)
        self.assertEqual(by_id["BS002"]["rank"], 2)
        # Zero-score student still appears (roster-first), tied at 0, tie-broken by student_id.
        self.assertEqual(by_id["BS003"]["total_score"], 0.0)
        self.assertEqual(by_id["BS004"]["total_score"], 0.0)
        self.assertEqual(by_id["BS005"]["total_score"], 0.0)
        self.assertLess(by_id["BS003"]["rank"], by_id["BS004"]["rank"])
        self.assertLess(by_id["BS004"]["rank"], by_id["BS005"]["rank"])

    def test_broadsheet_excludes_unpublished_scores_unless_included(self):
        sheet = _class_broadsheet(self.class_a, self.term, self.admin, include_unpublished=False)
        by_id = {row["student_id"]: row for row in sheet["rows"]}
        self.assertEqual(by_id["BS001"]["total_score"], 170.0)
        self.assertNotIn("Basic Science", by_id["BS001"]["scores"])

        sheet_all = _class_broadsheet(self.class_a, self.term, self.admin, include_unpublished=True)
        by_id_all = {row["student_id"]: row for row in sheet_all["rows"]}
        self.assertEqual(by_id_all["BS001"]["total_score"], 270.0)
        self.assertIn("Basic Science", by_id_all["BS001"]["scores"])

    def test_broadsheet_is_isolated_to_its_own_class_and_term(self):
        sheet = _class_broadsheet(self.class_a, self.term, self.admin, include_unpublished=False)
        student_ids = {row["student_id"] for row in sheet["rows"]}
        self.assertNotIn("BS010", student_ids)  # student_b is in class_b, must not appear

        by_id = {row["student_id"]: row for row in sheet["rows"]}
        self.assertEqual(by_id["BS001"]["total_score"], 170.0)  # the other_term score (1) must not leak in

    def test_results_snapshot_adds_class_broadsheet_only_when_class_and_term_given(self):
        self.client.force_authenticate(user=self.admin)
        response = self.client.get(f"/api/app/results/?class_id={self.class_a.id}")
        self.assertEqual(response.status_code, 200)
        self.assertNotIn("class_broadsheet", response.data)

        response = self.client.get(f"/api/app/results/?class_id={self.class_a.id}&term_id={self.term.id}")
        self.assertEqual(response.status_code, 200)
        self.assertIn("class_broadsheet", response.data)
        self.assertEqual(response.data["class_broadsheet"]["class_size"], 5)

    # ── Parent resolution ───────────────────────────────────────────────────

    def test_parents_list_excludes_parents_with_no_child_in_class(self):
        self.client.force_authenticate(user=self.admin)
        response = self.client.get(f"/api/app/results/broadsheet/parents/?class_id={self.class_a.id}")
        self.assertEqual(response.status_code, 200)
        parent_ids = {row["user_id"] for row in response.data["parents"]}
        self.assertIn(str(self.parent1.user_id), parent_ids)
        self.assertNotIn(str(self.parent3.user_id), parent_ids)  # only has a child in class_b

    def test_parents_list_scopes_siblings_to_only_the_selected_class(self):
        self.client.force_authenticate(user=self.admin)
        response = self.client.get(f"/api/app/results/broadsheet/parents/?class_id={self.class_a.id}")
        parent2_row = next(row for row in response.data["parents"] if row["user_id"] == str(self.parent2.user_id))
        child_names = {child["name"] for child in parent2_row["children_in_class"]}
        self.assertEqual(child_names, {"Bola Okoro"})  # not Dami Lawal (class_b sibling)

    def test_parents_list_includes_both_twins(self):
        self.client.force_authenticate(user=self.admin)
        response = self.client.get(f"/api/app/results/broadsheet/parents/?class_id={self.class_a.id}")
        parent4_row = next(row for row in response.data["parents"] if row["user_id"] == str(self.parent4.user_id))
        self.assertEqual(len(parent4_row["children_in_class"]), 2)

    def test_parents_list_still_includes_parent_with_no_phone(self):
        self.client.force_authenticate(user=self.admin)
        response = self.client.get(f"/api/app/results/broadsheet/parents/?class_id={self.class_a.id}")
        parent5_row = next(row for row in response.data["parents"] if row["user_id"] == str(self.parent5.user_id))
        self.assertEqual(parent5_row["phone"], "")

    # ── Sending ──────────────────────────────────────────────────────────────

    @patch("finance.services.send_ebulksms")
    def test_send_creates_one_link_per_parent_with_correct_highlight(self, mock_send):
        mock_send.return_value = {"status": "success"}
        self.client.force_authenticate(user=self.admin)
        response = self.client.post("/api/app/results/broadsheet/send/", {
            "class_id": self.class_a.id, "term_id": self.term.id,
            "parent_ids": [str(self.parent1.user_id), str(self.parent2.user_id), str(self.parent4.user_id), str(self.parent5.user_id)],
        }, format="json")
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data["sent"], 3)
        self.assertEqual(response.data["skipped"], 1)  # parent5 has no phone
        self.assertEqual(response.data["failed"], 0)

        links = PaymentReceiptLink.objects.filter(receipt_type="class_broadsheet")
        self.assertEqual(links.count(), 3)

        link1 = links.get(phone="08010000001")
        self.assertEqual(link1.data["highlight_student_ids"], [str(self.student1.id)])

        link2 = links.get(phone="08010000002")
        self.assertEqual(link2.data["highlight_student_ids"], [str(self.student2.id)])  # not student_b

        link4 = links.get(phone="08010000004")
        self.assertEqual(set(link4.data["highlight_student_ids"]), {str(self.twin1.id), str(self.twin2.id)})

    @patch("finance.services.send_ebulksms")
    def test_send_never_creates_a_link_for_a_deselected_parent(self, mock_send):
        mock_send.return_value = {"status": "success"}
        self.client.force_authenticate(user=self.admin)
        self.client.post("/api/app/results/broadsheet/send/", {
            "class_id": self.class_a.id, "term_id": self.term.id,
            "parent_ids": [str(self.parent1.user_id)],
        }, format="json")
        self.assertFalse(PaymentReceiptLink.objects.filter(phone="08010000002").exists())

    @patch("finance.services.send_ebulksms")
    def test_send_ignores_a_parent_id_not_actually_in_the_class(self, mock_send):
        """A manipulated request selecting parent3 (no child in class_a) must
        not be trusted - re-filtered server-side, so no link/SMS goes out."""
        mock_send.return_value = {"status": "success"}
        self.client.force_authenticate(user=self.admin)
        response = self.client.post("/api/app/results/broadsheet/send/", {
            "class_id": self.class_a.id, "term_id": self.term.id,
            "parent_ids": [str(self.parent1.user_id), str(self.parent3.user_id)],
        }, format="json")
        self.assertEqual(response.data["sent"], 1)
        self.assertFalse(PaymentReceiptLink.objects.filter(phone="08010000003").exists())

    @patch("finance.services.send_ebulksms")
    def test_send_insufficient_credit_on_one_recipient_does_not_abort_batch(self, mock_send):
        mock_send.return_value = {"status": "success"}
        from finance.services import get_or_create_sms_wallet
        wallet = get_or_create_sms_wallet(self.school)
        wallet.balance = 1
        wallet.save(update_fields=["balance", "updated_at"])

        self.client.force_authenticate(user=self.admin)
        response = self.client.post("/api/app/results/broadsheet/send/", {
            "class_id": self.class_a.id, "term_id": self.term.id,
            "parent_ids": [str(self.parent1.user_id), str(self.parent2.user_id)],
        }, format="json")
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data["sent"], 1)
        self.assertEqual(response.data["failed"], 1)

    def test_send_requires_no_empty_parent_list(self):
        self.client.force_authenticate(user=self.admin)
        response = self.client.post("/api/app/results/broadsheet/send/", {
            "class_id": self.class_a.id, "term_id": self.term.id, "parent_ids": [],
        }, format="json")
        self.assertEqual(response.status_code, 400)

    def test_send_requires_admin_role_not_accountant(self):
        accountant = User.objects.create_user(email="accountant@broadsheet.edu", password="AccountantPass123", role="accountant", tenant=self.school, is_active=True, is_verified=True)
        self.client.force_authenticate(user=accountant)
        response = self.client.post("/api/app/results/broadsheet/send/", {
            "class_id": self.class_a.id, "term_id": self.term.id, "parent_ids": [str(self.parent1.user_id)],
        }, format="json")
        self.assertEqual(response.status_code, 403)

    def test_send_requires_admin_role_not_teacher_or_parent(self):
        for role, email in (("teacher", "t@broadsheet.edu"), ("parent", "p@broadsheet.edu")):
            user = User.objects.create_user(email=email, password="Pass12345", role=role, tenant=self.school, is_active=True, is_verified=True)
            self.client.force_authenticate(user=user)
            response = self.client.post("/api/app/results/broadsheet/send/", {
                "class_id": self.class_a.id, "term_id": self.term.id, "parent_ids": [str(self.parent1.user_id)],
            }, format="json")
            self.assertEqual(response.status_code, 403, f"role={role}")
