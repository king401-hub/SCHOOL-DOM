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
    # Blank for every ordinary teacher-owned bank; set only on the platform-admin-curated
    # central banks (see Topic below) that group JAMB/WAEC/NECO content by board.
    BOARD_CHOICES = [
        ("JAMB", "JAMB"),
        ("WAEC", "WAEC"),
        ("NECO", "NECO"),
    ]

    name = models.CharField(max_length=200)
    subject = models.ForeignKey('academic.Subject', on_delete=models.CASCADE)
    teacher = models.ForeignKey('users.User', on_delete=models.CASCADE)
    questions = models.ManyToManyField('Question', related_name='question_banks')
    is_shared = models.BooleanField(default=False)
    board = models.CharField(max_length=10, choices=BOARD_CHOICES, blank=True, default="")


class Topic(TenantAwareModel, TimeStampedModel):
    """A subject subdivision within a central (board-scoped) QuestionBank, e.g.
    "JAMB Mathematics" -> "Algebra". Only meaningful for central banks (board set);
    ordinary teacher banks have no topics."""

    name = models.CharField(max_length=200)
    bank = models.ForeignKey(QuestionBank, on_delete=models.CASCADE, related_name="topics")
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["order", "name"]

    def __str__(self):
        return self.name


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
        ('paragraph', 'Paragraph'),
        ('essay', 'Essay'),
    ]
    # Auto-gradable via options/correct_answer index-matching.
    OBJECTIVE_TYPES = ('mcq', 'true_false')
    # Free-text, manually graded by a teacher/admin.
    THEORY_TYPES = ('short_answer', 'paragraph', 'essay')

    question_type = models.CharField(max_length=20, choices=QUESTION_TYPES)
    text = models.TextField()
    image = models.ImageField(upload_to='question_images/', null=True, blank=True)
    attachment = models.FileField(upload_to='question_attachments/', null=True, blank=True)
    points = models.IntegerField(default=1)
    options = models.JSONField(null=True, blank=True)  # For MCQ
    correct_answer = models.TextField(null=True, blank=True)
    explanation = models.TextField(null=True, blank=True)
    group = models.ForeignKey(QuestionGroup, on_delete=models.SET_NULL, null=True, blank=True, related_name="questions")
    group_order = models.PositiveIntegerField(default=0)
    # Only set for questions living in a central (board-scoped) QuestionBank's Topic -
    # this is what the random-import-by-topic endpoint filters/samples on.
    topic = models.ForeignKey(Topic, on_delete=models.SET_NULL, null=True, blank=True, related_name="topic_questions")

class Exam(TenantAwareModel, TimeStampedModel):
    EXAM_FORMATS = [
        ('objective', 'Objective (MCQ)'),
        ('theory', 'Theory'),
        ('mixed', 'Mixed (Objective + Theory)'),
    ]

    title = models.CharField(max_length=200)
    subject = models.ForeignKey('academic.Subject', on_delete=models.CASCADE, null=True, blank=True)
    class_group = models.ForeignKey('academic.Class', on_delete=models.CASCADE, null=True, blank=True)
    teacher = models.ForeignKey('users.User', on_delete=models.CASCADE, null=True, blank=True)
    exam_type = models.ForeignKey(ExamType, on_delete=models.CASCADE, null=True, blank=True)
    exam_format = models.CharField(max_length=10, choices=EXAM_FORMATS, default='objective')
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

    # Exam Builder auto-save bookkeeping only - not used for access control or
    # CBT sync decisions (those still key off is_published exclusively).
    last_autosaved_at = models.DateTimeField(null=True, blank=True)


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
    plain_pin = models.CharField(max_length=16, blank=True, default="")
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
    def generate_plain_pin(cls, length=6):
        length = max(4, min(int(length or 6), 12))
        first_digit = secrets.choice("123456789")
        remaining = "".join(secrets.choice(string.digits) for _ in range(length - 1))
        return first_digit + remaining

    def set_pin(self, plain_pin):
        normalized = self.normalize_pin(plain_pin)
        self.pin_digest = self.digest_pin(normalized)
        self.pin_hash = make_password(normalized)
        self.pin_preview = normalized[-4:]
        self.plain_pin = normalized

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

    # Set when an admin or teacher releases this result. Until then a student
    # gets "Exam Completed" with no score - submitting is not the same event as
    # being told how you did, and theory papers are not even graded yet at that
    # point. Also the marker for whether the score has been pushed into
    # StudentSubjectScore for report cards and broadsheets.
    results_published_at = models.DateTimeField(null=True, blank=True)
    results_published_by = models.ForeignKey(
        "users.User",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="published_exam_results",
    )
    
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
