from django.conf import settings
from django.db import models

from core.models import TenantAwareModel, TimeStampedModel


class Quiz(TenantAwareModel):
    # Override tenant to give a unique related_name and avoid clashes with other Question models.
    tenant = models.ForeignKey(
        "tenants.Tenant",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="quiz_quizzes",
    )
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    teacher = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="quizzes")
    is_published = models.BooleanField(default=False)
    allow_multiple_attempts = models.BooleanField(default=False)
    time_limit_minutes = models.PositiveIntegerField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return self.title


class Question(TenantAwareModel):
    tenant = models.ForeignKey(
        "tenants.Tenant",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="quiz_questions",
    )
    quiz = models.ForeignKey(Quiz, related_name="questions", on_delete=models.CASCADE)
    text = models.TextField()
    explanation = models.TextField(blank=True)
    order = models.PositiveIntegerField(default=1)
    points = models.PositiveIntegerField(default=1)

    class Meta:
        ordering = ["order", "id"]

    def __str__(self) -> str:
        return self.text[:60]


class Choice(TimeStampedModel):
    question = models.ForeignKey(Question, related_name="choices", on_delete=models.CASCADE)
    text = models.CharField(max_length=255)
    is_correct = models.BooleanField(default=False)

    class Meta:
        ordering = ["id"]

    def __str__(self) -> str:
        return self.text[:80]


class Submission(TenantAwareModel):
    tenant = models.ForeignKey(
        "tenants.Tenant",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="quiz_submissions",
    )
    quiz = models.ForeignKey(Quiz, related_name="submissions", on_delete=models.CASCADE)
    student = models.ForeignKey(settings.AUTH_USER_MODEL, related_name="quiz_submissions", on_delete=models.CASCADE)
    score = models.FloatField(default=0)
    total_points = models.FloatField(default=0)
    submitted_at = models.DateTimeField(auto_now_add=True)
    is_final = models.BooleanField(default=True)

    class Meta:
        ordering = ["-submitted_at"]

    def __str__(self) -> str:
        return f"{self.student} • {self.quiz} ({self.score}/{self.total_points})"


class Answer(TimeStampedModel):
    submission = models.ForeignKey(Submission, related_name="answers", on_delete=models.CASCADE)
    question = models.ForeignKey(Question, related_name="answers", on_delete=models.CASCADE)
    choice = models.ForeignKey(Choice, related_name="answers", on_delete=models.SET_NULL, null=True, blank=True)
    is_correct = models.BooleanField(default=False)
    earned_points = models.FloatField(default=0)

    class Meta:
        unique_together = ("submission", "question")
        ordering = ["question_id"]

    def __str__(self) -> str:
        return f"{self.question} -> {self.choice}"


class PersonalQuizAttempt(TenantAwareModel):
    tenant = models.ForeignKey(
        "tenants.Tenant",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="personal_quiz_attempts",
    )
    student = models.ForeignKey(settings.AUTH_USER_MODEL, related_name="personal_quiz_attempts", on_delete=models.CASCADE)
    subject = models.ForeignKey("academic.Subject", related_name="personal_quiz_attempts", on_delete=models.SET_NULL, null=True, blank=True)
    class_group = models.ForeignKey("academic.Class", related_name="personal_quiz_attempts", on_delete=models.SET_NULL, null=True, blank=True)
    title = models.CharField(max_length=255)
    time_limit_minutes = models.PositiveIntegerField(default=10)
    score = models.FloatField(default=0)
    total_points = models.FloatField(default=0)
    daily_date = models.DateField(null=True, blank=True)
    started_at = models.DateTimeField(auto_now_add=True)
    submitted_at = models.DateTimeField(null=True, blank=True)
    is_submitted = models.BooleanField(default=False)
    auto_submitted = models.BooleanField(default=False)

    class Meta:
        ordering = ["-started_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["student", "subject", "daily_date"],
                name="unique_personal_daily_quiz_per_subject",
            )
        ]

    def __str__(self) -> str:
        return f"{self.student} - {self.title}"


class PersonalQuizFolder(TenantAwareModel):
    """Question folder used only by student personal quizzes."""

    tenant = models.ForeignKey(
        "tenants.Tenant",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="personal_quiz_folders",
    )
    name = models.CharField(max_length=160, default="Personal Quiz Questions")
    description = models.TextField(blank=True)
    subject = models.ForeignKey("academic.Subject", related_name="personal_quiz_folders", on_delete=models.SET_NULL, null=True, blank=True)
    subject_code = models.CharField(max_length=40, blank=True)
    subject_name = models.CharField(max_length=120, blank=True)
    class_group = models.ForeignKey("academic.Class", related_name="personal_quiz_folders", on_delete=models.SET_NULL, null=True, blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["name", "id"]

    def __str__(self) -> str:
        return self.name


class PersonalQuizFolderQuestion(TimeStampedModel):
    OBJECTIVE = "objective"
    TRUE_FALSE = "true_false"
    FILL_BLANK = "fill_blank"
    TYPE_CHOICES = [
        (OBJECTIVE, "Objective"),
        (TRUE_FALSE, "True or False"),
        (FILL_BLANK, "Fill in the blank"),
    ]

    folder = models.ForeignKey(PersonalQuizFolder, related_name="folder_questions", on_delete=models.CASCADE)
    question_type = models.CharField(max_length=20, choices=TYPE_CHOICES, default=OBJECTIVE)
    prompt = models.TextField()
    options = models.JSONField(default=list, blank=True)
    correct_answer = models.CharField(max_length=255)
    explanation = models.TextField(blank=True)
    order = models.PositiveIntegerField(default=1)
    points = models.PositiveIntegerField(default=1)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["order", "id"]

    def __str__(self) -> str:
        return self.prompt[:70]


class PersonalQuizQuestion(TimeStampedModel):
    OBJECTIVE = "objective"
    TRUE_FALSE = "true_false"
    FILL_BLANK = "fill_blank"
    TYPE_CHOICES = [
        (OBJECTIVE, "Objective"),
        (TRUE_FALSE, "True or False"),
        (FILL_BLANK, "Fill in the blank"),
    ]

    attempt = models.ForeignKey(PersonalQuizAttempt, related_name="questions", on_delete=models.CASCADE)
    question_type = models.CharField(max_length=20, choices=TYPE_CHOICES)
    prompt = models.TextField()
    options = models.JSONField(default=list, blank=True)
    correct_answer = models.CharField(max_length=255)
    explanation = models.TextField(blank=True)
    order = models.PositiveIntegerField(default=1)
    points = models.PositiveIntegerField(default=1)

    class Meta:
        ordering = ["order", "id"]

    def __str__(self) -> str:
        return self.prompt[:70]


class PersonalQuizAnswer(TimeStampedModel):
    attempt = models.ForeignKey(PersonalQuizAttempt, related_name="answers", on_delete=models.CASCADE)
    question = models.ForeignKey(PersonalQuizQuestion, related_name="answers", on_delete=models.CASCADE)
    answer_text = models.CharField(max_length=255, blank=True)
    is_correct = models.BooleanField(default=False)
    earned_points = models.FloatField(default=0)

    class Meta:
        unique_together = ("attempt", "question")
