"""A teacher can opt a question they just wrote into their own reusable
per-subject question bank instead of it being lost once the exam it was
written for is archived/deleted - see users.app_views._save_questions_to_
teacher_bank, cbt_question_bank (the listing endpoint, already built and
correctly tenant-scoped, but never actually populated or called from the
frontend until this feature), and the two new share/nominate toggles.

The central promise under test, same as the branch-switching work: a
teacher's saved questions must never be visible to a teacher at a
different school, even though both reach the exact same endpoint.
"""
from datetime import timedelta

from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from academic.models import Class, Subject
from core.models import SchoolTenant
from exams.models import QuestionBank
from tenants.models import Tenant
from users.models import TeacherProfile, User


class QuestionBankTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.school = SchoolTenant.objects.create(name="Bank School", schema_name="bank_school", is_active=True)
        self.legacy_tenant = Tenant.objects.create(name="Bank School Legacy", slug="bank_school")
        self.subject = Subject.objects.create(tenant=self.legacy_tenant, name="Biology", code="BIO")
        self.classroom = Class.objects.create(name="SS1", section="A", tenant=self.legacy_tenant)

        self.teacher = self._make_teacher("teacher@bankschool.edu", "Taylor", "Teacher")
        self.colleague = self._make_teacher("colleague@bankschool.edu", "Cole", "League")

        self.other_school = SchoolTenant.objects.create(name="Other Bank School", schema_name="other_bank_school", is_active=True)
        self.other_legacy_tenant = Tenant.objects.create(name="Other Bank School Legacy", slug="other_bank_school")
        self.other_subject = Subject.objects.create(tenant=self.other_legacy_tenant, name="Biology", code="BIO")
        self.other_teacher = User.objects.create_user(
            email="teacher@otherbankschool.edu", password="TeacherPass123", first_name="Oli", last_name="Teacher",
            role="teacher", tenant=self.other_school, is_active=True, is_verified=True,
        )
        TeacherProfile.objects.create(
            user=self.other_teacher, employee_id="OTH-1", qualification="B.Ed", specialization="Biology",
            years_of_experience=3, hire_date=timezone.now().date(), employment_type="full_time",
            emergency_contact_name="Contact", emergency_contact_phone="+15550001111", emergency_contact_relation="Sibling",
        ).subjects.add(self.other_subject)

    def _make_teacher(self, email, first_name, last_name):
        user = User.objects.create_user(
            email=email, password="TeacherPass123", first_name=first_name, last_name=last_name,
            role="teacher", tenant=self.school, is_active=True, is_verified=True,
        )
        profile = TeacherProfile.objects.create(
            user=user, employee_id=f"EMP-{email}", qualification="B.Ed", specialization="Biology",
            years_of_experience=4, hire_date=timezone.now().date(), employment_type="full_time",
            emergency_contact_name="Contact", emergency_contact_phone="+15550001111", emergency_contact_relation="Sibling",
        )
        profile.assigned_classes.add(self.classroom)
        profile.subjects.add(self.subject)
        return user

    def _create_exam(self, teacher, questions, exam_format="objective", title="Bank Test Exam"):
        start = timezone.now() + timedelta(days=2)
        end = start + timedelta(hours=1)
        self.client.force_authenticate(user=teacher)
        response = self.client.post(
            "/api/app/exams/create/",
            data={
                "title": title,
                "assessment_type": "test",
                "subject_id": self.subject.id,
                "exam_format": exam_format,
                "start_date": start.isoformat(),
                "end_date": end.isoformat(),
                "duration_minutes": 30,
                "questions": questions,
            },
            format="json",
        )
        self.assertEqual(response.status_code, 201, response.data)
        return response.data

    def test_saving_a_question_creates_a_reusable_bank(self):
        self._create_exam(
            self.teacher,
            [{"text": "What is the powerhouse of the cell?", "options": ["Nucleus", "Mitochondria", "Ribosome", "Golgi"],
              "correct_answer": "Mitochondria", "points": 1, "save_to_bank": True}],
        )
        bank = QuestionBank.objects.get(teacher=self.teacher, subject=self.subject, board="")
        self.assertEqual(bank.questions.count(), 1)
        self.assertEqual(bank.questions.first().text, "What is the powerhouse of the cell?")

    def test_a_question_without_save_to_bank_is_not_saved(self):
        self._create_exam(
            self.teacher,
            [{"text": "Unsaved question?", "options": ["A", "B"], "correct_answer": "A", "points": 1}],
        )
        self.assertFalse(QuestionBank.objects.filter(teacher=self.teacher, subject=self.subject, board="").exists())

    def test_theory_questions_are_never_saved_to_the_bank(self):
        self._create_exam(
            self.teacher,
            [
                {"text": "Objective one?", "options": ["A", "B"], "correct_answer": "A", "points": 1, "save_to_bank": True},
                {"text": "Explain photosynthesis.", "question_type": "essay", "points": 5, "save_to_bank": True},
            ],
            exam_format="mixed",
        )
        bank = QuestionBank.objects.get(teacher=self.teacher, subject=self.subject, board="")
        self.assertEqual(bank.questions.count(), 1)
        self.assertEqual(bank.questions.first().question_type, "mcq")

    def test_a_second_exam_adds_to_the_same_accumulating_bank(self):
        self._create_exam(
            self.teacher,
            [{"text": "First question?", "options": ["A", "B"], "correct_answer": "A", "points": 1, "save_to_bank": True}],
            title="Exam One",
        )
        self._create_exam(
            self.teacher,
            [{"text": "Second question?", "options": ["A", "B"], "correct_answer": "B", "points": 1, "save_to_bank": True}],
            title="Exam Two",
        )
        self.assertEqual(QuestionBank.objects.filter(teacher=self.teacher, subject=self.subject, board="").count(), 1)
        bank = QuestionBank.objects.get(teacher=self.teacher, subject=self.subject, board="")
        self.assertEqual(bank.questions.count(), 2)

    def test_the_listing_endpoint_shows_a_teachers_own_saved_questions(self):
        self._create_exam(
            self.teacher,
            [{"text": "Listed question?", "options": ["A", "B"], "correct_answer": "A", "points": 1, "save_to_bank": True}],
        )
        self.client.force_authenticate(user=self.teacher)
        response = self.client.get("/api/app/exams/question-bank/")
        self.assertEqual(response.status_code, 200, response.data)
        texts = {row["text"] for row in response.data["questions"]}
        self.assertIn("Listed question?", texts)
        own_bank = next(b for b in response.data["banks"] if b["is_mine"])
        self.assertFalse(own_bank["is_shared"])
        self.assertFalse(own_bank["nominated_for_central_bank"])

    def test_a_teachers_bank_is_invisible_to_a_teacher_at_a_different_school(self):
        self._create_exam(
            self.teacher,
            [{"text": "Private to my school?", "options": ["A", "B"], "correct_answer": "A", "points": 1, "save_to_bank": True}],
        )
        self.client.force_authenticate(user=self.other_teacher)
        response = self.client.get("/api/app/exams/question-bank/")
        self.assertEqual(response.status_code, 200, response.data)
        texts = {row["text"] for row in response.data["questions"]}
        self.assertNotIn("Private to my school?", texts)
        self.assertFalse(any(b["name"] and "Taylor" in b["name"] for b in response.data["banks"]))

    def test_an_unshared_bank_is_invisible_to_a_colleague_without_the_subject_assigned(self):
        colleague_no_subject = self._make_teacher("nobio@bankschool.edu", "No", "Biology")
        TeacherProfile.objects.filter(user=colleague_no_subject).first().subjects.clear()
        self._create_exam(
            self.teacher,
            [{"text": "Not shared yet?", "options": ["A", "B"], "correct_answer": "A", "points": 1, "save_to_bank": True}],
        )
        self.client.force_authenticate(user=colleague_no_subject)
        response = self.client.get("/api/app/exams/question-bank/")
        texts = {row["text"] for row in response.data["questions"]}
        self.assertNotIn("Not shared yet?", texts)

    def test_sharing_a_bank_makes_it_visible_to_colleagues_at_the_same_school(self):
        self._create_exam(
            self.teacher,
            [{"text": "Now shared?", "options": ["A", "B"], "correct_answer": "A", "points": 1, "save_to_bank": True}],
        )
        bank = QuestionBank.objects.get(teacher=self.teacher, subject=self.subject, board="")

        self.client.force_authenticate(user=self.teacher)
        share_response = self.client.post(f"/api/app/exams/question-bank/{bank.id}/share/", {"is_shared": True}, format="json")
        self.assertEqual(share_response.status_code, 200, share_response.data)
        self.assertTrue(share_response.data["is_shared"])

        self.client.force_authenticate(user=self.colleague)
        response = self.client.get("/api/app/exams/question-bank/")
        texts = {row["text"] for row in response.data["questions"]}
        self.assertIn("Now shared?", texts)

    def test_a_colleague_cannot_share_someone_elses_bank(self):
        self._create_exam(
            self.teacher,
            [{"text": "Not yours to share?", "options": ["A", "B"], "correct_answer": "A", "points": 1, "save_to_bank": True}],
        )
        bank = QuestionBank.objects.get(teacher=self.teacher, subject=self.subject, board="")
        self.client.force_authenticate(user=self.colleague)
        response = self.client.post(f"/api/app/exams/question-bank/{bank.id}/share/", {"is_shared": True}, format="json")
        self.assertEqual(response.status_code, 404)
        bank.refresh_from_db()
        self.assertFalse(bank.is_shared)

    def test_nominating_a_bank_for_the_central_bank_sets_the_flag_and_timestamp(self):
        self._create_exam(
            self.teacher,
            [{"text": "Worth nominating?", "options": ["A", "B"], "correct_answer": "A", "points": 1, "save_to_bank": True}],
        )
        bank = QuestionBank.objects.get(teacher=self.teacher, subject=self.subject, board="")
        self.client.force_authenticate(user=self.teacher)
        response = self.client.post(f"/api/app/exams/question-bank/{bank.id}/nominate/", {"nominated": True}, format="json")
        self.assertEqual(response.status_code, 200, response.data)
        self.assertTrue(response.data["nominated_for_central_bank"])
        bank.refresh_from_db()
        self.assertTrue(bank.nominated_for_central_bank)
        self.assertIsNotNone(bank.nominated_at)

        # Un-nominating clears the timestamp too, not just the flag.
        response = self.client.post(f"/api/app/exams/question-bank/{bank.id}/nominate/", {"nominated": False}, format="json")
        self.assertEqual(response.status_code, 200, response.data)
        bank.refresh_from_db()
        self.assertFalse(bank.nominated_for_central_bank)
        self.assertIsNone(bank.nominated_at)
