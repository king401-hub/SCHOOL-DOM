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


class SchoolActivityCalendar(TenantAwareModel, TimeStampedModel):
    month = models.PositiveSmallIntegerField()
    year = models.PositiveIntegerField(null=True, blank=True)
    title = models.CharField(max_length=200)
    activity_date = models.DateField(null=True, blank=True)
    end_date = models.DateField(null=True, blank=True)
    description = models.TextField(blank=True)
    color = models.CharField(max_length=7, default="#2563EB")
    created_by = models.ForeignKey(
        "users.User",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_school_activities",
    )

    class Meta:
        ordering = ["year", "month", "activity_date", "title"]
        indexes = [
            models.Index(fields=["tenant", "year", "month"]),
            models.Index(fields=["tenant", "activity_date"]),
        ]

    def __str__(self):
        return f"{self.title} - {self.month}/{self.year or ''}"

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


class StudentClassPromotion(TenantAwareModel, TimeStampedModel):
    SCOPE_CLASS = "class"
    SCOPE_DEPARTMENT = "department"
    SCOPE_LEVEL = "level"
    SCOPE_SESSION = "session"
    SCOPE_CHOICES = [
        (SCOPE_CLASS, "Class"),
        (SCOPE_DEPARTMENT, "Department"),
        (SCOPE_LEVEL, "Academic level"),
        (SCOPE_SESSION, "Academic session"),
    ]

    student = models.ForeignKey(
        "users.StudentProfile",
        on_delete=models.CASCADE,
        related_name="class_promotions",
    )
    from_class = models.ForeignKey(
        Class,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="promotions_from",
    )
    to_class = models.ForeignKey(
        Class,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="promotions_to",
    )
    from_term = models.ForeignKey(
        Term,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="promotions_from",
    )
    to_term = models.ForeignKey(
        Term,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="promotions_to",
    )
    from_academic_year = models.ForeignKey(
        AcademicYear,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="promotions_from",
    )
    to_academic_year = models.ForeignKey(
        AcademicYear,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="promotions_to",
    )
    scope = models.CharField(max_length=20, choices=SCOPE_CHOICES, default=SCOPE_CLASS)
    scope_value = models.CharField(max_length=120, blank=True)
    batch_reference = models.CharField(max_length=64, db_index=True)
    promoted_by = models.ForeignKey(
        "users.User",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="class_promotions_performed",
    )
    note = models.TextField(blank=True)

    class Meta:
        ordering = ["-created_at"]
        unique_together = (
            "student",
            "from_class",
            "to_class",
            "from_term",
            "to_term",
            "from_academic_year",
            "to_academic_year",
        )
        indexes = [
            models.Index(fields=["tenant", "batch_reference"]),
            models.Index(fields=["tenant", "scope", "scope_value"]),
        ]

    def __str__(self):
        return f"{self.student} promoted to {self.to_class}"


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
    latitude = models.DecimalField(max_digits=10, decimal_places=7, null=True, blank=True)
    longitude = models.DecimalField(max_digits=10, decimal_places=7, null=True, blank=True)
    location_accuracy_meters = models.DecimalField(max_digits=9, decimal_places=2, null=True, blank=True)
    location_address = models.TextField(blank=True, default="")
    device_info = models.TextField(blank=True, default="")

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


class TimetableEntry(TenantAwareModel, TimeStampedModel):
    MONDAY = 0
    TUESDAY = 1
    WEDNESDAY = 2
    THURSDAY = 3
    FRIDAY = 4
    SATURDAY = 5
    DAY_CHOICES = [
        (MONDAY, "Monday"),
        (TUESDAY, "Tuesday"),
        (WEDNESDAY, "Wednesday"),
        (THURSDAY, "Thursday"),
        (FRIDAY, "Friday"),
        (SATURDAY, "Saturday"),
    ]

    academic_year = models.ForeignKey(AcademicYear, on_delete=models.SET_NULL, null=True, blank=True, related_name="timetable_entries")
    term = models.ForeignKey(Term, on_delete=models.SET_NULL, null=True, blank=True, related_name="timetable_entries")
    class_group = models.ForeignKey(Class, on_delete=models.CASCADE, related_name="timetable_entries")
    subject = models.ForeignKey(Subject, on_delete=models.CASCADE, related_name="timetable_entries")
    teacher = models.ForeignKey("users.User", on_delete=models.SET_NULL, null=True, blank=True, related_name="timetable_entries")
    day_of_week = models.PositiveSmallIntegerField(choices=DAY_CHOICES)
    start_time = models.TimeField()
    end_time = models.TimeField()
    room = models.CharField(max_length=100, blank=True)

    class Meta:
        ordering = ["day_of_week", "start_time"]
        indexes = [
            models.Index(fields=["tenant", "class_group", "day_of_week"]),
            models.Index(fields=["tenant", "teacher", "day_of_week"]),
        ]

    def __str__(self):
        return f"{self.get_day_of_week_display()} {self.start_time}-{self.end_time}: {self.subject} ({self.class_group})"
