from datetime import timedelta

from django.core import mail
from django.core.cache import cache
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient

from academic.models import Class, GradeScale, ResultBatch, StudentSubjectScore, Subject
from core.models import SchoolTenant
from notifications.models import Notification
from tenants.models import Tenant
from users.models import StudentProfile, User
from .models import Exam, ExamAttempt, ExamPin, Question, QuestionBank, StudentAnswer


class FlagExamQuestionTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.student = User.objects.create_user(
            email="student@example.com",
            password="password",
            first_name="Test",
            last_name="Student",
            role="student",
        )
        self.teacher = User.objects.create_user(
            email="teacher@example.com",
            password="password",
            first_name="Test",
            last_name="Teacher",
            role="teacher",
        )
        self.exam = Exam.objects.create(
            title="English Mock",
            teacher=self.teacher,
            start_date=timezone.now() - timedelta(minutes=5),
            end_date=timezone.now() + timedelta(hours=1),
            duration_minutes=60,
            is_published=True,
        )
        self.question = Question.objects.create(
            question_type="mcq",
            text="Choose the offensive phrase.",
            options=["Safe option", "Bad option", "Another option", "Final option"],
            correct_answer="Bad option",
            points=1,
        )
        self.exam.questions.add(self.question)
        self.attempt = ExamAttempt.objects.create(exam=self.exam, student=self.student)
        StudentAnswer.objects.create(
            attempt=self.attempt,
            question=self.question,
            selected_options=1,
        )
        self.client.force_authenticate(self.student)

    @override_settings(
        EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
        INAPPROPRIATE_QUESTION_REPORT_EMAIL="owner@example.com",
        DEFAULT_FROM_EMAIL="SchoolDom <noreply@example.com>",
    )
    def test_student_can_flag_question_and_email_contains_full_context(self):
        response = self.client.post(
            reverse("exams:flag_question", args=[self.attempt.id]),
            {
                "question_id": self.question.id,
                "reason": "This question contains inappropriate wording.",
            },
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(mail.outbox), 1)
        message = mail.outbox[0]
        self.assertEqual(message.to, ["owner@example.com", "teacher@example.com"])
        self.assertIn("English Mock", message.subject)
        self.assertIn("Choose the offensive phrase.", message.body)
        self.assertIn("A. Safe option", message.body)
        self.assertIn("B. Bad option", message.body)
        self.assertIn("Correct answer: Bad option", message.body)
        self.assertIn("Student selected answer: B. Bad option", message.body)
        self.assertIn("This question contains inappropriate wording.", message.body)

    def test_auto_submission_reason_and_logs_are_stored(self):
        response = self.client.post(
            reverse("exams:submit_exam", args=[self.attempt.id]),
            {
                "auto_submitted": True,
                "auto_submit_reason": "tab_switch_limit",
                "auto_submit_reason_display": "Exceeded tab-switching warnings",
                "auto_submit_details": "Opening another tab or window was attempted.",
                "warning_history": [
                    {"type": "warning", "message": "Opening another tab was detected.", "time": timezone.now().isoformat()}
                ],
                "activity_logs": [
                    {"type": "security_violation", "message": "Second tab switch detected.", "time": timezone.now().isoformat()}
                ],
            },
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        self.attempt.refresh_from_db()
        self.assertTrue(self.attempt.is_submitted)
        self.assertTrue(self.attempt.auto_submitted)
        self.assertEqual(self.attempt.auto_submit_reason, "tab_switch_limit")
        self.assertEqual(self.attempt.auto_submit_reason_display, "Exceeded tab-switching warnings")
        self.assertEqual(len(self.attempt.auto_submit_warning_history), 1)
        self.assertEqual(len(self.attempt.auto_submit_activity_logs), 1)


class ExamResultGradingTests(TestCase):
    """The CBT result page must resolve grades through the same admin-
    configured GradeScale as manual score entry, report cards, and
    transcripts - it used to have its own private, hardcoded 90/80/70/60
    scale independent of whatever the admin actually configured.

    Note: ExamResultView.get() only reaches the score/grade calculation for
    the *teacher* role - a student hitting this same endpoint currently gets
    an early-return "Exam Completed" message with no score/grade at all
    (exam_views.py:974-981, pre-existing behavior, unrelated to grading and
    out of scope here). These tests authenticate as the teacher to exercise
    the code path that actually computes a grade."""

    def setUp(self):
        self.school = SchoolTenant.objects.create(
            name="Grading CBT School", schema_name="grading_cbt_school", is_active=True
        )
        self.legacy_tenant = Tenant.objects.create(name=self.school.name, slug=self.school.schema_name)
        self.teacher = User.objects.create_user(
            email="teacher@grading-cbt.edu", password="TeacherPass123", role="teacher",
            tenant=self.school, is_active=True, is_verified=True,
        )
        self.student = User.objects.create_user(
            email="student@grading-cbt.edu", password="StudentPass123", role="student",
            tenant=self.school, is_active=True, is_verified=True,
        )
        # A custom "A" starting at 65% - deliberately below both the old
        # hardcoded CBT scale's >=90 threshold AND the auto-seeded default
        # GradeScale's own 70% threshold, so a score of 68% only comes out
        # "A" if the admin's actual customization is honored (any leftover
        # letters this tenant doesn't define, like F, get auto-seeded with
        # the standard defaults - see grade_scale_for_percentage).
        GradeScale.objects.create(
            tenant=self.legacy_tenant, letter="A", min_percentage=65, max_percentage=100, remark="Excellent"
        )

        self.exam = Exam.objects.create(
            title="Grading Consistency Exam",
            teacher=self.teacher,
            start_date=timezone.now() - timedelta(minutes=5),
            end_date=timezone.now() + timedelta(hours=1),
            duration_minutes=60,
            is_published=True,
        )
        self.attempt = ExamAttempt.objects.create(
            exam=self.exam, student=self.student, is_submitted=True,
            score=68, total_points=100, end_time=timezone.now(),
        )
        self.client = APIClient()
        self.client.force_authenticate(self.teacher)

    def test_cbt_result_grade_uses_admin_configured_grading_scale(self):
        response = self.client.get(f"/api/exams/result/{self.attempt.id}/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["percentage"], 68.0)
        self.assertEqual(response.data["grade"], "A")
        self.assertTrue(response.data["is_passed"])

    def test_cbt_result_reports_failing_grade_as_not_passed(self):
        # 10% falls well within the auto-seeded default "F" band (0-39.99),
        # regardless of the custom "A" override above.
        self.attempt.score = 10
        self.attempt.save(update_fields=["score"])
        response = self.client.get(f"/api/exams/result/{self.attempt.id}/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["grade"], "F")
        self.assertFalse(response.data["is_passed"])


class ExamResultStudentPrivacyTests(TestCase):
    """Students must never see their own CBT score, percentage, or grade -
    only admins and teachers can view a completed attempt's result."""

    def setUp(self):
        self.school = SchoolTenant.objects.create(name="Privacy CBT School", schema_name="privacy_cbt_school", is_active=True)
        self.legacy_tenant = Tenant.objects.create(name=self.school.name, slug=self.school.schema_name)
        self.other_school = SchoolTenant.objects.create(name="Other CBT School", schema_name="other_cbt_school", is_active=True)
        self.other_legacy_tenant = Tenant.objects.create(name=self.other_school.name, slug=self.other_school.schema_name)

        self.teacher = User.objects.create_user(
            email="teacher@privacy-cbt.edu", password="TeacherPass123", role="teacher",
            tenant=self.school, is_active=True, is_verified=True,
        )
        self.admin = User.objects.create_user(
            email="admin@privacy-cbt.edu", password="AdminPass123", role="school_admin",
            tenant=self.school, is_active=True, is_verified=True,
        )
        self.other_school_admin = User.objects.create_user(
            email="admin@other-cbt.edu", password="AdminPass123", role="school_admin",
            tenant=self.other_school, is_active=True, is_verified=True,
        )
        self.student = User.objects.create_user(
            email="student@privacy-cbt.edu", password="StudentPass123", role="student",
            tenant=self.school, is_active=True, is_verified=True,
        )
        self.exam = Exam.objects.create(
            title="Privacy Exam", teacher=self.teacher, tenant=self.legacy_tenant,
            start_date=timezone.now() - timedelta(minutes=5), end_date=timezone.now() + timedelta(hours=1),
            duration_minutes=60, is_published=True,
        )
        self.attempt = ExamAttempt.objects.create(
            exam=self.exam, student=self.student, is_submitted=True,
            score=80, total_points=100, end_time=timezone.now(),
        )
        self.client = APIClient()

    def test_student_never_sees_own_score_or_grade(self):
        self.client.force_authenticate(self.student)
        response = self.client.get(f"/api/exams/result/{self.attempt.id}/")

        self.assertEqual(response.status_code, 200)
        self.assertNotIn("score", response.data)
        self.assertNotIn("percentage", response.data)
        self.assertNotIn("grade", response.data)
        self.assertNotIn("is_passed", response.data)
        self.assertNotIn("answers_review", response.data)
        self.assertEqual(response.data["message"], "Exam Completed")

    def test_admin_can_view_result_in_their_own_tenant(self):
        self.client.force_authenticate(self.admin)
        response = self.client.get(f"/api/exams/result/{self.attempt.id}/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["score"], 80)
        self.assertEqual(response.data["percentage"], 80.0)
        self.assertIn("grade", response.data)

    def test_admin_from_another_tenant_cannot_view_result(self):
        self.client.force_authenticate(self.other_school_admin)
        response = self.client.get(f"/api/exams/result/{self.attempt.id}/")

        self.assertEqual(response.status_code, 404)

    def test_offline_sync_response_never_includes_score(self):
        question = Question.objects.create(
            tenant=self.legacy_tenant, question_type="mcq", text="2 + 2?",
            options=["3", "4"], correct_answer="4", points=1,
        )
        self.exam.questions.add(question)
        self.client.force_authenticate(self.student)

        response = self.client.post(
            reverse("exams:sync_offline_exam_attempt"),
            {
                "exam_id": self.exam.id,
                "answers": {str(question.id): "4"},
                "offline_attempt_id": "offline-privacy-check",
            },
            format="json",
        )

        self.assertEqual(response.status_code, 201)
        self.assertNotIn("score", response.data)
        self.assertNotIn("percentage", response.data)
        self.assertNotIn("total_points", response.data)

    def test_student_cannot_import_cbt_results_package(self):
        self.client.force_authenticate(self.student)
        response = self.client.post(
            reverse("exams:cbt_results_package_import"),
            {"results": []},
            format="json",
        )
        self.assertEqual(response.status_code, 403)


class ExamTenantIsolationTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.school_a = SchoolTenant.objects.create(name="Alpha School", schema_name="alpha", is_active=True)
        self.school_b = SchoolTenant.objects.create(name="Beta School", schema_name="beta", is_active=True)
        self.legacy_a = Tenant.objects.create(name="Alpha School", slug="alpha")
        self.legacy_b = Tenant.objects.create(name="Beta School", slug="beta")
        self.student_a = User.objects.create_user(
            email="student.alpha@example.com",
            password="password",
            role="student",
            tenant=self.school_a,
        )
        self.teacher_b = User.objects.create_user(
            email="teacher.beta@example.com",
            password="password",
            role="teacher",
            tenant=self.school_b,
        )
        self.exam_b = Exam.objects.create(
            tenant=self.legacy_b,
            title="Beta Only Exam",
            teacher=self.teacher_b,
            start_date=timezone.now() - timedelta(minutes=5),
            end_date=timezone.now() + timedelta(hours=1),
            duration_minutes=60,
            is_published=True,
        )
        self.question_b = Question.objects.create(
            tenant=self.legacy_b,
            question_type="mcq",
            text="Beta-only question",
            options=["A", "B"],
            correct_answer="A",
            points=1,
        )
        self.exam_b.questions.add(self.question_b)
        self.client.force_authenticate(self.student_a)

    def test_student_cannot_start_exam_from_another_tenant(self):
        response = self.client.post(reverse("exams:start_exam", args=[self.exam_b.id]), {}, format="json")

        self.assertEqual(response.status_code, 404)
        self.assertFalse(ExamAttempt.objects.filter(exam=self.exam_b, student=self.student_a).exists())

    def test_offline_sync_rejects_exam_from_another_tenant(self):
        response = self.client.post(
            reverse("exams:sync_offline_exam_attempt"),
            {
                "exam_id": self.exam_b.id,
                "answers": {str(self.question_b.id): "A"},
                "offline_attempt_id": "offline-cross-tenant",
            },
            format="json",
        )

        self.assertEqual(response.status_code, 404)
        self.assertFalse(ExamAttempt.objects.filter(exam=self.exam_b, student=self.student_a).exists())


class StudentCbtEntryCollisionTests(TestCase):
    """
    student_id and admission_number are each unique individually, but the CBT entry
    identifier is matched with student_id OR admission_number OR email - so a value
    that happens to equal one student's student_id AND a *different* student's
    admission_number (a cross-field collision, entirely possible since each field's
    uniqueness is enforced independently) must still never let a PIN from one school
    log a CBT terminal into the wrong school's student record.
    """

    def setUp(self):
        self.client = APIClient()
        self.school_a = SchoolTenant.objects.create(name="Alpha CBT School", schema_name="alpha_cbt", is_active=True)
        self.school_b = SchoolTenant.objects.create(name="Beta CBT School", schema_name="beta_cbt", is_active=True)
        self.legacy_a = Tenant.objects.create(name="Alpha CBT School", slug="alpha_cbt")
        self.legacy_b = Tenant.objects.create(name="Beta CBT School", slug="beta_cbt")

        self.student_user_a = User.objects.create_user(
            email="student.a@cbt.test", password="password", role="student", tenant=self.school_a,
        )
        self.student_profile_a = StudentProfile.objects.create(
            user=self.student_user_a, student_id="STU001", admission_number="ADM-A-001",
            admission_date=timezone.localdate(), guardian_name="Guardian", guardian_relation="Parent",
        )
        self.student_user_b = User.objects.create_user(
            email="student.b@cbt.test", password="password", role="student", tenant=self.school_b,
        )
        self.student_profile_b = StudentProfile.objects.create(
            # Collides with school A's student_id via a different field (admission_number)
            # - each field is individually unique, but the OR-based lookup still matches both.
            user=self.student_user_b, student_id="ADM-B-001", admission_number="STU001",
            admission_date=timezone.localdate(), guardian_name="Guardian", guardian_relation="Parent",
        )

        teacher_b = User.objects.create_user(
            email="teacher.b@cbt.test", password="password", role="teacher", tenant=self.school_b,
        )
        self.exam_b = Exam.objects.create(
            tenant=self.legacy_b,
            title="Beta CBT Exam",
            teacher=teacher_b,
            start_date=timezone.now() - timedelta(minutes=5),
            end_date=timezone.now() + timedelta(hours=1),
            duration_minutes=60,
            is_published=True,
        )
        self.pin_b = ExamPin(exam=self.exam_b, tenant=self.legacy_b)
        self.pin_b.set_pin("654321")
        self.pin_b.save()

    def test_colliding_student_id_with_school_bs_pin_logs_into_school_b_only(self):
        response = self.client.post(
            reverse("exams:student_cbt_entry"),
            {"student_id": "STU001", "pin": "654321"},
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["student"]["id"], str(self.student_user_b.id))
        self.assertEqual(response.data["session"]["school_code"], self.school_b.schema_name)

    def test_colliding_student_id_with_wrong_pin_is_rejected(self):
        response = self.client.post(
            reverse("exams:student_cbt_entry"),
            {"student_id": "STU001", "pin": "000000"},
            format="json",
        )

        self.assertEqual(response.status_code, 404)


class TheoryExamAuthoringTests(TestCase):
    """Objective exams keep working exactly as before; Theory/Mixed exams
    relax the options/correct-answer requirement for theory-typed questions
    and reject a question whose type doesn't match the exam's format."""

    def setUp(self):
        self.school = SchoolTenant.objects.create(name="Theory Authoring School", schema_name="theory_authoring", is_active=True)
        self.teacher = User.objects.create_user(
            email="teacher@theory-authoring.edu", password="TeacherPass123", role="teacher",
            tenant=self.school, is_active=True, is_verified=True,
        )
        self.client = APIClient()
        self.client.force_authenticate(self.teacher)

    def _payload(self, exam_format, questions):
        now = timezone.now()
        return {
            "title": f"{exam_format} exam",
            "exam_format": exam_format,
            "start_date": (now + timedelta(minutes=5)).isoformat(),
            "end_date": (now + timedelta(hours=1)).isoformat(),
            "duration_minutes": 30,
            "questions": questions,
        }

    def test_objective_exam_unaffected_still_requires_options(self):
        response = self.client.post(
            "/api/app/exams/create/",
            self._payload("objective", [{"text": "2 + 2?", "options": ["3", "4"], "correct_answer": "4"}]),
            format="json",
        )
        self.assertEqual(response.status_code, 201, response.data)
        exam = Exam.objects.get(id=response.data["exam"]["id"])
        self.assertEqual(exam.exam_format, "objective")
        self.assertEqual(exam.questions.get().question_type, "mcq")

    def test_theory_exam_accepts_question_with_no_options(self):
        response = self.client.post(
            "/api/app/exams/create/",
            self._payload("theory", [{"text": "Explain photosynthesis.", "question_type": "essay", "points": 10}]),
            format="json",
        )
        self.assertEqual(response.status_code, 201, response.data)
        exam = Exam.objects.get(id=response.data["exam"]["id"])
        question = exam.questions.get()
        self.assertEqual(question.question_type, "essay")
        self.assertEqual(question.options, [])

    def test_theory_exam_rejects_empty_question_text(self):
        response = self.client.post(
            "/api/app/exams/create/",
            self._payload("theory", [{"text": "", "question_type": "essay"}]),
            format="json",
        )
        self.assertEqual(response.status_code, 400)

    def test_theory_exam_rejects_an_mcq_question(self):
        response = self.client.post(
            "/api/app/exams/create/",
            self._payload("theory", [{"text": "2 + 2?", "options": ["3", "4"], "correct_answer": "4"}]),
            format="json",
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("Objective/Theory/Mixed", response.data["message"])

    def test_mixed_exam_accepts_both_mcq_and_theory_questions(self):
        response = self.client.post(
            "/api/app/exams/create/",
            self._payload("mixed", [
                {"text": "2 + 2?", "options": ["3", "4"], "correct_answer": "4"},
                {"text": "Explain photosynthesis.", "question_type": "essay", "points": 10},
            ]),
            format="json",
        )
        self.assertEqual(response.status_code, 201, response.data)
        exam = Exam.objects.get(id=response.data["exam"]["id"])
        types = sorted(exam.questions.values_list("question_type", flat=True))
        self.assertEqual(types, ["essay", "mcq"])


class ExamAutosaveTests(TestCase):
    """Exam Builder auto-save: the lenient draft-create endpoint, the upsert-by-id
    question sync (no duplicate Question rows across repeated auto-save ticks,
    no data loss for questions shared via a QuestionBank), and the auto-save flag
    that must never spam admins with a review notification on every tick."""

    def setUp(self):
        self.school = SchoolTenant.objects.create(name="Autosave School", schema_name="autosave_school", is_active=True)
        self.teacher = User.objects.create_user(
            email="teacher@autosave.edu", password="TeacherPass123", role="teacher",
            tenant=self.school, is_active=True, is_verified=True,
        )
        self.admin = User.objects.create_user(
            email="admin@autosave.edu", password="AdminPass123", role="school_admin",
            tenant=self.school, is_active=True, is_verified=True,
        )
        self.client = APIClient()
        self.client.force_authenticate(self.teacher)

    def test_autosave_creates_draft_with_only_a_title_and_sane_defaults(self):
        response = self.client.post("/api/app/exams/autosave/", {"title": "My new exam"}, format="json")

        self.assertEqual(response.status_code, 201, response.data)
        exam = Exam.objects.get(id=response.data["exam"]["id"])
        self.assertEqual(exam.title, "My new exam")
        self.assertFalse(exam.is_published)
        self.assertIsNotNone(exam.start_date)
        self.assertIsNotNone(exam.end_date)
        self.assertGreater(exam.duration_minutes, 0)
        self.assertEqual(exam.questions.count(), 0)

    def test_autosave_with_blank_title_defaults_to_untitled_draft(self):
        response = self.client.post("/api/app/exams/autosave/", {}, format="json")

        self.assertEqual(response.status_code, 201, response.data)
        exam = Exam.objects.get(id=response.data["exam"]["id"])
        self.assertEqual(exam.title, "Untitled Draft")

    def test_autosave_does_not_notify_admins(self):
        before = Notification.objects.filter(event_type="exam_ready_for_publishing").count()

        response = self.client.post("/api/app/exams/autosave/", {"title": "Quiet draft"}, format="json")

        self.assertEqual(response.status_code, 201, response.data)
        after = Notification.objects.filter(event_type="exam_ready_for_publishing").count()
        self.assertEqual(after, before)

    def test_repeated_autosave_updates_existing_question_instead_of_duplicating(self):
        create_response = self.client.post(
            "/api/app/exams/autosave/",
            {
                "title": "Repeated autosave exam",
                "exam_format": "objective",
                "questions": [{"text": "2 + 2?", "options": ["3", "4"], "correct_answer": "4", "points": 1}],
            },
            format="json",
        )
        self.assertEqual(create_response.status_code, 201, create_response.data)
        exam_id = create_response.data["exam"]["id"]
        question_id = create_response.data["exam"]["questions"][0]["id"]
        self.assertEqual(Question.objects.count(), 1)

        # Each tick's payload differs slightly (like real autosave ticks would as
        # the user keeps typing) so this also isn't just exercising the
        # unrelated request-idempotency middleware's duplicate-body cache.
        for tick, points in enumerate([2, 3, 4], start=1):
            patch_response = self.client.patch(
                f"/api/app/exams/{exam_id}/",
                {
                    "autosave": True,
                    "questions": [
                        {"id": question_id, "text": f"2 + 2 = ? (tick {tick})", "options": ["3", "4"], "correct_answer": "4", "points": points},
                    ],
                },
                format="json",
            )
            self.assertEqual(patch_response.status_code, 200, patch_response.json())

        # Same question row updated in place three times, not recreated.
        self.assertEqual(Question.objects.count(), 1)
        question = Question.objects.get(id=question_id)
        self.assertEqual(question.text, "2 + 2 = ? (tick 3)")
        self.assertEqual(question.points, 4)

    def test_manual_patch_only_notifies_admins_when_notify_admin_is_requested(self):
        """Save Draft vs Send to Admin: both are manual (non-autosave) PATCHes,
        distinguished only by the notify_admin flag - a plain content save must
        never notify by itself (that was the old, overly-eager behavior; a
        teacher's "Save Draft" click used to spam admins on every edit)."""
        create_response = self.client.post("/api/app/exams/autosave/", {"title": "Notify test exam"}, format="json")
        exam_id = create_response.data["exam"]["id"]
        before = Notification.objects.filter(event_type="exam_ready_for_publishing").count()

        self.client.patch(f"/api/app/exams/{exam_id}/", {"autosave": True, "instructions": "Read carefully."}, format="json")
        after_autosave = Notification.objects.filter(event_type="exam_ready_for_publishing").count()
        self.assertEqual(after_autosave, before)

        # Manual "Save Draft" (no notify_admin) - still must not notify.
        self.client.patch(f"/api/app/exams/{exam_id}/", {"instructions": "Final instructions."}, format="json")
        after_manual_save = Notification.objects.filter(event_type="exam_ready_for_publishing").count()
        self.assertEqual(after_manual_save, before)

        # Manual "Send to Admin" (notify_admin: true) - this is the one that must notify.
        self.client.patch(f"/api/app/exams/{exam_id}/", {"notify_admin": True}, format="json")
        after_send = Notification.objects.filter(event_type="exam_ready_for_publishing").count()
        self.assertGreater(after_send, before)

    def test_removing_a_question_deletes_it_unless_shared_with_a_question_bank(self):
        create_response = self.client.post(
            "/api/app/exams/autosave/",
            {
                "title": "Cleanup exam",
                "exam_format": "objective",
                "questions": [
                    {"text": "Orphan question", "options": ["A", "B"], "correct_answer": "A"},
                    {"text": "Bank-shared question", "options": ["A", "B"], "correct_answer": "B"},
                ],
            },
            format="json",
        )
        exam = Exam.objects.get(id=create_response.data["exam"]["id"])
        orphan_id, shared_id = [q["id"] for q in create_response.data["exam"]["questions"]]
        shared_question = Question.objects.get(id=shared_id)
        # get_or_create - _tenant_for_model may have already auto-vivified a
        # legacy Tenant row matching this schema_name from an earlier autosave
        # call in this test.
        legacy_tenant, _ = Tenant.objects.get_or_create(slug=self.school.schema_name, defaults={"name": self.school.name})
        subject = Subject.objects.create(tenant=legacy_tenant, name="General Studies", code="GST")
        bank = QuestionBank.objects.create(tenant=legacy_tenant, name="Shared bank", subject=subject, teacher=self.teacher)
        bank.questions.add(shared_question)

        response = self.client.patch(
            f"/api/app/exams/{exam.id}/",
            {"autosave": True, "questions": []},
            format="json",
        )

        self.assertEqual(response.status_code, 200, response.data)
        self.assertFalse(Question.objects.filter(id=orphan_id).exists())
        self.assertTrue(Question.objects.filter(id=shared_id).exists())
        self.assertEqual(exam.questions.count(), 0)


class TheoryGradingFlowTests(TestCase):
    """End-to-end: submitting a Mixed attempt auto-grades only the MCQ
    portion; the essay stays pending until a teacher scores and publishes
    it, which then folds both portions into the final combined score."""

    def setUp(self):
        self.school = SchoolTenant.objects.create(name="Theory Grading School", schema_name="theory_grading", is_active=True)
        self.legacy_tenant = Tenant.objects.create(name=self.school.name, slug=self.school.schema_name)
        self.teacher = User.objects.create_user(
            email="teacher@theory-grading.edu", password="TeacherPass123", role="teacher",
            tenant=self.school, is_active=True, is_verified=True,
        )
        self.student = User.objects.create_user(
            email="student@theory-grading.edu", password="StudentPass123", role="student",
            tenant=self.school, is_active=True, is_verified=True,
        )
        self.exam = Exam.objects.create(
            title="Mixed Midterm", teacher=self.teacher, tenant=self.legacy_tenant, exam_format="mixed",
            start_date=timezone.now() - timedelta(minutes=5), end_date=timezone.now() + timedelta(hours=1),
            duration_minutes=60, is_published=True,
        )
        self.mcq_question = Question.objects.create(
            tenant=self.legacy_tenant, question_type="mcq", text="2 + 2?",
            options=["3", "4"], correct_answer="4", points=10,
        )
        self.essay_question = Question.objects.create(
            tenant=self.legacy_tenant, question_type="essay", text="Explain photosynthesis.", points=20,
        )
        self.exam.questions.add(self.mcq_question, self.essay_question)
        self.client = APIClient()

    def _submit_attempt(self):
        # Every test in this class posts byte-identical answer/submit
        # bodies against the same URLs - IdempotencyMiddleware's response
        # cache (process-level, not per-test-transaction) would otherwise
        # serve a stale cached response from a previous test instead of
        # actually processing this one.
        from django.core.cache import cache as django_cache
        django_cache.clear()

        self.client.force_authenticate(self.student)
        attempt = ExamAttempt.objects.create(exam=self.exam, student=self.student, tenant=self.legacy_tenant)
        self.client.post(
            reverse("exams:save_answer", args=[attempt.id]),
            {"question_id": self.mcq_question.id, "selected_options": 1},
            format="json",
        )
        self.client.post(
            reverse("exams:save_answer", args=[attempt.id]),
            {"question_id": self.essay_question.id, "answer_text": "Plants convert light into energy."},
            format="json",
        )
        self.client.post(reverse("exams:submit_exam", args=[attempt.id]))
        attempt.refresh_from_db()
        return attempt

    def test_submit_auto_grades_mcq_only_leaves_essay_pending(self):
        attempt = self._submit_attempt()

        mcq_answer = StudentAnswer.objects.get(attempt=attempt, question=self.mcq_question)
        essay_answer = StudentAnswer.objects.get(attempt=attempt, question=self.essay_question)
        self.assertTrue(mcq_answer.is_correct)
        self.assertEqual(mcq_answer.score, 10)
        self.assertIsNone(essay_answer.score)
        self.assertIsNone(essay_answer.is_correct)
        # Partial score reflects only the auto-graded MCQ portion so far.
        self.assertEqual(attempt.score, 10)
        self.assertEqual(attempt.total_points, 30)

    def test_grading_queue_lists_attempt_until_published(self):
        attempt = self._submit_attempt()
        self.client.force_authenticate(self.teacher)

        queue_response = self.client.get(reverse("exams:theory_grading_queue"))
        self.assertEqual(queue_response.status_code, 200)
        self.assertIn(attempt.id, [row["attempt_id"] for row in queue_response.data["attempts"]])

        answers_response = self.client.get(reverse("exams:attempt_theory_answers", args=[attempt.id]))
        self.assertEqual(answers_response.status_code, 200)
        self.assertEqual(len(answers_response.data["answers"]), 1)
        essay_answer_id = answers_response.data["answers"][0]["answer_id"]
        self.assertEqual(answers_response.data["answers"][0]["answer_text"], "Plants convert light into energy.")

        publish_too_early = self.client.post(reverse("exams:publish_theory_grades", args=[attempt.id]))
        self.assertEqual(publish_too_early.status_code, 400)

        grade_response = self.client.post(
            reverse("exams:grade_theory_answer", args=[attempt.id, essay_answer_id]),
            {"score": 15, "feedback": "Good explanation, missing chlorophyll detail."},
            format="json",
        )
        self.assertEqual(grade_response.status_code, 200, grade_response.data)
        self.assertFalse(grade_response.data["attempt_needs_grading"])

        queue_after_grading = self.client.get(reverse("exams:theory_grading_queue"))
        self.assertNotIn(attempt.id, [row["attempt_id"] for row in queue_after_grading.data["attempts"]])

        publish_response = self.client.post(reverse("exams:publish_theory_grades", args=[attempt.id]))
        self.assertEqual(publish_response.status_code, 200, publish_response.data)
        self.assertEqual(publish_response.data["score"], 25)  # 10 (mcq) + 15 (essay)
        self.assertEqual(publish_response.data["total_points"], 30)

        attempt.refresh_from_db()
        self.assertEqual(attempt.score, 25)
        self.assertAlmostEqual(attempt.percentage, 25 / 30 * 100)
        essay_answer = StudentAnswer.objects.get(id=essay_answer_id)
        self.assertEqual(essay_answer.teacher_feedback, "Good explanation, missing chlorophyll detail.")

    def test_grade_rejects_score_above_question_points(self):
        attempt = self._submit_attempt()
        essay_answer = StudentAnswer.objects.get(attempt=attempt, question=self.essay_question)
        self.client.force_authenticate(self.teacher)

        response = self.client.post(
            reverse("exams:grade_theory_answer", args=[attempt.id, essay_answer.id]),
            {"score": 999, "feedback": ""},
            format="json",
        )
        self.assertEqual(response.status_code, 400)
        essay_answer.refresh_from_db()
        self.assertIsNone(essay_answer.score)


class TheoryGradingPermissionTests(TestCase):
    """Teachers only grade their own exams; admins grade within their own
    tenant; students and other tenants' admins are blocked."""

    def setUp(self):
        self.school = SchoolTenant.objects.create(name="Grading Perm School", schema_name="grading_perm", is_active=True)
        self.legacy_tenant = Tenant.objects.create(name=self.school.name, slug=self.school.schema_name)
        self.other_school = SchoolTenant.objects.create(name="Other Grading Perm School", schema_name="other_grading_perm", is_active=True)
        self.other_legacy_tenant = Tenant.objects.create(name=self.other_school.name, slug=self.other_school.schema_name)

        self.owning_teacher = User.objects.create_user(
            email="owner@grading-perm.edu", password="TeacherPass123", role="teacher",
            tenant=self.school, is_active=True, is_verified=True,
        )
        self.other_teacher = User.objects.create_user(
            email="other@grading-perm.edu", password="TeacherPass123", role="teacher",
            tenant=self.school, is_active=True, is_verified=True,
        )
        self.admin = User.objects.create_user(
            email="admin@grading-perm.edu", password="AdminPass123", role="school_admin",
            tenant=self.school, is_active=True, is_verified=True,
        )
        self.other_school_admin = User.objects.create_user(
            email="admin@other-grading-perm.edu", password="AdminPass123", role="school_admin",
            tenant=self.other_school, is_active=True, is_verified=True,
        )
        self.student = User.objects.create_user(
            email="student@grading-perm.edu", password="StudentPass123", role="student",
            tenant=self.school, is_active=True, is_verified=True,
        )

        self.exam = Exam.objects.create(
            title="Perm Exam", teacher=self.owning_teacher, tenant=self.legacy_tenant, exam_format="theory",
            start_date=timezone.now() - timedelta(minutes=5), end_date=timezone.now() + timedelta(hours=1),
            duration_minutes=60, is_published=True,
        )
        self.essay_question = Question.objects.create(
            tenant=self.legacy_tenant, question_type="essay", text="Explain photosynthesis.", points=20,
        )
        self.exam.questions.add(self.essay_question)
        self.attempt = ExamAttempt.objects.create(
            exam=self.exam, student=self.student, tenant=self.legacy_tenant,
            is_submitted=True, total_points=20, end_time=timezone.now(),
        )
        self.answer = StudentAnswer.objects.create(
            attempt=self.attempt, question=self.essay_question, tenant=self.legacy_tenant,
            answer_text="Plants convert light into energy.",
        )
        self.client = APIClient()

    def test_other_teacher_cannot_grade_a_colleagues_exam(self):
        self.client.force_authenticate(self.other_teacher)
        response = self.client.get(reverse("exams:attempt_theory_answers", args=[self.attempt.id]))
        self.assertEqual(response.status_code, 404)

    def test_owning_teacher_can_grade(self):
        self.client.force_authenticate(self.owning_teacher)
        response = self.client.get(reverse("exams:attempt_theory_answers", args=[self.attempt.id]))
        self.assertEqual(response.status_code, 200)

    def test_admin_in_same_tenant_can_grade(self):
        self.client.force_authenticate(self.admin)
        response = self.client.get(reverse("exams:attempt_theory_answers", args=[self.attempt.id]))
        self.assertEqual(response.status_code, 200)

    def test_admin_from_other_tenant_cannot_grade(self):
        self.client.force_authenticate(self.other_school_admin)
        response = self.client.get(reverse("exams:attempt_theory_answers", args=[self.attempt.id]))
        self.assertEqual(response.status_code, 404)

    def test_student_cannot_access_grading_queue(self):
        self.client.force_authenticate(self.student)
        response = self.client.get(reverse("exams:theory_grading_queue"))
        self.assertEqual(response.status_code, 403)


class AttemptSubmissionReviewTests(TestCase):
    """The submission popup's summary has to reconcile with the rows under it.

    ExamAttempt.score holds the objective-only subtotal until theory grades are
    published, so a mixed paper reviewed off that field shows a total that does
    not match the marks printed beside each question. These tests pin the sum,
    and pin that an ungraded theory answer is reported as pending rather than
    quietly counted as a zero the student earned.
    """

    def setUp(self):
        self.school = SchoolTenant.objects.create(
            name="Review School", schema_name="review_school", is_active=True
        )
        self.legacy_tenant = Tenant.objects.create(name=self.school.name, slug=self.school.schema_name)
        GradeScale.objects.create(
            tenant=self.legacy_tenant, letter="A", min_percentage=60, max_percentage=100, remark="Excellent"
        )
        self.teacher = User.objects.create_user(
            email="teacher@review.edu", password="TeacherPass123", role="teacher",
            tenant=self.school, is_active=True, is_verified=True,
        )
        self.student = User.objects.create_user(
            email="pupil@review.edu", password="StudentPass123", first_name="Ada", last_name="Pupil",
            role="student", tenant=self.school, is_active=True, is_verified=True,
        )
        self.exam = Exam.objects.create(
            title="Mixed Paper", teacher=self.teacher,
            start_date=timezone.now() - timedelta(minutes=5),
            end_date=timezone.now() + timedelta(hours=1),
            duration_minutes=60, exam_format="mixed", is_published=True,
            tenant=self.legacy_tenant,
        )
        self.right = Question.objects.create(
            question_type="mcq", text="2 + 2?", points=10,
            options=["3", "4", "5", "6"], correct_answer="4", tenant=self.legacy_tenant,
        )
        self.wrong = Question.objects.create(
            question_type="mcq", text="Capital of France?", points=10,
            options=["Lagos", "Paris", "Rome", "Madrid"], correct_answer="Paris", tenant=self.legacy_tenant,
        )
        self.skipped = Question.objects.create(
            question_type="mcq", text="Largest planet?", points=10,
            options=["Mars", "Jupiter", "Venus", "Earth"], correct_answer="Jupiter", tenant=self.legacy_tenant,
        )
        self.theory = Question.objects.create(
            question_type="essay", text="Discuss photosynthesis.", points=20, tenant=self.legacy_tenant,
        )
        self.exam.questions.set([self.right, self.wrong, self.skipped, self.theory])

        self.attempt = ExamAttempt.objects.create(
            exam=self.exam, student=self.student, is_submitted=True,
            end_time=timezone.now(), tenant=self.legacy_tenant,
        )
        StudentAnswer.objects.create(
            attempt=self.attempt, question=self.right, selected_options=1,
            is_correct=True, score=10, tenant=self.legacy_tenant,
        )
        StudentAnswer.objects.create(
            attempt=self.attempt, question=self.wrong, selected_options=0,
            is_correct=False, score=0, tenant=self.legacy_tenant,
        )
        # self.skipped deliberately has no StudentAnswer row at all.
        StudentAnswer.objects.create(
            attempt=self.attempt, question=self.theory, answer_text="Plants use sunlight...",
            is_correct=None, score=None, tenant=self.legacy_tenant,
        )
        self.client = APIClient()
        self.client.force_authenticate(self.teacher)

    def _review(self):
        response = self.client.get(f"/api/exams/attempt/{self.attempt.id}/review/")
        self.assertEqual(response.status_code, 200)
        return response.data

    def test_summary_total_equals_the_sum_of_the_question_rows(self):
        data = self._review()
        row_total = sum(row["marks_awarded"] for row in data["questions"])
        self.assertEqual(data["score"], row_total)
        self.assertEqual(data["score"], 10)          # only the correct MCQ has been awarded
        self.assertEqual(data["total_marks"], 50)    # 10 + 10 + 10 + 20 across the whole paper
        self.assertEqual(sum(row["marks_possible"] for row in data["questions"]), 50)

    def test_ungraded_theory_is_pending_not_a_zero(self):
        data = self._review()
        theory_row = next(row for row in data["questions"] if row["question_id"] == self.theory.id)
        self.assertEqual(theory_row["status"], "pending")
        self.assertEqual(theory_row["marks_awarded"], 0)
        self.assertEqual(theory_row["marks_possible"], 20)
        self.assertEqual(data["pending_questions"], 1)
        # Pending marks are excluded from what has actually been graded, so an
        # admin can see the total only covers 30 of the paper's 50 marks.
        self.assertEqual(data["graded_marks"], 30)
        self.assertEqual(data["incorrect_questions"], 1)

    def test_each_question_status_and_counts(self):
        data = self._review()
        by_id = {row["question_id"]: row for row in data["questions"]}
        self.assertEqual(by_id[self.right.id]["status"], "correct")
        self.assertEqual(by_id[self.right.id]["student_answer"], "B. 4")
        self.assertEqual(by_id[self.right.id]["correct_answer"], "B. 4")
        self.assertEqual(by_id[self.wrong.id]["status"], "incorrect")
        self.assertEqual(by_id[self.wrong.id]["student_answer"], "A. Lagos")
        self.assertEqual(by_id[self.wrong.id]["correct_answer"], "B. Paris")
        self.assertEqual(by_id[self.skipped.id]["status"], "unanswered")
        self.assertEqual(by_id[self.skipped.id]["student_answer"], "")
        self.assertEqual(data["total_questions"], 4)
        self.assertEqual(data["answered_questions"], 3)
        self.assertEqual(data["unanswered_questions"], 1)
        self.assertEqual(data["correct_questions"], 1)

    def test_graded_theory_counts_toward_the_total_and_the_grade(self):
        answer = StudentAnswer.objects.get(attempt=self.attempt, question=self.theory)
        answer.score = 20
        answer.save(update_fields=["score"])

        data = self._review()
        theory_row = next(row for row in data["questions"] if row["question_id"] == self.theory.id)
        self.assertEqual(theory_row["status"], "correct")
        self.assertEqual(data["score"], 30)
        self.assertEqual(data["graded_marks"], 50)
        self.assertEqual(data["pending_questions"], 0)
        self.assertEqual(data["percentage"], 60.0)
        # Resolved through the school's own GradeScale, not a private scale.
        self.assertEqual(data["grade"], "A")

    def test_partially_credited_theory_is_neither_correct_nor_incorrect(self):
        answer = StudentAnswer.objects.get(attempt=self.attempt, question=self.theory)
        answer.score = 12
        answer.save(update_fields=["score"])

        data = self._review()
        theory_row = next(row for row in data["questions"] if row["question_id"] == self.theory.id)
        self.assertEqual(theory_row["status"], "partial")
        self.assertEqual(theory_row["marks_awarded"], 12)
        self.assertEqual(data["score"], 22)
        self.assertEqual(data["partial_questions"], 1)

    def test_students_cannot_read_a_submission_review(self):
        self.client.force_authenticate(self.student)
        response = self.client.get(f"/api/exams/attempt/{self.attempt.id}/review/")
        self.assertEqual(response.status_code, 403)

    def test_a_teacher_from_another_school_cannot_read_it(self):
        other_school = SchoolTenant.objects.create(
            name="Other School", schema_name="other_review_school", is_active=True
        )
        outsider = User.objects.create_user(
            email="outsider@other.edu", password="TeacherPass123", role="teacher",
            tenant=other_school, is_active=True, is_verified=True,
        )
        self.client.force_authenticate(outsider)
        response = self.client.get(f"/api/exams/attempt/{self.attempt.id}/review/")
        self.assertEqual(response.status_code, 404)


class PublishAttemptResultTests(TestCase):
    """Publishing does two separate things - releases the score to the student,
    and pushes it into StudentSubjectScore so report cards and the broadsheet
    pick it up. These pin both, and pin that it cannot happen while theory is
    still ungraded or quietly wipe a teacher's other marks for the subject.
    """

    def setUp(self):
        self.school = SchoolTenant.objects.create(
            name="Publish School", schema_name="publish_school", is_active=True
        )
        self.legacy_tenant = Tenant.objects.create(name=self.school.name, slug=self.school.schema_name)
        GradeScale.objects.create(
            tenant=self.legacy_tenant, letter="A", min_percentage=60, max_percentage=100, remark="Excellent"
        )
        self.teacher = User.objects.create_user(
            email="teacher@publish.edu", password="TeacherPass123", role="teacher",
            tenant=self.school, is_active=True, is_verified=True,
        )
        self.student_user = User.objects.create_user(
            email="pupil@publish.edu", password="StudentPass123", first_name="Ada", last_name="Pupil",
            role="student", tenant=self.school, is_active=True, is_verified=True,
        )
        self.school_class = Class.objects.create(tenant=self.legacy_tenant, name="JSS 1", section="A")
        self.student = StudentProfile.objects.create(
            user=self.student_user, student_id="PUB001", admission_number="ADM-PUB-001",
            admission_date=timezone.now().date(), guardian_name="Guardian", guardian_relation="Parent",
            current_class=self.school_class,
        )
        self.subject = Subject.objects.create(name="Mathematics", code="MTH", tenant=self.legacy_tenant)
        self.exam = Exam.objects.create(
            title="Mid Term", teacher=self.teacher, subject=self.subject, class_group=self.school_class,
            start_date=timezone.now() - timedelta(minutes=5),
            end_date=timezone.now() + timedelta(hours=1),
            duration_minutes=60, exam_format="mixed", is_published=True, tenant=self.legacy_tenant,
        )
        self.objective = Question.objects.create(
            question_type="mcq", text="2 + 2?", points=30,
            options=["3", "4", "5", "6"], correct_answer="4", tenant=self.legacy_tenant,
        )
        self.theory = Question.objects.create(
            question_type="essay", text="Explain addition.", points=20, tenant=self.legacy_tenant,
        )
        self.exam.questions.set([self.objective, self.theory])
        self.attempt = ExamAttempt.objects.create(
            exam=self.exam, student=self.student_user, is_submitted=True,
            score=30, total_points=50, end_time=timezone.now(), tenant=self.legacy_tenant,
        )
        StudentAnswer.objects.create(
            attempt=self.attempt, question=self.objective, selected_options=1,
            is_correct=True, score=30, tenant=self.legacy_tenant,
        )
        self.theory_answer = StudentAnswer.objects.create(
            attempt=self.attempt, question=self.theory, answer_text="You add them.",
            is_correct=None, score=None, tenant=self.legacy_tenant,
        )
        # Rolled-back test DBs reuse primary keys, so a cached idempotency
        # entry from an earlier test can match this one request-for-request.
        cache.clear()
        self.client = APIClient()
        self.client.force_authenticate(self.teacher)

    def _grade_the_theory(self, score=20):
        self.theory_answer.score = score
        self.theory_answer.save(update_fields=["score"])

    def test_cannot_publish_while_theory_is_still_ungraded(self):
        response = self.client.post(f"/api/exams/attempt/{self.attempt.id}/publish-result/")
        self.assertEqual(response.status_code, 400)
        self.attempt.refresh_from_db()
        self.assertIsNone(self.attempt.results_published_at)

    def test_publishing_releases_the_score_and_writes_the_subject_score(self):
        self._grade_the_theory()
        response = self.client.post(f"/api/exams/attempt/{self.attempt.id}/publish-result/")
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.data["added_to_report"])

        self.attempt.refresh_from_db()
        self.assertIsNotNone(self.attempt.results_published_at)
        self.assertEqual(self.attempt.results_published_by, self.teacher)
        self.assertEqual(self.attempt.score, 50)

        score_obj = StudentSubjectScore.objects.get(student=self.student, subject=self.subject)
        # Raw marks awarded, not a percentage.
        self.assertEqual(float(score_obj.cbt_score), 50.0)
        self.assertEqual(float(score_obj.score), 50.0)
        # Enters the results pipeline as a draft, like a teacher-entered score.
        self.assertEqual(score_obj.approval_status, ResultBatch.DRAFT)

    def test_publishing_never_wipes_a_teachers_other_component_marks(self):
        """The other components are the teacher's own marks for theory,
        assessment and so on - a blanket overwrite would silently destroy
        them."""
        existing = StudentSubjectScore.objects.create(
            student=self.student, subject=self.subject, class_group=self.school_class,
            tenant=self.legacy_tenant, score=25, max_score=100,
            theory_score=15, assessment_score=10, approval_status=ResultBatch.APPROVED,
        )
        self._grade_the_theory()
        self.client.post(f"/api/exams/attempt/{self.attempt.id}/publish-result/")

        existing.refresh_from_db()
        self.assertEqual(float(existing.theory_score), 15.0)
        self.assertEqual(float(existing.assessment_score), 10.0)
        self.assertEqual(float(existing.cbt_score), 50.0)
        self.assertEqual(float(existing.score), 75.0)  # 15 + 10 + 50
        # An already-approved row is not quietly knocked back to draft.
        self.assertEqual(existing.approval_status, ResultBatch.APPROVED)

    def test_student_sees_nothing_until_it_is_published(self):
        self._grade_the_theory()
        self.client.force_authenticate(self.student_user)
        response = self.client.get(f"/api/exams/result/{self.attempt.id}/")
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.data["is_published"])
        self.assertNotIn("score", response.data)
        self.assertEqual(response.data["message"], "Exam Completed")

    def test_student_sees_the_score_once_published(self):
        self._grade_the_theory()
        self.client.post(f"/api/exams/attempt/{self.attempt.id}/publish-result/")

        self.client.force_authenticate(self.student_user)
        response = self.client.get(f"/api/exams/result/{self.attempt.id}/")
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.data["is_published"])
        self.assertEqual(response.data["score"], 50)
        self.assertEqual(response.data["total_points"], 50)
        self.assertEqual(response.data["percentage"], 100.0)
        self.assertEqual(response.data["grade"], "A")

    def test_unpublishing_hides_it_again_without_touching_the_subject_score(self):
        self._grade_the_theory()
        self.client.post(f"/api/exams/attempt/{self.attempt.id}/publish-result/")
        response = self.client.post(f"/api/exams/attempt/{self.attempt.id}/unpublish-result/")
        self.assertEqual(response.status_code, 200)

        self.attempt.refresh_from_db()
        self.assertIsNone(self.attempt.results_published_at)
        # The score is a draft in the school's results pipeline by now and may
        # already have been approved, so it is left where it is.
        self.assertTrue(StudentSubjectScore.objects.filter(student=self.student, subject=self.subject).exists())

        self.client.force_authenticate(self.student_user)
        response = self.client.get(f"/api/exams/result/{self.attempt.id}/")
        self.assertFalse(response.data["is_published"])

    def test_students_cannot_publish_their_own_result(self):
        self._grade_the_theory()
        self.client.force_authenticate(self.student_user)
        response = self.client.post(f"/api/exams/attempt/{self.attempt.id}/publish-result/")
        self.assertEqual(response.status_code, 403)
        self.attempt.refresh_from_db()
        self.assertIsNone(self.attempt.results_published_at)

    def test_publishing_still_reaches_the_student_when_there_is_no_subject(self):
        """A missing subject only blocks the report-card half. Failing the whole
        action would leave the student unable to see a result that is ready."""
        self.exam.subject = None
        self.exam.save(update_fields=["subject"])
        self._grade_the_theory()

        response = self.client.post(f"/api/exams/attempt/{self.attempt.id}/publish-result/")
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.data["added_to_report"])
        self.assertTrue(response.data["report_warning"])
        self.attempt.refresh_from_db()
        self.assertIsNotNone(self.attempt.results_published_at)
