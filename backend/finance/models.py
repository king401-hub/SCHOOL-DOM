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
    kuda_virtual_account_number = models.CharField(max_length=20, blank=True)
    kuda_virtual_account_name = models.CharField(max_length=150, blank=True)
    kuda_virtual_account_bank_name = models.CharField(max_length=80, blank=True, default="Kuda Microfinance Bank")
    kuda_virtual_account_reference = models.CharField(max_length=100, blank=True)
    kuda_virtual_account_status = models.CharField(max_length=30, blank=True)
    kuda_virtual_account_metadata = models.JSONField(default=dict, blank=True)
    last_settled_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    # NEW: Paystack split payment fields
    subaccount_code = models.CharField(max_length=50, blank=True, null=True, help_text="Paystack subaccount code for this school")
    split_code = models.CharField(max_length=50, blank=True, null=True, help_text="Paystack split code for this school (flat, used at checkout)")
    dva_split_code = models.CharField(max_length=50, blank=True, null=True, help_text="Paystack percentage split code applied to this school's dedicated virtual accounts")

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["tenant"], name="unique_admin_wallet_per_tenant"),
        ]

    def __str__(self):
        code = self.tenant.schema_name if self.tenant else "public"
        return f"AdminWallet({code})"


class FinanceLedgerLog(models.Model):
    """Append-only audit ledger for school financial activity."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(
        "core.SchoolTenant",
        on_delete=models.PROTECT,
        related_name="finance_ledger_logs",
        null=True,
        blank=True,
    )
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="finance_ledger_logs",
        null=True,
        blank=True,
    )
    action = models.CharField(max_length=80)
    description = models.CharField(max_length=255)
    amount = models.DecimalField(max_digits=16, decimal_places=2, default=Decimal("0.00"))
    currency = models.CharField(max_length=5, default="NGN")
    reference = models.CharField(max_length=100, blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["tenant", "created_at"]),
            models.Index(fields=["action"]),
            models.Index(fields=["reference"]),
        ]

    def save(self, *args, **kwargs):
        if self.pk and FinanceLedgerLog.objects.filter(pk=self.pk).exists():
            raise ValueError("Finance ledger logs are append-only and cannot be modified.")
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValueError("Finance ledger logs are append-only and cannot be deleted.")

    def __str__(self):
        return f"FinanceLedgerLog({self.action}: {self.amount} {self.currency})"


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
    
    # NEW: Add split payment transaction types
    SPLIT_PAYMENT = "split_payment"
    SCHOOL_SETTLEMENT = "school_settlement"
    SCHOOLDOM_FEE = "schooldom_fee"
    PAYSTACK_FEE = "paystack_fee"

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
        (SPLIT_PAYMENT, "Split Payment"),
        (SCHOOL_SETTLEMENT, "School Settlement"),
        (SCHOOLDOM_FEE, "Schooldom Fee"),
        (PAYSTACK_FEE, "Paystack Fee"),
    ]

    STATUS_PENDING = "pending"
    STATUS_SUCCESS = "successful"
    STATUS_FAILED = "failed"
    STATUS_CHOICES = [
        (STATUS_PENDING, "Pending"),
        (STATUS_SUCCESS, "Successful"),
        (STATUS_FAILED, "Failed"),
    ]

    # NEW: Allocation status for split payments
    ALLOCATION_PENDING = "pending"
    ALLOCATION_ALLOCATED = "allocated"
    ALLOCATION_PARTIAL = "partial"
    ALLOCATION_OVERPAID = "overpaid"
    ALLOCATION_CHOICES = [
        (ALLOCATION_PENDING, "Pending"),
        (ALLOCATION_ALLOCATED, "Allocated"),
        (ALLOCATION_PARTIAL, "Partial"),
        (ALLOCATION_OVERPAID, "Overpaid"),
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
    
    # NEW: Split payment fields
    paystack_ref = models.CharField(max_length=100, blank=True, null=True, unique=True, help_text="Paystack transaction reference")
    split_code = models.CharField(max_length=50, blank=True, null=True, help_text="Paystack split code used")
    allocation_status = models.CharField(max_length=16, choices=ALLOCATION_CHOICES, default=ALLOCATION_PENDING)
    tuition_amount = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal("0.00"), help_text="Total tuition amount")
    schooldom_markup = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal("0.00"), help_text="Schooldom service fee")
    paystack_fee_amount = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal("0.00"), help_text="Paystack processing fee")
    school_id = models.UUIDField(null=True, blank=True, help_text="School tenant ID for this transaction")
    parent_id = models.UUIDField(null=True, blank=True, help_text="Parent user ID for this transaction")
    fee_ids = models.JSONField(default=list, blank=True, help_text="List of fee IDs allocated")

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.CheckConstraint(
                check=(
                    models.Q(wallet__isnull=False, admin_wallet__isnull=True)
                    | models.Q(wallet__isnull=True, admin_wallet__isnull=False)
                    | models.Q(wallet__isnull=True, admin_wallet__isnull=True, tx_type="split_payment")
                ),
                name="transaction_requires_single_wallet",
            ),
        ]
        indexes = [
            models.Index(fields=["paystack_ref"]),
            models.Index(fields=["allocation_status"]),
            models.Index(fields=["parent_id"]),
            models.Index(fields=["school_id"]),
        ]

    def __str__(self):
        return f"{self.reference} • {self.tx_type} • {self.status}"
    
    def get_breakdown(self):
        """Get payment breakdown for this transaction"""
        return {
            'total_paid': float(self.amount),
            'tuition': float(self.tuition_amount),
            'schooldom_fee': float(self.schooldom_markup),
            'paystack_fee': float(self.paystack_fee_amount),
            'school_net': float(self.tuition_amount - self.paystack_fee_amount)
        }


class SchoolFee(models.Model):
    """School fee schedules tracked per student profile."""

    STATUS_PENDING = "pending"
    STATUS_PAID = "paid"
    STATUS_OVERDUE = "overdue"
    STATUS_PARTIAL = "partial"  # NEW: For partial payments
    STATUS_CHOICES = [
        (STATUS_PENDING, "Pending"),
        (STATUS_PAID, "Paid"),
        (STATUS_OVERDUE, "Overdue"),
        (STATUS_PARTIAL, "Partial"),
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
    
    # NEW: Track payments
    amount_paid = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))
    payment_date = models.DateTimeField(null=True, blank=True)
    last_payment_date = models.DateTimeField(null=True, blank=True)
    
    # NEW: Split payment tracking
    paystack_ref = models.CharField(max_length=100, blank=True, null=True, help_text="Paystack reference for last payment")
    
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
            models.Index(fields=["paystack_ref"]),
        ]

    def mark_attempted(self):
        self.last_attempted_at = timezone.now()
        self.save(update_fields=["last_attempted_at"])
    
    def calculate_total_with_fees(self):
        """Calculate total including Schooldom and Paystack fees"""
        tuition = float(self.amount)
        return {
            'tuition': tuition,
            'schooldom_fee': 100,
            'paystack_fee': 300,
            'total': tuition + 400,
            'fee_id': str(self.id),
            'student_name': self.student.user.get_full_name() if self.student.user else str(self.student),
            'class': self.student.class_name if hasattr(self.student, 'class_name') else ''
        }
    
    def get_remaining_balance(self):
        """Get remaining balance including fees"""
        tuition = float(self.amount)
        paid = float(self.amount_paid or 0)
        remaining_tuition = tuition - paid
        if remaining_tuition <= 0:
            return 0
        # Add fees only if not fully paid
        return remaining_tuition + 400  # 100 Schooldom + 300 Paystack
    
    def is_fully_paid(self):
        return float(self.amount_paid or 0) >= float(self.amount)

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


class BankLink(models.Model):
    """Bank app URI template used to prefill parent transfers."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    bank_name = models.CharField(max_length=80, unique=True)
    deep_link_template = models.CharField(max_length=500)
    nuban_format = models.CharField(max_length=120, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["bank_name"]
        indexes = [
            models.Index(fields=["bank_name", "is_active"]),
        ]

    def __str__(self):
        return self.bank_name


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


# NEW: Fee Allocation Model for Split Payments
class FeeAllocation(models.Model):
    """Track how split payments are allocated to individual fees."""
    
    STATUS_PAID = "paid"
    STATUS_PARTIAL = "partial"
    STATUS_PENDING = "pending"
    STATUS_CHOICES = [
        (STATUS_PAID, "Paid"),
        (STATUS_PARTIAL, "Partial"),
        (STATUS_PENDING, "Pending"),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    fee = models.ForeignKey(
        SchoolFee,
        on_delete=models.CASCADE,
        related_name="allocations",
    )
    transaction = models.ForeignKey(
        Transaction,
        on_delete=models.CASCADE,
        related_name="allocations",
    )
    amount_allocated = models.DecimalField(max_digits=14, decimal_places=2, help_text="Tuition amount allocated to this fee")
    paystack_fee_paid = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal("0.00"))
    schooldom_fee_paid = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal("0.00"))
    status = models.CharField(max_length=16, choices=STATUS_CHOICES, default=STATUS_PENDING)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["fee", "status"]),
            models.Index(fields=["transaction"]),
        ]
        unique_together = [["fee", "transaction"]]  # One allocation per fee per transaction
    
    def __str__(self):
        return f"Allocation {self.fee.title} - {self.amount_allocated} ({self.status})"


class ParentVirtualAccount(models.Model):
    """Static virtual account manually assigned by admin to a parent for school fee payments."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    parent = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="virtual_account",
    )
    tenant = models.ForeignKey(
        "core.SchoolTenant",
        on_delete=models.CASCADE,
        related_name="parent_virtual_accounts",
        null=True,
        blank=True,
    )
    account_number = models.CharField(max_length=20)
    bank_name = models.CharField(max_length=100)
    account_name = models.CharField(max_length=150)
    provider = models.CharField(max_length=30, default="paystack", help_text="Payment provider (paystack, kuda, etc.)")
    paystack_reference = models.CharField(max_length=100, blank=True, help_text="Paystack DVA customer code or reference")
    is_active = models.BooleanField(default=True)
    assigned_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="assigned_virtual_accounts",
    )
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(fields=["account_number"]),
            models.Index(fields=["tenant"]),
        ]

    def __str__(self):
        return f"VirtualAccount({self.account_number} → {self.parent.email})"


class PaymentReceiptLink(models.Model):
    RECEIPT = "receipt"
    BILL = "bill"
    TYPE_CHOICES = [(RECEIPT, "Receipt"), (BILL, "Bill")]

    token = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    short_code = models.CharField(max_length=12, unique=True, null=True, blank=True, editable=False)
    receipt_type = models.CharField(max_length=20, choices=TYPE_CHOICES, default=RECEIPT)
    tenant = models.ForeignKey(
        "core.SchoolTenant",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="receipt_links",
    )
    phone = models.CharField(max_length=20, blank=True)
    data = models.JSONField(default=dict)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        indexes = [
            models.Index(fields=["token"]),
            models.Index(fields=["short_code"], name="finance_pay_short_c_5f6a89_idx"),
        ]

    def save(self, *args, **kwargs):
        if not self.short_code:
            code = uuid.uuid4().hex[:8]
            while PaymentReceiptLink.objects.filter(short_code=code).exists():
                code = uuid.uuid4().hex[:8]
            self.short_code = code
        super().save(*args, **kwargs)


class SmsBundle(models.Model):
    """Purchasable SMS credit package. Managed by SchoolDom staff, bought by schools."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=100)
    credits = models.PositiveIntegerField(help_text="Number of SMS credits (1 credit = 1 SMS, up to 160 chars).")
    bonus_credits = models.PositiveIntegerField(default=0)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    currency = models.CharField(max_length=5, default="NGN")
    is_active = models.BooleanField(default=True)
    sort_order = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["sort_order", "credits"]

    def __str__(self):
        return f"SmsBundle({self.name}: {self.credits}+{self.bonus_credits} credits, {self.currency} {self.price})"


class SmsWallet(models.Model):
    """Per-school prepaid SMS credit balance. SchoolDom uses a single shared eBulkSMS
    account/API key; this wallet is what actually meters and caps each school's usage."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.OneToOneField(
        "core.SchoolTenant",
        on_delete=models.CASCADE,
        related_name="sms_wallet",
        null=True,
        blank=True,
    )
    balance = models.PositiveIntegerField(default=0)
    low_balance_threshold = models.PositiveIntegerField(default=50)
    is_locked = models.BooleanField(default=False, help_text="Kill switch - blocks all sends for this school.")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        code = self.tenant.schema_name if self.tenant else "public"
        return f"SmsWallet({code}: {self.balance})"


class SmsWalletTransaction(models.Model):
    """Immutable ledger for every SMS wallet balance movement. Every row records a unique
    reference and the balance before/after the movement - balances must never be mutated
    without a matching row here."""

    PURCHASE = "purchase"
    DEBIT = "debit"
    REFUND = "refund"
    ADMIN_CREDIT = "admin_credit"
    ADJUSTMENT = "adjustment"
    TYPE_CHOICES = [
        (PURCHASE, "Purchase"),
        (DEBIT, "Debit"),
        (REFUND, "Refund"),
        (ADMIN_CREDIT, "Admin Credit"),
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
    wallet = models.ForeignKey(SmsWallet, on_delete=models.CASCADE, related_name="transactions")
    tx_type = models.CharField(max_length=20, choices=TYPE_CHOICES)
    status = models.CharField(max_length=16, choices=STATUS_CHOICES, default=STATUS_SUCCESS)
    credits = models.IntegerField(help_text="Signed: positive for purchase/refund/admin_credit, negative for debit.")
    balance_before = models.PositiveIntegerField(null=True, blank=True)
    balance_after = models.PositiveIntegerField(null=True, blank=True)
    amount = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))
    reference = models.CharField(max_length=64, unique=True)
    bundle = models.ForeignKey(SmsBundle, on_delete=models.SET_NULL, null=True, blank=True, related_name="purchases")
    related_message_log = models.ForeignKey(
        "finance.SmsMessageLog",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="wallet_transactions",
    )
    narration = models.CharField(max_length=255, blank=True)
    provider = models.CharField(max_length=30, default="paystack")
    metadata = models.JSONField(default=dict, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="sms_wallet_transactions",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["wallet", "tx_type"], name="finance_smswtx_wt_idx"),
            models.Index(fields=["created_at"], name="finance_smswtx_ca_idx"),
        ]

    def __str__(self):
        return f"SmsWalletTransaction({self.tx_type}: {self.credits})"


class SmsMessageLog(models.Model):
    """Per-SMS delivery record - every message sent through the wallet-metered pipeline
    gets a row here, regardless of which part of the app triggered it."""

    ATTENDANCE = "attendance"
    FEE_REMINDER = "fee_reminder"
    RESULTS = "results"
    OTP = "otp"
    PARENT_ALERT = "parent_alert"
    TEACHER_NOTICE = "teacher_notice"
    BULK = "bulk"
    OTHER = "other"
    CATEGORY_CHOICES = [
        (ATTENDANCE, "Attendance"),
        (FEE_REMINDER, "Fee Reminder"),
        (RESULTS, "Results"),
        (OTP, "OTP"),
        (PARENT_ALERT, "Parent Alert"),
        (TEACHER_NOTICE, "Teacher Notice"),
        (BULK, "Bulk Message"),
        (OTHER, "Other"),
    ]
    QUEUED = "queued"
    SENT = "sent"
    DELIVERED = "delivered"
    FAILED = "failed"
    REFUNDED = "refunded"
    DELIVERY_STATUS_CHOICES = [
        (QUEUED, "Queued"),
        (SENT, "Sent"),
        (DELIVERED, "Delivered"),
        (FAILED, "Failed"),
        (REFUNDED, "Refunded"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(
        "core.SchoolTenant",
        on_delete=models.CASCADE,
        related_name="sms_message_logs",
        null=True,
        blank=True,
    )
    wallet = models.ForeignKey(SmsWallet, on_delete=models.CASCADE, related_name="message_logs")
    category = models.CharField(max_length=20, choices=CATEGORY_CHOICES, default=OTHER)
    recipient_phone = models.CharField(max_length=20)
    message = models.TextField()
    credits_charged = models.PositiveIntegerField(default=1)
    delivery_status = models.CharField(max_length=16, choices=DELIVERY_STATUS_CHOICES, default=QUEUED)
    provider_response = models.JSONField(default=dict, blank=True)
    provider_message_id = models.CharField(max_length=100, blank=True)
    sent_at = models.DateTimeField(null=True, blank=True)
    refunded_at = models.DateTimeField(null=True, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="sms_message_logs",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["tenant", "created_at"], name="finance_smsmsg_tc_idx"),
            models.Index(fields=["wallet", "delivery_status"], name="finance_smsmsg_wds_idx"),
            models.Index(fields=["category"], name="finance_smsmsg_cat_idx"),
        ]

    def __str__(self):
        return f"SmsMessageLog({self.recipient_phone}: {self.delivery_status})"