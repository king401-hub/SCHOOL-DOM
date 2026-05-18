# exams/models.py
import hashlib
import hmac
import secrets
import string

from django.conf import settings
from django.contrib.auth.hashers import check_password, make_password
from django.db import models
from django.utils import timezone
from core.models import TimeStampedModel, TenantAwareModel

class ExamType(TenantAwareModel, TimeStampedModel):
    name = models.CharField(max_length=100)  # MCQ, Essay, Mixed
    
    def __str__(self):
        return self.name

class QuestionBank(TenantAwareModel, TimeStampedModel):
    name = models.CharField(max_length=200)
    subject = models.ForeignKey('academic.Subject', on_delete=models.CASCADE)
    teacher = models.ForeignKey('users.User', on_delete=models.CASCADE)
    questions = models.ManyToManyField('Question', related_name='question_banks')
    is_shared = models.BooleanField(default=False)


class QuestionGroup(TenantAwareModel, TimeStampedModel):
    GROUP_TYPES = [
        ("comprehension", "Comprehension"),
        ("register", "Register"),
        ("passage", "Passage"),
        ("diagram", "Diagram / Chart"),
        ("other", "Other"),
    ]

    title = models.CharField(max_length=200, blank=True, default="")
    group_type = models.CharField(max_length=30, choices=GROUP_TYPES, default="passage")
    passage_text = models.TextField(blank=True, default="")
    image = models.ImageField(upload_to="question_passages/", null=True, blank=True)
    teacher = models.ForeignKey("users.User", on_delete=models.SET_NULL, null=True, blank=True, related_name="question_groups")

    class Meta:
        ordering = ["created_at", "id"]

    def __str__(self):
        return self.title or f"{self.get_group_type_display()} {self.pk}"


class Question(TenantAwareModel, TimeStampedModel):
    QUESTION_TYPES = [
        ('mcq', 'Multiple Choice'),
        ('true_false', 'True/False'),
        ('short_answer', 'Short Answer'),
        ('essay', 'Essay'),
    ]
    
    question_type = models.CharField(max_length=20, choices=QUESTION_TYPES)
    text = models.TextField()
    image = models.ImageField(upload_to='question_images/', null=True, blank=True)
    points = models.IntegerField(default=1)
    options = models.JSONField(null=True, blank=True)  # For MCQ
    correct_answer = models.TextField(null=True, blank=True)
    explanation = models.TextField(null=True, blank=True)
    group = models.ForeignKey(QuestionGroup, on_delete=models.SET_NULL, null=True, blank=True, related_name="questions")
    group_order = models.PositiveIntegerField(default=0)

class Exam(TenantAwareModel, TimeStampedModel):
    title = models.CharField(max_length=200)
    subject = models.ForeignKey('academic.Subject', on_delete=models.CASCADE, null=True, blank=True)
    class_group = models.ForeignKey('academic.Class', on_delete=models.CASCADE, null=True, blank=True)
    teacher = models.ForeignKey('users.User', on_delete=models.CASCADE, null=True, blank=True)
    exam_type = models.ForeignKey(ExamType, on_delete=models.CASCADE, null=True, blank=True)
    questions = models.ManyToManyField(Question, related_name="exams", blank=True)
    instructions = models.TextField(blank=True)
    
    # Scheduling
    start_date = models.DateTimeField()
    end_date = models.DateTimeField()
    duration_minutes = models.IntegerField()
    
    # Settings
    shuffle_questions = models.BooleanField(default=False)
    show_results_immediately = models.BooleanField(default=False)
    allow_retake = models.BooleanField(default=False)
    max_attempts = models.IntegerField(default=1)
    
    # Offline support
    offline_package_id = models.UUIDField(null=True, blank=True)
    last_sync = models.DateTimeField(null=True, blank=True)
    is_published = models.BooleanField(default=False)


class ExamPin(TenantAwareModel, TimeStampedModel):
    USE_ONE_TIME = "one_time"
    USE_REUSABLE = "reusable"
    USE_CHOICES = [
        (USE_ONE_TIME, "One-time use"),
        (USE_REUSABLE, "Reusable"),
    ]

    exam = models.ForeignKey(Exam, on_delete=models.CASCADE, related_name="pins")
    pin_digest = models.CharField(max_length=64, unique=True, db_index=True)
    pin_hash = models.CharField(max_length=128)
    pin_preview = models.CharField(max_length=8, blank=True, default="")
    usage_policy = models.CharField(max_length=20, choices=USE_CHOICES, default=USE_ONE_TIME)
    expires_at = models.DateTimeField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    created_by = models.ForeignKey(
        "users.User",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="generated_exam_pins",
    )
    deactivated_by = models.ForeignKey(
        "users.User",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="deactivated_exam_pins",
    )
    deactivated_at = models.DateTimeField(null=True, blank=True)
    reset_at = models.DateTimeField(null=True, blank=True)
    reset_by = models.ForeignKey(
        "users.User",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="reset_exam_pins",
    )
    last_regenerated_at = models.DateTimeField(null=True, blank=True)
    last_regenerated_by = models.ForeignKey(
        "users.User",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="regenerated_exam_pins",
    )

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["exam", "is_active", "expires_at"]),
            models.Index(fields=["tenant", "created_at"]),
        ]

    @staticmethod
    def normalize_pin(pin):
        return "".join(str(pin or "").upper().split())

    @classmethod
    def digest_pin(cls, pin):
        normalized = cls.normalize_pin(pin)
        secret = str(getattr(settings, "SECRET_KEY", "schooldom-exam-pin-secret")).encode("utf-8")
        return hmac.new(secret, normalized.encode("utf-8"), hashlib.sha256).hexdigest()

    @classmethod
    def generate_plain_pin(cls, length=5):
        alphabet = string.ascii_uppercase + string.digits
        while True:
            plain_pin = "".join(secrets.choice(alphabet) for _ in range(5))
            if any(char.isalpha() for char in plain_pin) and any(char.isdigit() for char in plain_pin):
                return plain_pin

    def set_pin(self, plain_pin):
        normalized = self.normalize_pin(plain_pin)
        self.pin_digest = self.digest_pin(normalized)
        self.pin_hash = make_password(normalized)
        self.pin_preview = normalized[-4:]

    def check_pin(self, plain_pin):
        return check_password(self.normalize_pin(plain_pin), self.pin_hash)

    @property
    def is_expired(self):
        return bool(self.expires_at and self.expires_at <= timezone.now())

    def successful_usage_queryset(self):
        queryset = self.usages.filter(status=ExamPinUsage.STATUS_ACCEPTED)
        if self.reset_at:
            queryset = queryset.filter(created_at__gte=self.reset_at)
        return queryset

    def can_be_used(self):
        if not self.is_active:
            return False, "PIN has been deactivated."
        if self.is_expired:
            return False, "PIN has expired."
        if self.usage_policy == self.USE_ONE_TIME and self.successful_usage_queryset().exists():
            return False, "PIN has already been used."
        return True, ""

    def __str__(self):
        return f"{self.exam.title} PIN ending {self.pin_preview or 'hidden'}"


class ExamPinUsage(TenantAwareModel, TimeStampedModel):
    STATUS_ACCEPTED = "accepted"
    STATUS_REJECTED = "rejected"
    STATUS_RESET = "reset"
    STATUS_REGENERATED = "regenerated"
    STATUS_DEACTIVATED = "deactivated"
    STATUS_CHOICES = [
        (STATUS_ACCEPTED, "Accepted"),
        (STATUS_REJECTED, "Rejected"),
        (STATUS_RESET, "Reset"),
        (STATUS_REGENERATED, "Regenerated"),
        (STATUS_DEACTIVATED, "Deactivated"),
    ]

    pin = models.ForeignKey(ExamPin, on_delete=models.CASCADE, related_name="usages", null=True, blank=True)
    exam = models.ForeignKey(Exam, on_delete=models.CASCADE, related_name="pin_usage_events")
    student = models.ForeignKey(
        "users.User",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="exam_pin_usage_events",
    )
    attempt = models.ForeignKey("exams.ExamAttempt", on_delete=models.SET_NULL, null=True, blank=True, related_name="pin_usage_events")
    entered_pin_digest = models.CharField(max_length=64, blank=True, default="", db_index=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES)
    message = models.CharField(max_length=255, blank=True, default="")
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.CharField(max_length=255, blank=True, default="")

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["exam", "status", "created_at"]),
            models.Index(fields=["pin", "status", "created_at"]),
        ]
class ExamAttempt(TenantAwareModel, TimeStampedModel):
    exam = models.ForeignKey(Exam, on_delete=models.CASCADE)
    student = models.ForeignKey('users.User', on_delete=models.CASCADE)
    start_time = models.DateTimeField(auto_now_add=True)
    end_time = models.DateTimeField(null=True, blank=True)
    is_completed = models.BooleanField(default=False)
    is_submitted = models.BooleanField(default=False)
    score = models.FloatField(default=0)
    total_points = models.FloatField(default=0)
    percentage = models.FloatField(default=0)
    graded_at = models.DateTimeField(null=True, blank=True)
    auto_submitted = models.BooleanField(default=False)
    auto_submit_reason = models.CharField(max_length=80, blank=True, default="")
    auto_submit_reason_display = models.CharField(max_length=160, blank=True, default="")
    auto_submit_details = models.TextField(blank=True, default="")
    auto_submit_warning_history = models.JSONField(default=list, blank=True)
    auto_submit_activity_logs = models.JSONField(default=list, blank=True)
    question_order = models.JSONField(default=list, blank=True)
    
    # Sync fields
    device_id = models.CharField(max_length=255, null=True, blank=True)
    is_offline = models.BooleanField(default=False)
    sync_status = models.CharField(
        max_length=20,
        choices=[('pending', 'Pending'), ('synced', 'Synced'), ('failed', 'Failed')],
        default='pending'
    )

class StudentAnswer(TenantAwareModel, TimeStampedModel):
    attempt = models.ForeignKey(ExamAttempt, on_delete=models.CASCADE, related_name='answers')
    question = models.ForeignKey(Question, on_delete=models.CASCADE)
    answer_text = models.TextField(null=True, blank=True)
    selected_options = models.JSONField(null=True, blank=True)  # For MCQ
    is_correct = models.BooleanField(null=True, blank=True)
    score = models.FloatField(null=True, blank=True)
    teacher_feedback = models.TextField(null=True, blank=True)
