"""
Superadmin-facing device fleet management (Part B of the scanner spec) plus
the two endpoints a scanner device itself calls directly (provision,
heartbeat) - those use AllowAny + validate their own credential (a
provisioning key, then a device auth token) rather than a normal user JWT,
the same pattern scan_qr_code already uses for the QR gate-scan GET.

Card assignment and attendance recording are NOT duplicated here - a
provisioned device authenticates as a normal SchoolDom user (whoever signs
the device into its school) and calls rfid_attendance's existing
/api/rfid/card-assignments/ and /api/rfid/attendance/scan/, exactly like the
RFID Win7 desktop app does.
"""
import secrets

from django.db.models import Q
from django.utils import timezone
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework_simplejwt.tokens import RefreshToken

from core.models import SchoolTenant
from users.models import User

from .models import Device, DeviceAuditLog, ProvisioningKey
from .serializers import DeviceAuditLogSerializer, DeviceSerializer, ProvisioningKeySerializer

SUPERADMIN_ROLE = 'super_admin'


def _require_superadmin(user):
    if user.role != SUPERADMIN_ROLE and not user.is_superuser:
        return Response(
            {'success': False, 'message': 'Only SchoolDom super administrators can manage devices.'},
            status=status.HTTP_403_FORBIDDEN,
        )
    return None


def _log(device, actor, action, details='', result='success'):
    DeviceAuditLog.objects.create(device=device, actor=actor, action=action, details=details, result=result)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def schools_list(request):
    """Feeds the Control Panel's "Select School" pickers (device assignment,
    Assign Card wizard) - schema_name is what rfid_attendance's school_code
    param expects, not the UUID pk."""
    forbidden = _require_superadmin(request.user)
    if forbidden:
        return forbidden

    schools = SchoolTenant.objects.filter(is_active=True).order_by('name')
    return Response({
        'success': True,
        'data': [{'id': str(s.id), 'schema_name': s.schema_name, 'name': s.name} for s in schools],
    })


# ==================== Superadmin: devices ====================

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def devices_list(request):
    forbidden = _require_superadmin(request.user)
    if forbidden:
        return forbidden

    devices = list(Device.objects.select_related('tenant').all())

    filter_key = str(request.query_params.get('filter') or 'all').strip()
    if filter_key == 'online':
        devices = [d for d in devices if d.is_online]
    elif filter_key == 'offline':
        devices = [d for d in devices if not d.is_online]
    elif filter_key == 'low_battery':
        devices = [d for d in devices if d.is_low_battery]
    elif filter_key == 'charging':
        devices = [d for d in devices if d.battery_charging]
    elif filter_key == 'unassigned':
        devices = [d for d in devices if not d.tenant_id]
    elif filter_key == 'suspended':
        devices = [d for d in devices if d.status == 'suspended']
    elif filter_key == 'needs_attention':
        devices = [d for d in devices if d.needs_attention()]

    all_devices = Device.objects.all()
    stats = {
        'total': all_devices.count(),
        'online': sum(1 for d in all_devices if d.is_online),
        'offline': sum(1 for d in all_devices if not d.is_online),
        'low_battery': sum(1 for d in all_devices if d.is_low_battery),
        'charging': all_devices.filter(battery_charging=True).count(),
        'needs_attention': sum(1 for d in all_devices if d.needs_attention()),
        'total_schools': SchoolTenant.objects.filter(is_active=True).count(),
    }

    return Response({
        'success': True,
        'stats': stats,
        'data': DeviceSerializer(devices, many=True).data,
    })


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def device_detail(request, device_pk):
    forbidden = _require_superadmin(request.user)
    if forbidden:
        return forbidden

    device = Device.objects.select_related('tenant').filter(pk=device_pk).first()
    if not device:
        return Response({'success': False, 'message': 'Device not found.'}, status=status.HTTP_404_NOT_FOUND)
    return Response({'success': True, 'data': DeviceSerializer(device).data})


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def generate_provisioning_key(request):
    forbidden = _require_superadmin(request.user)
    if forbidden:
        return forbidden

    key = ProvisioningKey.objects.create(
        created_by=request.user,
        single_use=request.data.get('single_use', True),
        notes=str(request.data.get('notes') or '').strip(),
    )
    _log(None, request.user, 'provisioning_key_generated', details=key.key)
    return Response({'success': True, 'data': ProvisioningKeySerializer(key).data}, status=status.HTTP_201_CREATED)


def _device_action(request, device_pk, allowed_from=None):
    """Shared boilerplate for the simple state-transition endpoints below.
    Returns (device, None) on success or (None, error_response)."""
    forbidden = _require_superadmin(request.user)
    if forbidden:
        return None, forbidden

    device = Device.objects.filter(pk=device_pk).first()
    if not device:
        return None, Response({'success': False, 'message': 'Device not found.'}, status=status.HTTP_404_NOT_FOUND)

    if allowed_from and device.status not in allowed_from:
        return None, Response(
            {'success': False, 'message': f'Device is {device.status}, expected one of {", ".join(allowed_from)}.'},
            status=status.HTTP_400_BAD_REQUEST,
        )
    return device, None


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def assign_school(request, device_pk):
    device, error = _device_action(request, device_pk)
    if error:
        return error

    school_id = request.data.get('school_id')
    school = SchoolTenant.objects.filter(pk=school_id, is_active=True).first()
    if not school:
        return Response({'success': False, 'message': 'School not found.'}, status=status.HTTP_404_NOT_FOUND)

    was_reassignment = device.tenant_id is not None and device.tenant_id != school.id
    old_school_name = device.tenant.name if was_reassignment else None

    device.tenant = school
    if device.status in ('unregistered', 'provisioning'):
        device.status = 'active'
    device.save(update_fields=['tenant', 'status', 'updated_at'])

    if device.scanner_user_id:
        # Scans this device posts (via its own JWT, not this admin's) resolve
        # to a school through _resolve_school_tenant_for_user's plain
        # user.tenant check - keep it in lockstep with the device's own
        # assignment, especially on reassignment where the old school's
        # students must stop being reachable through this device at all.
        device.scanner_user.tenant = school
        device.scanner_user.save(update_fields=['tenant'])

    action = 'device_reassigned' if was_reassignment else 'device_assigned'
    details = f'{old_school_name} -> {school.name}' if was_reassignment else school.name
    _log(device, request.user, action, details=details)

    return Response({'success': True, 'data': DeviceSerializer(device).data})


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def unassign_school(request, device_pk):
    device, error = _device_action(request, device_pk)
    if error:
        return error

    old_school_name = device.tenant.name if device.tenant else None
    device.tenant = None
    device.status = 'unregistered' if not device.authorized else device.status
    device.save(update_fields=['tenant', 'status', 'updated_at'])
    _log(device, request.user, 'device_unassigned', details=old_school_name or '')
    return Response({'success': True, 'data': DeviceSerializer(device).data})


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def _set_scanner_user_active(device, is_active):
    if device.scanner_user_id:
        device.scanner_user.is_active = is_active
        device.scanner_user.save(update_fields=['is_active'])


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def suspend_device(request, device_pk):
    device, error = _device_action(request, device_pk)
    if error:
        return error
    device.status = 'suspended'
    device.save(update_fields=['status', 'updated_at'])
    # is_active=False makes SimpleJWT reject this user's access AND refresh
    # tokens on the next request - the device can't silently keep scanning
    # just because its current access token hasn't expired yet.
    _set_scanner_user_active(device, False)
    _log(device, request.user, 'device_suspended')
    return Response({'success': True, 'data': DeviceSerializer(device).data})


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def reactivate_device(request, device_pk):
    device, error = _device_action(request, device_pk, allowed_from=['suspended', 'maintenance'])
    if error:
        return error
    device.status = 'active' if device.tenant_id else 'unregistered'
    device.save(update_fields=['status', 'updated_at'])
    _set_scanner_user_active(device, True)
    _log(device, request.user, 'device_reactivated')
    return Response({'success': True, 'data': DeviceSerializer(device).data})


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def revoke_device(request, device_pk):
    device, error = _device_action(request, device_pk)
    if error:
        return error
    device.authorized = False
    device.auth_token = ''
    device.status = 'revoked'
    device.revoked_at = timezone.now()
    device.revoked_by = request.user
    device.save(update_fields=['authorized', 'auth_token', 'status', 'revoked_at', 'revoked_by', 'updated_at'])
    # Permanent, unlike suspend - re-authorizing a revoked device means
    # provisioning it again from scratch (spec: "Require authorized
    # reactivation before normal operation resumes"), not a simple toggle.
    _set_scanner_user_active(device, False)
    _log(device, request.user, 'session_revoked')
    return Response({'success': True, 'data': DeviceSerializer(device).data})


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def audit_logs_list(request):
    forbidden = _require_superadmin(request.user)
    if forbidden:
        return forbidden

    logs = DeviceAuditLog.objects.select_related('device', 'actor').all()
    device_pk = request.query_params.get('device_id')
    if device_pk:
        logs = logs.filter(device_id=device_pk)
    logs = logs[:200]
    return Response({'success': True, 'data': DeviceAuditLogSerializer(logs, many=True).data})


# ==================== Device-facing: provisioning + heartbeat ====================
# AllowAny - these authenticate via their OWN credential (provisioning key,
# then device auth token), not a user JWT. A device has no SchoolDom user
# account of its own.

@api_view(['POST'])
@permission_classes([AllowAny])
def device_provision(request):
    key_value = str(request.data.get('provisioning_key') or '').strip().upper()
    if not key_value:
        return Response({'success': False, 'message': 'provisioning_key is required.'}, status=status.HTTP_400_BAD_REQUEST)

    key = ProvisioningKey.objects.filter(key=key_value).first()
    if not key or not key.is_valid:
        return Response({'success': False, 'message': 'This provisioning key is invalid, used, or expired.'}, status=status.HTTP_401_UNAUTHORIZED)

    device = Device.objects.create(
        name=str(request.data.get('device_name') or '').strip(),
        license_key=key.key,
        device_model=str(request.data.get('device_model') or '').strip(),
        os_version=str(request.data.get('os_version') or '').strip(),
        app_version=str(request.data.get('app_version') or '').strip(),
        status='provisioning',
        authorized=True,
        auth_token=secrets.token_hex(32),
        authorized_at=timezone.now(),
        first_activated_at=timezone.now(),
    )

    # "Permanent login" (spec section 9) - a real staff-role User the device
    # authenticates as via a normal JWT refresh token, not a bespoke session
    # system. Unusable password: this account can never be logged into by
    # email/password, only by the refresh token handed back below.
    device.scanner_user = User.objects.create_user(
        email=f'device-{device.device_id.lower()}@scanner.schooldom.internal',
        password=None,
        first_name='SchoolDom Scanner',
        last_name=device.device_id,
        role='staff',
        is_active=True,
    )
    device.save(update_fields=['scanner_user'])

    if key.single_use:
        key.status = 'used'
    key.used_at = timezone.now()
    key.used_by_device = device
    key.save(update_fields=['status', 'used_at', 'used_by_device'])

    _log(device, None, 'device_registered', details=f'via key {key.key}')

    refresh = RefreshToken.for_user(device.scanner_user)

    return Response({
        'success': True,
        'message': 'Device registered. Waiting for a superadmin to assign a school.',
        'data': {
            'device_pk': str(device.pk),
            'device_id': device.device_id,
            'auth_token': device.auth_token,
            'status': device.status,
            # Store this permanently and use it like any other SchoolDom
            # client's session (POST /api/token/refresh/ to get a fresh
            # access token whenever needed) - there is no separate login step.
            'refresh_token': str(refresh),
            'access_token': str(refresh.access_token),
        },
    }, status=status.HTTP_201_CREATED)


def _device_from_token(request):
    token = str(request.data.get('auth_token') or request.headers.get('X-Device-Token') or '').strip()
    if not token:
        return None
    return Device.objects.select_related('tenant').filter(auth_token=token).first()


@api_view(['POST'])
@permission_classes([AllowAny])
def device_heartbeat(request):
    device = _device_from_token(request)
    if not device:
        return Response({'success': False, 'message': 'Unknown or revoked device token.'}, status=status.HTTP_401_UNAUTHORIZED)

    data = request.data
    update_fields = ['last_seen_at', 'updated_at']
    device.last_seen_at = timezone.now()

    if 'app_version' in data:
        device.app_version = str(data.get('app_version') or '')[:20]
        update_fields.append('app_version')
    if 'battery_percentage' in data and data.get('battery_percentage') is not None:
        try:
            device.battery_percentage = max(0, min(100, int(data.get('battery_percentage'))))
            update_fields.append('battery_percentage')
        except (TypeError, ValueError):
            pass
    if 'battery_charging' in data:
        device.battery_charging = bool(data.get('battery_charging'))
        update_fields.append('battery_charging')
    if 'battery_health' in data:
        health = str(data.get('battery_health') or '').lower()
        if health in dict(Device.BATTERY_HEALTH_CHOICES):
            device.battery_health = health
            update_fields.append('battery_health')
    if 'battery_temperature_c' in data and data.get('battery_temperature_c') is not None:
        try:
            device.battery_temperature_c = float(data.get('battery_temperature_c'))
            update_fields.append('battery_temperature_c')
        except (TypeError, ValueError):
            pass
    if data.get('synced'):
        device.last_sync_at = timezone.now()
        update_fields.append('last_sync_at')

    device.save(update_fields=update_fields)

    return Response({
        'success': True,
        'authorized': device.authorized and device.status not in ('suspended', 'revoked'),
        'status': device.status,
        'school_id': str(device.tenant_id) if device.tenant_id else None,
        'school_name': device.tenant.name if device.tenant else None,
    })
