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

    def _create_exam(self, teacher, questions, exam_format="objective", title="Bank Test Exam", class_id=None):
        start = timezone.now() + timedelta(days=2)
        end = start + timedelta(hours=1)
        self.client.force_authenticate(user=teacher)
        payload = {
            "title": title,
            "assessment_type": "test",
            "subject_id": self.subject.id,
            "exam_format": exam_format,
            "start_date": start.isoformat(),
            "end_date": end.isoformat(),
            "duration_minutes": 30,
            "questions": questions,
        }
        if class_id is not None:
            payload["class_id"] = class_id
        response = self.client.post("/api/app/exams/create/", data=payload, format="json")
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


class QuestionBankClassSeparationTests(TestCase):
    """QuestionBank.school_class - a bank now accumulates per (subject,
    class) pair, not just per subject, so a JSS1 and an SS1 bank for the
    same subject stay separate."""

    def setUp(self):
        self.client = APIClient()
        self.school = SchoolTenant.objects.create(name="Class Bank School", schema_name="class_bank_school", is_active=True)
        self.legacy_tenant = Tenant.objects.create(name="Class Bank School Legacy", slug="class_bank_school")
        self.subject = Subject.objects.create(tenant=self.legacy_tenant, name="Mathematics", code="MTH")
        self.jss1 = Class.objects.create(name="JSS1", section="A", tenant=self.legacy_tenant)
        self.ss1 = Class.objects.create(name="SS1", section="A", tenant=self.legacy_tenant)

        self.teacher = User.objects.create_user(
            email="teacher@classbankschool.edu", password="TeacherPass123", first_name="Taylor", last_name="Teacher",
            role="teacher", tenant=self.school, is_active=True, is_verified=True,
        )
        profile = TeacherProfile.objects.create(
            user=self.teacher, employee_id="EMP-CB-1", qualification="B.Ed", specialization="Mathematics",
            years_of_experience=4, hire_date=timezone.now().date(), employment_type="full_time",
            emergency_contact_name="Contact", emergency_contact_phone="+15550001111", emergency_contact_relation="Sibling",
        )
        profile.assigned_classes.add(self.jss1, self.ss1)
        profile.subjects.add(self.subject)

    def _create_exam(self, questions, class_id, title="Class Bank Exam"):
        start = timezone.now() + timedelta(days=2)
        end = start + timedelta(hours=1)
        self.client.force_authenticate(user=self.teacher)
        response = self.client.post(
            "/api/app/exams/create/",
            data={
                "title": title,
                "assessment_type": "test",
                "subject_id": self.subject.id,
                "class_id": class_id,
                "exam_format": "objective",
                "start_date": start.isoformat(),
                "end_date": end.isoformat(),
                "duration_minutes": 30,
                "questions": questions,
            },
            format="json",
        )
        self.assertEqual(response.status_code, 201, response.data)
        return response.data

    def test_two_classes_in_the_same_subject_get_two_separate_banks(self):
        self._create_exam(
            [{"text": "JSS1 question?", "options": ["A", "B"], "correct_answer": "A", "points": 1, "save_to_bank": True}],
            class_id=self.jss1.id, title="JSS1 Exam",
        )
        self._create_exam(
            [{"text": "SS1 question?", "options": ["A", "B"], "correct_answer": "B", "points": 1, "save_to_bank": True}],
            class_id=self.ss1.id, title="SS1 Exam",
        )
        self.assertEqual(QuestionBank.objects.filter(teacher=self.teacher, subject=self.subject).count(), 2)
        jss1_bank = QuestionBank.objects.get(teacher=self.teacher, subject=self.subject, school_class=self.jss1)
        ss1_bank = QuestionBank.objects.get(teacher=self.teacher, subject=self.subject, school_class=self.ss1)
        self.assertEqual(jss1_bank.questions.get().text, "JSS1 question?")
        self.assertEqual(ss1_bank.questions.get().text, "SS1 question?")

    def test_the_listing_endpoint_can_filter_by_class(self):
        self._create_exam(
            [{"text": "JSS1 only?", "options": ["A", "B"], "correct_answer": "A", "points": 1, "save_to_bank": True}],
            class_id=self.jss1.id,
        )
        self._create_exam(
            [{"text": "SS1 only?", "options": ["A", "B"], "correct_answer": "A", "points": 1, "save_to_bank": True}],
            class_id=self.ss1.id,
        )
        self.client.force_authenticate(user=self.teacher)
        response = self.client.get(f"/api/app/exams/question-bank/?class_id={self.jss1.id}")
        self.assertEqual(response.status_code, 200, response.data)
        texts = {row["text"] for row in response.data["questions"]}
        self.assertIn("JSS1 only?", texts)
        self.assertNotIn("SS1 only?", texts)
        for bank in response.data["banks"]:
            self.assertEqual(bank["class_id"], self.jss1.id)


class QuestionBankSaveOnUpdateTests(TestCase):
    """exam_detail's PATCH path (draft saves and every auto-save tick after
    the first) used to silently ignore save_to_bank entirely - only the
    one-shot exam_create call ever honored it. This is the path a teacher
    actually hits on every edit after the exam already exists."""

    def setUp(self):
        self.client = APIClient()
        self.school = SchoolTenant.objects.create(name="Update Bank School", schema_name="update_bank_school", is_active=True)
        self.legacy_tenant = Tenant.objects.create(name="Update Bank School Legacy", slug="update_bank_school")
        self.subject = Subject.objects.create(tenant=self.legacy_tenant, name="Chemistry", code="CHM")
        self.teacher = User.objects.create_user(
            email="teacher@updatebankschool.edu", password="TeacherPass123", first_name="Uma", last_name="Teacher",
            role="teacher", tenant=self.school, is_active=True, is_verified=True,
        )
        profile = TeacherProfile.objects.create(
            user=self.teacher, employee_id="EMP-UB-1", qualification="B.Ed", specialization="Chemistry",
            years_of_experience=4, hire_date=timezone.now().date(), employment_type="full_time",
            emergency_contact_name="Contact", emergency_contact_phone="+15550001111", emergency_contact_relation="Sibling",
        )
        profile.subjects.add(self.subject)

        start = timezone.now() + timedelta(days=2)
        end = start + timedelta(hours=1)
        self.client.force_authenticate(user=self.teacher)
        create_response = self.client.post(
            "/api/app/exams/create/",
            data={
                "title": "Draft Exam", "assessment_type": "test", "subject_id": self.subject.id,
                "exam_format": "objective", "start_date": start.isoformat(), "end_date": end.isoformat(),
                "duration_minutes": 30,
                "questions": [{"text": "Not banked yet?", "options": ["A", "B"], "correct_answer": "A", "points": 1}],
            },
            format="json",
        )
        self.assertEqual(create_response.status_code, 201, create_response.data)
        self.exam_id = create_response.data["exam"]["id"]
        from exams.models import Exam
        self.question = Exam.objects.get(id=self.exam_id).questions.get()

    def test_ticking_save_to_bank_on_a_patch_actually_saves_it(self):
        self.assertFalse(QuestionBank.objects.filter(teacher=self.teacher, subject=self.subject).exists())

        response = self.client.patch(
            f"/api/app/exams/{self.exam_id}/",
            data={
                "questions": [
                    {
                        "id": self.question.id, "text": "Not banked yet?", "options": ["A", "B"],
                        "correct_answer": "A", "points": 1, "save_to_bank": True,
                    }
                ],
            },
            format="json",
        )
        self.assertEqual(response.status_code, 200, response.data)
        bank = QuestionBank.objects.get(teacher=self.teacher, subject=self.subject, board="")
        self.assertEqual(bank.questions.get().id, self.question.id)

    def test_a_question_already_sourced_from_a_bank_can_still_be_saved_again(self):
        """The frontend used to suppress save_to_bank once a question had a
        source_question_id (i.e. came from the bank already) - but the
        backend itself never enforced that, and shouldn't: the same
        question reused in a different exam's subject/class should still
        be filed under THIS exam's own bank when the teacher asks for it."""
        response = self.client.patch(
            f"/api/app/exams/{self.exam_id}/",
            data={
                "questions": [
                    {
                        "id": self.question.id, "text": "Not banked yet?", "options": ["A", "B"],
                        "correct_answer": "A", "points": 1, "save_to_bank": True,
                        "source_question_id": self.question.id,
                    }
                ],
            },
            format="json",
        )
        self.assertEqual(response.status_code, 200, response.data)
        bank = QuestionBank.objects.get(teacher=self.teacher, subject=self.subject, board="")
        self.assertEqual(bank.questions.count(), 1)
