"""Card-to-student mapping for the RFID attendance desktop app.

Attendance records themselves stay in academic.AttendanceRecord (see the
card_uid/idempotency_key fields added there) - this app only owns the
card_uid -> student assignment, matching the spec's requirement that this
mapping is written exclusively by the desktop app and only ever *read* by
Android/web through the API.
"""
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
    student = models.ForeignKey(
        'users.User',
        on_delete=models.CASCADE,
        related_name='card_assignments',
        limit_choices_to={'role': 'student'},
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
            # A student can have at most one active card at a time.
            models.UniqueConstraint(
                fields=['student'],
                condition=Q(status='active'),
                name='unique_active_card_per_student',
            ),
        ]
        indexes = [
            models.Index(fields=['tenant', 'status'], name='rfid_attend_tenant__d3f1a2_idx'),
            models.Index(fields=['card_uid'], name='rfid_attend_card_ui_7c9e4b_idx'),
        ]

    def __str__(self):
        return f'{self.card_uid} -> {self.student.get_full_name()} ({self.status})'
