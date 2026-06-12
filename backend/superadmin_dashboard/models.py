from decimal import Decimal

from django.db import models


class SchoolTokenPaymentSetting(models.Model):
    school_model = models.CharField(max_length=120)
    school_pk = models.CharField(max_length=64)
    school_name = models.CharField(max_length=255)
    token_price = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))
    tokens_per_payment = models.PositiveIntegerField(default=1)
    minimum_tokens = models.PositiveIntegerField(default=0)
    payment_required = models.BooleanField(default=True)
    is_active = models.BooleanField(default=True)
    notes = models.TextField(blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ("school_model", "school_pk")
        ordering = ("school_name",)

    def __str__(self):
        return f"{self.school_name} token settings"


class PlatformNotification(models.Model):
    AUDIENCE_CHOICES = [
        ("all", "All schools"),
        ("active", "Active schools"),
        ("suspended", "Suspended schools"),
        ("admins", "School admins"),
    ]

    title = models.CharField(max_length=200)
    message = models.TextField()
    audience = models.CharField(max_length=20, choices=AUDIENCE_CHOICES, default="all")
    is_active = models.BooleanField(default=True)
    publish_at = models.DateTimeField(null=True, blank=True)
    created_by = models.ForeignKey(
        "users.User",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_platform_notifications",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("-created_at",)

    def __str__(self):
        return self.title
