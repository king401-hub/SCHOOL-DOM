"""The single attendance-calculation engine every Attendance Analytics screen
reads from (overview dashboard, daily analytics, individual staff/student
profiles) - the CTO brief's own explicit requirement that "all dashboards,
charts and reports must use the same calculation logic to prevent
inconsistent figures."

Three attendance sources, normalized into one shape by the fetch_* adapters
below:
- academic.AttendanceRecord - students (clock_in_at/clock_out_at).
- attendance.TeacherAttendance - teachers (check_in_time/check_out_time from
  the gate terminals) - full clock-based analytics.
- hr.StaffAttendance - non-teaching staff (security, cleaning, admin,
  bursary) - manually marked by an admin, no clock timestamps, so only
  present/absent/attendance % apply; late/early/hours are always None for
  this population (see day_status_from_manual_status).

Phase 1 deliberately has no raw per-scan event log (see the "Attendance
Analytics - Phase 1" plan) - everything here reads directly from the
existing session-level models above, which means a second clock-in/out pair
on the same day (left and returned) isn't captured.

Scheduling/lateness config is NOT reinvented here - every late/early/cutoff
decision delegates to the tenant's existing rfid_attendance.models.GateSettings
and its classify_event(), the same config the gate terminals themselves use,
so these numbers always agree with what a terminal already classified an
event as.
"""
import datetime

from django.core.cache import cache
from django.db import transaction
from django.db.models import Q

from academic.models import AttendanceRecord, Class, SchoolActivityCalendar, Term
from attendance.models import TeacherAttendance
from core.models import AuditLog
from hr.models import StaffAttendance, StaffProfile
from rfid_attendance.services import _legacy_tenant_for_attendance, _school_localtime
from rfid_attendance.views import get_or_create_gate_settings
from users.models import StudentProfile, User

PAGE_SIZE_DEFAULT = 25


# ---------------------------------------------------------------------------
# Calendar / "what day is it" primitives
# ---------------------------------------------------------------------------

def school_today(tenant, now=None):
    return _school_localtime(tenant, now).date()


def closed_dates(tenant, start_date, end_date):
    """Every date in [start_date, end_date] covered by a SchoolActivityCalendar
    entry flagged is_non_school_day. A month/year-only entry (no
    activity_date) has no concrete day to exclude and is skipped.

    SchoolActivityCalendar is a TenantAwareModel - its `tenant` FK points at
    the legacy tenants.Tenant model, not core.SchoolTenant, exactly like
    AttendanceRecord (see rfid_attendance.services._legacy_tenant_for_attendance's
    own docstring) - resolve that first rather than filtering on `tenant`
    directly."""
    closed = set()
    legacy_tenant = _legacy_tenant_for_attendance(tenant)
    entries = SchoolActivityCalendar.objects.filter(
        tenant=legacy_tenant, is_non_school_day=True, activity_date__isnull=False, activity_date__lte=end_date,
    ).filter(Q(end_date__isnull=True, activity_date__gte=start_date) | Q(end_date__gte=start_date))
    for entry in entries:
        span_end = entry.end_date or entry.activity_date
        day = max(entry.activity_date, start_date)
        last = min(span_end, end_date)
        while day <= last:
            closed.add(day)
            day += datetime.timedelta(days=1)
    return closed


def cutoff_passed_for_day(tenant, day, *, gate_settings=None, now=None):
    """True once `day` is fully resolved (a past day, or today past its
    configured clock-out-end time) - the single source of truth for "is it
    safe to call someone absent for this day yet." A future day is never
    resolved (returns False), which naturally keeps it out of any
    present/absent count until it actually happens."""
    today = school_today(tenant, now)
    if day < today:
        return True
    if day > today:
        return False
    if gate_settings is None:
        gate_settings = get_or_create_gate_settings(tenant)
    current_time = _school_localtime(tenant, now).time()
    return current_time >= gate_settings.clockout_end


def expected_working_days(tenant, start_date, end_date):
    """The school's calendar-defined working days in [start_date, end_date] -
    weekdays minus flagged holidays. Deliberately a PURE calendar function,
    independent of "now"/cutoff timing: it is the fixed denominator for the
    period (e.g. "65 expected working days this term"), regardless of
    whether a given day is in the past, is today, or hasn't happened yet.
    Per-day present/absent/in-progress classification (which DOES depend on
    cutoff timing) happens separately in day_status/day_status_from_manual_status
    - a day whose cutoff hasn't passed is simply never counted as present or
    absent, which is what structurally guarantees today (and any future day)
    is never prematurely marked absent, without needing to exclude it from
    this denominator at all."""
    closed = closed_dates(tenant, start_date, end_date)
    days = []
    day = start_date
    while day <= end_date:
        if day.weekday() < 5 and day not in closed:
            days.append(day)
        day += datetime.timedelta(days=1)
    return days


def resolve_term(tenant, now=None):
    """The tenant's active academic.Term row, or None if none is marked
    active. Term is a TenantAwareModel keyed on the legacy tenant - same
    bridge as closed_dates. Moved here (Phase 2) from views._period_range,
    which now calls term_date_range below instead of re-querying Term
    itself - one lookup, not two copies of it."""
    legacy_tenant = _legacy_tenant_for_attendance(tenant)
    return Term.objects.filter(tenant=legacy_tenant, is_active=True).first()


def term_date_range(tenant, now=None):
    """(start, end) for the active term, end clamped to today so a term that
    hasn't finished yet never pulls in future dates. Falls back to the last
    90 days when no term is marked active - same fallback views._period_range
    already used before this was centralized here."""
    term = resolve_term(tenant, now=now)
    today = school_today(tenant, now)
    if term:
        return term.start_date, min(term.end_date, today)
    return today - datetime.timedelta(days=90), today


# ---------------------------------------------------------------------------
# Classification (always delegates to GateSettings.classify_event)
# ---------------------------------------------------------------------------

def is_late_arrival(tenant, clock_in_at, gate_settings):
    local_time = _school_localtime(tenant, clock_in_at).time()
    return gate_settings.classify_event(local_time) == 'late'


def is_early_departure(tenant, clock_out_at, gate_settings):
    # Anything before the clock-out window even opens counts as leaving
    # early - that covers a clock-out that lands in the too_early/early/late
    # buckets, not just the boundary case of leaving exactly as the window
    # opens. See the Phase 1 plan's documented limitation on this choice.
    local_time = _school_localtime(tenant, clock_out_at).time()
    return gate_settings.classify_event(local_time) in ('too_early', 'early', 'late')


# ---------------------------------------------------------------------------
# Per-day status
# ---------------------------------------------------------------------------

def day_status(tenant, day, clock_in_at, clock_out_at, *, gate_settings=None, now=None):
    """One day's status for one person, derived from raw clock timestamps -
    never from a stored status column. Returns
    {"status": "present"|"absent"|"in_progress", "is_late", "is_early_departure",
    "clocked_out", "hours"}."""
    if gate_settings is None:
        gate_settings = get_or_create_gate_settings(tenant)
    if clock_in_at is None:
        resolved = cutoff_passed_for_day(tenant, day, gate_settings=gate_settings, now=now)
        return {
            'status': 'absent' if resolved else 'in_progress',
            'is_late': False, 'is_early_departure': False, 'clocked_out': False, 'hours': None,
        }
    is_late = is_late_arrival(tenant, clock_in_at, gate_settings)
    clocked_out = clock_out_at is not None
    is_early = is_early_departure(tenant, clock_out_at, gate_settings) if clocked_out else False
    hours = round((clock_out_at - clock_in_at).total_seconds() / 3600, 2) if clocked_out else None
    return {
        'status': 'present', 'is_late': is_late, 'is_early_departure': is_early,
        'clocked_out': clocked_out, 'hours': hours,
    }


def day_status_from_manual_status(status_value, day, cutoff_passed):
    """One day's status for a non-teaching staff member, from
    hr.StaffAttendance's manually-set status - no clock math, since that
    model has no reliable raw timestamps. present/late/half_day all count as
    "attended" for this reduced view; excused is pulled out of the
    denominator entirely (same treatment as a holiday, never counted as an
    absence); a missing row or an explicit "absent" status only resolves to
    "absent" once the day is resolved (cutoff_passed), matching the
    never-mark-absent-mid-day rule even though there's no literal clock-out
    cutoff for a manually-marked system."""
    always_none = {'is_late': None, 'is_early_departure': None, 'clocked_out': None, 'hours': None}
    if status_value in (StaffAttendance.PRESENT, StaffAttendance.LATE, StaffAttendance.HALF_DAY):
        return {'status': 'present', **always_none}
    if status_value == StaffAttendance.EXCUSED:
        return {'status': 'excused', **always_none}
    # status_value is ABSENT or there's no row at all for this day.
    return {'status': 'absent' if cutoff_passed else 'in_progress', **always_none}


def _average_time(times):
    if not times:
        return None
    total_seconds = sum(t.hour * 3600 + t.minute * 60 + t.second for t in times)
    avg_seconds = total_seconds // len(times)
    hours, remainder = divmod(avg_seconds, 3600)
    minutes = remainder // 60
    return f"{hours:02d}:{minutes:02d}"


def attendance_percent(days_present, expected_days):
    """Guards the one divide-by-zero case every call site must share -
    pulled out as its own function so no screen/export ever re-implements
    this guard slightly differently."""
    if expected_days <= 0:
        return 0.0
    return round(days_present / expected_days * 100, 1)


# ---------------------------------------------------------------------------
# Model adapters - normalize the three source models into one shape, keyed
# (person_id, date) -> {"clock_in_at":, "clock_out_at":} or {"status":}
# ---------------------------------------------------------------------------

def fetch_student_day_records(student_ids, start_date, end_date):
    rows = AttendanceRecord.objects.filter(
        student_id__in=student_ids, date__range=(start_date, end_date),
    ).values('student_id', 'date', 'clock_in_at', 'clock_out_at')
    return {
        (row['student_id'], row['date']): {'clock_in_at': row['clock_in_at'], 'clock_out_at': row['clock_out_at']}
        for row in rows
    }


def fetch_teacher_day_records(tenant, teacher_ids, start_date, end_date):
    rows = TeacherAttendance.objects.filter(
        tenant=tenant, teacher_id__in=teacher_ids, attendance_date__range=(start_date, end_date),
    ).values('teacher_id', 'attendance_date', 'check_in_time', 'check_out_time')
    return {
        (row['teacher_id'], row['attendance_date']): {
            'clock_in_at': row['check_in_time'], 'clock_out_at': row['check_out_time'],
        }
        for row in rows
    }


def fetch_nonteaching_staff_day_records(staff_profile_ids, start_date, end_date):
    rows = StaffAttendance.objects.filter(
        staff_id__in=staff_profile_ids, date__range=(start_date, end_date),
    ).values('staff_id', 'date', 'status')
    return {(row['staff_id'], row['date']): {'status': row['status']} for row in rows}


def _records_for_person(records_by_person_date, person_id):
    return {date: v for (pid, date), v in records_by_person_date.items() if pid == person_id}


def _records_for_day(records_by_person_date, day, person_ids):
    by_day = {pid: v for (pid, date), v in records_by_person_date.items() if date == day}
    return {pid: by_day.get(pid, {}) for pid in person_ids}


# ---------------------------------------------------------------------------
# Aggregation
# ---------------------------------------------------------------------------

def compute_person_period_stats(tenant, start_date, end_date, day_records_by_date, *, gate_settings=None, now=None, manual=False):
    """One person's attendance stats over [start_date, end_date].
    day_records_by_date maps date -> {"clock_in_at":, "clock_out_at":} (clock
    path) or date -> {"status":} (manual=True, non-teaching staff path).
    late_arrivals/early_departures/total_hours/average_hours_per_day/
    average_arrival_time/average_departure_time are always None when
    manual=True - that system has nothing to derive them from."""
    if not manual and gate_settings is None:
        gate_settings = get_or_create_gate_settings(tenant)
    today = school_today(tenant, now)
    expected_days = expected_working_days(tenant, start_date, end_date)

    days_present = days_absent = days_excused = late_arrivals = early_departures = 0
    total_hours = 0.0
    days_with_hours = 0
    arrival_times, departure_times = [], []
    day_in_progress = False
    not_yet_clocked_out = False

    for day in expected_days:
        record = day_records_by_date.get(day) or {}
        if manual:
            cutoff = cutoff_passed_for_day(tenant, day, now=now)
            result = day_status_from_manual_status(record.get('status'), day, cutoff)
        else:
            result = day_status(
                tenant, day, record.get('clock_in_at'), record.get('clock_out_at'),
                gate_settings=gate_settings, now=now,
            )
        status = result['status']
        if status == 'present':
            days_present += 1
            if not manual:
                if result['is_late']:
                    late_arrivals += 1
                if result['is_early_departure']:
                    early_departures += 1
                if result['hours'] is not None:
                    total_hours += result['hours']
                    days_with_hours += 1
                if record.get('clock_in_at'):
                    arrival_times.append(_school_localtime(tenant, record['clock_in_at']).time())
                if record.get('clock_out_at'):
                    departure_times.append(_school_localtime(tenant, record['clock_out_at']).time())
                if day == today and not result['clocked_out']:
                    not_yet_clocked_out = True
        elif status == 'absent':
            days_absent += 1
        elif status == 'excused':
            days_excused += 1
        elif status == 'in_progress' and day == today:
            day_in_progress = True
        # a future in_progress day (day > today) contributes to nothing and
        # isn't surfaced as "day in progress" - only today is.

    effective_expected = len(expected_days) - days_excused
    return {
        'days_present': days_present,
        'days_absent': days_absent,
        'days_excused': days_excused,
        'expected_working_days': effective_expected,
        'attendance_percent': attendance_percent(days_present, effective_expected),
        'day_in_progress': day_in_progress,
        'not_yet_clocked_out': not_yet_clocked_out,
        'late_arrivals': None if manual else late_arrivals,
        'early_departures': None if manual else early_departures,
        'total_hours': None if manual else round(total_hours, 2),
        'average_hours_per_day': None if manual else (round(total_hours / days_with_hours, 2) if days_with_hours else None),
        'average_arrival_time': None if manual else _average_time(arrival_times),
        'average_departure_time': None if manual else _average_time(departure_times),
    }


def compute_bulk_day_stats(tenant, day, day_records_by_person, *, gate_settings=None, now=None, manual=False):
    """One day across many people - what Screen 1's cards and Screen 2's
    donut/summary are built from. Every person falls into exactly one of
    present_on_time/present_late/total_absent/unresolved, so those four
    always sum to total_registered - the brief's "late is a subset of
    present, never double-counted" guarantee, enforced by construction."""
    if not manual and gate_settings is None:
        gate_settings = get_or_create_gate_settings(tenant)
    cutoff = cutoff_passed_for_day(tenant, day, gate_settings=gate_settings, now=now)
    today = school_today(tenant, now)
    day_in_progress = (day == today and not cutoff)

    per_person = {}
    present_on_time = present_late = absent = unresolved = 0
    not_yet_clocked_out = early_departures = 0
    total_hours = 0.0
    days_with_hours = 0
    arrival_times, departure_times = [], []

    for person_id, record in day_records_by_person.items():
        record = record or {}
        if manual:
            result = day_status_from_manual_status(record.get('status'), day, cutoff)
        else:
            result = day_status(
                tenant, day, record.get('clock_in_at'), record.get('clock_out_at'),
                gate_settings=gate_settings, now=now,
            )
        per_person[person_id] = result
        status = result['status']
        if status == 'present':
            if not manual and result['is_late']:
                present_late += 1
            else:
                present_on_time += 1
            if not manual:
                if result['hours'] is not None:
                    total_hours += result['hours']
                    days_with_hours += 1
                if record.get('clock_in_at'):
                    arrival_times.append(_school_localtime(tenant, record['clock_in_at']).time())
                if record.get('clock_out_at'):
                    departure_times.append(_school_localtime(tenant, record['clock_out_at']).time())
                if not result['clocked_out']:
                    not_yet_clocked_out += 1
                elif result['is_early_departure']:
                    early_departures += 1
        elif status == 'absent':
            absent += 1
        else:  # 'in_progress' or 'excused' - unresolved for the donut, never counted absent
            unresolved += 1

    total = len(day_records_by_person)
    resolved_total = total - unresolved
    return {
        'per_person': per_person,
        'total_registered': total,
        'total_present': present_on_time + present_late,
        'present_on_time': present_on_time,
        'present_late': present_late,
        'total_absent': absent,
        'unresolved': unresolved,
        'day_in_progress': day_in_progress,
        'not_yet_clocked_out': None if manual else not_yet_clocked_out,
        'early_departures': None if manual else early_departures,
        'attendance_percent': attendance_percent(present_on_time + present_late, resolved_total) if resolved_total else 0.0,
        'total_hours': None if manual else round(total_hours, 2),
        'average_hours_per_person': None if manual else (round(total_hours / days_with_hours, 2) if days_with_hours else None),
        'average_arrival_time': None if manual else _average_time(arrival_times),
        'average_departure_time': None if manual else _average_time(departure_times),
    }


def _merge_staff_bulk_stats(teacher_stats, nonteaching_stats):
    """Screen 1 shows ONE staff donut covering every staff member - combine
    the clock-based teacher rollup and the manual non-teaching rollup into
    one shape. Hours/late-arrival figures reflect teachers only, since
    non-teaching staff have none of those - this is noted in the API
    response rather than silently blended in a misleading way."""
    total_present = teacher_stats['total_present'] + nonteaching_stats['total_present']
    total_registered = teacher_stats['total_registered'] + nonteaching_stats['total_registered']
    total_absent = teacher_stats['total_absent'] + nonteaching_stats['total_absent']
    unresolved = teacher_stats['unresolved'] + nonteaching_stats['unresolved']
    resolved_total = total_registered - unresolved
    return {
        'total_registered': total_registered,
        'total_present': total_present,
        'present_on_time': teacher_stats['present_on_time'] + nonteaching_stats['present_on_time'],
        'present_late': teacher_stats['present_late'],
        'total_absent': total_absent,
        'unresolved': unresolved,
        'day_in_progress': teacher_stats['day_in_progress'] or nonteaching_stats['day_in_progress'],
        'attendance_percent': attendance_percent(total_present, resolved_total) if resolved_total else 0.0,
        'total_hours': teacher_stats['total_hours'],
        'average_hours_per_person': teacher_stats['average_hours_per_person'],
        'average_arrival_time': teacher_stats['average_arrival_time'],
        'average_departure_time': teacher_stats['average_departure_time'],
        'late_arrivals': teacher_stats['present_late'],
        'early_departures': teacher_stats['early_departures'],
        'not_yet_clocked_out': teacher_stats['not_yet_clocked_out'],
        'hours_and_lateness_cover_teachers_only': True,
    }


def _bulk_period_rollup(tenant, start_date, end_date, people, fetch_fn, *, gate_settings=None, now=None, manual=False):
    """The Phase 2 analog of compute_bulk_day_stats, for a whole date range
    instead of one day - what Screen 5's term totals, Screen 5's rankings and
    Screen 6's class/department comparisons are all built from.

    people: [{"id":, "name":, "group_label":}, ...]. fetch_fn takes exactly
    (ids, start_date, end_date) - callers wrap fetch_teacher_day_records(tenant,
    ...)'s tenant-first signature in a small lambda/partial before passing it
    in, since fetch_student_day_records/fetch_nonteaching_staff_day_records
    already match this shape directly. Called ONCE for every id across the
    whole range (every adapter already supports that), then
    compute_person_period_stats is reused per person via _records_for_person,
    exactly like Phase 1's per-person profile screens already do - no new
    fetch logic, only new orchestration around it.

    Returns {"people": [{...person, **compute_person_period_stats shape}],
    "totals": {...summed across every person}}. total's attendance_percent is
    a ratio of sums (total present-person-days / total expected person-days),
    never a mean of each person's own percentage - the same formula
    attendance_percent() already uses everywhere else, so this number can
    never quietly disagree with any other screen's definition of it."""
    ids = [p['id'] for p in people]
    records = fetch_fn(ids, start_date, end_date)

    expected_days_count = len(expected_working_days(tenant, start_date, end_date))

    rows = []
    total_present = total_absent = total_excused = total_late = total_early = 0
    total_hours = 0.0
    total_days_with_hours = 0
    for person in people:
        by_date = _records_for_person(records, person['id'])
        stats = compute_person_period_stats(
            tenant, start_date, end_date, by_date, gate_settings=gate_settings, now=now, manual=manual,
        )
        rows.append({**person, **stats})
        total_present += stats['days_present']
        total_absent += stats['days_absent']
        total_excused += stats['days_excused']
        if not manual:
            total_late += stats['late_arrivals'] or 0
            total_early += stats['early_departures'] or 0
            if stats['total_hours']:
                total_hours += stats['total_hours']
                total_days_with_hours += 1

    total_expected_person_days = expected_days_count * len(people) - total_excused
    totals = {
        'total_people': len(people),
        'expected_working_days': expected_days_count,
        'total_days_present': total_present,
        'total_absences': total_absent,
        'total_excused': total_excused,
        'average_attendance_percent': attendance_percent(total_present, total_expected_person_days),
        'late_arrivals': None if manual else total_late,
        'early_departures': None if manual else total_early,
        'total_hours': None if manual else round(total_hours, 2),
        'average_daily_hours': None if manual else (round(total_hours / total_days_with_hours, 2) if total_days_with_hours else None),
    }
    return {'people': rows, 'totals': totals}


def _merge_staff_period_rollup(teacher_rollup, nonteaching_rollup):
    """Period-totals counterpart to _merge_staff_bulk_stats - combines the
    clock-based teacher rollup and the manual non-teaching rollup into one
    "staff" totals block, same hours/lateness-is-teachers-only caveat."""
    t, n = teacher_rollup['totals'], nonteaching_rollup['totals']
    total_present = t['total_days_present'] + n['total_days_present']
    total_expected = (
        (t['expected_working_days'] * t['total_people'] - t['total_excused'])
        + (n['expected_working_days'] * n['total_people'] - n['total_excused'])
    )
    totals = {
        'total_people': t['total_people'] + n['total_people'],
        'expected_working_days': t['expected_working_days'],
        'total_days_present': total_present,
        'total_absences': t['total_absences'] + n['total_absences'],
        'total_excused': t['total_excused'] + n['total_excused'],
        'average_attendance_percent': attendance_percent(total_present, total_expected),
        'late_arrivals': t['late_arrivals'],
        'early_departures': t['early_departures'],
        'total_hours': t['total_hours'],
        'average_daily_hours': t['average_daily_hours'],
        'hours_and_lateness_cover_teachers_only': True,
    }
    return {'people': teacher_rollup['people'] + nonteaching_rollup['people'], 'totals': totals}


def _cached_term_result(tenant, fn_name, cache_key_parts, compute):
    """Term-wide screens (term_overview/attendance_trends/rankings/
    class_department_comparison) scan every person x every day in a term -
    cheap at this platform's actual school sizes but not free, and production
    runs only 3 sync gunicorn workers, so a slow request blocks a third of
    backend capacity. Cached for 15 minutes rather than built as a
    pre-aggregation table - simpler, and a dashboard that's up to 15 minutes
    behind the latest scan is an acceptable trade the user explicitly chose.

    The cache backend (DatabaseCache on one shared table, see
    config.settings.CACHES) does NOT namespace by tenant on its own -
    tenant.schema_name must be the first key component or two schools could
    read each other's cached figures. Matches the existing
    pending_card_scan:{school.schema_name} convention in
    rfid_attendance.views."""
    key = 'attn:' + ':'.join([tenant.schema_name, fn_name, *map(str, cache_key_parts)])
    cached = cache.get(key)
    if cached is not None:
        return cached
    result = compute()
    cache.set(key, result, timeout=900)
    return result


# ---------------------------------------------------------------------------
# Screen-shaped entry points
# ---------------------------------------------------------------------------

def _teacher_ids(tenant):
    return list(User.objects.filter(tenant=tenant, role='teacher').values_list('id', flat=True))


def _nonteaching_staff_ids(tenant):
    return list(StaffProfile.objects.filter(tenant=tenant, staff_type=StaffProfile.NON_TEACHING).values_list('id', flat=True))


def _student_ids(tenant):
    return list(StudentProfile.objects.filter(user__tenant=tenant).values_list('user_id', flat=True))


def _student_people(tenant):
    profiles = StudentProfile.objects.filter(user__tenant=tenant).select_related('user', 'current_class')
    return [
        {'id': p.user_id, 'name': p.user.get_full_name(), 'group_label': p.current_class.name if p.current_class else ''}
        for p in profiles
    ]


def _teacher_people(tenant):
    teachers = User.objects.filter(tenant=tenant, role='teacher')
    # Matches daily_register's own hardcoded "Teaching" group_label for
    # teachers - one convention for what a teacher's group is, not two.
    return [{'id': t.id, 'name': t.get_full_name(), 'group_label': 'Teaching'} for t in teachers]


def _nonteaching_people(tenant):
    staff = StaffProfile.objects.filter(tenant=tenant, staff_type=StaffProfile.NON_TEACHING)
    return [{'id': s.id, 'name': s.full_name, 'group_label': s.department or 'Non-teaching'} for s in staff]


def _merge_staff_day_stats(tenant, day, teacher_by_person, nonteaching_by_person, *, gate_settings=None, now=None):
    """The actual per-day teacher+non-teaching merge, pulled out of
    _staff_bulk_stats_for_day so attendance_trends can bulk-fetch the whole
    term ONCE and call this per day without re-querying per day (same
    bulk-fetch-then-loop shape as everything else in this file)."""
    teacher_stats = compute_bulk_day_stats(tenant, day, teacher_by_person, gate_settings=gate_settings, now=now)
    nonteaching_stats = compute_bulk_day_stats(tenant, day, nonteaching_by_person, gate_settings=gate_settings, now=now, manual=True)
    return _merge_staff_bulk_stats(teacher_stats, nonteaching_stats)


def _staff_bulk_stats_for_day(tenant, target_date, *, gate_settings=None, now=None):
    teacher_ids = _teacher_ids(tenant)
    teacher_records = fetch_teacher_day_records(tenant, teacher_ids, target_date, target_date)
    teacher_by_person = _records_for_day(teacher_records, target_date, teacher_ids)

    staff_ids = _nonteaching_staff_ids(tenant)
    staff_records = fetch_nonteaching_staff_day_records(staff_ids, target_date, target_date)
    staff_by_person = _records_for_day(staff_records, target_date, staff_ids)

    return _merge_staff_day_stats(tenant, target_date, teacher_by_person, staff_by_person, gate_settings=gate_settings, now=now)


def overview_summary(tenant, target_date, now=None):
    gate_settings = get_or_create_gate_settings(tenant)
    cutoff = cutoff_passed_for_day(tenant, target_date, gate_settings=gate_settings, now=now)
    today = school_today(tenant, now)
    result = {'date': target_date.isoformat(), 'day_in_progress': target_date == today and not cutoff}

    if tenant.attendance_analytics_includes_students:
        student_ids = _student_ids(tenant)
        records = fetch_student_day_records(student_ids, target_date, target_date)
        by_person = _records_for_day(records, target_date, student_ids)
        result['students'] = compute_bulk_day_stats(tenant, target_date, by_person, gate_settings=gate_settings, now=now)
    if tenant.attendance_analytics_includes_staff:
        result['staff'] = _staff_bulk_stats_for_day(tenant, target_date, gate_settings=gate_settings, now=now)
    return result


def daily_summary(tenant, population, target_date, *, bucket_minutes=15, now=None):
    gate_settings = get_or_create_gate_settings(tenant)
    if population == 'student':
        stats = overview_summary(tenant, target_date, now=now).get('students') or compute_bulk_day_stats(
            tenant, target_date, {}, gate_settings=gate_settings, now=now,
        )
    else:
        stats = _staff_bulk_stats_for_day(tenant, target_date, gate_settings=gate_settings, now=now)
    histogram = daily_arrival_histogram(tenant, population, target_date, bucket_minutes=bucket_minutes, now=now)
    return {
        'date': target_date.isoformat(),
        'summary': stats,
        'donut': {
            'present_on_time': stats['present_on_time'],
            'present_late': stats['present_late'],
            'absent': stats['total_absent'],
            'unresolved': stats['unresolved'],
        },
        'histogram': histogram,
    }


def daily_arrival_histogram(tenant, population, target_date, *, bucket_minutes=15, now=None):
    if population == 'student':
        ids = _student_ids(tenant)
        records = fetch_student_day_records(ids, target_date, target_date)
    else:
        ids = _teacher_ids(tenant)
        records = fetch_teacher_day_records(tenant, ids, target_date, target_date)
    arrivals = []
    for (_pid, date), record in records.items():
        if date == target_date and record.get('clock_in_at'):
            arrivals.append(_school_localtime(tenant, record['clock_in_at']).time())
    if not arrivals:
        return []
    buckets = {}
    for t in arrivals:
        minutes_since_midnight = t.hour * 60 + t.minute
        bucket_start = (minutes_since_midnight // bucket_minutes) * bucket_minutes
        buckets[bucket_start] = buckets.get(bucket_start, 0) + 1
    out = []
    for bucket_start in sorted(buckets):
        start_h, start_m = divmod(bucket_start, 60)
        end_h, end_m = divmod(bucket_start + bucket_minutes, 60)
        out.append({
            'bucket_start': f"{start_h:02d}:{start_m:02d}",
            'bucket_end': f"{end_h:02d}:{end_m:02d}",
            'count': buckets[bucket_start],
        })
    return out


# ---------------------------------------------------------------------------
# Screen 5/6 - term-wide overview, trends, rankings, class/department
# comparisons. Each is wrapped in _cached_term_result (~15 min) - these scan
# every person x every day in a term, unlike every Screen 1/2 function above.
# ---------------------------------------------------------------------------

def term_overview(tenant, *, now=None):
    term = resolve_term(tenant, now=now)
    start, end = term_date_range(tenant, now=now)
    gate_settings = get_or_create_gate_settings(tenant)

    def _compute():
        expected_days = len(expected_working_days(tenant, start, end))
        students = _student_people(tenant) if tenant.attendance_analytics_includes_students else []
        teachers = _teacher_people(tenant) if tenant.attendance_analytics_includes_staff else []
        nonteaching = _nonteaching_people(tenant) if tenant.attendance_analytics_includes_staff else []
        result = {
            'term': {
                'session': term.academic_year.name if term and term.academic_year else '',
                'name': term.name if term else '',
                'start_date': start.isoformat(),
                'end_date': end.isoformat(),
                'expected_working_days': expected_days,
                'total_registered_staff': (len(teachers) + len(nonteaching)) if tenant.attendance_analytics_includes_staff else None,
                'total_registered_students': len(students) if tenant.attendance_analytics_includes_students else None,
            },
        }
        if tenant.attendance_analytics_includes_students:
            result['students'] = _bulk_period_rollup(
                tenant, start, end, students, fetch_student_day_records, gate_settings=gate_settings, now=now,
            )['totals']
        if tenant.attendance_analytics_includes_staff:
            teacher_rollup = _bulk_period_rollup(
                tenant, start, end, teachers, lambda ids, s, e: fetch_teacher_day_records(tenant, ids, s, e),
                gate_settings=gate_settings, now=now,
            )
            nonteaching_rollup = _bulk_period_rollup(
                tenant, start, end, nonteaching, fetch_nonteaching_staff_day_records, now=now, manual=True,
            )
            result['staff'] = _merge_staff_period_rollup(teacher_rollup, nonteaching_rollup)['totals']
        return result

    return _cached_term_result(tenant, 'term_overview', [start, end], _compute)


def _bucket_daily_stats(daily, granularity):
    """Groups a list of {"date":, **compute_bulk_day_stats shape} dicts (one
    per calendar day, in order) into weekly or monthly buckets. Each bucket's
    attendance_percent is a fresh ratio of that bucket's own present/resolved
    totals, never an average of each day's already-rounded percentage - same
    "ratio of sums, not mean of ratios" rule attendance_percent() enforces
    everywhere else in this file."""
    buckets, order = {}, []
    for day_stats in daily:
        day = day_stats['date']
        if granularity == 'monthly':
            bucket_key = day.replace(day=1)
            label = bucket_key.strftime('%b %Y')
        else:
            bucket_key = day - datetime.timedelta(days=day.weekday())
            label = f"Week of {bucket_key.strftime('%b %d')}"
        if bucket_key not in buckets:
            buckets[bucket_key] = {'period_label': label, 'total_present': 0, 'total_resolved': 0, 'late_count': 0, 'absent_count': 0}
            order.append(bucket_key)
        bucket = buckets[bucket_key]
        bucket['total_present'] += day_stats['total_present']
        bucket['total_resolved'] += day_stats['total_registered'] - day_stats['unresolved']
        bucket['late_count'] += day_stats['present_late']
        bucket['absent_count'] += day_stats['total_absent']
    return [
        {
            'period_label': buckets[key]['period_label'],
            'attendance_percent': attendance_percent(buckets[key]['total_present'], buckets[key]['total_resolved']),
            'late_count': buckets[key]['late_count'],
            'absent_count': buckets[key]['absent_count'],
        }
        for key in order
    ]


def attendance_trends(tenant, population, start_date, end_date, *, granularity='weekly', now=None):
    gate_settings = get_or_create_gate_settings(tenant)

    def _compute():
        daily = []
        if population == 'student':
            ids = _student_ids(tenant)
            records = fetch_student_day_records(ids, start_date, end_date)
            day = start_date
            while day <= end_date:
                by_person = _records_for_day(records, day, ids)
                stats = compute_bulk_day_stats(tenant, day, by_person, gate_settings=gate_settings, now=now)
                daily.append({'date': day, **stats})
                day += datetime.timedelta(days=1)
        else:
            teacher_ids = _teacher_ids(tenant)
            teacher_records = fetch_teacher_day_records(tenant, teacher_ids, start_date, end_date)
            staff_ids = _nonteaching_staff_ids(tenant)
            staff_records = fetch_nonteaching_staff_day_records(staff_ids, start_date, end_date)
            day = start_date
            while day <= end_date:
                teacher_by_person = _records_for_day(teacher_records, day, teacher_ids)
                staff_by_person = _records_for_day(staff_records, day, staff_ids)
                stats = _merge_staff_day_stats(tenant, day, teacher_by_person, staff_by_person, gate_settings=gate_settings, now=now)
                daily.append({'date': day, **stats})
                day += datetime.timedelta(days=1)
        return _bucket_daily_stats(daily, granularity)

    return _cached_term_result(tenant, f'attendance_trends:{population}:{granularity}', [start_date, end_date], _compute)


def _top(people, key, limit, *, reverse):
    """Top `limit` people by `key`, skipping anyone it's None for (e.g.
    non-teaching staff on an hours/lateness ranking - that system has no
    clock data to rank them by at all, not a tie at zero)."""
    ranked = sorted((p for p in people if p.get(key) is not None), key=lambda p: p[key], reverse=reverse)
    return [{'id': str(p['id']), 'name': p['name'], 'group_label': p['group_label'], key: p[key]} for p in ranked[:limit]]


def rankings(tenant, population, start_date, end_date, *, limit=5, now=None):
    gate_settings = get_or_create_gate_settings(tenant)

    def _compute():
        if population == 'student':
            people = _bulk_period_rollup(
                tenant, start_date, end_date, _student_people(tenant), fetch_student_day_records,
                gate_settings=gate_settings, now=now,
            )['people']
            return {
                'highest_attendance': _top(people, 'attendance_percent', limit, reverse=True),
                'lowest_attendance': _top(people, 'attendance_percent', limit, reverse=False),
            }
        teacher_rollup = _bulk_period_rollup(
            tenant, start_date, end_date, _teacher_people(tenant),
            lambda ids, s, e: fetch_teacher_day_records(tenant, ids, s, e), gate_settings=gate_settings, now=now,
        )
        nonteaching_rollup = _bulk_period_rollup(
            tenant, start_date, end_date, _nonteaching_people(tenant), fetch_nonteaching_staff_day_records,
            now=now, manual=True,
        )
        # A combined people list, not teachers-only: attendance-percent
        # rankings are meaningful for non-teaching staff too, while
        # hours/lateness rankings naturally exclude them since _top already
        # skips a None value for the ranked key - one list, no special-casing.
        people = _merge_staff_period_rollup(teacher_rollup, nonteaching_rollup)['people']
        return {
            'most_punctual': _top(people, 'late_arrivals', limit, reverse=False),
            'highest_attendance': _top(people, 'attendance_percent', limit, reverse=True),
            'lowest_attendance': _top(people, 'attendance_percent', limit, reverse=False),
            'highest_hours': _top(people, 'total_hours', limit, reverse=True),
            'most_late_arrivals': _top(people, 'late_arrivals', limit, reverse=True),
        }

    return _cached_term_result(tenant, f'rankings:{population}', [start_date, end_date, limit], _compute)


def class_department_comparison(tenant, population, start_date, end_date, *, now=None):
    gate_settings = get_or_create_gate_settings(tenant)

    def _compute():
        if population == 'student':
            people = _bulk_period_rollup(
                tenant, start_date, end_date, _student_people(tenant), fetch_student_day_records,
                gate_settings=gate_settings, now=now,
            )['people']
        else:
            teacher_rollup = _bulk_period_rollup(
                tenant, start_date, end_date, _teacher_people(tenant),
                lambda ids, s, e: fetch_teacher_day_records(tenant, ids, s, e), gate_settings=gate_settings, now=now,
            )
            nonteaching_rollup = _bulk_period_rollup(
                tenant, start_date, end_date, _nonteaching_people(tenant), fetch_nonteaching_staff_day_records,
                now=now, manual=True,
            )
            people = _merge_staff_period_rollup(teacher_rollup, nonteaching_rollup)['people']

        groups = {}
        for p in people:
            label = p['group_label'] or 'Unassigned'
            g = groups.setdefault(label, {'group_label': label, 'total_people': 0, 'total_present': 0, 'total_expected': 0})
            g['total_people'] += 1
            g['total_present'] += p['days_present']
            g['total_expected'] += p['expected_working_days']
        return [
            {
                'group_label': g['group_label'], 'total_people': g['total_people'], 'total_present': g['total_present'],
                'attendance_percent': attendance_percent(g['total_present'], g['total_expected']),
            }
            for g in sorted(groups.values(), key=lambda g: g['group_label'])
        ]

    return _cached_term_result(tenant, f'class_department:{population}', [start_date, end_date], _compute)


def daily_register(tenant, population, target_date, *, status_filter=None, class_group_id=None, department=None,
                    search='', page=1, page_size=PAGE_SIZE_DEFAULT, now=None):
    """Returns {"count":, "page":, "page_size":, "results": [...]}. Each
    result row's "id" is a composite "student:<uuid>" / "teacher:<uuid>" /
    "staff:<uuid>" so the frontend's View Profile action knows which
    profile endpoint to call."""
    gate_settings = get_or_create_gate_settings(tenant)
    rows = []

    if population == 'student':
        qs = StudentProfile.objects.filter(user__tenant=tenant).select_related('user', 'current_class')
        if class_group_id:
            qs = qs.filter(current_class_id=class_group_id)
        if search:
            qs = qs.filter(Q(user__first_name__icontains=search) | Q(user__last_name__icontains=search) | Q(student_id__icontains=search))
        profiles = list(qs)
        ids = [p.user_id for p in profiles]
        records = fetch_student_day_records(ids, target_date, target_date)
        by_person = _records_for_day(records, target_date, ids)
        corrections = _corrections_for_range(tenant, 'student', ids, target_date, target_date)
        date_str = target_date.isoformat()
        for profile in profiles:
            result = day_status(tenant, target_date, by_person[profile.user_id].get('clock_in_at'),
                                 by_person[profile.user_id].get('clock_out_at'), gate_settings=gate_settings, now=now)
            rows.append(_register_row(
                row_id=f"student:{profile.user_id}", name=profile.user.get_full_name(),
                identifier=profile.student_id, group_label=profile.current_class.name if profile.current_class else '',
                record=by_person[profile.user_id], result=result, tenant=tenant,
                corrected=corrections.get((str(profile.user_id), date_str)),
            ))
    else:
        teacher_qs = User.objects.filter(tenant=tenant, role='teacher')
        if search:
            teacher_qs = teacher_qs.filter(Q(first_name__icontains=search) | Q(last_name__icontains=search))
        teacher_ids = list(teacher_qs.values_list('id', flat=True))
        teacher_records = fetch_teacher_day_records(tenant, teacher_ids, target_date, target_date)
        by_teacher = _records_for_day(teacher_records, target_date, teacher_ids)
        teachers_by_id = {t.id: t for t in teacher_qs}
        teacher_corrections = _corrections_for_range(tenant, 'teacher', teacher_ids, target_date, target_date)
        date_str = target_date.isoformat()
        for teacher_id in teacher_ids:
            teacher = teachers_by_id[teacher_id]
            result = day_status(tenant, target_date, by_teacher[teacher_id].get('clock_in_at'),
                                 by_teacher[teacher_id].get('clock_out_at'), gate_settings=gate_settings, now=now)
            rows.append(_register_row(
                row_id=f"teacher:{teacher_id}", name=teacher.get_full_name(), identifier=getattr(teacher, 'email', ''),
                group_label='Teaching', record=by_teacher[teacher_id], result=result, tenant=tenant,
                corrected=teacher_corrections.get((str(teacher_id), date_str)),
            ))

        staff_qs = StaffProfile.objects.filter(tenant=tenant, staff_type=StaffProfile.NON_TEACHING)
        if department:
            staff_qs = staff_qs.filter(department=department)
        if search:
            staff_qs = staff_qs.filter(Q(first_name__icontains=search) | Q(last_name__icontains=search))
        staff_profiles = list(staff_qs)
        staff_ids = [s.id for s in staff_profiles]
        staff_records = fetch_nonteaching_staff_day_records(staff_ids, target_date, target_date)
        by_staff = _records_for_day(staff_records, target_date, staff_ids)
        staff_corrections = _corrections_for_range(tenant, 'staff', staff_ids, target_date, target_date)
        date_str = target_date.isoformat()
        for staff in staff_profiles:
            cutoff = cutoff_passed_for_day(tenant, target_date, gate_settings=gate_settings, now=now)
            result = day_status_from_manual_status(by_staff[staff.id].get('status'), target_date, cutoff)
            rows.append(_register_row(
                row_id=f"staff:{staff.id}", name=staff.full_name, identifier=staff.staff_code,
                group_label=staff.department or 'Non-teaching', record={}, result=result, tenant=tenant,
                corrected=staff_corrections.get((str(staff.id), date_str)),
            ))

    if status_filter:
        rows = [r for r in rows if r['status'] == status_filter]

    count = len(rows)
    start = (page - 1) * page_size
    return {'count': count, 'page': page, 'page_size': page_size, 'results': rows[start:start + page_size]}


def _register_row(*, row_id, name, identifier, group_label, record, result, tenant, corrected=None):
    first_arrival = None
    last_departure = None
    if record.get('clock_in_at'):
        first_arrival = _school_localtime(tenant, record['clock_in_at']).strftime('%I:%M %p').lstrip('0')
    if record.get('clock_out_at'):
        last_departure = _school_localtime(tenant, record['clock_out_at']).strftime('%I:%M %p').lstrip('0')
    return {
        'id': row_id, 'name': name, 'identifier': identifier, 'group_label': group_label,
        'first_arrival': first_arrival, 'last_departure': last_departure,
        'total_hours': result.get('hours'), 'status': result['status'],
        'corrected': corrected,
    }


def staff_profile_summary(tenant, person_id, period_start, period_end):
    """person_id is a composite "teacher:<uuid>" or "staff:<uuid>" (see
    daily_register). Returns {"kind": "teacher"|"non_teaching", "person": {...header...},
    "stats": {...compute_person_period_stats shape...}}."""
    kind, _, raw_id = person_id.partition(':')
    if kind == 'teacher':
        teacher = User.objects.filter(tenant=tenant, role='teacher', id=raw_id).first()
        if not teacher:
            return None
        profile = getattr(teacher, 'teacher_profile', None)
        hr_profile = getattr(teacher, 'hr_staff_profile', None)
        person = {
            'name': teacher.get_full_name(),
            'staff_id': getattr(profile, 'employee_id', '') if profile else '',
            'department': getattr(hr_profile, 'department', '') if hr_profile else '',
            'designation': getattr(hr_profile, 'role', 'Teacher') if hr_profile else 'Teacher',
            'employment_status': getattr(hr_profile, 'employment_status', '') if hr_profile else '',
        }
        records = fetch_teacher_day_records(tenant, [teacher.id], period_start, period_end)
        by_date = {date: v for (pid, date), v in records.items() if pid == teacher.id}
        stats = compute_person_period_stats(tenant, period_start, period_end, by_date)
        return {'kind': 'teacher', 'person': person, 'stats': stats}

    if kind == 'staff':
        staff = StaffProfile.objects.filter(tenant=tenant, id=raw_id).first()
        if not staff:
            return None
        person = {
            'name': staff.full_name, 'staff_id': staff.staff_code, 'department': staff.department,
            'designation': staff.role, 'employment_status': staff.employment_status,
        }
        records = fetch_nonteaching_staff_day_records([staff.id], period_start, period_end)
        by_date = {date: v for (pid, date), v in records.items() if pid == staff.id}
        stats = compute_person_period_stats(tenant, period_start, period_end, by_date, manual=True)
        return {'kind': 'non_teaching', 'person': person, 'stats': stats}

    return None


def staff_history(tenant, person_id, period_start, period_end, *, page=1, page_size=PAGE_SIZE_DEFAULT):
    kind, _, raw_id = person_id.partition(':')
    gate_settings = get_or_create_gate_settings(tenant)
    corrections = _corrections_for_range(tenant, 'teacher' if kind == 'teacher' else 'staff', [raw_id], period_start, period_end)
    rows = []
    for day in expected_working_days(tenant, period_start, period_end):
        if kind == 'teacher':
            records = fetch_teacher_day_records(tenant, [raw_id], day, day)
            record = records.get((raw_id, day), {})
            result = day_status(tenant, day, record.get('clock_in_at'), record.get('clock_out_at'), gate_settings=gate_settings)
        else:
            records = fetch_nonteaching_staff_day_records([raw_id], day, day)
            record = records.get((raw_id, day), {})
            result = day_status_from_manual_status(record.get('status'), day, cutoff_passed_for_day(tenant, day))
        rows.append(_register_row(
            row_id=str(day), name='', identifier='', group_label='', record=record, result=result, tenant=tenant,
            corrected=corrections.get((str(raw_id), day.isoformat())),
        ))
        rows[-1]['date'] = day.isoformat()
    rows.reverse()
    count = len(rows)
    start = (page - 1) * page_size
    return {'count': count, 'page': page, 'page_size': page_size, 'results': rows[start:start + page_size]}


def student_profile_summary(tenant, student_id, period_start, period_end):
    profile = StudentProfile.objects.filter(user__tenant=tenant, user_id=student_id).select_related('user', 'current_class').first()
    if not profile:
        return None
    person = {
        'name': profile.user.get_full_name(), 'admission_number': profile.student_id,
        'class_name': profile.current_class.name if profile.current_class else '',
        'arm': profile.current_class.section if profile.current_class else '',
    }
    records = fetch_student_day_records([student_id], period_start, period_end)
    by_date = {date: v for (pid, date), v in records.items() if pid == student_id}
    stats = compute_person_period_stats(tenant, period_start, period_end, by_date)
    return {'person': person, 'stats': stats}


def student_history(tenant, student_id, period_start, period_end, *, page=1, page_size=PAGE_SIZE_DEFAULT):
    gate_settings = get_or_create_gate_settings(tenant)
    corrections = _corrections_for_range(tenant, 'student', [student_id], period_start, period_end)
    rows = []
    for day in expected_working_days(tenant, period_start, period_end):
        records = fetch_student_day_records([student_id], day, day)
        record = records.get((student_id, day), {})
        result = day_status(tenant, day, record.get('clock_in_at'), record.get('clock_out_at'), gate_settings=gate_settings)
        row = _register_row(
            row_id=str(day), name='', identifier='', group_label='', record=record, result=result, tenant=tenant,
            corrected=corrections.get((str(student_id), day.isoformat())),
        )
        row['date'] = day.isoformat()
        rows.append(row)
    rows.reverse()
    count = len(rows)
    start = (page - 1) * page_size
    return {'count': count, 'page': page, 'page_size': page_size, 'results': rows[start:start + page_size]}


def filters_lookup(tenant, population):
    # Term and Class are both TenantAwareModel - same legacy-tenant quirk as
    # SchoolActivityCalendar (see closed_dates).
    legacy_tenant = _legacy_tenant_for_attendance(tenant)
    terms = list(Term.objects.filter(tenant=legacy_tenant).order_by('-start_date').values('id', 'name', 'is_active'))
    if population == 'student':
        classes = list(Class.objects.filter(tenant=legacy_tenant).values('id', 'name', 'section'))
        return {'classes': [{'id': str(c['id']), 'label': f"{c['name']} {c['section'] or ''}".strip()} for c in classes], 'terms': [
            {'id': str(t['id']), 'name': t['name'], 'is_active': t['is_active']} for t in terms
        ]}
    departments = list(
        StaffProfile.objects.filter(tenant=tenant, staff_type=StaffProfile.NON_TEACHING)
        .exclude(department='').values_list('department', flat=True).distinct()
    )
    return {'departments': sorted(set(departments)), 'terms': [
        {'id': str(t['id']), 'name': t['name'], 'is_active': t['is_active']} for t in terms
    ]}


# ---------------------------------------------------------------------------
# Manual attendance corrections - admin-only, audited. The brief's own
# acceptance criteria require every correction to be logged with the
# administrator's identity, timestamp and reason; core.AuditLog already
# exists for exactly this but had no caller writing a "reason" anywhere, and
# only hr.views.mark_attendance_manual (non-teaching staff) had any
# correction path at all - students and teachers had none.
# ---------------------------------------------------------------------------

CORRECTION_MODEL_NAMES = {'student': 'AttendanceRecord', 'teacher': 'TeacherAttendance', 'staff': 'StaffAttendance'}


def _upsert_student_attendance(tenant, person_id, date, *, clock_in_at=None, clock_out_at=None, status=None):
    existing = AttendanceRecord.objects.filter(student_id=person_id, date=date).first()
    previous = {
        'status': existing.status if existing else None,
        'clock_in_at': existing.clock_in_at.isoformat() if existing and existing.clock_in_at else None,
        'clock_out_at': existing.clock_out_at.isoformat() if existing and existing.clock_out_at else None,
    }
    defaults = {'tenant': _legacy_tenant_for_attendance(tenant)}
    if status == 'absent':
        defaults.update(status='absent', clock_in_at=None, clock_out_at=None)
    else:
        if status is not None:
            defaults['status'] = status
        if clock_in_at is not None:
            defaults['clock_in_at'] = clock_in_at
            defaults.setdefault('status', 'present')
        if clock_out_at is not None:
            defaults['clock_out_at'] = clock_out_at
            defaults.setdefault('status', 'present')
    obj, _created = AttendanceRecord.objects.update_or_create(student_id=person_id, date=date, defaults=defaults)
    new = {
        'status': obj.status,
        'clock_in_at': obj.clock_in_at.isoformat() if obj.clock_in_at else None,
        'clock_out_at': obj.clock_out_at.isoformat() if obj.clock_out_at else None,
    }
    return obj, previous, new


def _upsert_teacher_attendance(tenant, person_id, date, *, clock_in_at=None, clock_out_at=None, status=None):
    existing = TeacherAttendance.objects.filter(teacher_id=person_id, attendance_date=date).first()
    previous = {
        'status': existing.status if existing else None,
        'clock_in_at': existing.check_in_time.isoformat() if existing and existing.check_in_time else None,
        'clock_out_at': existing.check_out_time.isoformat() if existing and existing.check_out_time else None,
    }
    if status == 'absent':
        # check_in_time has no null=True (it's auto_now_add) - there is no
        # way to represent "absent" on a row that must always carry a
        # check-in time, and day_status() never reads the stored status
        # column anyway (see its own docstring) - only a MISSING row reads
        # as absent. Delete rather than leave a non-null check_in_time
        # behind that would make this day keep showing as present.
        if existing:
            existing.delete()
        return None, previous, {'status': 'absent', 'clock_in_at': None, 'clock_out_at': None}

    defaults = {'tenant': tenant, 'attendance_date': date}
    if status is not None:
        defaults['status'] = status
    if clock_out_at is not None:
        defaults['check_out_time'] = clock_out_at
        defaults.setdefault('status', 'present')
    obj, _created = TeacherAttendance.objects.update_or_create(teacher_id=person_id, attendance_date=date, defaults=defaults)
    if clock_in_at is not None:
        # check_in_time is auto_now_add - defaults above can't set it on a
        # newly created row (Django forces now()), same reason
        # _record_staff_scan's own extra_update two-step exists.
        TeacherAttendance.objects.filter(pk=obj.pk).update(check_in_time=clock_in_at)
        obj.refresh_from_db()
    new = {
        'status': obj.status,
        'clock_in_at': obj.check_in_time.isoformat() if obj.check_in_time else None,
        'clock_out_at': obj.check_out_time.isoformat() if obj.check_out_time else None,
    }
    return obj, previous, new


def _upsert_staff_attendance(tenant, person_id, date, *, status=None, **_ignored):
    """Non-teaching staff attendance is status-only, same as the existing
    hr.views.mark_attendance_manual - there are no clock timestamps to
    correct, so clock_in_at/clock_out_at (accepted by write_attendance_correction's
    uniform signature) are simply not meaningful here."""
    existing = StaffAttendance.objects.filter(staff_id=person_id, date=date).first()
    previous = {'status': existing.status if existing else None}
    obj, _created = StaffAttendance.objects.update_or_create(staff_id=person_id, date=date, defaults={'status': status})
    return obj, previous, {'status': obj.status}


def write_attendance_correction(tenant, actor, kind, person_id, date, reason, *, status=None, clock_in_at=None, clock_out_at=None):
    """The one place every manual attendance correction goes through,
    whichever of the three populations it's for - upserts the right model,
    then writes one core.AuditLog row in the same transaction (upsert first,
    so object_id = str(obj.pk) is always known by the time the audit row is
    written, including for a correction that creates a day's record from
    nothing). Raises ValueError for the view to turn into a 400 - never
    silently accepts an unreasoned correction, per the brief's own
    acceptance criteria."""
    reason = (reason or '').strip()
    if not reason:
        raise ValueError('A reason is required for a manual attendance correction.')
    if kind not in CORRECTION_MODEL_NAMES:
        raise ValueError(f"Unknown correction kind: {kind!r}")

    with transaction.atomic():
        if kind == 'student':
            obj, previous, new = _upsert_student_attendance(tenant, person_id, date, clock_in_at=clock_in_at, clock_out_at=clock_out_at, status=status)
        elif kind == 'teacher':
            obj, previous, new = _upsert_teacher_attendance(tenant, person_id, date, clock_in_at=clock_in_at, clock_out_at=clock_out_at, status=status)
        else:
            obj, previous, new = _upsert_staff_attendance(tenant, person_id, date, status=status)

        # obj is None for a teacher correction that deleted the row (marked
        # absent) - no real pk exists to point to, so fall back to a
        # synthetic person+date id. _corrections_for_range matches on
        # person_id+date from metadata, never on object_id, so this is only
        # ever informational.
        object_id = str(obj.pk) if obj is not None else f"{person_id}:{date.isoformat()}"
        AuditLog.objects.create(
            user=actor, tenant=tenant, action='UPDATE', model_name=CORRECTION_MODEL_NAMES[kind],
            object_id=object_id,
            metadata={
                'reason': reason, 'previous_values': previous, 'new_values': new,
                'date': date.isoformat(), 'person_id': str(person_id), 'kind': kind,
            },
        )
    return obj


def _corrections_for_range(tenant, kind, person_ids, start_date, end_date):
    """Every correction AuditLog row for `kind`'s population in
    [start_date, end_date], in ONE query, keyed by (person_id, date_iso).
    Matched on person_id+date (stored in metadata), not object_id - a
    correction that creates a day's record from nothing (e.g. marking a
    previously-absent student present) has no pre-existing object_id to
    match against, while person_id+date always exists regardless. Ordered
    oldest-first so a later re-correction of the same person+day overwrites
    an earlier one in the returned dict - the most recent reason is the one
    worth showing."""
    if not person_ids:
        return {}
    person_id_set = {str(pid) for pid in person_ids}
    rows = AuditLog.objects.filter(
        tenant=tenant, model_name=CORRECTION_MODEL_NAMES[kind], action='UPDATE',
        metadata__date__gte=start_date.isoformat(), metadata__date__lte=end_date.isoformat(),
    ).order_by('created_at').values('metadata', 'created_at', 'user__first_name', 'user__last_name')
    out = {}
    for row in rows:
        meta = row['metadata'] or {}
        pid = meta.get('person_id')
        date_str = meta.get('date')
        if pid not in person_id_set or not date_str:
            continue
        actor_name = f"{row['user__first_name'] or ''} {row['user__last_name'] or ''}".strip() or 'An administrator'
        out[(pid, date_str)] = {'reason': meta.get('reason', ''), 'actor': actor_name, 'at': row['created_at'].isoformat()}
    return out
