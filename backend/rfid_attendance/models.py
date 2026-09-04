"""Card-to-person mapping for the RFID attendance desktop app.

A card can be assigned to any tenant user - student, teacher, or admin
(admins can badge themselves in too) - which is why the FK below is named
`holder`, not `student`. Attendance records land in different places
depending on the holder's role (academic.AttendanceRecord for students,
attendance.TeacherAttendance for everyone else) - see
attendance_scan_create in views.py. This app only owns the card_uid ->
holder assignment, matching the spec's requirement that this mapping is
written exclusively by the desktop app and only ever *read* by
Android/web through the API.
"""
import datetime
import uuid

from django.db import models
from django.db.models import Q


class CardAssignment(models.Model):
    STATUS_CHOICES = [
        ('active', 'Active'),
        ('revoked', 'Revoked'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(
        'core.SchoolTenant',
        on_delete=models.CASCADE,
        related_name='card_assignments',
    )
    holder = models.ForeignKey(
        'users.User',
        on_delete=models.CASCADE,
        related_name='card_assignments',
    )
    card_uid = models.CharField(max_length=64)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='active')
    assigned_at = models.DateTimeField(auto_now_add=True)
    revoked_at = models.DateTimeField(null=True, blank=True)
    assigned_by = models.ForeignKey(
        'users.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='card_assignments_made',
    )
    revoked_by = models.ForeignKey(
        'users.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='card_assignments_revoked',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Card Assignment'
        verbose_name_plural = 'Card Assignments'
        ordering = ['-assigned_at']
        constraints = [
            # A card UID can have at most one active assignment within a school -
            # scoped per-tenant (not globally) since two different schools each
            # running their own reader batch could coincidentally share a UID.
            models.UniqueConstraint(
                fields=['tenant', 'card_uid'],
                condition=Q(status='active'),
                name='unique_active_card_uid_per_tenant',
            ),
            # A person can have at most one active card at a time.
            models.UniqueConstraint(
                fields=['holder'],
                condition=Q(status='active'),
                name='unique_active_card_per_holder',
            ),
        ]
        indexes = [
            models.Index(fields=['tenant', 'status'], name='rfid_attend_tenant__d3f1a2_idx'),
            models.Index(fields=['card_uid'], name='rfid_attend_card_ui_7c9e4b_idx'),
        ]

    def __str__(self):
        return f'{self.card_uid} -> {self.holder.get_full_name()} ({self.status})'


class GateSettings(models.Model):
    """Per-school configuration for the SchoolGate terminal (spec sections
    2, 5, 6, 7) - one row per tenant, lazily created with these defaults the
    first time a gate terminal asks for its settings (see
    get_or_create_gate_settings in views.py)."""

    MODE_ATTENDANCE_ONLY = 'attendance_only'
    MODE_FEE_TRACKER = 'fee_tracker'
    MODE_CHOICES = [
        (MODE_ATTENDANCE_ONLY, 'Attendance Only'),
        (MODE_FEE_TRACKER, 'Fee Tracker'),
    ]

    tenant = models.OneToOneField(
        'core.SchoolTenant',
        on_delete=models.CASCADE,
        related_name='gate_settings',
    )
    mode = models.CharField(max_length=20, choices=MODE_CHOICES, default=MODE_ATTENDANCE_ONLY)

    # Example defaults straight from the spec (section 5) - every field is
    # editable per-school from the terminal's own Settings screen, never
    # hardcoded in view logic.
    early_start = models.TimeField(default=datetime.time(7, 30))
    early_end = models.TimeField(default=datetime.time(8, 30))
    late_start = models.TimeField(default=datetime.time(8, 31))
    late_end = models.TimeField(default=datetime.time(10, 0))
    clockout_start = models.TimeField(default=datetime.time(13, 0))
    clockout_end = models.TimeField(default=datetime.time(16, 0))

    # Section 7 - "duplicate-protection interval should ideally be
    # configurable at the backend/device level."
    duplicate_protection_seconds = models.PositiveIntegerField(default=30)

    # Section 6 - "Settings should be protected by an admin PIN". Hashed with
    # Django's own password hasher (see users/app_views.py's
    # notification_preferences-style get-or-create pattern) - never stored
    # or transmitted in the clear. Blank means "no PIN set yet" - the
    # terminal treats that as open rather than locking admins out before
    # they've ever configured one.
    admin_pin_hash = models.CharField(max_length=128, blank=True, default='')

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Gate Settings'
        verbose_name_plural = 'Gate Settings'

    def classify_event(self, check_time):
        """Early/Late/Clockout/other, from a plain datetime.time - spec
        section 5's configured windows, never a hardcoded time comparison."""
        if self.early_start <= check_time <= self.early_end:
            return 'early'
        if self.late_start <= check_time <= self.late_end:
            return 'late'
        if self.clockout_start <= check_time <= self.clockout_end:
            return 'clockout'
        return 'other'

    def __str__(self):
        return f'Gate settings for {self.tenant_id}'
