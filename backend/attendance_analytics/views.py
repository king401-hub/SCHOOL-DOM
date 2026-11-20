"""Device-free, admin-facing endpoints for the Attendance Analytics feature -
all read-only, all backed by services.py's single calculation engine. Each
view also re-checks the tenant's attendance_analytics_scope server-side
(the frontend gates this too) so a student-only or staff-only school can
never pull data for the population it doesn't have, even by hitting the API
directly."""
import datetime

from django.utils import timezone
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from users.app_views import _resolve_school_tenant_for_user

from . import services

ADMIN_ROLES = {'school_admin', 'principal', 'super_admin', 'school_superadmin'}


def _forbidden(message):
    return Response({'success': False, 'message': message}, status=status.HTTP_403_FORBIDDEN)


def _bad_request(message):
    return Response({'success': False, 'message': message}, status=status.HTTP_400_BAD_REQUEST)


def _admin_tenant_or_error(request):
    user = request.user
    if user.role not in ADMIN_ROLES:
        return None, _forbidden('Only school administrators can view attendance analytics.')
    tenant = _resolve_school_tenant_for_user(user)
    if not tenant:
        return None, _bad_request('Your account is not linked to a school.')
    return tenant, None


def _check_population_scope(tenant, population):
    if population == 'student' and not tenant.attendance_analytics_includes_students:
        return _forbidden('Student attendance analytics is not included in this school\'s plan.')
    if population == 'staff' and not tenant.attendance_analytics_includes_staff:
        return _forbidden('Staff attendance analytics is not included in this school\'s plan.')
    return None


def _parse_date(value, default):
    if not value:
        return default
    try:
        return datetime.date.fromisoformat(value)
    except ValueError:
        return default


def _parse_int(value, default, *, minimum=1):
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return default
    return max(minimum, parsed)


def _period_range(tenant, period, now=None):
    """daily/weekly/monthly/termly -> (start, end) inclusive, ending today."""
    today = services.school_today(tenant, now)
    if period == 'daily':
        return today, today
    if period == 'weekly':
        return today - datetime.timedelta(days=today.weekday()), today
    if period == 'monthly':
        return today.replace(day=1), today
    # termly / default: current active term, else fall back to the last 90 days.
    # Term is a TenantAwareModel keyed on the legacy tenants.Tenant model, not
    # core.SchoolTenant - see services.closed_dates's docstring for the same quirk.
    from academic.models import Term
    from rfid_attendance.services import _legacy_tenant_for_attendance
    term = Term.objects.filter(tenant=_legacy_tenant_for_attendance(tenant), is_active=True).first()
    if term:
        return term.start_date, min(term.end_date, today)
    return today - datetime.timedelta(days=90), today


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def overview(request):
    tenant, error = _admin_tenant_or_error(request)
    if error:
        return error
    target_date = _parse_date(request.query_params.get('date'), services.school_today(tenant))
    data = services.overview_summary(tenant, target_date)
    return Response({'success': True, **data})


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def daily_summary(request):
    tenant, error = _admin_tenant_or_error(request)
    if error:
        return error
    population = request.query_params.get('population') or ('student' if tenant.attendance_analytics_includes_students else 'staff')
    scope_error = _check_population_scope(tenant, population)
    if scope_error:
        return scope_error
    target_date = _parse_date(request.query_params.get('date'), services.school_today(tenant))
    bucket_minutes = _parse_int(request.query_params.get('bucket_minutes'), 15)
    data = services.daily_summary(tenant, population, target_date, bucket_minutes=bucket_minutes)
    return Response({'success': True, 'population': population, **data})


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def daily_register(request):
    tenant, error = _admin_tenant_or_error(request)
    if error:
        return error
    population = request.query_params.get('population') or ('student' if tenant.attendance_analytics_includes_students else 'staff')
    scope_error = _check_population_scope(tenant, population)
    if scope_error:
        return scope_error
    target_date = _parse_date(request.query_params.get('date'), services.school_today(tenant))
    page = _parse_int(request.query_params.get('page'), 1)
    page_size = _parse_int(request.query_params.get('page_size'), services.PAGE_SIZE_DEFAULT)
    data = services.daily_register(
        tenant, population, target_date,
        status_filter=request.query_params.get('status') or None,
        class_group_id=request.query_params.get('class_group_id') or None,
        department=request.query_params.get('department') or None,
        search=request.query_params.get('search') or '',
        page=page, page_size=page_size,
    )
    return Response({'success': True, 'population': population, 'date': target_date.isoformat(), **data})


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def staff_profile(request, person_id):
    tenant, error = _admin_tenant_or_error(request)
    if error:
        return error
    scope_error = _check_population_scope(tenant, 'staff')
    if scope_error:
        return scope_error
    period = request.query_params.get('period') or 'termly'
    period_start, period_end = _period_range(tenant, period)
    data = services.staff_profile_summary(tenant, str(person_id), period_start, period_end)
    if not data:
        return Response({'success': False, 'message': 'Staff member not found.'}, status=status.HTTP_404_NOT_FOUND)
    return Response({'success': True, 'period': period, **data})


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def staff_history(request, person_id):
    tenant, error = _admin_tenant_or_error(request)
    if error:
        return error
    scope_error = _check_population_scope(tenant, 'staff')
    if scope_error:
        return scope_error
    period = request.query_params.get('period') or 'termly'
    period_start, period_end = _period_range(tenant, period)
    page = _parse_int(request.query_params.get('page'), 1)
    page_size = _parse_int(request.query_params.get('page_size'), services.PAGE_SIZE_DEFAULT)
    data = services.staff_history(tenant, str(person_id), period_start, period_end, page=page, page_size=page_size)
    return Response({'success': True, 'period': period, **data})


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def student_profile(request, student_id):
    tenant, error = _admin_tenant_or_error(request)
    if error:
        return error
    scope_error = _check_population_scope(tenant, 'student')
    if scope_error:
        return scope_error
    period = request.query_params.get('period') or 'termly'
    period_start, period_end = _period_range(tenant, period)
    data = services.student_profile_summary(tenant, str(student_id), period_start, period_end)
    if not data:
        return Response({'success': False, 'message': 'Student not found.'}, status=status.HTTP_404_NOT_FOUND)
    return Response({'success': True, 'period': period, **data})


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def student_history(request, student_id):
    tenant, error = _admin_tenant_or_error(request)
    if error:
        return error
    scope_error = _check_population_scope(tenant, 'student')
    if scope_error:
        return scope_error
    period = request.query_params.get('period') or 'termly'
    period_start, period_end = _period_range(tenant, period)
    page = _parse_int(request.query_params.get('page'), 1)
    page_size = _parse_int(request.query_params.get('page_size'), services.PAGE_SIZE_DEFAULT)
    data = services.student_history(tenant, str(student_id), period_start, period_end, page=page, page_size=page_size)
    return Response({'success': True, 'period': period, **data})


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def filters_lookup(request):
    tenant, error = _admin_tenant_or_error(request)
    if error:
        return error
    population = request.query_params.get('population') or 'student'
    scope_error = _check_population_scope(tenant, population)
    if scope_error:
        return scope_error
    data = services.filters_lookup(tenant, population)
    return Response({'success': True, **data})
