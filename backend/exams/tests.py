from datetime import timedelta

from django.core import mail
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient

from users.models import User
from .models import Exam, ExamAttempt, Question, StudentAnswer


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
