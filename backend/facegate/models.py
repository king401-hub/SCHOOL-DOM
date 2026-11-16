"""Models for the vendor face-recognition SchoolGate terminal integration -
the "cloud solution" HTTP+JSON protocol (device registers/heartbeats with
`cmd`/`sn`, the server answers a heartbeat with a queued command instead of
a plain ack when one is pending - see facegate/views.py's module docstring
for why that needs no new infrastructure).

This repurposes an app originally built against a *different* vendor's
protocol (`deviceId`/`selectPassInfo`/`insertNoteFace`) - that device choice
turned out to be wrong and was never deployed to a real school, but the
model shapes below (and facegate/services.py's attendance-integration
logic) needed almost no change to fit the new protocol: both need a
tenant-scoped device row, a generic pending-command queue by boolean flag
(restart/shutdown/opendoor), and a way to bridge a real user's UUID to the
small numeric id (`enrollid` in this protocol, `employeeNumberId` in the
old one) these vendor protocols require.
"""
import uuid

from django.db import models


class FaceGateDevice(models.Model):
    """One row per physical terminal. `device_id` is the vendor's own
    serial number (the protocol's `sn` field), printed on the unit - it is
    also the device's ONLY credential in this protocol (see
    facegate/views.py's module docstring for why that's weak, and the
    IP-allowlist recommendation that goes with it)."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(
        'core.SchoolTenant', on_delete=models.CASCADE, related_name='facegate_devices',
    )
    device_id = models.CharField(max_length=63, unique=True)
    label = models.CharField(max_length=100, blank=True, default='')
    device_type = models.CharField(max_length=31, blank=True, default='')
    firmware_version = models.CharField(max_length=63, blank=True, default='')
    mac_address = models.CharField(max_length=31, blank=True, default='')
    is_active = models.BooleanField(default=True)
    last_seen_at = models.DateTimeField(null=True, blank=True)

    # Handed out sequentially to each new FaceGateEnrollment on this device -
    # the device's own `enrollid` field must be pure numeric, so a SchoolDom
    # user's real (UUID) id can't be sent as-is.
    next_employee_number = models.PositiveIntegerField(default=1)

    # One-shot commands delivered on the device's NEXT checklive/reg poll
    # (this protocol has no dedicated "any commands for me?" endpoint like
    # the old one's device_select_restart - the queued command is returned
    # in place of the plain heartbeat ack instead) - cleared the moment
    # they're served (pop semantics, see views.device_api's _handle_checklive).
    pending_restart = models.BooleanField(default=False)
    pending_shutdown = models.BooleanField(default=False)
    pending_opendoor = models.BooleanField(default=False)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Face Gate Device'
        verbose_name_plural = 'Face Gate Devices'
        ordering = ['tenant', 'label']

    def __str__(self):
        return f'{self.label or self.device_id} ({self.tenant_id})'

    def allocate_employee_number(self):
        """Atomically hand out the next numeric id for a new enrollment on
        this device and advance the counter - see
        FaceGateEnrollment.device_employee_number. Caller must already hold
        a row lock (select_for_update) on this device."""
        number = self.next_employee_number
        self.next_employee_number = number + 1
        self.save(update_fields=['next_employee_number', 'updated_at'])
        return number


class FaceGateEnrollment(models.Model):
    """One row per (device, person) that should exist on that specific
    terminal. Created/removed by an admin action (see
    facegate.services.enroll_user_on_device); a PENDING_ADD row here is
    what views.py's _handle_checklive pushes down as a `senduser` command
    on the device's next heartbeat - never driven by querying
    StudentProfile/User directly - that keeps each device's roster
    explicit, revocable per-terminal, and lets one school run several
    gates with different rosters (e.g. a staff-only side door)."""

    STATUS_PENDING_ADD = 'pending_add'
    STATUS_SYNCED = 'synced'
    STATUS_FAILED = 'failed'
    STATUS_CHOICES = [
        (STATUS_PENDING_ADD, 'Pending add'),
        (STATUS_SYNCED, 'Synced'),
        (STATUS_FAILED, 'Failed'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    device = models.ForeignKey(FaceGateDevice, on_delete=models.CASCADE, related_name='enrollments')
    user = models.ForeignKey('users.User', on_delete=models.CASCADE, related_name='facegate_enrollments')
    device_employee_number = models.PositiveIntegerField()
    status = models.CharField(max_length=15, choices=STATUS_CHOICES, default=STATUS_PENDING_ADD)
    error_message = models.CharField(max_length=255, blank=True, default='')

    # De-dupes a repeated check-in upload for the exact same event - the
    # vendor protocol retries a `sendlog` batch until it gets back success,
    # which must never replay as a second clock toggle. See
    # facegate.services.record_checkin.
    last_note_time = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Face Gate Enrollment'
        verbose_name_plural = 'Face Gate Enrollments'
        constraints = [
            models.UniqueConstraint(fields=['device', 'user'], name='unique_facegate_enrollment_per_device'),
            models.UniqueConstraint(
                fields=['device', 'device_employee_number'],
                name='unique_facegate_employee_number_per_device',
            ),
        ]
        indexes = [
            models.Index(fields=['device', 'status'], name='facegate_enroll_dev_stat_idx'),
        ]

    def __str__(self):
        return f'{self.user.get_full_name()} on {self.device.label or self.device.device_id} ({self.status})'
