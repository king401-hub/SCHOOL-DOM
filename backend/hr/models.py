import uuid
import secrets
from decimal import Decimal

from django.conf import settings
from django.db import models
from django.utils import timezone


class StaffProfile(models.Model):
    TEACHING = "teaching"
    NON_TEACHING = "non_teaching"
    STAFF_TYPE_CHOICES = [
        (TEACHING, "Teaching"),
        (NON_TEACHING, "Non-teaching"),
    ]
    ACTIVE = "active"
    ON_LEAVE = "on_leave"
    SUSPENDED = "suspended"
    EXITED = "exited"
    STATUS_CHOICES = [
        (ACTIVE, "Active"),
        (ON_LEAVE, "On leave"),
        (SUSPENDED, "Suspended"),
        (EXITED, "Exited"),
    ]
    MARITAL_STATUS_CHOICES = [
        ("single", "Single"),
        ("married", "Married"),
        ("divorced", "Divorced"),
        ("widowed", "Widowed"),
        ("separated", "Separated"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey("core.SchoolTenant", on_delete=models.CASCADE, related_name="staff_profiles")
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="hr_staff_profile",
        null=True,
        blank=True,
    )
    staff_code = models.CharField(max_length=40)
    attendance_token = models.CharField(max_length=64, unique=True, default=secrets.token_urlsafe)
    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100)
    email = models.EmailField(blank=True)
    phone = models.CharField(max_length=30, blank=True)
    gender = models.CharField(max_length=20, blank=True)
    date_of_birth = models.DateField(null=True, blank=True)
    address = models.TextField(blank=True)
    nationality = models.CharField(max_length=100, blank=True)
    cv = models.FileField(upload_to="staff/documents/", null=True, blank=True)
    credentials = models.FileField(upload_to="staff/credentials/", null=True, blank=True)
    staff_type = models.CharField(max_length=20, choices=STAFF_TYPE_CHOICES, default=TEACHING)
    role = models.CharField(max_length=120)
    department = models.CharField(max_length=120, blank=True)
    employment_type = models.CharField(max_length=30, default="full_time")
    employment_status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=ACTIVE)
    hire_date = models.DateField(default=timezone.localdate)
    base_salary = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))
    salary_balance = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))
    bank_name = models.CharField(max_length=120, blank=True)
    bank_code = models.CharField(max_length=20, blank=True)
    bank_account_name = models.CharField(max_length=150, blank=True)
    bank_account_number = models.CharField(max_length=30, blank=True)
    emergency_contact_name = models.CharField(max_length=150, blank=True)
    emergency_contact_phone = models.CharField(max_length=30, blank=True)
    emergency_contact_relation = models.CharField(max_length=100, blank=True)
    marital_status = models.CharField(max_length=20, blank=True, choices=MARITAL_STATUS_CHOICES)
    guarantor_name = models.CharField(max_length=150, blank=True)
    guarantor_phone = models.CharField(max_length=30, blank=True)
    guarantor_address = models.TextField(blank=True)
    guarantor_relationship = models.CharField(max_length=100, blank=True)
    guarantor_form = models.FileField(upload_to="staff/guarantor/", null=True, blank=True)
    notes = models.TextField(blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="created_staff_profiles",
        null=True,
        blank=True,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["first_name", "last_name"]
        constraints = [
            models.UniqueConstraint(fields=["tenant", "staff_code"], name="unique_staff_code_per_school"),
        ]
        indexes = [
            models.Index(fields=["tenant", "staff_type"], name="hr_staffpro_tenant__6fb9e8_idx"),
            models.Index(fields=["tenant", "department"], name="hr_staffpro_tenant__88d00d_idx"),
            models.Index(fields=["employment_status"], name="hr_staffpro_employm_589508_idx"),
        ]

    @property
    def full_name(self):
        return f"{self.first_name} {self.last_name}".strip()

    def __str__(self):
        return f"{self.full_name} - {self.staff_code}"


class StaffAttendance(models.Model):
    PRESENT = "present"
    ABSENT = "absent"
    LATE = "late"
    HALF_DAY = "half_day"
    STATUS_CHOICES = [
        (PRESENT, "Present"),
        (ABSENT, "Absent"),
        (LATE, "Late"),
        (HALF_DAY, "Half day"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    staff = models.ForeignKey(StaffProfile, on_delete=models.CASCADE, related_name="attendance_records")
    date = models.DateField(default=timezone.localdate)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=PRESENT)
    check_in = models.TimeField(null=True, blank=True)
    check_out = models.TimeField(null=True, blank=True)
    notes = models.CharField(max_length=255, blank=True)
    marked_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="marked_staff_attendance",
        null=True,
        blank=True,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-date", "staff__first_name"]
        constraints = [
            models.UniqueConstraint(fields=["staff", "date"], name="unique_staff_attendance_per_day"),
        ]
        indexes = [
            models.Index(fields=["date", "status"], name="hr_staffatt_date_3e1475_idx"),
        ]


class LeaveRequest(models.Model):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    STATUS_CHOICES = [
        (PENDING, "Pending"),
        (APPROVED, "Approved"),
        (REJECTED, "Rejected"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    staff = models.ForeignKey(StaffProfile, on_delete=models.CASCADE, related_name="leave_requests")
    leave_type = models.CharField(max_length=60, default="Annual")
    start_date = models.DateField()
    end_date = models.DateField()
    reason = models.TextField(blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=PENDING)
    admin_note = models.TextField(blank=True)
    requested_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="requested_staff_leaves",
        null=True,
        blank=True,
    )
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="reviewed_staff_leaves",
        null=True,
        blank=True,
    )
    reviewed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["status", "start_date"], name="hr_leavere_status_8d0e3b_idx"),
        ]

    @property
    def days(self):
        return max((self.end_date - self.start_date).days + 1, 0)


class SalaryAdvanceRequest(models.Model):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    PAID = "paid"
    STATUS_CHOICES = [
        (PENDING, "Pending"),
        (APPROVED, "Approved"),
        (REJECTED, "Rejected"),
        (PAID, "Paid"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    staff = models.ForeignKey(StaffProfile, on_delete=models.CASCADE, related_name="salary_advances")
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    reason = models.TextField(blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=PENDING)
    request_date = models.DateField(default=timezone.localdate)
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="approved_salary_advances",
        null=True,
        blank=True,
    )
    approved_at = models.DateTimeField(null=True, blank=True)
    paid_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["status", "request_date"], name="hr_salaryad_status_86489c_idx"),
        ]


class PayrollRecord(models.Model):
    DRAFT = "draft"
    APPROVED = "approved"
    PAID = "paid"
    STATUS_CHOICES = [
        (DRAFT, "Draft"),
        (APPROVED, "Approved"),
        (PAID, "Paid"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    staff = models.ForeignKey(StaffProfile, on_delete=models.CASCADE, related_name="payroll_records")
    year = models.PositiveIntegerField()
    month = models.PositiveIntegerField()
    base_salary = models.DecimalField(max_digits=12, decimal_places=2)
    allowances = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))
    deductions = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))
    advances_applied = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))
    gross_salary = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))
    net_salary = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))
    amount_paid = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))
    balance_after_payment = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=DRAFT)
    notes = models.TextField(blank=True)
    processed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="processed_payroll_records",
        null=True,
        blank=True,
    )
    paid_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-year", "-month", "staff__first_name"]
        constraints = [
            models.UniqueConstraint(fields=["staff", "year", "month"], name="unique_staff_payroll_month"),
        ]
        indexes = [
            models.Index(fields=["year", "month", "status"], name="hr_payrollr_year_7b0749_idx"),
        ]

    @property
    def period_label(self):
        return f"{self.year}-{self.month:02d}"


class StaffActivity(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey("core.SchoolTenant", on_delete=models.CASCADE, related_name="staff_activities")
    staff = models.ForeignKey(StaffProfile, on_delete=models.SET_NULL, related_name="activities", null=True, blank=True)
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="staff_activity_actions",
        null=True,
        blank=True,
    )
    action = models.CharField(max_length=80)
    details = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["tenant", "created_at"], name="hr_staffact_tenant__0492ce_idx"),
        ]
