from decimal import Decimal
import uuid

from django.conf import settings
from django.db import models


class CollectionConfig(models.Model):
    """Global SchoolDom collection settings."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    commission_type = models.CharField(
        max_length=16,
        choices=[("percentage", "Percentage"), ("flat", "Flat")],
        default="percentage",
    )
    commission_value = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal("1.50"))
    minimum_commission = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))
    maximum_commission = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    settlement_frequency = models.CharField(
        max_length=16,
        choices=[("daily", "Daily"), ("weekly", "Weekly")],
        default="daily",
    )
    settlement_weekday = models.PositiveSmallIntegerField(default=0, help_text="Monday=0, Sunday=6")
    auto_settlement_enabled = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Collection configuration"
        verbose_name_plural = "Collection configuration"

    def __str__(self):
        return f"{self.commission_type}:{self.commission_value}"


class SchoolCollectionProfile(models.Model):
    """Approved school fee-collection profile and settlement destination."""

    STATUS_PENDING = "pending"
    STATUS_APPROVED = "approved"
    STATUS_SUSPENDED = "suspended"
    STATUS_CHOICES = [
        (STATUS_PENDING, "Pending"),
        (STATUS_APPROVED, "Approved"),
        (STATUS_SUSPENDED, "Suspended"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    school = models.OneToOneField(
        "core.SchoolTenant",
        on_delete=models.CASCADE,
        related_name="collection_profile",
    )
    status = models.CharField(max_length=16, choices=STATUS_CHOICES, default=STATUS_PENDING)
    bank_name = models.CharField(max_length=120)
    bank_code = models.CharField(max_length=30)
    account_number = models.CharField(max_length=20)
    account_name = models.CharField(max_length=160)
    flutterwave_customer_id = models.CharField(max_length=80, blank=True)
    flutterwave_customer_reference = models.CharField(max_length=80, blank=True)
    flutterwave_customer_metadata = models.JSONField(default=dict, blank=True)
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="approved_collection_profiles",
    )
    approved_at = models.DateTimeField(null=True, blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(fields=["school", "status"]),
            models.Index(fields=["status"]),
        ]

    def __str__(self):
        return f"{self.school.name} collections"


class SchoolVirtualAccount(models.Model):
    """Permanent Flutterwave virtual account assigned to one school."""

    STATUS_PENDING = "pending"
    STATUS_ACTIVE = "active"
    STATUS_FAILED = "failed"
    STATUS_DISABLED = "disabled"
    STATUS_CHOICES = [
        (STATUS_PENDING, "Pending"),
        (STATUS_ACTIVE, "Active"),
        (STATUS_FAILED, "Failed"),
        (STATUS_DISABLED, "Disabled"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    school = models.OneToOneField(
        "core.SchoolTenant",
        on_delete=models.CASCADE,
        related_name="fee_virtual_account",
    )
    provider = models.CharField(max_length=30, default="flutterwave")
    account_number = models.CharField(max_length=20, unique=True)
    account_name = models.CharField(max_length=160)
    bank_name = models.CharField(max_length=120, default="Flutterwave")
    provider_reference = models.CharField(max_length=120, unique=True)
    order_reference = models.CharField(max_length=120, blank=True)
    status = models.CharField(max_length=16, choices=STATUS_CHOICES, default=STATUS_PENDING)
    raw_response = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(fields=["account_number"]),
            models.Index(fields=["provider_reference"]),
            models.Index(fields=["school", "status"]),
        ]

    def __str__(self):
        return f"{self.school.name} - {self.account_number}"


class FeePayment(models.Model):
    """Immutable-ish record of a fee transfer received into a school virtual account."""

    STATUS_PENDING = "pending"
    STATUS_SUCCESSFUL = "successful"
    STATUS_FAILED = "failed"
    STATUS_DUPLICATE = "duplicate"
    STATUS_CHOICES = [
        (STATUS_PENDING, "Pending"),
        (STATUS_SUCCESSFUL, "Successful"),
        (STATUS_FAILED, "Failed"),
        (STATUS_DUPLICATE, "Duplicate"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    school = models.ForeignKey("core.SchoolTenant", on_delete=models.PROTECT, related_name="fee_collection_payments")
    virtual_account = models.ForeignKey(SchoolVirtualAccount, on_delete=models.PROTECT, related_name="payments")
    provider = models.CharField(max_length=30, default="flutterwave")
    provider_reference = models.CharField(max_length=120, unique=True)
    session_id = models.CharField(max_length=120, blank=True, db_index=True)
    payer_name = models.CharField(max_length=160, blank=True)
    payer_account_number = models.CharField(max_length=30, blank=True)
    payer_bank_name = models.CharField(max_length=120, blank=True)
    narration = models.CharField(max_length=255, blank=True)
    currency = models.CharField(max_length=5, default="NGN")
    gross_amount = models.DecimalField(max_digits=14, decimal_places=2)
    platform_fee = models.DecimalField(max_digits=14, decimal_places=2)
    net_amount = models.DecimalField(max_digits=14, decimal_places=2)
    status = models.CharField(max_length=16, choices=STATUS_CHOICES, default=STATUS_SUCCESSFUL)
    paid_at = models.DateTimeField()
    raw_payload = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-paid_at", "-created_at"]
        indexes = [
            models.Index(fields=["school", "status", "paid_at"]),
            models.Index(fields=["provider_reference"]),
            models.Index(fields=["session_id"]),
        ]

    def __str__(self):
        return f"{self.provider_reference} - {self.gross_amount}"


class SchoolSettlement(models.Model):
    """Batch settlement from SchoolDom to a school's registered bank account."""

    STATUS_PENDING = "pending"
    STATUS_PROCESSING = "processing"
    STATUS_SUCCESSFUL = "successful"
    STATUS_FAILED = "failed"
    STATUS_CHOICES = [
        (STATUS_PENDING, "Pending"),
        (STATUS_PROCESSING, "Processing"),
        (STATUS_SUCCESSFUL, "Successful"),
        (STATUS_FAILED, "Failed"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    school = models.ForeignKey("core.SchoolTenant", on_delete=models.PROTECT, related_name="fee_settlements")
    gross_amount = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal("0.00"))
    platform_fee = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal("0.00"))
    net_amount = models.DecimalField(max_digits=14, decimal_places=2)
    currency = models.CharField(max_length=5, default="NGN")
    transfer_reference = models.CharField(max_length=120, unique=True)
    provider_transfer_id = models.CharField(max_length=120, blank=True)
    status = models.CharField(max_length=16, choices=STATUS_CHOICES, default=STATUS_PENDING)
    scheduled_for = models.DateField()
    settled_at = models.DateTimeField(null=True, blank=True)
    failure_reason = models.TextField(blank=True)
    raw_response = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    payments = models.ManyToManyField(FeePayment, related_name="settlements", blank=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["school", "status"]),
            models.Index(fields=["scheduled_for", "status"]),
            models.Index(fields=["transfer_reference"]),
        ]

    def __str__(self):
        return f"{self.school.name} settlement {self.transfer_reference}"


class CollectionAuditLog(models.Model):
    """Append-only audit log for collection and settlement activity."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    school = models.ForeignKey(
        "core.SchoolTenant",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="collection_audit_logs",
    )
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="collection_audit_logs",
    )
    action = models.CharField(max_length=80)
    reference = models.CharField(max_length=120, blank=True)
    message = models.CharField(max_length=255)
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["school", "created_at"]),
            models.Index(fields=["action"]),
            models.Index(fields=["reference"]),
        ]

    def save(self, *args, **kwargs):
        if self.pk and CollectionAuditLog.objects.filter(pk=self.pk).exists():
            raise ValueError("Collection audit logs are append-only.")
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValueError("Collection audit logs are append-only.")
