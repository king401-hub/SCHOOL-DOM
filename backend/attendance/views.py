import io
import uuid

import qrcode
from django.db import IntegrityError, transaction
from django.db.models import Q
from django.http import FileResponse
from django.utils import timezone
from rest_framework import status
from rest_framework.decorators import api_view, authentication_classes, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from users.models import User
from .models import AttendanceQRCode, TeacherAttendance
from .serializers import (
    AttendanceListSerializer,
    QRCodeDetailSerializer,
    TeacherAttendanceSerializer,
)
from .utils import build_teacher_scan_url


ADMIN_ROLES = {'school_admin', 'principal', 'super_admin'}
ATTENDANCE_USER_ROLES = ADMIN_ROLES | {'teacher', 'staff'}


def is_attendance_admin(user):
    return bool(user and user.is_authenticated and user.role in ADMIN_ROLES)


def can_mark_attendance(user):
    if not (user and user.is_authenticated):
        return False
    if user.role in ATTENDANCE_USER_ROLES:
        return True
    try:
        from hr.models import StaffProfile

        return StaffProfile.objects.filter(
            Q(user=user) | Q(email__iexact=user.email),
            tenant=user.tenant,
            employment_status__in=[StaffProfile.ACTIVE, StaffProfile.ON_LEAVE],
        ).exists()
    except Exception:
        return False


def attendance_role_label(user):
    if user.role == 'teacher':
        return 'teacher'
    if user.role == 'staff':
        return 'staff'
    try:
        from hr.models import StaffProfile

        staff = StaffProfile.objects.filter(
            Q(user=user) | Q(email__iexact=user.email),
            tenant=user.tenant,
        ).first()
        if staff:
            return staff.role or staff.get_staff_type_display()
    except Exception:
        pass
    return 'admin'


def request_actor(request):
    """Resolve the app user without relying on JWT authentication headers."""
    user = getattr(request, 'user', None)
    if user and user.is_authenticated:
        return user

    lookup = (
        request.data.get('user_id')
        or request.data.get('actor_id')
        or request.query_params.get('user_id')
        or request.query_params.get('actor_id')
        or request.data.get('email')
        or request.query_params.get('email')
    )
    if not lookup:
        return None

    lookup = str(lookup).strip()
    filters = Q(email__iexact=lookup)
    try:
        filters |= Q(id=uuid.UUID(lookup))
    except (TypeError, ValueError):
        pass

    return User.objects.filter(filters, is_active=True).select_related('tenant').first()


def actor_required_response():
    return Response(
        {'success': False, 'message': 'User account is required for attendance.'},
        status=status.HTTP_400_BAD_REQUEST,
    )


# ==================== QR Code Management (Admin Only) ====================

@api_view(['POST'])
@authentication_classes([])
@permission_classes([AllowAny])
def generate_qr_code(request):
    """
    Generate or regenerate QR code for tenant.
    Admin only endpoint.
    """
    user = request_actor(request)
    if not user:
        return actor_required_response()
    if not is_attendance_admin(user):
        return Response(
            {'success': False, 'message': 'Admin access required.'},
            status=status.HTTP_403_FORBIDDEN
        )
    
    tenant = user.tenant
    if not tenant:
        return Response(
            {'success': False, 'message': 'No tenant associated with user.'},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    try:
        qr_code, created = AttendanceQRCode.get_or_create_for_tenant(tenant)
        
        qr_code.created_by = user
        qr_code.notes = request.data.get('notes', '')
        qr_code.save()
        
        serializer = QRCodeDetailSerializer(qr_code, context={'request': request})
        return Response({
            'success': True,
            'message': 'Static QR code is ready.',
            'data': serializer.data
        }, status=status.HTTP_201_CREATED if created else status.HTTP_200_OK)
    
    except Exception as e:
        return Response(
            {'success': False, 'message': f'Error generating QR code: {str(e)}'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['GET'])
@authentication_classes([])
@permission_classes([AllowAny])
def get_qr_code(request):
    """
    Get QR code details for the tenant.
    Admin endpoint.
    """
    user = request_actor(request)
    if not user:
        return actor_required_response()
    if not is_attendance_admin(user):
        return Response(
            {'success': False, 'message': 'Admin access required.'},
            status=status.HTTP_403_FORBIDDEN
        )
    
    try:
        qr_code, _created = AttendanceQRCode.get_or_create_for_tenant(user.tenant)
        serializer = QRCodeDetailSerializer(qr_code, context={'request': request})
        return Response({
            'success': True,
            'data': serializer.data
        })
    except AttendanceQRCode.DoesNotExist:
        return Response(
            {'success': False, 'message': 'QR code not found.'},
            status=status.HTTP_404_NOT_FOUND
        )


@api_view(['GET'])
@authentication_classes([])
@permission_classes([AllowAny])
def download_qr_code(request):
    """
    Download QR code as PNG image.
    Admin endpoint.
    """
    user = request_actor(request)
    if not user:
        return actor_required_response()
    if not is_attendance_admin(user):
        return Response(
            {'success': False, 'message': 'Admin access required.'},
            status=status.HTTP_403_FORBIDDEN
        )
    
    try:
        qr_code_obj, _created = AttendanceQRCode.get_or_create_for_tenant(user.tenant)
        
        qr_url = build_teacher_scan_url(request, qr_code_obj)
        
        # Generate QR code image
        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_L,
            box_size=10,
            border=4,
        )
        qr.add_data(qr_url)
        qr.make(fit=True)
        
        img = qr.make_image(fill_color="black", back_color="white")
        
        # Save to bytes
        img_io = io.BytesIO()
        img.save(img_io, 'PNG')
        img_io.seek(0)
        
        response = FileResponse(img_io, content_type='image/png')
        response['Content-Disposition'] = 'attachment; filename="staff_attendance_qr.png"'
        return response
    
    except AttendanceQRCode.DoesNotExist:
        return Response(
            {'success': False, 'message': 'QR code not found.'},
            status=status.HTTP_404_NOT_FOUND
        )
    except Exception as e:
        return Response(
            {'success': False, 'message': f'Error downloading QR code: {str(e)}'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


# ==================== Staff Attendance Marking ====================

@api_view(['GET', 'POST'])
@authentication_classes([])
@permission_classes([AllowAny])
def scan_qr_code(request, token):
    """
    Scan QR code endpoint.
    GET: Verify token and return attendance page
    POST: Mark attendance for authenticated teachers and admins
    """
    # Verify QR token
    qr_code = AttendanceQRCode.verify_token(token)
    if not qr_code:
        return Response(
            {'success': False, 'message': 'Invalid or expired QR code.'},
            status=status.HTTP_401_UNAUTHORIZED
        )
    
    if request.method == 'GET':
        return Response({
            'success': True,
            'message': 'QR code verified. Please sign in to continue.',
            'tenant_id': str(qr_code.tenant.id),
            'tenant_name': qr_code.tenant.name,
        })
    
    # POST: Mark attendance
    user = request_actor(request)
    if not user:
        return actor_required_response()
    
    # Verify user can use staff attendance.
    if not can_mark_attendance(user):
        return Response(
            {'success': False, 'message': 'Only staff, teachers, and admins can mark attendance.'},
            status=status.HTTP_403_FORBIDDEN
        )
    
    # Verify user belongs to same tenant
    if user.tenant != qr_code.tenant:
        return Response(
            {'success': False, 'message': 'Unauthorized access.'},
            status=status.HTTP_403_FORBIDDEN
        )
    
    today = timezone.localdate()

    try:
        with transaction.atomic():
            attendance, created = TeacherAttendance.objects.get_or_create(
                teacher=user,
                attendance_date=today,
                defaults={
                    'tenant': qr_code.tenant,
                    'qr_code': qr_code,
                    'status': 'present',
                    'ip_address': get_client_ip(request),
                    'device_info': request.META.get('HTTP_USER_AGENT', '')[:255],
                },
            )

        if not created:
            serializer = TeacherAttendanceSerializer(attendance)
            return Response(
                {
                    'success': True,
                    'message': 'You have already clocked in today.',
                    'checked_in': True,
                    'checked_out': bool(attendance.check_out_time),
                    'data': serializer.data,
                },
                status=status.HTTP_200_OK,
            )
        
        serializer = TeacherAttendanceSerializer(attendance)
        return Response({
            'success': True,
            'message': f'{attendance_role_label(user).title()} clock-in recorded at {timezone.localtime(attendance.check_in_time).strftime("%H:%M:%S")}',
            'checked_in': True,
            'checked_out': False,
            'data': serializer.data
        }, status=status.HTTP_201_CREATED)
    except IntegrityError:
        attendance = TeacherAttendance.objects.filter(
            teacher=user,
            attendance_date=today,
        ).first()
        return Response(
            {
                'success': True,
                'message': 'You have already clocked in today.',
                'checked_in': True,
                'checked_out': bool(attendance.check_out_time) if attendance else False,
                'data': TeacherAttendanceSerializer(attendance).data if attendance else None,
            },
            status=status.HTTP_200_OK,
        )
    
    except Exception as e:
        return Response(
            {'success': False, 'message': f'Error marking attendance: {str(e)}'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['GET'])
@authentication_classes([])
@permission_classes([AllowAny])
def check_attendance_status(request):
    """
    Check if a teacher or admin has already marked attendance today.
    """
    user = request_actor(request)
    if not user:
        return actor_required_response()
    
    if not can_mark_attendance(user):
        return Response(
            {'success': False, 'message': 'Only staff, teachers, and admins can check attendance status.'},
            status=status.HTTP_403_FORBIDDEN
        )
    
    today = timezone.localdate()
    has_checked_in = TeacherAttendance.has_checked_in_today(user, today)
    
    if has_checked_in:
        attendance = TeacherAttendance.objects.get(
            teacher=user,
            attendance_date=today
        )
        serializer = TeacherAttendanceSerializer(attendance)
        return Response({
            'success': True,
            'checked_in': True,
            'checked_out': bool(attendance.check_out_time),
            'message': 'You have already clocked in today.',
            'data': serializer.data
        })
    
    return Response({
        'success': True,
        'checked_in': False,
        'checked_out': False,
        'message': 'You have not clocked in yet today.'
    })


@api_view(['POST'])
@authentication_classes([])
@permission_classes([AllowAny])
def clock_out(request):
    """Record today's check-out time for teachers and admins."""
    user = request_actor(request)
    if not user:
        return actor_required_response()
    if not can_mark_attendance(user):
        return Response(
            {'success': False, 'message': 'Only staff, teachers, and admins can clock out.'},
            status=status.HTTP_403_FORBIDDEN
        )

    today = timezone.localdate()
    attendance = TeacherAttendance.objects.filter(
        teacher=user,
        attendance_date=today,
    ).first()

    if not attendance:
        return Response(
            {'success': False, 'message': 'Clock in before clocking out.'},
            status=status.HTTP_400_BAD_REQUEST
        )

    if attendance.check_out_time:
        serializer = TeacherAttendanceSerializer(attendance)
        return Response({
            'success': True,
            'checked_in': True,
            'checked_out': True,
            'message': 'You have already clocked out today.',
            'data': serializer.data,
        })

    attendance.check_out_time = timezone.now()
    attendance.save(update_fields=['check_out_time'])
    serializer = TeacherAttendanceSerializer(attendance)
    return Response({
        'success': True,
        'checked_in': True,
        'checked_out': True,
        'message': f'Clock-out recorded at {timezone.localtime(attendance.check_out_time).strftime("%H:%M:%S")}',
        'data': serializer.data,
    })


# ==================== Admin Dashboard - Attendance Viewing ====================

@api_view(['GET'])
@authentication_classes([])
@permission_classes([AllowAny])
def today_attendance_list(request):
    """
    Get all teachers who marked attendance today.
    Admin endpoint.
    """
    user = request_actor(request)
    if not user:
        return actor_required_response()
    if not is_attendance_admin(user):
        return Response(
            {'success': False, 'message': 'Admin access required.'},
            status=status.HTTP_403_FORBIDDEN
        )
    
    try:
        today = timezone.localdate()
        attendance_records = TeacherAttendance.get_today_attendance(user.tenant, today)
        
        serializer = AttendanceListSerializer(attendance_records, many=True)
        return Response({
            'success': True,
            'date': today.isoformat(),
            'total_present': attendance_records.count(),
            'data': serializer.data
        })
    
    except Exception as e:
        return Response(
            {'success': False, 'message': f'Error retrieving attendance: {str(e)}'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['GET'])
@authentication_classes([])
@permission_classes([AllowAny])
def attendance_by_date(request, date_str):
    """
    Get attendance records for a specific date.
    Admin endpoint.
    Format: YYYY-MM-DD
    """
    user = request_actor(request)
    if not user:
        return actor_required_response()
    if not is_attendance_admin(user):
        return Response(
            {'success': False, 'message': 'Admin access required.'},
            status=status.HTTP_403_FORBIDDEN
        )
    
    try:
        from datetime import datetime
        attendance_date = datetime.strptime(date_str, '%Y-%m-%d').date()
        
        attendance_records = TeacherAttendance.objects.filter(
            tenant=user.tenant,
            attendance_date=attendance_date
        ).select_related('teacher').order_by('-check_in_time')
        
        serializer = AttendanceListSerializer(attendance_records, many=True)
        return Response({
            'success': True,
            'date': attendance_date.isoformat(),
            'total_present': attendance_records.count(),
            'data': serializer.data
        })
    
    except ValueError:
        return Response(
            {'success': False, 'message': 'Invalid date format. Use YYYY-MM-DD'},
            status=status.HTTP_400_BAD_REQUEST
        )
    except Exception as e:
        return Response(
            {'success': False, 'message': f'Error retrieving attendance: {str(e)}'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['GET'])
@authentication_classes([])
@permission_classes([AllowAny])
def teacher_attendance_history(request, teacher_id):
    """
    Get attendance history for a specific teacher.
    Admin endpoint.
    """
    user = request_actor(request)
    if not user:
        return actor_required_response()
    if not is_attendance_admin(user):
        return Response(
            {'success': False, 'message': 'Admin access required.'},
            status=status.HTTP_403_FORBIDDEN
        )
    
    try:
        teacher = User.objects.get(id=teacher_id, role='teacher', tenant=user.tenant)
        
        # Get query parameters
        days = int(request.query_params.get('days', 30))
        start_date = timezone.localdate() - timezone.timedelta(days=days)
        
        attendance_records = TeacherAttendance.objects.filter(
            teacher=teacher,
            attendance_date__gte=start_date
        ).order_by('-attendance_date')
        
        serializer = TeacherAttendanceSerializer(attendance_records, many=True)
        return Response({
            'success': True,
            'teacher': {
                'id': str(teacher.id),
                'name': teacher.get_full_name(),
                'email': teacher.email
            },
            'period_days': days,
            'total_records': attendance_records.count(),
            'data': serializer.data
        })
    
    except User.DoesNotExist:
        return Response(
            {'success': False, 'message': 'Teacher not found.'},
            status=status.HTTP_404_NOT_FOUND
        )
    except Exception as e:
        return Response(
            {'success': False, 'message': f'Error retrieving attendance: {str(e)}'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['GET'])
@authentication_classes([])
@permission_classes([AllowAny])
def attendance_summary(request):
    """
    Get attendance summary for the month.
    Admin endpoint.
    """
    user = request_actor(request)
    if not user:
        return actor_required_response()
    if not is_attendance_admin(user):
        return Response(
            {'success': False, 'message': 'Admin access required.'},
            status=status.HTTP_403_FORBIDDEN
        )
    
    try:
        today = timezone.localdate()
        month_start = today.replace(day=1)
        
        # Get all teachers in tenant
        teachers = User.objects.filter(tenant=user.tenant, role='teacher').order_by('first_name', 'last_name')
        
        summary = []
        for teacher in teachers:
            attendance_count = TeacherAttendance.objects.filter(
                teacher=teacher,
                attendance_date__gte=month_start,
                attendance_date__lte=today
            ).count()
            
            summary.append({
                'teacher_id': str(teacher.id),
                'teacher_name': teacher.get_full_name(),
                'teacher_email': teacher.email,
                'attendance_days': attendance_count
            })
        
        return Response({
            'success': True,
            'month': month_start.strftime('%B %Y'),
            'total_teachers': teachers.count(),
            'data': summary
        })
    
    except Exception as e:
        return Response(
            {'success': False, 'message': f'Error generating summary: {str(e)}'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


# ==================== Utility Functions ====================

def get_client_ip(request):
    """Get client IP address from request."""
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0]
    else:
        ip = request.META.get('REMOTE_ADDR')
    return ip
