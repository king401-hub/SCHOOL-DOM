from django.db import models
from django.core.validators import MinValueValidator
from core.models import TenantAwareModel, TimeStampedModel

class Term(TenantAwareModel, TimeStampedModel):
    name = models.CharField(max_length=100)
    start_date = models.DateField()
    end_date = models.DateField()
    is_active = models.BooleanField(default=False)
    academic_year = models.ForeignKey(
        "academic.AcademicYear",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="terms",
    )
    
    def __str__(self):
        return self.name


class AcademicYear(TenantAwareModel):
    name = models.CharField(max_length=20)
    start_date = models.DateField()
    end_date = models.DateField()
    is_active = models.BooleanField(default=False)

    class Meta:
        ordering = ["-start_date", "name"]

    def __str__(self):
        return self.name

class Subject(TenantAwareModel, TimeStampedModel):
    name = models.CharField(max_length=100)
    code = models.CharField(max_length=20)
    
    def __str__(self):
        return self.name

class Class(TenantAwareModel, TimeStampedModel):
    name = models.CharField(max_length=100)
    section = models.CharField(max_length=50, null=True, blank=True)
    subjects = models.ManyToManyField(Subject, related_name="classes", blank=True)
    
    def __str__(self):
        return f"{self.name} - {self.section}"


class GradeScale(TenantAwareModel, TimeStampedModel):
    letter = models.CharField(max_length=5)
    min_percentage = models.DecimalField(max_digits=5, decimal_places=2)
    max_percentage = models.DecimalField(max_digits=5, decimal_places=2)
    remark = models.CharField(max_length=120, blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["-min_percentage", "letter"]
        unique_together = ("tenant", "letter")

    def __str__(self):
        return f"{self.letter}: {self.min_percentage}-{self.max_percentage}"


class ResultBatch(TenantAwareModel, TimeStampedModel):
    DRAFT = "draft"
    PENDING = "pending"
    APPROVED = "approved"
    PUBLISHED = "published"
    REJECTED = "rejected"
    STATUS_CHOICES = [
        (DRAFT, "Draft"),
        (PENDING, "Pending admin review"),
        (APPROVED, "Approved"),
        (PUBLISHED, "Published"),
        (REJECTED, "Rejected"),
    ]

    title = models.CharField(max_length=200)
    class_group = models.ForeignKey(Class, on_delete=models.SET_NULL, null=True, blank=True, related_name="result_batches")
    term = models.ForeignKey("academic.Term", on_delete=models.SET_NULL, null=True, blank=True, related_name="result_batches")
    teacher = models.ForeignKey("users.User", on_delete=models.SET_NULL, null=True, blank=True, related_name="result_batches")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=DRAFT)
    submitted_at = models.DateTimeField(null=True, blank=True)
    reviewed_by = models.ForeignKey("users.User", on_delete=models.SET_NULL, null=True, blank=True, related_name="reviewed_result_batches")
    reviewed_at = models.DateTimeField(null=True, blank=True)
    admin_note = models.TextField(blank=True)
    published_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-updated_at"]

    def __str__(self):
        return self.title

class StudentSubjectScore(TenantAwareModel, TimeStampedModel):
    """
    A per-subject score submitted by a teacher for a student.
    Stored per class/term to allow class-wide ranking.
    """
    student = models.ForeignKey(
        "users.StudentProfile",
        on_delete=models.CASCADE,
        related_name="subject_scores",
    )
    subject = models.ForeignKey(
        Subject,
        on_delete=models.CASCADE,
        related_name="student_scores",
    )
    class_group = models.ForeignKey(
        Class,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="subject_scores",
    )
    term = models.ForeignKey(
        Term,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="subject_scores",
    )
    teacher = models.ForeignKey(
        "users.User",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="submitted_scores",
    )
    score = models.DecimalField(
        max_digits=6,
        decimal_places=2,
        validators=[MinValueValidator(0)],
    )
    max_score = models.DecimalField(
        max_digits=6,
        decimal_places=2,
        default=100,
        validators=[MinValueValidator(1)],
    )
    remarks = models.TextField(blank=True)
    theory_score = models.DecimalField(max_digits=6, decimal_places=2, default=0)
    cbt_score = models.DecimalField(max_digits=6, decimal_places=2, default=0)
    assessment_score = models.DecimalField(max_digits=6, decimal_places=2, default=0)
    assignment_score = models.DecimalField(max_digits=6, decimal_places=2, default=0)
    attendance_score = models.DecimalField(max_digits=6, decimal_places=2, default=0)
    other_score = models.DecimalField(max_digits=6, decimal_places=2, default=0)
    grade = models.CharField(max_length=5, blank=True)
    performance_remark = models.CharField(max_length=120, blank=True)
    approval_status = models.CharField(max_length=20, choices=ResultBatch.STATUS_CHOICES, default=ResultBatch.DRAFT)
    result_batch = models.ForeignKey(ResultBatch, on_delete=models.SET_NULL, null=True, blank=True, related_name="scores")
    submitted_at = models.DateTimeField(null=True, blank=True)
    approved_by = models.ForeignKey(
        "users.User",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="approved_subject_scores",
    )
    approved_at = models.DateTimeField(null=True, blank=True)
    published_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        unique_together = ("student", "subject", "term", "class_group")
        ordering = ["-updated_at"]

    def __str__(self):
        return f"{self.student.student_id} - {self.subject.name} ({self.score})"

    @property
    def percentage(self):
        if not self.max_score:
            return None
        try:
            return round((float(self.score) / float(self.max_score)) * 100, 2)
        except Exception:
            return None


class AttendanceRecord(TenantAwareModel, TimeStampedModel):
    STATUS_CHOICES = [
        ("present", "Present"),
        ("absent", "Absent"),
        ("late", "Late"),
    ]

    student = models.ForeignKey(
        "users.User",
        on_delete=models.CASCADE,
        related_name="attendance_records",
    )
    class_group = models.ForeignKey(
        "academic.Class",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="attendance_records",
    )
    date = models.DateField()
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default="present")
    noted_by = models.ForeignKey(
        "users.User",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="noted_attendance",
    )

    class Meta:
        unique_together = ("student", "date")
        verbose_name = "Attendance Record"
        verbose_name_plural = "Attendance Records"


class QuestionPrompt(TenantAwareModel, TimeStampedModel):
    title = models.CharField(max_length=200)
    body = models.TextField()
    class_group = models.ForeignKey(
        "academic.Class",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="question_prompts",
    )
    due_date = models.DateField(null=True, blank=True)
    created_by = models.ForeignKey(
        "users.User",
        on_delete=models.CASCADE,
        related_name="created_prompts",
    )
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return self.title


class QuestionResponse(TenantAwareModel, TimeStampedModel):
    prompt = models.ForeignKey(
        QuestionPrompt,
        on_delete=models.CASCADE,
        related_name="responses",
    )
    student = models.ForeignKey(
        "users.User",
        on_delete=models.CASCADE,
        related_name="question_responses",
    )
    response_text = models.TextField()

    class Meta:
        unique_together = ("prompt", "student")


class LessonPlan(TenantAwareModel):
    DRAFT = "draft"
    PLANNED = "planned"
    COMPLETED = "completed"
    STATUS_CHOICES = [
        (DRAFT, "Draft"),
        (PLANNED, "Planned"),
        (COMPLETED, "Completed"),
    ]

    teacher = models.ForeignKey("users.User", on_delete=models.CASCADE, related_name="lesson_plans")
    academic_year = models.ForeignKey(AcademicYear, on_delete=models.SET_NULL, null=True, blank=True, related_name="lesson_plans")
    term = models.ForeignKey(Term, on_delete=models.SET_NULL, null=True, blank=True, related_name="lesson_plans")
    class_group = models.ForeignKey(Class, on_delete=models.CASCADE, related_name="lesson_plans")
    subject = models.ForeignKey(Subject, on_delete=models.CASCADE, related_name="lesson_plans")
    week_number = models.PositiveIntegerField(default=1)
    title = models.CharField(max_length=200)
    objectives = models.TextField(blank=True)
    activities = models.TextField(blank=True)
    resources = models.TextField(blank=True)
    assessment = models.TextField(blank=True)
    notes = models.TextField(blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=PLANNED)

    class Meta:
        ordering = ["week_number", "subject__name", "class_group__name"]
        unique_together = ("tenant", "academic_year", "term", "class_group", "subject", "week_number", "teacher")

    def __str__(self):
        return f"Week {self.week_number}: {self.subject} - {self.class_group}"


class TeacherNote(TenantAwareModel):
    teacher = models.ForeignKey("users.User", on_delete=models.CASCADE, related_name="academic_notes")
    academic_year = models.ForeignKey(AcademicYear, on_delete=models.SET_NULL, null=True, blank=True, related_name="teacher_notes")
    term = models.ForeignKey(Term, on_delete=models.SET_NULL, null=True, blank=True, related_name="teacher_notes")
    title = models.CharField(max_length=200, default="Quick note")
    body = models.TextField(blank=True)
    pinned = models.BooleanField(default=False)

    class Meta:
        ordering = ["-pinned", "-updated_at"]
