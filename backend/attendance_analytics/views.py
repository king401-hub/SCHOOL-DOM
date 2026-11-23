"""Device-free, admin-facing endpoints for the Attendance Analytics feature -
all read-only, all backed by services.py's single calculation engine. Each
view also re-checks the tenant's attendance_analytics_scope server-side
(the frontend gates this too) so a student-only or staff-only school can
never pull data for the population it doesn't have, even by hitting the API
directly."""
import csv
import datetime
import io
import logging

from django.http import HttpResponse
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from users.app_views import _resolve_school_tenant_for_user

from . import reports, services

logger = logging.getLogger(__name__)
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
    # termly / default: services.term_date_range is the one place this is
    # resolved now - Phase 2's term-wide screens need the same lookup.
    return services.term_date_range(tenant, now=now)


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


# ---------------------------------------------------------------------------
# Screen 5/6 - term overview, trends, rankings, class/department comparison.
# Each delegates to a services.py function already wrapped in a ~15 minute
# cache (see services._cached_term_result) - no caching logic lives here.
# ---------------------------------------------------------------------------

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def term_overview(request):
    tenant, error = _admin_tenant_or_error(request)
    if error:
        return error
    data = services.term_overview(tenant)
    return Response({'success': True, **data})


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def term_trends(request):
    tenant, error = _admin_tenant_or_error(request)
    if error:
        return error
    population = request.query_params.get('population') or ('student' if tenant.attendance_analytics_includes_students else 'staff')
    scope_error = _check_population_scope(tenant, population)
    if scope_error:
        return scope_error
    granularity = request.query_params.get('granularity') or 'weekly'
    if granularity not in ('weekly', 'monthly'):
        return _bad_request('granularity must be weekly or monthly.')
    start, end = services.term_date_range(tenant)
    data = services.attendance_trends(tenant, population, start, end, granularity=granularity)
    return Response({'success': True, 'population': population, 'granularity': granularity, 'trends': data})


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def term_rankings(request):
    tenant, error = _admin_tenant_or_error(request)
    if error:
        return error
    population = request.query_params.get('population') or ('student' if tenant.attendance_analytics_includes_students else 'staff')
    scope_error = _check_population_scope(tenant, population)
    if scope_error:
        return scope_error
    limit = _parse_int(request.query_params.get('limit'), 5)
    start, end = services.term_date_range(tenant)
    data = services.rankings(tenant, population, start, end, limit=limit)
    return Response({'success': True, 'population': population, 'rankings': data})


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def class_department(request):
    tenant, error = _admin_tenant_or_error(request)
    if error:
        return error
    population = request.query_params.get('population') or ('student' if tenant.attendance_analytics_includes_students else 'staff')
    scope_error = _check_population_scope(tenant, population)
    if scope_error:
        return scope_error
    start, end = services.term_date_range(tenant)
    data = services.class_department_comparison(tenant, population, start, end)
    return Response({'success': True, 'population': population, 'groups': data})


def _parse_optional_datetime(value):
    if not value:
        return None
    parsed = parse_datetime(str(value))
    if parsed is None:
        raise ValueError(f'Invalid datetime: {value!r}')
    if timezone.is_naive(parsed):
        parsed = timezone.make_aware(parsed)
    return parsed


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def correct_attendance(request):
    """Admin-only manual attendance correction for any of the three
    populations - see services.write_attendance_correction for the audited
    upsert itself. A reason is required (enforced in the service layer, not
    duplicated here) per the brief's own acceptance criteria."""
    tenant, error = _admin_tenant_or_error(request)
    if error:
        return error

    kind = str(request.data.get('kind') or '').strip()
    if kind not in ('student', 'teacher', 'staff'):
        return _bad_request('kind must be student, teacher, or staff.')
    population = 'student' if kind == 'student' else 'staff'
    scope_error = _check_population_scope(tenant, population)
    if scope_error:
        return scope_error

    person_id = str(request.data.get('person_id') or '').strip()
    date_str = str(request.data.get('date') or '').strip()
    reason = str(request.data.get('reason') or '').strip()
    status_value = str(request.data.get('status') or '').strip() or None
    if not person_id or not date_str:
        return _bad_request('person_id and date are required.')
    try:
        date = datetime.date.fromisoformat(date_str)
    except ValueError:
        return _bad_request('date must be in YYYY-MM-DD format.')

    try:
        clock_in_at = _parse_optional_datetime(request.data.get('clock_in_at'))
        clock_out_at = _parse_optional_datetime(request.data.get('clock_out_at'))
    except ValueError as exc:
        return _bad_request(str(exc))

    if kind == 'staff' and not status_value:
        return _bad_request('status is required for a non-teaching staff correction.')
    if kind in ('student', 'teacher') and not (status_value or clock_in_at or clock_out_at):
        return _bad_request('Provide a status or a clock time to correct.')

    try:
        services.write_attendance_correction(
            tenant, request.user, kind, person_id, date, reason,
            status=status_value, clock_in_at=clock_in_at, clock_out_at=clock_out_at,
        )
    except ValueError as exc:
        return _bad_request(str(exc))

    return Response({'success': True, 'message': 'Attendance correction saved.'})


# ---------------------------------------------------------------------------
# Phase 3 - PDF reports (finance.pdf.render_html_to_pdf, the same headless-
# Chromium pipeline already used for receipts/bills/report cards - never a
# new PDF library) and CSV exports (the brief's "Excel" deliverable, matching
# the plain csv-module convention already used elsewhere in this codebase).
# Report generation is on-demand only - no scheduling/cron here.
# ---------------------------------------------------------------------------

def _pdf_response(html, filename):
    from finance.pdf import render_html_to_pdf
    try:
        pdf = render_html_to_pdf(html)
    except Exception:
        logger.exception('Attendance report PDF could not be rendered')
        return HttpResponse('The PDF could not be generated right now.', status=503)
    response = HttpResponse(pdf, content_type='application/pdf')
    response['Content-Disposition'] = f'inline; filename="{filename}"'
    return response


def _csv_response(rows, header, filename):
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(header)
    for row in rows:
        writer.writerow(row)
    response = HttpResponse(output.getvalue(), content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    return response


def _register_csv_rows(rows):
    return [[r['name'], r['identifier'], r['group_label'], r['first_arrival'] or '', r['last_departure'] or '', r['total_hours'] if r['total_hours'] is not None else '', r['status']] for r in rows]


REGISTER_CSV_HEADER = ['Name', 'ID', 'Class/Dept', 'First arrival', 'Last departure', 'Hours', 'Status']


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def daily_report_pdf(request):
    tenant, error = _admin_tenant_or_error(request)
    if error:
        return error
    population = request.query_params.get('population') or ('student' if tenant.attendance_analytics_includes_students else 'staff')
    scope_error = _check_population_scope(tenant, population)
    if scope_error:
        return scope_error
    target_date = _parse_date(request.query_params.get('date'), services.school_today(tenant))
    html = reports.daily_report_html(tenant, request, population, target_date)
    return _pdf_response(html, f'SchoolDom-Attendance-Daily-{target_date.isoformat()}.pdf')


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def daily_report_csv(request):
    tenant, error = _admin_tenant_or_error(request)
    if error:
        return error
    population = request.query_params.get('population') or ('student' if tenant.attendance_analytics_includes_students else 'staff')
    scope_error = _check_population_scope(tenant, population)
    if scope_error:
        return scope_error
    target_date = _parse_date(request.query_params.get('date'), services.school_today(tenant))
    data = services.daily_register(tenant, population, target_date, page=1, page_size=10000)
    return _csv_response(_register_csv_rows(data['results']), REGISTER_CSV_HEADER, f'attendance-daily-{target_date.isoformat()}.csv')


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def staff_report_pdf(request, person_id):
    tenant, error = _admin_tenant_or_error(request)
    if error:
        return error
    scope_error = _check_population_scope(tenant, 'staff')
    if scope_error:
        return scope_error
    period = request.query_params.get('period') or 'termly'
    start, end = _period_range(tenant, period)
    html = reports.staff_report_html(tenant, request, str(person_id), period, start, end)
    return _pdf_response(html, f'SchoolDom-Attendance-Staff-{person_id}.pdf')


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def staff_report_csv(request, person_id):
    tenant, error = _admin_tenant_or_error(request)
    if error:
        return error
    scope_error = _check_population_scope(tenant, 'staff')
    if scope_error:
        return scope_error
    period = request.query_params.get('period') or 'termly'
    start, end = _period_range(tenant, period)
    data = services.staff_history(tenant, str(person_id), start, end, page=1, page_size=10000)
    rows = _register_csv_rows([{**r, 'name': r['date'], 'identifier': '', 'group_label': ''} for r in data['results']])
    return _csv_response(rows, REGISTER_CSV_HEADER, f'attendance-staff-{person_id}.csv')


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def student_report_pdf(request, student_id):
    tenant, error = _admin_tenant_or_error(request)
    if error:
        return error
    scope_error = _check_population_scope(tenant, 'student')
    if scope_error:
        return scope_error
    period = request.query_params.get('period') or 'termly'
    start, end = _period_range(tenant, period)
    html = reports.student_report_html(tenant, request, str(student_id), period, start, end)
    return _pdf_response(html, f'SchoolDom-Attendance-Student-{student_id}.pdf')


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def student_report_csv(request, student_id):
    tenant, error = _admin_tenant_or_error(request)
    if error:
        return error
    scope_error = _check_population_scope(tenant, 'student')
    if scope_error:
        return scope_error
    period = request.query_params.get('period') or 'termly'
    start, end = _period_range(tenant, period)
    data = services.student_history(tenant, str(student_id), start, end, page=1, page_size=10000)
    rows = _register_csv_rows([{**r, 'name': r['date'], 'identifier': '', 'group_label': ''} for r in data['results']])
    return _csv_response(rows, REGISTER_CSV_HEADER, f'attendance-student-{student_id}.csv')


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def class_department_report_pdf(request):
    tenant, error = _admin_tenant_or_error(request)
    if error:
        return error
    population = request.query_params.get('population') or ('student' if tenant.attendance_analytics_includes_students else 'staff')
    scope_error = _check_population_scope(tenant, population)
    if scope_error:
        return scope_error
    period = request.query_params.get('period') or 'termly'
    start, end = _period_range(tenant, period)
    html = reports.class_department_report_html(tenant, request, population, period, start, end)
    return _pdf_response(html, f'SchoolDom-Attendance-ClassDept-{population}.pdf')


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def class_department_report_csv(request):
    tenant, error = _admin_tenant_or_error(request)
    if error:
        return error
    population = request.query_params.get('population') or ('student' if tenant.attendance_analytics_includes_students else 'staff')
    scope_error = _check_population_scope(tenant, population)
    if scope_error:
        return scope_error
    period = request.query_params.get('period') or 'termly'
    start, end = _period_range(tenant, period)
    data = services.class_department_comparison(tenant, population, start, end)
    header = ['Class' if population == 'student' else 'Department', 'Total', 'Present', 'Attendance %']
    rows = [[g['group_label'], g['total_people'], g['total_present'], g['attendance_percent']] for g in data]
    return _csv_response(rows, header, f'attendance-class-department-{population}.csv')


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def termly_report_pdf(request):
    tenant, error = _admin_tenant_or_error(request)
    if error:
        return error
    html = reports.termly_report_html(tenant, request)
    return _pdf_response(html, 'SchoolDom-Attendance-Termly-Report.pdf')
