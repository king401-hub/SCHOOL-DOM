"""HTTP integration for the vendor's face-recognition SchoolGate terminal -
the "cloud solution" protocol (plain `cmd`/`sn`-keyed JSON over HTTP POST;
the same vendor also documents a WebSocket variant, not built here since
the polling design below reaches full duplex with zero new infrastructure -
see _handle_checklive's docstring).

First-pass scope only (see project discussion): device registration and
heartbeat, pushing enrolled students' faces down to the device, pulling
check-ins back up into the normal attendance/SMS pipeline, and
restart/door-open commands. NOT built yet: access-control time periods
(setdevlock), attendance holiday/questionnaire settings, terminal system
settings (setdevinfo - volume, screensaver, etc.), bulk log backfill
(getnewlog/getalllog - the device already pushes logs unprompted via
sendlog, so pulling is redundant for a pilot), and staff biometric
attendance (student-only for now, same as the attendance-integration
helpers in services.py already assume) - all left for a later pass once
the core loop is confirmed working against real hardware.

Trust model / known limitation: every view below is reached directly by
the device, not a signed-in SchoolDom user, so none of these use the
normal JWT authentication. The ONLY credential this protocol's HTTP
examples ever send is the device's own `sn` (serial number) in the request
body - there is no signature/token field anywhere in it. That means anyone
who learns or guesses a real `sn` could pose as that device. Two
mitigations:
  1. Every command below is a safe no-op (a documented failure reply, not
     a crash or a silent write) unless that exact `sn` was already
     registered by a school admin first (see admin_register_device) - a
     guessed serial can only ever replay "not registered", never attach
     itself to a school it wasn't registered against.
  2. In production, put the device_api/ path below behind
     middleware.ip_whitelist.IPWhitelistMiddleware, restricted to each
     school's own gate terminal's public IP/VPN - the terminal is the
     only thing that should ever call it, and that middleware already
     exists in this codebase for exactly this kind of weak-auth device
     endpoint (currently wired in but disabled by default - IP_WHITELIST_ENABLED).
If real hardware testing turns up an actual signature field after all, add
verification here before relying on mitigation 1 alone.
"""
from django.db import transaction
from django.utils import timezone
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response

from users.app_views import _can_manage_school_settings, _resolve_school_tenant_for_user
from users.models import StudentProfile

from .models import FaceGateDevice, FaceGateEnrollment
from .services import enroll_user_on_device, parse_device_note_time, record_checkin, senduser_payload, unenroll_user_from_device

# How many PENDING_ADD rows _handle_checklive is willing to look through on
# one poll to find a person who actually has a photo uploaded - bounds the
# work done on a device with a large backlog of photo-less enrollments
# instead of scanning all of them every heartbeat.
PENDING_ENROLLMENT_SCAN_LIMIT = 10


def _device_or_none(sn):
    sn = str(sn or '').strip()
    if not sn:
        return None
    return FaceGateDevice.objects.select_related('tenant').filter(device_id=sn, is_active=True).first()


def _cloudtime():
    return timezone.now().strftime('%Y-%m-%d %H:%M:%S')


# ── Device-facing endpoint (no SchoolDom auth - see module docstring) ───────
# One URL, commands multiplexed by the JSON body's `cmd` (device-initiated,
# "Section A" of the protocol doc) or `ret` (the device acknowledging a
# command WE pushed, "Section B") field - that's the actual wire shape this
# protocol uses, unlike the old vendor's one-path-per-command design.

@api_view(['POST'])
@permission_classes([AllowAny])
def device_api(request):
    cmd = str(request.data.get('cmd') or '').strip()
    if cmd:
        handler = _CMD_HANDLERS.get(cmd)
        if handler:
            return handler(request)
        return Response({'ret': cmd, 'result': False, 'reason': 1})

    ret = str(request.data.get('ret') or '').strip()
    handler = _ACK_HANDLERS.get(ret)
    if handler:
        return handler(request)
    # An ack for a command we don't specifically track (or a malformed
    # body with neither cmd nor ret) - nothing to do, but still a
    # plain 200 so the terminal's retry logic has nothing to retry.
    return Response({'result': True})


def _handle_reg(request):
    sn = request.data.get('sn')
    device = _device_or_none(sn)
    if not device:
        # Matches the protocol doc's own documented failure shape for reg
        # specifically (a string reason, unlike every other command's
        # numeric one) - this message is meant to show on the terminal's
        # own screen per the doc's comment on this field.
        return Response({'ret': 'reg', 'result': False, 'reason': 'did not reg'})

    devinfo = request.data.get('devinfo') or {}
    FaceGateDevice.objects.filter(pk=device.pk).update(
        last_seen_at=timezone.now(),
        device_type=str(devinfo.get('modelname') or device.device_type)[:31],
        firmware_version=str(devinfo.get('firmware') or device.firmware_version)[:63],
        mac_address=str(devinfo.get('mac') or device.mac_address)[:31],
    )
    return Response({
        'ret': 'reg', 'result': True, 'cloudtime': _cloudtime(),
        # We are the roster's source of truth (admin enroll/unenroll), not
        # the device's local keypad - tell it not to bother uploading
        # whatever users it already has on its own.
        'nosenduser': True,
    })


def _handle_checklive(request):
    """Heartbeat. If this device has something queued, the reply IS that
    command instead of the plain ack - the protocol has no separate
    "anything for me?" endpoint, so this is the one and only place a
    server-initiated command can reach the terminal over plain HTTP. Exactly
    the same "answer the next poll with the command instead of a plain ack"
    pattern device_fleet.views.device_heartbeat already uses for its own
    self-update check - zero new infrastructure, no WebSocket/Channels.

    Priority: door-open and restart (one-shot admin actions, see
    admin_queue_opendoor/admin_queue_restart) before a pending face
    enrollment, since an admin asking to open a door right now is more
    time-sensitive than a routine roster sync.
    """
    sn = request.data.get('sn')
    device = _device_or_none(sn)
    if not device:
        return Response({'ret': 'checklive', 'result': False, 'reason': 1})

    FaceGateDevice.objects.filter(pk=device.pk).update(last_seen_at=timezone.now())

    if device.pending_opendoor:
        FaceGateDevice.objects.filter(pk=device.pk).update(pending_opendoor=False)
        return Response({'cmd': 'opendoor'})
    if device.pending_restart:
        FaceGateDevice.objects.filter(pk=device.pk).update(pending_restart=False)
        return Response({'cmd': 'reboot'})

    pending = (
        FaceGateEnrollment.objects.filter(device=device, status=FaceGateEnrollment.STATUS_PENDING_ADD)
        .select_related('user', 'user__student_profile')
        .order_by('device_employee_number')[:PENDING_ENROLLMENT_SCAN_LIMIT]
    )
    for enrollment in pending:
        payload = senduser_payload(enrollment)
        if payload:
            return Response(payload)
        # No photo uploaded yet for this one - leave it PENDING_ADD and
        # check the next candidate instead of pushing an empty command.

    return Response({'ret': 'checklive', 'result': True, 'cloudtime': _cloudtime()})


def _handle_sendlog(request):
    sn = request.data.get('sn')
    device = _device_or_none(sn)
    if not device:
        return Response({'ret': 'sendlog', 'result': False, 'reason': 1})

    FaceGateDevice.objects.filter(pk=device.pk).update(last_seen_at=timezone.now())

    records = request.data.get('record') or []
    count = request.data.get('count', len(records))
    if count:
        numbers = []
        for record in records:
            try:
                numbers.append(int(record.get('enrollid')))
            except (TypeError, ValueError):
                continue
        enrollments_by_number = {
            e.device_employee_number: e
            for e in FaceGateEnrollment.objects.filter(
                device=device, device_employee_number__in=numbers,
            ).select_related('user', 'user__student_profile')
        }
        for record in records:
            try:
                enrollid = int(record.get('enrollid'))
            except (TypeError, ValueError):
                continue
            if enrollid == 0:
                continue  # a door/system event, not a person tap - not wired up yet (see module docstring)
            enrollment = enrollments_by_number.get(enrollid)
            note_time = record.get('time')
            if not enrollment or not note_time:
                continue
            occurred_at = parse_device_note_time(device.tenant, note_time)
            record_checkin(device, enrollment, occurred_at)

    response = {'ret': 'sendlog', 'result': True, 'cloudtime': _cloudtime()}
    if 'count' in request.data:
        response['count'] = count
    if 'logindex' in request.data:
        response['logindex'] = request.data['logindex']
    return Response(response)


FINGERPRINT_BACKUPNUM_MAX = 9  # 0~9 per the protocol's backupnum convention


def _handle_senduser(request):
    """A user added via the device's OWN local keypad (Section A - "When
    use keypad to add new user, and then send this message to server").

    The only case this acts on is a fingerprint (backupnum 0-9): that's the
    one enrollment a terminal operator can ONLY capture locally, in person,
    on the device's own sensor - there's no way to push a fingerprint
    template down from a photo like a face enrollment, and the template
    itself is an opaque, vendor-algorithm-specific blob we deliberately
    never store (see FaceGateEnrollment.fingerprint_enrolled_at). An
    enrollid the device reports that we never pre-allocated via
    admin_bulk_enroll is ignored outright - this app's roster is one-way
    (admin enroll/unenroll -> device), so there is no SchoolDom user to
    attribute an unexpected local add to; acking without recording
    anything just stops the device retrying a message it thinks failed."""
    sn = request.data.get('sn')
    device = _device_or_none(sn)
    if device:
        try:
            number = int(request.data.get('enrollid'))
            backupnum = int(request.data.get('backupnum'))
        except (TypeError, ValueError):
            number = backupnum = None
        if number is not None and 0 <= backupnum <= FINGERPRINT_BACKUPNUM_MAX:
            FaceGateEnrollment.objects.filter(
                device=device, device_employee_number=number,
            ).update(fingerprint_enrolled_at=timezone.now())
    return Response({'ret': 'senduser', 'result': True, 'cloudtime': _cloudtime()})


_CMD_HANDLERS = {
    'reg': _handle_reg,
    'checklive': _handle_checklive,
    'sendlog': _handle_sendlog,
    'senduser': _handle_senduser,
}


def _handle_ack_setuserinfo(request):
    """The terminal confirming it accepted a `setuserinfo` push - marks
    that specific enrollment synced. A reported failure has no `enrollid`
    in the vendor's own documented reply shape, so there is nothing to mark;
    it just stays PENDING_ADD and gets retried on a future heartbeat."""
    if not request.data.get('result'):
        return Response({'result': True})
    sn = request.data.get('sn')
    device = _device_or_none(sn)
    try:
        number = int(request.data.get('enrollid'))
    except (TypeError, ValueError):
        return Response({'result': True})
    if device:
        FaceGateEnrollment.objects.filter(device=device, device_employee_number=number).update(
            status=FaceGateEnrollment.STATUS_SYNCED, error_message='',
        )
    return Response({'result': True})


def _handle_ack_opendoor(request):
    # pending_opendoor was already cleared the moment it was served (see
    # _handle_checklive) - nothing left to do but acknowledge.
    return Response({'result': True})


_ACK_HANDLERS = {
    'setuserinfo': _handle_ack_setuserinfo,
    'opendoor': _handle_ack_opendoor,
    # reboot has no ack at all per the spec ("will reboot immediately, so
    # no response message") - nothing to register here.
}


# ── Admin-facing endpoints (normal SchoolDom auth) ──────────────────────────

def _forbidden(message):
    return Response({'success': False, 'message': message}, status=status.HTTP_403_FORBIDDEN)


def _bad_request(message):
    return Response({'success': False, 'message': message}, status=status.HTTP_400_BAD_REQUEST)


def _device_payload(device):
    by_status = {}
    for row in device.enrollments.values('status').annotate(total=_count_star()):
        by_status[row['status']] = row['total']
    return {
        'id': str(device.id),
        'device_id': device.device_id,
        'label': device.label,
        'device_type': device.device_type,
        'firmware_version': device.firmware_version,
        'is_active': device.is_active,
        'last_seen_at': device.last_seen_at,
        'enrolled_count': sum(by_status.values()),
        'enrolled_by_status': by_status,
        'fingerprint_enrolled_count': device.enrollments.filter(fingerprint_enrolled_at__isnull=False).count(),
    }


def _count_star():
    from django.db.models import Count
    return Count('id')


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def admin_list_devices(request):
    user = request.user
    if not _can_manage_school_settings(user):
        return _forbidden('Only school administrators can manage face gate devices.')
    school = _resolve_school_tenant_for_user(user)
    if not school:
        return _bad_request('Your account is not linked to a school.')

    devices = FaceGateDevice.objects.filter(tenant=school).order_by('label', 'device_id')
    return Response({'success': True, 'devices': [_device_payload(d) for d in devices]})


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def admin_register_device(request):
    user = request.user
    if not _can_manage_school_settings(user):
        return _forbidden('Only school administrators can register face gate devices.')
    school = _resolve_school_tenant_for_user(user)
    if not school:
        return _bad_request('Your account is not linked to a school.')

    device_id = str(request.data.get('device_id') or '').strip()
    label = str(request.data.get('label') or '').strip()
    if not device_id:
        return _bad_request('device_id is required - it is printed on the terminal itself.')

    if FaceGateDevice.objects.filter(device_id=device_id).exclude(tenant=school).exists():
        return _bad_request('That device id is already registered to a different school.')

    device, created = FaceGateDevice.objects.get_or_create(
        tenant=school, device_id=device_id, defaults={'label': label},
    )
    if not created and label:
        FaceGateDevice.objects.filter(pk=device.pk).update(label=label)
        device.label = label
    return Response({'success': True, 'device': _device_payload(device)}, status=status.HTTP_201_CREATED)


def _device_for_admin(request, device_pk):
    user = request.user
    if not _can_manage_school_settings(user):
        return None, _forbidden('Only school administrators can manage face gate devices.')
    school = _resolve_school_tenant_for_user(user)
    if not school:
        return None, _bad_request('Your account is not linked to a school.')
    device = FaceGateDevice.objects.filter(pk=device_pk, tenant=school).first()
    if not device:
        return None, Response({'success': False, 'message': 'Device not found.'}, status=status.HTTP_404_NOT_FOUND)
    return device, None


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def admin_bulk_enroll(request, device_pk):
    device, error = _device_for_admin(request, device_pk)
    if error:
        return error

    student_ids = request.data.get('student_ids') or []
    students = StudentProfile.objects.filter(
        id__in=student_ids, user__tenant=device.tenant,
    ).select_related('user')

    enrolled, failed = 0, []
    with transaction.atomic():
        for student in students:
            try:
                enroll_user_on_device(device, student.user)
                enrolled += 1
            except Exception as exc:  # noqa: BLE001 - one bad row must not sink the whole batch
                failed.append({'student_id': str(student.id), 'message': str(exc)})

    return Response({'success': True, 'enrolled': enrolled, 'failed': failed})


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def admin_bulk_unenroll(request, device_pk):
    device, error = _device_for_admin(request, device_pk)
    if error:
        return error

    student_ids = request.data.get('student_ids') or []
    students = StudentProfile.objects.filter(
        id__in=student_ids, user__tenant=device.tenant,
    ).select_related('user')
    for student in students:
        unenroll_user_from_device(device, student.user)

    return Response({'success': True})


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def admin_queue_opendoor(request, device_pk):
    device, error = _device_for_admin(request, device_pk)
    if error:
        return error
    FaceGateDevice.objects.filter(pk=device.pk).update(pending_opendoor=True)
    return Response({'success': True, 'message': 'Door-open command queued - the terminal picks it up on its next poll.'})


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def admin_queue_restart(request, device_pk):
    device, error = _device_for_admin(request, device_pk)
    if error:
        return error
    FaceGateDevice.objects.filter(pk=device.pk).update(pending_restart=True)
    return Response({'success': True, 'message': 'Restart command queued - the terminal picks it up on its next poll.'})
