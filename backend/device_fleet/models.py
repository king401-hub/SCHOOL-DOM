"""Device provisioning and fleet management for SchoolDom Scanner terminals.

Card-to-student assignment and the actual attendance-recording call already
live in rfid_attendance (CardAssignment, attendance_scan_create) - a scanner
device authenticates as a normal SchoolDom user (or acts on behalf of one)
and posts to those same endpoints, exactly like the RFID Win7 desktop app
does. This app owns only what's genuinely new: the physical device's own
identity, its provisioning key, its permanent-session authorization, and its
telemetry (battery/online-offline/heartbeat) - the fleet-management layer
described as "Part B" of the scanner spec.
"""
import secrets
import uuid

from django.db import models
from django.utils import timezone


def generate_provisioning_key():
    # Not a normal user password - a device-registration credential. 32 bytes
    # of URL-safe randomness, formatted in groups for easier manual entry on
    # a device that doesn't have a camera/QR scanner for it yet.
    raw = secrets.token_hex(16).upper()
    return '-'.join(raw[i:i + 4] for i in range(0, len(raw), 4))


class ProvisioningKey(models.Model):
    STATUS_CHOICES = [
        ('unused', 'Unused'),
        ('used', 'Used'),
        ('revoked', 'Revoked'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    key = models.CharField(max_length=64, unique=True, default=generate_provisioning_key)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='unused')
    single_use = models.BooleanField(default=True)
    expires_at = models.DateTimeField(null=True, blank=True)
    created_by = models.ForeignKey(
        'users.User', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='provisioning_keys_created',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    used_at = models.DateTimeField(null=True, blank=True)
    used_by_device = models.ForeignKey(
        'Device', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='provisioning_keys_used',
    )
    notes = models.CharField(max_length=255, blank=True, default='')

    class Meta:
        verbose_name = 'Provisioning Key'
        verbose_name_plural = 'Provisioning Keys'
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.key} ({self.status})'

    @property
    def is_valid(self):
        if self.status != 'unused':
            return False
        if self.expires_at and timezone.now() > self.expires_at:
            return False
        return True


class Device(models.Model):
    STATUS_CHOICES = [
        ('unregistered', 'Unregistered'),
        ('provisioning', 'Provisioning'),
        ('active', 'Active'),
        ('suspended', 'Suspended'),
        ('revoked', 'Revoked'),
        ('maintenance', 'Maintenance'),
    ]
    BATTERY_HEALTH_CHOICES = [
        ('good', 'Good'),
        ('normal', 'Normal'),
        ('fair', 'Fair'),
        ('poor', 'Poor'),
        ('unknown', 'Unknown'),
        ('not_supported', 'Not Supported'),
    ]

    # How long with no heartbeat before a device is considered offline -
    # "Do not mark a device offline after only one missed heartbeat" from the
    # spec; the mobile app's heartbeat interval is expected to be well under
    # this, so one or two missed beats (a brief network blip) don't flip it.
    OFFLINE_AFTER_SECONDS = 5 * 60

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    device_id = models.CharField(max_length=20, unique=True, editable=False)
    name = models.CharField(max_length=120, blank=True, default='')
    # The provisioning key this device was registered with, kept for display/
    # support reference after the key itself is consumed (ProvisioningKey.key
    # is copied here at provision time, not looked up live).
    license_key = models.CharField(max_length=64, blank=True, default='')

    status = models.CharField(max_length=15, choices=STATUS_CHOICES, default='unregistered')
    tenant = models.ForeignKey(
        'core.SchoolTenant', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='scanner_devices',
    )

    # Permanent-session authorization (spec section 9/19) - independent of
    # `status` so "suspended" and "revoked" both read as unauthorized without
    # overloading one field's meaning.
    authorized = models.BooleanField(default=False)
    auth_token = models.CharField(max_length=64, blank=True, default='', db_index=True)
    authorized_at = models.DateTimeField(null=True, blank=True)

    # "Permanent login" (spec section 9) is implemented with the SchoolDom
    # API's existing JWT auth, not a parallel credential system: each device
    # gets its own synthetic staff-role User (password unusable - login is
    # only ever by refresh token) created at provisioning time, so a scan
    # posted from this device hits rfid_attendance.attendance_scan_create
    # exactly like a human staff member's phone would, with normal
    # role/tenant scoping and audit trail. The device stores a long-lived
    # refresh token (7 days, rotated on each use - see SIMPLE_JWT in
    # settings) and silently refreshes it forever; revoking here deletes
    # this user's ability to authenticate at all (see revoke_device).
    scanner_user = models.OneToOneField(
        'users.User', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='scanner_device',
    )
    revoked_at = models.DateTimeField(null=True, blank=True)
    revoked_by = models.ForeignKey(
        'users.User', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='devices_revoked',
    )

    # Telemetry - never invented client-side; "Not Supported" is a real,
    # distinct value from "unknown/not yet reported" (null).
    app_version = models.CharField(max_length=20, blank=True, default='')
    # Android versionCode (packageInfo.buildNumber) - an integer that only
    # ever increases, unlike app_version's semver string, so comparing it
    # against AppRelease.version_code to decide "is a newer build
    # available" never has to parse/compare semver strings.
    app_version_code = models.PositiveIntegerField(null=True, blank=True)
    device_model = models.CharField(max_length=120, blank=True, default='')
    os_version = models.CharField(max_length=60, blank=True, default='')
    battery_percentage = models.PositiveSmallIntegerField(null=True, blank=True)
    battery_charging = models.BooleanField(null=True, blank=True)
    battery_health = models.CharField(max_length=15, choices=BATTERY_HEALTH_CHOICES, blank=True, default='')
    battery_temperature_c = models.DecimalField(max_digits=4, decimal_places=1, null=True, blank=True)
    last_seen_at = models.DateTimeField(null=True, blank=True)
    last_sync_at = models.DateTimeField(null=True, blank=True)

    first_activated_at = models.DateTimeField(null=True, blank=True)
    created_by = models.ForeignKey(
        'users.User', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='devices_registered',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Scanner Device'
        verbose_name_plural = 'Scanner Devices'
        ordering = ['device_id']

    def __str__(self):
        return f'{self.device_id} ({self.status})'

    def save(self, *args, **kwargs):
        if not self.device_id:
            self.device_id = self._next_device_id()
        super().save(*args, **kwargs)

    @staticmethod
    def _next_device_id():
        last = Device.objects.order_by('-created_at').values_list('device_id', flat=True).first()
        last_n = 0
        if last and last.startswith('SCN-'):
            try:
                last_n = int(last.split('-')[1])
            except (IndexError, ValueError):
                last_n = 0
        return f'SCN-{last_n + 1:03d}'

    @property
    def is_online(self):
        if not self.last_seen_at:
            return False
        return (timezone.now() - self.last_seen_at).total_seconds() <= self.OFFLINE_AFTER_SECONDS

    @property
    def is_low_battery(self):
        return self.battery_percentage is not None and self.battery_percentage <= 20

    def needs_attention(self):
        return self.is_low_battery or not self.is_online or self.battery_health == 'poor' or self.status == 'suspended'


class DeviceAuditLog(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    device = models.ForeignKey(
        Device, on_delete=models.SET_NULL, null=True, blank=True, related_name='audit_logs',
    )
    actor = models.ForeignKey(
        'users.User', on_delete=models.SET_NULL, null=True, blank=True, related_name='device_audit_actions',
    )
    action = models.CharField(max_length=60)
    details = models.TextField(blank=True, default='')
    result = models.CharField(max_length=20, default='success')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Device Audit Log'
        verbose_name_plural = 'Device Audit Logs'
        ordering = ['-created_at']
        indexes = [models.Index(fields=['device', '-created_at'])]


class AppRelease(models.Model):
    """A published build of a fleet app (currently only the scanner kiosk),
    checked against Device.app_version_code on every heartbeat
    (device_heartbeat) to tell a device "there's a newer build" and hand it
    a download URL - no code deploy needed to ship a new kiosk build, just
    upload the APK here and bump version_code (staff does this from the
    Control Panel, which auto-registers this model with a real add/change
    form and file upload, same as every other unregistered model)."""

    APP_SCANNER_KIOSK = 'scanner_kiosk'
    APP_CHOICES = [(APP_SCANNER_KIOSK, 'Scanner Kiosk')]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    app = models.CharField(max_length=30, choices=APP_CHOICES, default=APP_SCANNER_KIOSK)
    # Must match the Android versionCode this build was compiled with
    # (pubspec.yaml's version: X.Y.Z+<version_code>) - the app compares
    # this against its own buildNumber, not version_name.
    version_code = models.PositiveIntegerField()
    version_name = models.CharField(max_length=20, help_text='e.g. 1.2.0 - shown to staff, not compared by the app')
    apk_file = models.FileField(upload_to='app_releases/%Y/%m/')
    release_notes = models.TextField(blank=True)
    # Only one active release per app is ever served as "latest" - lets
    # staff stage/upload a build without it going live, and instantly roll
    # back by flipping is_active on an older row instead of deleting the
    # bad one.
    is_active = models.BooleanField(default=True)
    created_by = models.ForeignKey('users.User', on_delete=models.SET_NULL, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'App Release'
        verbose_name_plural = 'App Releases'
        ordering = ['-version_code']

    def __str__(self):
        return f'{self.get_app_display()} {self.version_name} ({self.version_code})'

    def __str__(self):
        who = self.actor.get_full_name() if self.actor else 'System'
        return f'{self.action} - {who}'
