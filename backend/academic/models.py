import datetime
from decimal import Decimal

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
    grade_point = models.DecimalField(max_digits=3, decimal_places=2, default=Decimal("0.00"))
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


class ClassResultSnapshot(TenantAwareModel):
    """A saved, point-in-time class result list (same shape the live
    broadsheet computation produces from StudentSubjectScore rows), so an
    admin re-checking a class's results for a given term doesn't force a
    fresh aggregation of every score row on every visit. An admin explicitly
    (re)generates this via the Class Results filter; until they do, viewing
    it again is just reading this saved row - not recomputing anything."""
    class_group = models.ForeignKey(Class, on_delete=models.CASCADE, related_name="result_snapshots")
    term = models.ForeignKey("academic.Term", on_delete=models.CASCADE, related_name="result_snapshots")
    subjects = models.JSONField(default=list, blank=True)
    rows = models.JSONField(default=list, blank=True)
    class_size = models.PositiveIntegerField(default=0)
    generated_by = models.ForeignKey(
        "users.User", on_delete=models.SET_NULL, null=True, blank=True, related_name="generated_class_result_snapshots",
    )

    class Meta:
        ordering = ["-updated_at"]
        unique_together = ("tenant", "class_group", "term")

    def __str__(self):
        return f"{self.class_group} results - {self.term}"


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
        ("excused", "Excused"),
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

    # Arrival/departure times. The existing latitude/longitude/address columns
    # above describe the clock-IN, matching what they already held before
    # clock-out existed; the clock_out_* columns below mirror them for the
    # departure. Same split TeacherAttendance already uses for staff
    # (attendance/models.py check_in_*/check_out_*).
    clock_in_at = models.DateTimeField(null=True, blank=True)
    clock_out_at = models.DateTimeField(null=True, blank=True)
    clock_out_latitude = models.DecimalField(max_digits=10, decimal_places=7, null=True, blank=True)
    clock_out_longitude = models.DecimalField(max_digits=10, decimal_places=7, null=True, blank=True)
    clock_out_accuracy_meters = models.DecimalField(max_digits=9, decimal_places=2, null=True, blank=True)
    clock_out_address = models.TextField(blank=True, default="")
    clock_out_device_info = models.TextField(blank=True, default="")
    clock_out_recorded_by = models.ForeignKey(
        "users.User",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="clocked_out_attendance",
    )
    remarks = models.TextField(blank=True, default="")

    # Set only when this record was created/updated by an RFID scan (see
    # rfid_attendance.views.attendance_scan_create) - card_uid is for audit
    # ("which physical card produced this row"), idempotency_key is what makes
    # a retried sync POST from the desktop app's offline queue safe: a repeat
    # request with the same key returns the existing row instead of toggling
    # clock_in -> clock_out a second time.
    card_uid = models.CharField(max_length=64, blank=True, default="")
    idempotency_key = models.CharField(max_length=64, blank=True, null=True, unique=True)

    class Meta:
        unique_together = ("student", "date")
        verbose_name = "Attendance Record"
        verbose_name_plural = "Attendance Records"

    @property
    def is_clocked_in(self):
        return self.clock_in_at is not None

    @property
    def is_clocked_out(self):
        return self.clock_out_at is not None

    @property
    def hours_on_site(self):
        """Time between clock-in and clock-out, or None while still on site."""
        if not self.clock_in_at or not self.clock_out_at:
            return None
        seconds = (self.clock_out_at - self.clock_in_at).total_seconds()
        return round(seconds / 3600, 2) if seconds > 0 else 0.0


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
    subject = models.ForeignKey(Subject, on_delete=models.SET_NULL, null=True, blank=True, related_name="timetable_entries")
    title = models.CharField(max_length=150, blank=True, default="")
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

    @property
    def display_label(self):
        return self.title or (self.subject.name if self.subject_id else "")

    def __str__(self):
        return f"{self.get_day_of_week_display()} {self.start_time}-{self.end_time}: {self.display_label} ({self.class_group})"


def _default_school_days():
    return [
        TimetableEntry.MONDAY, TimetableEntry.TUESDAY, TimetableEntry.WEDNESDAY,
        TimetableEntry.THURSDAY, TimetableEntry.FRIDAY,
    ]


class TimetableSettings(TenantAwareModel, TimeStampedModel):
    """Per-tenant configuration for the weekly timetable grid and the
    auto-generator: how many periods a day has, how long each is, which time
    the day starts, and which days count as school days. One row per tenant,
    lazily created on first access - the generator and the grid both read the
    same computed period boundaries from here so they can never disagree."""

    periods_per_day = models.PositiveSmallIntegerField(default=8)
    period_duration_minutes = models.PositiveSmallIntegerField(default=40)
    day_start_time = models.TimeField(default=datetime.time(8, 0))
    school_days = models.JSONField(default=_default_school_days, blank=True)

    class Meta:
        indexes = [models.Index(fields=["tenant"])]

    def __str__(self):
        return f"TimetableSettings({self.tenant})"

    def compute_periods(self):
        """Return the fixed list of periods for one school day, as
        [{"index": 1, "start_time": time, "end_time": time}, ...] - purely
        computed from settings, never stored per-period."""
        periods = []
        cursor = datetime.datetime.combine(datetime.date.today(), self.day_start_time)
        for index in range(1, self.periods_per_day + 1):
            period_end = cursor + datetime.timedelta(minutes=self.period_duration_minutes)
            periods.append({"index": index, "start_time": cursor.time(), "end_time": period_end.time()})
            cursor = period_end
        return periods
