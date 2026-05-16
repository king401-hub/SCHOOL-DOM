"""Finance domain models for SchoolDom wallets and school fees."""
from decimal import Decimal
import uuid

from django.conf import settings
from django.db import models
from django.utils import timezone


class Wallet(models.Model):
    """Student wallet that holds on-platform balance."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="wallet",
    )
    balance = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal("0.00"))
    currency = models.CharField(max_length=5, default="NGN")
    is_locked = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(fields=["user"]),
        ]

    def __str__(self):
        return f"Wallet({self.user.email})"


class AdminWallet(models.Model):
    """Platform-controlled wallet that receives fees and payouts per school tenant."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(
        "core.SchoolTenant",
        on_delete=models.CASCADE,
        related_name="admin_wallet",
        null=True,
        blank=True,
    )
    balance = models.DecimalField(max_digits=16, decimal_places=2, default=Decimal("0.00"))
    currency = models.CharField(max_length=5, default="NGN")
    bank_account_name = models.CharField(max_length=150, blank=True)
    bank_account_number = models.CharField(max_length=20, blank=True)
    bank_code = models.CharField(max_length=20, blank=True)
    last_settled_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["tenant"], name="unique_admin_wallet_per_tenant"),
        ]

    def __str__(self):
        code = self.tenant.schema_name if self.tenant else "public"
        return f"AdminWallet({code})"


class ActivationCreditPool(models.Model):
    """School-owned activation credits used only for student login access."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.OneToOneField(
        "core.SchoolTenant",
        on_delete=models.CASCADE,
        related_name="activation_credit_pool",
        null=True,
        blank=True,
    )
    balance = models.PositiveIntegerField(default=0)
    price_per_credit = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal("200.00"))
    currency = models.CharField(max_length=5, default="NGN")
    auto_assign_enabled = models.BooleanField(default=False)
    auto_assign_scope = models.CharField(max_length=20, default="all")
    last_auto_assigned_month = models.CharField(max_length=7, blank=True)
    last_reminder_month = models.CharField(max_length=7, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        code = self.tenant.schema_name if self.tenant else "public"
        return f"ActivationCreditPool({code}: {self.balance})"


class StudentActivationCredit(models.Model):
    """Per-student account activation state controlled by monthly credits."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    student = models.OneToOneField(
        "users.StudentProfile",
        on_delete=models.CASCADE,
        related_name="activation_credit",
    )
    credits_assigned = models.PositiveIntegerField(default=0)
    active_until = models.DateField(null=True, blank=True)
    last_credit_assigned_at = models.DateTimeField(null=True, blank=True)
    inactive_since = models.DateField(null=True, blank=True)
    inactive_flagged_at = models.DateTimeField(null=True, blank=True)
    is_excluded_from_auto_deductions = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(fields=["active_until"]),
            models.Index(fields=["is_excluded_from_auto_deductions"]),
        ]

    @property
    def has_login_credit(self):
        return bool(self.active_until and self.active_until >= timezone.localdate())

    def __str__(self):
        return f"ActivationCredit({self.student.user.email})"


class ActivationCreditTransaction(models.Model):
    """Ledger for activation credit pool purchases and student assignments."""

    PURCHASE = "purchase"
    ASSIGNMENT = "assignment"
    AUTO_ASSIGNMENT = "auto_assignment"
    ADJUSTMENT = "adjustment"
    TYPE_CHOICES = [
        (PURCHASE, "Credit Purchase"),
        (ASSIGNMENT, "Manual Assignment"),
        (AUTO_ASSIGNMENT, "Auto Assignment"),
        (ADJUSTMENT, "Adjustment"),
    ]
    STATUS_PENDING = "pending"
    STATUS_SUCCESS = "successful"
    STATUS_FAILED = "failed"
    STATUS_CHOICES = [
        (STATUS_PENDING, "Pending"),
        (STATUS_SUCCESS, "Successful"),
        (STATUS_FAILED, "Failed"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    pool = models.ForeignKey(
        ActivationCreditPool,
        on_delete=models.CASCADE,
        related_name="transactions",
    )
    student_credit = models.ForeignKey(
        StudentActivationCredit,
        on_delete=models.SET_NULL,
        related_name="transactions",
        null=True,
        blank=True,
    )
    tx_type = models.CharField(max_length=32, choices=TYPE_CHOICES)
    status = models.CharField(max_length=16, choices=STATUS_CHOICES, default=STATUS_SUCCESS)
    credits = models.IntegerField()
    price_per_credit = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal("200.00"))
    amount = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))
    reference = models.CharField(max_length=64, unique=True)
    narration = models.CharField(max_length=255, blank=True)
    provider = models.CharField(max_length=30, default="flutterwave")
    metadata = models.JSONField(default=dict, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="activation_credit_transactions",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["pool", "tx_type"]),
            models.Index(fields=["created_at"]),
        ]


class DocumentGenerationCreditTransaction(models.Model):
    """Ledger for document generation credit deductions (1 credit per transcript/testimonial/ID card)."""

    TRANSCRIPT = "transcript"
    TESTIMONIAL = "testimonial"
    ID_CARD = "id_card"
    DOCUMENT_TYPE_CHOICES = [
        (TRANSCRIPT, "Transcript"),
        (TESTIMONIAL, "Testimonial"),
        (ID_CARD, "ID Card"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    pool = models.ForeignKey(
        ActivationCreditPool,
        on_delete=models.CASCADE,
        related_name="document_credit_transactions",
    )
    student = models.ForeignKey(
        "users.StudentProfile",
        on_delete=models.CASCADE,
        related_name="document_generation_credits",
        null=True,
        blank=True,
    )
    document_type = models.CharField(max_length=20, choices=DOCUMENT_TYPE_CHOICES)
    credits_deducted = models.PositiveIntegerField(default=1)
    action = models.CharField(max_length=50, blank=True, help_text="generate, download, print, etc.")
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="document_credit_transactions",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["pool", "student", "document_type"],
                condition=models.Q(student__isnull=False),
                name="unique_student_document_generation_charge",
            ),
        ]
        indexes = [
            models.Index(fields=["pool", "document_type"]),
            models.Index(fields=["created_at"]),
        ]

    def __str__(self):
        return f"DocCredit({self.document_type}: -{self.credits_deducted})"


class Transaction(models.Model):
    """Ledger entries for both student and admin wallets."""

    FUNDING = "fund"
    FEE_DEBIT = "fee_debit"
    FEE_CREDIT = "fee_credit"
    WITHDRAWAL = "withdrawal"
    ADJUSTMENT_CREDIT = "adjustment_credit"
    ADJUSTMENT_DEBIT = "adjustment_debit"

    TYPE_CHOICES = [
        (FUNDING, "Funding"),
        (FEE_DEBIT, "Fee Debit"),
        (FEE_CREDIT, "Fee Credit"),
        (WITHDRAWAL, "Withdrawal"),
        (ADJUSTMENT_CREDIT, "Adjustment Credit"),
        (ADJUSTMENT_DEBIT, "Adjustment Debit"),
    ]

    STATUS_PENDING = "pending"
    STATUS_SUCCESS = "successful"
    STATUS_FAILED = "failed"
    STATUS_CHOICES = [
        (STATUS_PENDING, "Pending"),
        (STATUS_SUCCESS, "Successful"),
        (STATUS_FAILED, "Failed"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    wallet = models.ForeignKey(
        Wallet,
        on_delete=models.CASCADE,
        related_name="transactions",
        null=True,
        blank=True,
    )
    admin_wallet = models.ForeignKey(
        AdminWallet,
        on_delete=models.CASCADE,
        related_name="transactions",
        null=True,
        blank=True,
    )
    amount = models.DecimalField(max_digits=14, decimal_places=2)
    currency = models.CharField(max_length=5, default="NGN")
    tx_type = models.CharField(max_length=32, choices=TYPE_CHOICES)
    status = models.CharField(max_length=16, choices=STATUS_CHOICES, default=STATUS_PENDING)
    reference = models.CharField(max_length=64, unique=True)
    provider = models.CharField(max_length=30, default="flutterwave")
    narration = models.CharField(max_length=255, blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="initiated_transactions",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.CheckConstraint(
                check=(
                    models.Q(wallet__isnull=False, admin_wallet__isnull=True)
                    | models.Q(wallet__isnull=True, admin_wallet__isnull=False)
                ),
                name="transaction_requires_single_wallet",
            ),
        ]

    def __str__(self):
        return f"{self.reference} • {self.tx_type} • {self.status}"


class SchoolFee(models.Model):
    """School fee schedules tracked per student profile."""

    STATUS_PENDING = "pending"
    STATUS_PAID = "paid"
    STATUS_OVERDUE = "overdue"
    STATUS_CHOICES = [
        (STATUS_PENDING, "Pending"),
        (STATUS_PAID, "Paid"),
        (STATUS_OVERDUE, "Overdue"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    student = models.ForeignKey(
        "users.StudentProfile",
        on_delete=models.CASCADE,
        related_name="fees",
    )
    class_fee = models.ForeignKey(
        "finance.ClassFee",
        on_delete=models.SET_NULL,
        related_name="student_fees",
        null=True,
        blank=True,
    )
    title = models.CharField(max_length=150)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    currency = models.CharField(max_length=5, default="NGN")
    due_date = models.DateField()
    status = models.CharField(max_length=12, choices=STATUS_CHOICES, default=STATUS_PENDING)
    auto_deduct = models.BooleanField(default=True)
    is_customized = models.BooleanField(default=False)
    last_attempted_at = models.DateTimeField(null=True, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="created_fees",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["due_date"]
        indexes = [
            models.Index(fields=["student", "due_date"]),
            models.Index(fields=["status"]),
        ]

    def mark_attempted(self):
        self.last_attempted_at = timezone.now()
        self.save(update_fields=["last_attempted_at"])

    def __str__(self):
        return f"{self.title} • {self.student.user.email}"


class StudentPaymentReference(models.Model):
    """Stable bank-transfer narration code assigned to one student."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    student = models.OneToOneField(
        "users.StudentProfile",
        on_delete=models.CASCADE,
        related_name="payment_reference",
    )
    tenant = models.ForeignKey(
        "core.SchoolTenant",
        on_delete=models.CASCADE,
        related_name="student_payment_references",
        null=True,
        blank=True,
    )
    code = models.CharField(max_length=32, unique=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(fields=["tenant", "code"]),
            models.Index(fields=["student"]),
        ]

    def __str__(self):
        return f"{self.code} • {self.student.user.email}"


class BankPayment(models.Model):
    """Incoming transfer from a school bank account matched by narration code."""

    STATUS_PENDING = "pending"
    STATUS_CONFIRMED = "confirmed"
    STATUS_PARTIAL = "partial"
    STATUS_FAILED = "failed"
    STATUS_UNMATCHED = "unmatched"
    STATUS_CHOICES = [
        (STATUS_PENDING, "Pending"),
        (STATUS_CONFIRMED, "Confirmed"),
        (STATUS_PARTIAL, "Partial"),
        (STATUS_FAILED, "Failed"),
        (STATUS_UNMATCHED, "Unmatched"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(
        "core.SchoolTenant",
        on_delete=models.CASCADE,
        related_name="bank_payments",
        null=True,
        blank=True,
    )
    student = models.ForeignKey(
        "users.StudentProfile",
        on_delete=models.SET_NULL,
        related_name="bank_payments",
        null=True,
        blank=True,
    )
    payment_reference = models.ForeignKey(
        StudentPaymentReference,
        on_delete=models.SET_NULL,
        related_name="bank_payments",
        null=True,
        blank=True,
    )
    amount = models.DecimalField(max_digits=14, decimal_places=2)
    currency = models.CharField(max_length=5, default="NGN")
    narration = models.CharField(max_length=255)
    bank_reference = models.CharField(max_length=100, unique=True)
    status = models.CharField(max_length=16, choices=STATUS_CHOICES, default=STATUS_PENDING)
    applied_amount = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal("0.00"))
    unapplied_amount = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal("0.00"))
    matched_at = models.DateTimeField(null=True, blank=True)
    receipt_number = models.CharField(max_length=64, unique=True, null=True, blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["tenant", "status"]),
            models.Index(fields=["student", "created_at"]),
            models.Index(fields=["bank_reference"]),
        ]

    def __str__(self):
        return f"{self.bank_reference} • {self.status} • {self.amount}"

class ExpenseRecord(models.Model):
    """School-owned bills, expenses, and receipts tracked by authenticated admins."""

    TYPE_EXPENSE = "expense"
    TYPE_BILL = "bill"
    TYPE_RECEIPT = "receipt"
    TYPE_CHOICES = [
        (TYPE_EXPENSE, "Expense"),
        (TYPE_BILL, "Bill"),
        (TYPE_RECEIPT, "Receipt"),
    ]

    STATUS_PENDING = "pending"
    STATUS_DUE = "due"
    STATUS_PAID = "paid"
    STATUS_CHOICES = [
        (STATUS_PENDING, "Pending"),
        (STATUS_DUE, "Due"),
        (STATUS_PAID, "Paid"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(
        "core.SchoolTenant",
        on_delete=models.CASCADE,
        related_name="expense_records",
        null=True,
        blank=True,
    )
    title = models.CharField(max_length=160)
    vendor = models.CharField(max_length=160, blank=True)
    phone_number = models.CharField(max_length=40, blank=True)
    amount = models.DecimalField(max_digits=14, decimal_places=2)
    currency = models.CharField(max_length=5, default="NGN")
    record_type = models.CharField(max_length=16, choices=TYPE_CHOICES, default=TYPE_EXPENSE)
    category = models.CharField(max_length=80, default="Operations")
    color = models.CharField(max_length=16, default="#14b8a6")
    status = models.CharField(max_length=16, choices=STATUS_CHOICES, default=STATUS_PENDING)
    record_date = models.DateField()
    receipt_number = models.CharField(max_length=80, blank=True)
    note = models.TextField(blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="created_expense_records",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-record_date", "-created_at"]
        indexes = [
            models.Index(fields=["tenant", "record_type"]),
            models.Index(fields=["tenant", "status"]),
            models.Index(fields=["record_date"]),
        ]

    def __str__(self):
        return f"{self.title} - {self.record_type} - {self.amount}"


class ClassFee(models.Model):
    """Fee amount per class that is auto-assigned to students in that class."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    school_class = models.ForeignKey(
        "academic.Class",
        on_delete=models.CASCADE,
        related_name="fees",
    )
    title = models.CharField(max_length=150)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    currency = models.CharField(max_length=5, default="NGN")
    due_date = models.DateField()
    is_active = models.BooleanField(default=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="created_class_fees",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["due_date"]
        indexes = [
            models.Index(fields=["school_class", "is_active"]),
        ]
        unique_together = [["school_class", "title", "due_date"]]

    def __str__(self):
        return f"{self.title} • {self.school_class.name} • ₦{self.amount}"
