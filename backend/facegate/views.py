"""HTTP integration for the vendor's face-recognition SchoolGate terminal
(the "Cloud Attendance and Access Control (HTTP)" protocol the vendor's
PDF documents). This implements the HTTP variant only - the same vendor
also offers an MQTT variant, not built here because it would need a
standing message broker this project has no other use for (see
[[project-no-celery-in-production]] for the same "avoid an always-on
extra service" reasoning applied elsewhere in this codebase).

First-pass scope only (see project discussion): device registration and
heartbeat, pushing enrolled students down to the device with their photo,
pulling check-ins back up into the normal attendance/SMS pipeline, and
restart/shutdown/door-open commands. NOT built yet: access-control time
periods, attendance shift/holiday settings, system settings (volume,
screensaver, etc.), device log upload, firmware push, and staff biometric
attendance (student-only for now) - all optional per the vendor spec, and
left for a later pass once the core loop is confirmed working against
real hardware.

Trust model / known limitation: every view below is reached directly by
the device, not a signed-in SchoolDom user, so none of these use the
normal JWT authentication. The ONLY credential the vendor's own HTTP
examples ever send is the device's own `deviceId` in the request body -
there is no signature/token field anywhere in this protocol's HTTP
variant (a `sign` header appears only in the vendor's separate MQTT
variant's docs, and never in a single HTTP request example). That means
anyone who learns or guesses a real deviceId could pose as that device.
Two mitigations:
  1. Every endpoint below 404s-as-a-no-op unless that exact deviceId was
     already registered by a school admin first (see admin_register_device) -
     a guessed id can only ever replay "nothing to do", never attach
     itself to a school it wasn't registered against.
  2. In production, put the device_api/ paths below behind
     middleware.ip_whitelist.IPWhitelistMiddleware, restricted to each
     school's own gate terminal's public IP/VPN - the terminal is the
     only thing that should ever call them, and that middleware already
     exists in this codebase for exactly this kind of weak-auth device
     endpoint.
If real hardware testing turns up an actual sign header after all, add
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
from .services import enroll_user_on_device, parse_device_note_time, person_payload, record_checkin, unenroll_user_from_device

PASS_INFO_BATCH_SIZE = 40  # vendor spec 4.1/4.3 - up to 40 people per poll when photos are URLs


def _device_or_none(device_id):
    device_id = str(device_id or '').strip()
    if not device_id:
        return None
    return FaceGateDevice.objects.select_related('tenant').filter(device_id=device_id, is_active=True).first()


# ── Device-facing endpoints (no SchoolDom auth - see module docstring) ──────

@api_view(['POST'])
@permission_classes([AllowAny])
def device_update_state(request):
    device = _device_or_none(request.data.get('deviceId'))
    if not device:
        # Nothing useful to tell an unregistered/unknown device - a flat
        # "success" with no further action is the quietest way to let it
        # keep polling harmlessly until an admin registers it, rather than
        # a 404 the vendor's retry logic has no backoff for.
        return Response({'success': 0, 'msg': 'Success'})

    info = request.data.get('data') or {}
    FaceGateDevice.objects.filter(pk=device.pk).update(
        last_seen_at=timezone.now(),
        device_type=str(info.get('deviceType') or device.device_type)[:31],
        firmware_version=str(info.get('parameterVersion') or device.firmware_version)[:63],
        mac_address=str(info.get('parameterMAC') or device.mac_address)[:31],
    )
    return Response({'success': 0, 'msg': 'Success'})


@api_view(['POST'])
@permission_classes([AllowAny])
def device_select_pass_info(request):
    device = _device_or_none(request.data.get('deviceId'))
    if not device:
        return Response({'success': 0, 'msg': 'Success', 'passinfo': []})

    try:
        cursor = int(request.data.get('last_employee_number') or 0)
    except (TypeError, ValueError):
        cursor = 0

    pending = (
        FaceGateEnrollment.objects.filter(
            device=device,
            status=FaceGateEnrollment.STATUS_PENDING_ADD,
            device_employee_number__gt=cursor,
        )
        .select_related('user', 'user__student_profile')
        .order_by('device_employee_number')[:PASS_INFO_BATCH_SIZE]
    )
    FaceGateDevice.objects.filter(pk=device.pk).update(last_seen_at=timezone.now())
    return Response({
        'success': 0,
        'msg': 'Success',
        'passinfo': [person_payload(request, enrollment) for enrollment in pending],
    })


@api_view(['POST'])
@permission_classes([AllowAny])
def device_set_pass_result(request):
    device = _device_or_none(request.data.get('deviceId'))
    if not device:
        return Response({'success': 0, 'msg': 'Success'})

    for failed in request.data.get('failEmployeeId') or []:
        try:
            number = int(failed.get('employeeId'))
        except (TypeError, ValueError):
            continue
        FaceGateEnrollment.objects.filter(device=device, device_employee_number=number).update(
            status=FaceGateEnrollment.STATUS_FAILED,
            error_message=str(failed.get('errorCode') or ''),
        )

    for succeeded in request.data.get('successEmployeeId') or []:
        try:
            number = int(succeeded.get('employeeId'))
        except (TypeError, ValueError):
            continue
        FaceGateEnrollment.objects.filter(device=device, device_employee_number=number).update(
            status=FaceGateEnrollment.STATUS_SYNCED, error_message='',
        )

    return Response({'success': 0, 'msg': 'Success'})


@api_view(['POST'])
@permission_classes([AllowAny])
def device_select_delete_info(request):
    device = _device_or_none(request.data.get('deviceId'))
    if not device:
        return Response({'success': 0, 'msg': 'Success', 'empty': 0, 'deleteInfo': []})

    # unenroll_user_from_device deletes the row immediately (the protocol
    # has no delete-result feedback to wait for), so by the time a device
    # polls here there is nothing left queued to hand back - this endpoint
    # exists to satisfy a device that calls it anyway, not because this
    # app currently queues deletes separately from deleting them.
    FaceGateDevice.objects.filter(pk=device.pk).update(last_seen_at=timezone.now())
    return Response({'success': 0, 'msg': 'Success', 'empty': 0, 'deleteInfo': []})


@api_view(['POST'])
@permission_classes([AllowAny])
def note_insert_note_face(request):
    device = _device_or_none(request.data.get('deviceId'))
    data = request.data.get('data') or {}
    if not device:
        return Response({'success': 0, 'msg': 'Success'})

    FaceGateDevice.objects.filter(pk=device.pk).update(last_seen_at=timezone.now())

    try:
        number = int(data.get('employeeNumberId'))
    except (TypeError, ValueError):
        return Response({'success': 0, 'msg': 'Success'})

    enrollment = FaceGateEnrollment.objects.select_related('user', 'user__student_profile').filter(
        device=device, device_employee_number=number,
    ).first()
    note_time = data.get('noteTime')
    if not enrollment or not note_time:
        return Response({'success': 0, 'msg': 'Success'})

    occurred_at = parse_device_note_time(device.tenant, note_time)
    record_checkin(device, enrollment, occurred_at)
    return Response({'success': 0, 'msg': 'Success'})


@api_view(['POST'])
@permission_classes([AllowAny])
def device_select_restart(request):
    device = _device_or_none(request.data.get('deviceId'))
    if not device:
        return Response({'restart': 0, 'shutdown': 0, 'opendoor': 0})

    payload = {
        'restart': 1 if device.pending_restart else 0,
        'shutdown': 1 if device.pending_shutdown else 0,
        'opendoor': 1 if device.pending_opendoor else 0,
    }
    updates = {'last_seen_at': timezone.now()}
    if device.pending_restart or device.pending_shutdown or device.pending_opendoor:
        updates.update(pending_restart=False, pending_shutdown=False, pending_opendoor=False)
    FaceGateDevice.objects.filter(pk=device.pk).update(**updates)
    return Response(payload)


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
