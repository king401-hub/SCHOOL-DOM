"""Generic request queue: durable, retryable, deduplicated async requests.

Any flow that needs "submit now, process reliably in the background, never
double-process a resubmission" goes through QueuedRequest. See
request_queue/registry.py for how a request_type is wired to its handler.
"""
import uuid

from django.conf import settings
from django.db import models
from django.db.models import Q
from django.utils import timezone


def default_expiry():
    return timezone.now() + timezone.timedelta(hours=24)


class QueuedRequest(models.Model):
    """One logical request submitted by a user, tracked end-to-end."""

    STATUS_PENDING = "pending"
    STATUS_QUEUED = "queued"
    STATUS_PROCESSING = "processing"
    STATUS_RETRYING = "retrying"
    STATUS_APPROVED = "approved"
    STATUS_REJECTED = "rejected"
    STATUS_FAILED = "failed"
    STATUS_CANCELLED = "cancelled"
    STATUS_EXPIRED = "expired"

    STATUS_CHOICES = [
        (STATUS_PENDING, "Pending"),
        (STATUS_QUEUED, "Queued"),
        (STATUS_PROCESSING, "Processing"),
        (STATUS_RETRYING, "Retrying"),
        (STATUS_APPROVED, "Approved"),
        (STATUS_REJECTED, "Rejected"),
        (STATUS_FAILED, "Failed"),
        (STATUS_CANCELLED, "Cancelled"),
        (STATUS_EXPIRED, "Expired"),
    ]

    # Statuses where the request is still "alive" - eligible for retry,
    # counted toward dedupe, shown as active in the admin queue view.
    ACTIVE_STATUSES = [STATUS_PENDING, STATUS_QUEUED, STATUS_PROCESSING, STATUS_RETRYING]
    TERMINAL_STATUSES = [STATUS_APPROVED, STATUS_REJECTED, STATUS_FAILED, STATUS_CANCELLED, STATUS_EXPIRED]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(
        "core.SchoolTenant",
        on_delete=models.CASCADE,
        related_name="queued_requests",
        null=True,
        blank=True,
    )
    requester = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="queued_requests",
        null=True,
        blank=True,
    )
    request_type = models.CharField(max_length=50, db_index=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_PENDING, db_index=True)
    payload = models.JSONField(default=dict, blank=True)
    result = models.JSONField(null=True, blank=True)

    dedupe_key = models.CharField(max_length=64, db_index=True)
    linked_request = models.ForeignKey(
        "self",
        on_delete=models.SET_NULL,
        related_name="duplicates",
        null=True,
        blank=True,
    )
    is_archived = models.BooleanField(default=False)

    retry_count = models.IntegerField(default=0)
    max_retries = models.IntegerField(default=5)
    last_attempt_at = models.DateTimeField(null=True, blank=True)
    next_retry_at = models.DateTimeField(null=True, blank=True)
    expires_at = models.DateTimeField(default=default_expiry)
    error_message = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["tenant", "status", "created_at"]),
            models.Index(fields=["request_type", "status"]),
            models.Index(fields=["dedupe_key"]),
        ]
        constraints = [
            # Hard DB-level guarantee: at most one *active* request per
            # dedupe key, closing the race a plain SELECT-then-INSERT check
            # can't fully close on its own.
            models.UniqueConstraint(
                fields=["dedupe_key"],
                condition=Q(status__in=["pending", "queued", "processing", "retrying"]),
                name="unique_active_dedupe_key",
            ),
        ]

    def __str__(self):
        return f"QueuedRequest({self.request_type}, {self.status}, {self.id})"

    @property
    def is_terminal(self):
        return self.status in self.TERMINAL_STATUSES

    def log(self, event_type, description="", actor=None, metadata=None):
        return QueuedRequestEvent.objects.create(
            request=self,
            actor=actor,
            event_type=event_type,
            description=description[:255],
            metadata=metadata or {},
        )


class QueuedRequestEvent(models.Model):
    """Append-only processing history / audit trail for a QueuedRequest."""

    EVENT_CREATED = "created"
    EVENT_QUEUED = "queued"
    EVENT_PROCESSING_STARTED = "processing_started"
    EVENT_RETRY_SCHEDULED = "retry_scheduled"
    EVENT_SUCCEEDED = "succeeded"
    EVENT_FAILED = "failed"
    EVENT_REJECTED = "rejected"
    EVENT_CANCELLED = "cancelled"
    EVENT_EXPIRED = "expired"
    EVENT_DUPLICATE_DETECTED = "duplicate_detected"
    EVENT_ARCHIVED = "archived"
    EVENT_MANUAL_RETRY = "manual_retry"

    EVENT_CHOICES = [
        (EVENT_CREATED, "Created"),
        (EVENT_QUEUED, "Queued"),
        (EVENT_PROCESSING_STARTED, "Processing started"),
        (EVENT_RETRY_SCHEDULED, "Retry scheduled"),
        (EVENT_SUCCEEDED, "Succeeded"),
        (EVENT_FAILED, "Failed"),
        (EVENT_REJECTED, "Rejected"),
        (EVENT_CANCELLED, "Cancelled"),
        (EVENT_EXPIRED, "Expired"),
        (EVENT_DUPLICATE_DETECTED, "Duplicate detected"),
        (EVENT_ARCHIVED, "Archived"),
        (EVENT_MANUAL_RETRY, "Manual retry"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    request = models.ForeignKey(QueuedRequest, on_delete=models.CASCADE, related_name="history")
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="queued_request_events",
        null=True,
        blank=True,
    )
    event_type = models.CharField(max_length=30, choices=EVENT_CHOICES)
    description = models.CharField(max_length=255, blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at"]
        indexes = [
            models.Index(fields=["request", "created_at"]),
        ]

    def save(self, *args, **kwargs):
        if self.pk and QueuedRequestEvent.objects.filter(pk=self.pk).exists():
            raise ValueError("Processing history is append-only and cannot be modified.")
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValueError("Processing history is append-only and cannot be deleted.")

    def __str__(self):
        return f"QueuedRequestEvent({self.event_type} on {self.request_id})"
