"""CBT license key models.

A CBTLicense gates CBT/exam access (both the web app and the offline Win7
desktop apps) per school. Every activation/expiry computation lives on the
server (see licensing/services.py) - clients only ever display what the
server returns, never recompute expires_at themselves. This mirrors
finance.models.TokenAllocation's shape (start/expiry dates, a computed
status property, a scheduled expiry sweep) since a license is structurally
the same kind of thing: a school-level, time-bounded access grant.
"""
import uuid

from django.conf import settings
from django.db import models
from django.utils import timezone


class CBTLicense(models.Model):
    STATUS_PENDING = "pending"
    STATUS_ACTIVE = "active"
    STATUS_EXPIRED = "expired"
    STATUS_REVOKED = "revoked"
    STATUS_CHOICES = [
        (STATUS_PENDING, "Pending"),
        (STATUS_ACTIVE, "Active"),
        (STATUS_EXPIRED, "Expired"),
        (STATUS_REVOKED, "Revoked"),
    ]

    SOURCE_MANUAL = "manual"
    SOURCE_PAYMENT = "payment"
    SOURCE_PROMO = "promo"
    SOURCE_CHOICES = [
        (SOURCE_MANUAL, "Manual (Super Admin)"),
        (SOURCE_PAYMENT, "Payment"),
        (SOURCE_PROMO, "Special deal / promo"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    key = models.CharField(max_length=32, unique=True, db_index=True)
    school = models.ForeignKey(
        "core.SchoolTenant", null=True, blank=True,
        on_delete=models.SET_NULL, related_name="cbt_licenses",
        help_text="Blank until a key generated for the general pool is redeemed by a school.",
    )
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default=STATUS_PENDING)
    source = models.CharField(max_length=10, choices=SOURCE_CHOICES, default=SOURCE_MANUAL)
    activated_at = models.DateTimeField(null=True, blank=True)
    expires_at = models.DateTimeField(
        null=True, blank=True,
        help_text="Server-computed only (activated_at + 3 months 15 days) - never accept this from a client.",
    )
    revoked_at = models.DateTimeField(null=True, blank=True)
    revoked_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True,
        on_delete=models.SET_NULL, related_name="+",
    )
    revoke_reason = models.CharField(max_length=255, blank=True)
    payment_reference = models.CharField(max_length=100, blank=True)
    notes = models.CharField(max_length=255, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True,
        on_delete=models.SET_NULL, related_name="+",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["school", "status"]),
            models.Index(fields=["key"]),
        ]

    def __str__(self):
        school_label = self.school.name if self.school_id else "(unassigned)"
        return f"{self.key} - {school_label} ({self.status})"

    @property
    def is_currently_active(self):
        """The one check that matters - always re-verified live against the
        server clock, never trusting the (periodically-swept) status field
        alone, since that field can lag the exact expiry instant by up to
        one sweep interval."""
        return (
            self.status == self.STATUS_ACTIVE
            and self.expires_at is not None
            and self.expires_at > timezone.now()
        )

    @property
    def days_remaining(self):
        if not self.expires_at:
            return None
        return max(0, (self.expires_at - timezone.now()).days)


class CBTLicensePayment(models.Model):
    STATUS_PENDING = "pending"
    STATUS_SUCCESSFUL = "successful"
    STATUS_FAILED = "failed"
    STATUS_CHOICES = [
        (STATUS_PENDING, "Pending"),
        (STATUS_SUCCESSFUL, "Successful"),
        (STATUS_FAILED, "Failed"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    reference = models.CharField(max_length=100, unique=True, db_index=True)
    school = models.ForeignKey(
        "core.SchoolTenant", on_delete=models.CASCADE, related_name="cbt_license_payments",
    )
    amount = models.DecimalField(max_digits=10, decimal_places=2, default=20000)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default=STATUS_PENDING)
    provider = models.CharField(max_length=20, blank=True)
    license = models.ForeignKey(
        CBTLicense, null=True, blank=True, on_delete=models.SET_NULL, related_name="payments",
    )
    initiated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True,
        on_delete=models.SET_NULL, related_name="+",
    )
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.reference} - {self.school} ({self.status})"
