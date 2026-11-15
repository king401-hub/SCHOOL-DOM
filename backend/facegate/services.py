"""Business logic for the face-gate HTTP integration - kept out of
views.py so the device-facing endpoints there stay thin request/response
plumbing. Deliberately reuses the SAME attendance-clocking and gate-SMS
primitives every other SchoolGate terminal type (RFID desktop app, QR
self-scan) already goes through, rather than forking a parallel copy:

- users.app_views._record_attendance_clock - the shared clock-in/out
  engine every tap/scan endpoint in the platform calls.
- rfid_attendance.views.get_or_create_gate_settings /
  ._send_gate_sms / ._send_gate_sms_from_wallet - the shared
  early/late/clockout window classification and parent-SMS billing
  policy ("only a premium SchoolGate school gets it free") that already
  applies to every other gate terminal type.
- rfid_attendance.services._legacy_tenant_for_attendance - the same
  SchoolTenant -> legacy tenants.Tenant resolution every other
  attendance writer uses.

That keeps this new hardware vendor's check-ins behaving identically to
every other SchoolGate terminal a school might run side by side with it.
"""
from datetime import datetime
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from django.db import transaction
from django.utils import timezone

from rfid_attendance.services import _legacy_tenant_for_attendance
from users.app_views import AttendanceClockError, _profile_picture_url, _record_attendance_clock

from .models import FaceGateEnrollment


def person_payload(request, enrollment):
    """One entry of the `passinfo` array selectPassInfo hands back - the
    minimum fields the vendor's own examples send: a numeric identity (see
    FaceGateDevice.allocate_employee_number for why it can't just be the
    real UUID), a display name, and a face photo URL when one exists.

    A person with no uploaded profile photo yet is still sent (so the
    device at least recognises their number for door-open/record purposes
    once face data is added later), just without the face/photo keys -
    the vendor spec treats those as optional per person, not required.
    """
    user_obj = enrollment.user
    number = str(enrollment.device_employee_number)
    payload = {
        'employeeId': number,
        'employeeNumberId': number,
        'employeeName': (user_obj.get_full_name() or user_obj.email or number)[:31],
        'employeeType': 0,  # regular person - see protocol appendix 8.5
    }
    photo_url = _profile_picture_url(request, user_obj)
    if photo_url:
        payload['faceType'] = 'photo'
        payload['employeePhotoWay'] = 'path'
        payload['employeePhoto'] = photo_url
    return payload


def enroll_user_on_device(device, user):
    """Queue `user` to be pushed to `device` on its next selectPassInfo
    poll. Idempotent - re-enrolling someone already pending/synced on this
    device just returns the existing row, so a bulk "enable face gate for
    this class" admin action is safe to re-run."""
    existing = FaceGateEnrollment.objects.filter(device=device, user=user).first()
    if existing:
        return existing
    with transaction.atomic():
        from .models import FaceGateDevice
        device_locked = FaceGateDevice.objects.select_for_update().get(pk=device.pk)
        number = device_locked.allocate_employee_number()
        return FaceGateEnrollment.objects.create(
            device=device_locked, user=user, device_employee_number=number,
        )


def unenroll_user_from_device(device, user):
    """Remove `user` from `device`'s roster. The vendor protocol has no
    delete-result feedback endpoint (unlike add, which has setPassResult),
    so there is nothing to wait for - the row is deleted the moment it is
    handed back by selectDeleteInfo (see views.device_select_delete_info),
    matching the lack of an ack step in the spec."""
    FaceGateEnrollment.objects.filter(device=device, user=user).delete()


def _school_tzinfo(school):
    """Same blank/'UTC' -> platform-default fallback as
    rfid_attendance.services._school_localtime, so a device's wall-clock
    reading is interpreted in the exact same timezone every other gate
    scan's "what time is it for this school" logic already uses."""
    tz_name = str(getattr(school, 'timezone', '') or '').strip()
    if tz_name and tz_name != 'UTC':
        try:
            return ZoneInfo(tz_name)
        except (ZoneInfoNotFoundError, ValueError):
            pass
    return timezone.get_default_timezone()


def parse_device_note_time(school, note_time_str):
    """The device's own local wall-clock reading ("2025-07-22 15:43:20",
    always naive per the protocol) -> an aware datetime, on the assumption
    that the terminal is physically on-site and so reads that school's
    local time, not UTC."""
    naive = datetime.strptime(str(note_time_str).strip(), '%Y-%m-%d %H:%M:%S')
    return naive.replace(tzinfo=_school_tzinfo(school))


def record_checkin(device, enrollment, occurred_at):
    """Turn one face-gate tap into a clock-in/out, exactly like an RFID
    gate tap (see rfid_attendance.views._record_student_scan, which this
    mirrors at a smaller scale - only the student path, since this first
    pass doesn't cover staff biometric attendance yet).

    Returns True if a new attendance event was actually recorded, False if
    this was a replay of an already-processed note (see
    FaceGateEnrollment.last_note_time) or the person isn't a student.
    Never raises - a clock-ordering conflict (e.g. "already clocked out
    today") is swallowed rather than surfaced, since the device has no use
    for an error and would otherwise retry the same rejected tap forever
    (spec section 5.1).
    """
    # rfid_attendance.views import is deferred to avoid a import-time
    # circular import (that module imports academic/users models at
    # module scope the same way this one does).
    from rfid_attendance.views import get_or_create_gate_settings, _send_gate_sms, _send_gate_sms_from_wallet

    if enrollment.last_note_time == occurred_at:
        return False  # exact replay of a note we already processed

    user = enrollment.user
    student_profile = getattr(user, 'student_profile', None)
    if student_profile is None:
        # Staff biometric attendance isn't wired up yet (see module
        # docstring) - record the tap as seen so it stops retrying, but do
        # nothing else with it.
        FaceGateEnrollment.objects.filter(pk=enrollment.pk).update(last_note_time=occurred_at)
        return False

    school = device.tenant
    gate_settings = get_or_create_gate_settings(school)
    event = gate_settings.classify_event(occurred_at.time())
    if event == 'too_early':
        return False

    tenant_obj = _legacy_tenant_for_attendance(school)
    no_location = {
        'latitude': None, 'longitude': None, 'accuracy': None,
        'address': '', 'device_info': f'FaceGate terminal {device.device_id}'[:2000],
    }
    requested_action = 'clock_out' if event == 'clockout' else ''

    try:
        attendance, action, _message = _record_attendance_clock(
            student_user=user,
            student_profile=student_profile,
            tenant_obj=tenant_obj,
            actor=user,  # self-identification via biometric, like a QR self-scan
            location=no_location,
            attendance_date=occurred_at.date(),
            school_name=school.name,
            occurred_at=occurred_at,
            requested_action=requested_action,
            allow_clock_out_without_clock_in=(event == 'clockout'),
        )
    except AttendanceClockError:
        FaceGateEnrollment.objects.filter(pk=enrollment.pk).update(last_note_time=occurred_at)
        return False

    # No AttendanceRecord.idempotency_key here - that field is unique=True
    # and keyed per-scan for the RFID desktop app's own retry mechanism
    # (a client-generated token per tap); this app's replay protection is
    # last_note_time below instead, so writing a same-device-wide value
    # into idempotency_key would collide on this device's second ever
    # check-in.
    FaceGateEnrollment.objects.filter(pk=enrollment.pk).update(last_note_time=occurred_at)

    if school.is_schoolgate and school.subscription_tier == 'premium':
        _send_gate_sms(school, user, student_profile, action, event, occurred_at=occurred_at)
    else:
        _send_gate_sms_from_wallet(school, user, student_profile, action, event, occurred_at=occurred_at)

    return True
