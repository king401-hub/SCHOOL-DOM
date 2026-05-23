from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase
from rest_framework.test import APIClient
from pathlib import Path
import tempfile
import zipfile
from xml.sax.saxutils import escape

from academic.models import Class, Subject
from core.models import SchoolTenant
from tenants.models import Tenant
from users.models import StudentProfile
from .models import Choice, PersonalQuizAttempt, PersonalQuizFolder, PersonalQuizFolderQuestion, Question, Quiz, Submission


User = get_user_model()


class StudentQuizSubmitTests(TestCase):
    def setUp(self):
        self.school = SchoolTenant.objects.create(name="Quiz School", schema_name="quiz_school")
        self.legacy_tenant = Tenant.objects.create(name="Quiz School", slug="quiz_school")
        self.teacher = User.objects.create_user(
            email="teacher@quiz.test",
            password="pass12345",
            role="teacher",
            tenant=self.school,
        )
        self.student = User.objects.create_user(
            email="student@quiz.test",
            password="pass12345",
            role="student",
            tenant=self.school,
        )
        self.quiz = Quiz.objects.create(
            tenant=self.legacy_tenant,
            teacher=self.teacher,
            title="Published quiz",
            is_published=True,
            allow_multiple_attempts=False,
        )
        self.question = Question.objects.create(
            tenant=self.legacy_tenant,
            quiz=self.quiz,
            text="What is 2 + 2?",
            points=1,
        )
        self.correct_choice = Choice.objects.create(question=self.question, text="4", is_correct=True)
        self.wrong_choice = Choice.objects.create(question=self.question, text="5", is_correct=False)
        self.client = APIClient()
        self.client.force_authenticate(user=self.student)

    def test_student_can_submit_teacher_quiz(self):
        response = self.client.post(
            f"/api/quizzes/student/{self.quiz.id}/submit/",
            {"answers": [{"question": self.question.id, "choice": self.correct_choice.id}]},
            format="json",
        )

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data["score"], 1)
        self.assertEqual(Submission.objects.filter(quiz=self.quiz, student=self.student).count(), 1)

    def test_repeat_submit_replaces_existing_submission_without_400(self):
        Submission.objects.create(
            tenant=self.legacy_tenant,
            quiz=self.quiz,
            student=self.student,
            score=0,
            total_points=1,
        )

        response = self.client.post(
            f"/api/quizzes/student/{self.quiz.id}/submit/",
            {"answers": [{"question": self.question.id, "choice": self.correct_choice.id}]},
            format="json",
        )

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data["score"], 1)
        self.assertEqual(Submission.objects.filter(quiz=self.quiz, student=self.student).count(), 1)


class DailyPersonalQuizTests(TestCase):
    def setUp(self):
        self.school = SchoolTenant.objects.create(name="Daily Quiz School", schema_name="daily_quiz_school")
        self.legacy_tenant = Tenant.objects.create(name="Daily Quiz School", slug="daily_quiz_school")
        self.school_class = Class.objects.create(tenant=self.legacy_tenant, name="JSS 1", section="A")
        self.subject = Subject.objects.create(tenant=self.legacy_tenant, name="Mathematics", code="MTH")
        self.school_class.subjects.add(self.subject)
        self.student = User.objects.create_user(
            email="daily.student@quiz.test",
            password="pass12345",
            role="student",
            tenant=self.school,
        )
        self.teacher = User.objects.create_user(
            email="daily.teacher@quiz.test",
            password="pass12345",
            role="teacher",
            tenant=self.school,
        )
        StudentProfile.objects.create(
            user=self.student,
            student_id="STDQZ001",
            admission_date="2026-01-01",
            current_class=self.school_class,
        )
        folder = PersonalQuizFolder.objects.create(
            tenant=self.legacy_tenant,
            name="Math pool",
            subject=self.subject,
            class_group=self.school_class,
        )
        for index in range(25):
            PersonalQuizFolderQuestion.objects.create(
                folder=folder,
                question_type="objective",
                prompt=f"Question {index + 1}",
                options=["A", "B", "C", "D"],
                correct_answer="A",
                order=index + 1,
            )
        self.client = APIClient()
        self.client.force_authenticate(user=self.student)

    def test_student_gets_one_daily_subject_attempt_with_fifteen_minute_timer(self):
        response = self.client.post(
            "/api/quizzes/personal/generate/",
            {"subject_id": self.subject.id, "question_count": 20},
            format="json",
        )

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data["time_limit_minutes"], 15)
        self.assertEqual(response.data["question_count"], 20)
        self.assertEqual(PersonalQuizAttempt.objects.count(), 1)

        repeat = self.client.post(
            "/api/quizzes/personal/generate/",
            {"subject_id": self.subject.id, "question_count": 20},
            format="json",
        )
        self.assertEqual(repeat.status_code, 200)
        self.assertEqual(PersonalQuizAttempt.objects.count(), 1)

    def test_personal_quiz_fallback_does_not_use_another_school_pool(self):
        other_tenant = Tenant.objects.create(name="Other Quiz School", slug="other_quiz_school")
        other_folder = PersonalQuizFolder.objects.create(
            tenant=other_tenant,
            name="Other school test pool",
        )
        PersonalQuizFolderQuestion.objects.create(
            folder=other_folder,
            question_type="objective",
            prompt="Other tenant test question should not appear",
            options=["A", "B", "C", "D"],
            correct_answer="A",
            order=1,
        )
        english = Subject.objects.create(tenant=self.legacy_tenant, name="English", code="ENG")
        self.school_class.subjects.add(english)

        response = self.client.post(
            "/api/quizzes/personal/generate/",
            {"subject_id": english.id, "question_count": 3},
            format="json",
        )

        self.assertEqual(response.status_code, 201)
        prompts = [item["prompt"] for item in response.data["questions"]]
        self.assertNotIn("Other tenant test question should not appear", prompts)
        self.assertTrue(any("English" in prompt or "subject" in prompt.lower() for prompt in prompts))

    def test_personal_quiz_uses_global_subject_pool_across_tenants(self):
        global_folder = PersonalQuizFolder.objects.create(
            tenant=None,
            name="Global math pool",
            subject=None,
            subject_code="MTH",
            subject_name="Mathematics",
        )
        PersonalQuizFolderQuestion.objects.create(
            folder=global_folder,
            question_type="objective",
            prompt="Global math question available to every tenant",
            options=["A", "B", "C", "D"],
            correct_answer="A",
            order=1,
        )
        self.legacy_tenant.personal_quiz_folders.all().delete()

        response = self.client.post(
            "/api/quizzes/personal/generate/",
            {"subject_id": self.subject.id, "question_count": 1},
            format="json",
        )

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data["questions"][0]["prompt"], "Global math question available to every tenant")

    def test_personal_quiz_uses_global_general_pool_when_subject_pool_missing(self):
        english = Subject.objects.create(tenant=self.legacy_tenant, name="English", code="ENG")
        self.school_class.subjects.add(english)
        global_folder = PersonalQuizFolder.objects.create(
            tenant=None,
            name="Global general pool",
            subject=None,
            subject_code="",
            subject_name="",
        )
        PersonalQuizFolderQuestion.objects.create(
            folder=global_folder,
            question_type="objective",
            prompt="Global general question available to every tenant",
            options=["A", "B", "C", "D"],
            correct_answer="A",
            order=1,
        )

        response = self.client.post(
            "/api/quizzes/personal/generate/",
            {"subject_id": english.id, "question_count": 1},
            format="json",
        )

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data["questions"][0]["prompt"], "Global general question available to every tenant")

    def test_submitted_daily_subject_cannot_be_recreated_until_next_day(self):
        first = self.client.post(
            "/api/quizzes/personal/generate/",
            {"subject_id": self.subject.id, "question_count": 5},
            format="json",
        )
        answers = [{"question": item["id"], "answer": "A"} for item in first.data["questions"]]
        submit = self.client.post(
            f"/api/quizzes/personal/{first.data['id']}/submit/",
            {"answers": answers},
            format="json",
        )
        self.assertEqual(submit.status_code, 201)
        self.assertEqual(submit.data["score"], 5)
        self.assertEqual(submit.data["grade"]["letter"], "A")

        repeat = self.client.post(
            "/api/quizzes/personal/generate/",
            {"subject_id": self.subject.id, "question_count": 5},
            format="json",
        )
        self.assertEqual(repeat.status_code, 409)

    def test_teacher_cannot_access_personal_quiz_options(self):
        self.client.force_authenticate(user=self.teacher)
        response = self.client.get("/api/quizzes/personal/options/")

        self.assertEqual(response.status_code, 403)


def _write_test_docx(path, lines):
    paragraphs = "".join(
        f"<w:p><w:r><w:t>{escape(line)}</w:t></w:r></w:p>"
        for line in lines
    )
    document = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
        f"<w:body>{paragraphs}</w:body>"
        "</w:document>"
    )
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("word/document.xml", document)


def _write_rich_test_docx(path, paragraphs):
    def run_xml(text, vertical=None, underline=False):
        props = []
        if underline:
            props.append('<w:u w:val="single"/>')
        if vertical:
            props.append(f'<w:vertAlign w:val="{vertical}"/>')
        props_xml = f"<w:rPr>{''.join(props)}</w:rPr>" if props else ""
        return f"<w:r>{props_xml}<w:t>{escape(text)}</w:t></w:r>"

    body = "".join(
        f"<w:p>{''.join(run_xml(**run) for run in paragraph)}</w:p>"
        for paragraph in paragraphs
    )
    document = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
        f"<w:body>{body}</w:body>"
        "</w:document>"
    )
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("word/document.xml", document)


class PersonalQuizDocxImportTests(TestCase):
    def setUp(self):
        self.legacy_tenant = Tenant.objects.create(name="Import School", slug="import_school")
        self.subject = Subject.objects.create(tenant=self.legacy_tenant, name="Biology", code="BIO")
        self.school_class = Class.objects.create(tenant=self.legacy_tenant, name="Science", section="SS1")

    def test_imports_separate_question_and_answer_docx_files(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            folder = Path(temp_dir)
            _write_test_docx(
                folder / "Biology Questions.docx",
                [
                    "1. What do green plants use to make food?",
                    "A. Chlorophyll",
                    "B. Sand",
                    "C. Smoke",
                    "D. Plastic",
                    "2. Which organ pumps blood?",
                    "A. Lung",
                    "B. Heart",
                    "C. Kidney",
                    "D. Skin",
                ],
            )
            _write_test_docx(folder / "Biology Answers.docx", ["1. A", "2. B"])

            call_command(
                "import_personal_quiz_docx",
                str(folder),
                "--tenant-slug",
                self.legacy_tenant.slug,
                "--class",
                "Science",
            )

        folder = PersonalQuizFolder.objects.get(subject=self.subject, class_group=self.school_class)
        questions = list(folder.folder_questions.order_by("order"))
        self.assertEqual(len(questions), 2)
        self.assertEqual(questions[0].question_type, "objective")
        self.assertEqual(questions[0].correct_answer, "Chlorophyll")
        self.assertEqual(questions[1].correct_answer, "Heart")

    def test_imports_single_docx_with_inline_answers(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            docx_path = Path(temp_dir) / "Biology Questions.docx"
            _write_test_docx(
                docx_path,
                [
                    "1. Which organelle is the powerhouse of the cell?",
                    "A. Nucleus",
                    "B. Ribosome",
                    "C. Mitochondrion",
                    "D. Golgi apparatus",
                    "Answer: C",
                    "2. The value of $0^\\circ$ Latitude is the:",
                    "A. Red blood cells",
                    "B. White blood cells",
                    "C. Platelets",
                    "D. Plasma",
                    "Answer: C",
                ],
            )

            call_command(
                "import_personal_quiz_docx",
                str(docx_path),
                "--tenant-slug",
                self.legacy_tenant.slug,
                "--subject",
                "Biology",
            )

        folder = PersonalQuizFolder.objects.get(subject=self.subject, class_group__isnull=True)
        questions = list(folder.folder_questions.order_by("order"))
        self.assertEqual(len(questions), 2)
        self.assertEqual(questions[0].correct_answer, "Mitochondrion")
        self.assertEqual(questions[1].prompt, "The value of 0 degrees Latitude is the:")
        self.assertEqual(questions[1].options, ["Red blood cells", "White blood cells", "Platelets", "Plasma"])

    def test_import_preserves_docx_subscript_and_superscript_runs(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            docx_path = Path(temp_dir) / "Chemistry Questions.docx"
            _write_rich_test_docx(
                docx_path,
                [
                    [
                        {"text": "1. Which electron configuration ends with 1s"},
                        {"text": "2", "vertical": "superscript"},
                        {"text": " 2s"},
                        {"text": "2", "vertical": "superscript"},
                        {"text": "?"},
                    ],
                    [{"text": "A. Hydrogen"}],
                    [{"text": "B. Helium"}],
                    [{"text": "C. Lithium"}],
                    [{"text": "D. Beryllium"}],
                    [{"text": "Answer: D"}],
                    [
                        {"text": "2. Water is written as H"},
                        {"text": "2", "vertical": "subscript"},
                        {"text": "O."},
                    ],
                    [{"text": "A. H2"}],
                    [{"text": "B. H2O"}],
                    [{"text": "C. O2"}],
                    [{"text": "D. CO2"}],
                    [{"text": "Answer: B"}],
                ],
            )

            call_command(
                "import_personal_quiz_docx",
                str(docx_path),
                "--tenant-slug",
                self.legacy_tenant.slug,
                "--subject",
                "Biology",
            )

        folder = PersonalQuizFolder.objects.get(subject=self.subject, class_group__isnull=True)
        questions = list(folder.folder_questions.order_by("order"))
        self.assertIn("1s<sup>2</sup>", questions[0].prompt)
        self.assertIn("2s<sup>2</sup>", questions[0].prompt)
        self.assertIn("H<sub>2</sub>O", questions[1].prompt)

    def test_exam_docx_parser_preserves_docx_subscript_and_superscript_runs(self):
        from exams.management.commands.import_chemistry_docx import parse_docx_questions

        with tempfile.TemporaryDirectory() as temp_dir:
            docx_path = Path(temp_dir) / "Chemistry Questions.docx"
            _write_rich_test_docx(
                docx_path,
                [
                    [
                        {"text": "1. A neutral atom has configuration 1s"},
                        {"text": "2", "vertical": "superscript"},
                        {"text": " 2s"},
                        {"text": "2", "vertical": "superscript"},
                    ],
                    [
                        {"text": "A. H"},
                        {"text": "2", "vertical": "subscript"},
                        {"text": "O"},
                    ],
                    [{"text": "B. NaCl"}],
                    [{"text": "C. CO2"}],
                    [{"text": "D. N2"}],
                    [{"text": "Answer: A"}],
                ],
            )

            questions, warnings = parse_docx_questions(docx_path)

        self.assertEqual(warnings, [])
        self.assertIn("1s<sup>2</sup>", questions[0]["text"])
        self.assertIn("2s<sup>2</sup>", questions[0]["text"])
        self.assertEqual(questions[0]["options"][0], "H<sub>2</sub>O")
