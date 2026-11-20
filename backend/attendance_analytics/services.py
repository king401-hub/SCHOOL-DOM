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

from django.db.models import Q

from academic.models import AttendanceRecord, Class, SchoolActivityCalendar, Term
from attendance.models import TeacherAttendance
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


# ---------------------------------------------------------------------------
# Screen-shaped entry points
# ---------------------------------------------------------------------------

def _teacher_ids(tenant):
    return list(User.objects.filter(tenant=tenant, role='teacher').values_list('id', flat=True))


def _nonteaching_staff_ids(tenant):
    return list(StaffProfile.objects.filter(tenant=tenant, staff_type=StaffProfile.NON_TEACHING).values_list('id', flat=True))


def _student_ids(tenant):
    return list(StudentProfile.objects.filter(user__tenant=tenant).values_list('user_id', flat=True))


def _staff_bulk_stats_for_day(tenant, target_date, *, gate_settings=None, now=None):
    teacher_ids = _teacher_ids(tenant)
    teacher_records = fetch_teacher_day_records(tenant, teacher_ids, target_date, target_date)
    teacher_by_person = _records_for_day(teacher_records, target_date, teacher_ids)
    teacher_stats = compute_bulk_day_stats(tenant, target_date, teacher_by_person, gate_settings=gate_settings, now=now)

    staff_ids = _nonteaching_staff_ids(tenant)
    staff_records = fetch_nonteaching_staff_day_records(staff_ids, target_date, target_date)
    staff_by_person = _records_for_day(staff_records, target_date, staff_ids)
    nonteaching_stats = compute_bulk_day_stats(tenant, target_date, staff_by_person, gate_settings=gate_settings, now=now, manual=True)

    return _merge_staff_bulk_stats(teacher_stats, nonteaching_stats)


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
        for profile in profiles:
            result = day_status(tenant, target_date, by_person[profile.user_id].get('clock_in_at'),
                                 by_person[profile.user_id].get('clock_out_at'), gate_settings=gate_settings, now=now)
            rows.append(_register_row(
                row_id=f"student:{profile.user_id}", name=profile.user.get_full_name(),
                identifier=profile.student_id, group_label=profile.current_class.name if profile.current_class else '',
                record=by_person[profile.user_id], result=result, tenant=tenant,
            ))
    else:
        teacher_qs = User.objects.filter(tenant=tenant, role='teacher')
        if search:
            teacher_qs = teacher_qs.filter(Q(first_name__icontains=search) | Q(last_name__icontains=search))
        teacher_ids = list(teacher_qs.values_list('id', flat=True))
        teacher_records = fetch_teacher_day_records(tenant, teacher_ids, target_date, target_date)
        by_teacher = _records_for_day(teacher_records, target_date, teacher_ids)
        teachers_by_id = {t.id: t for t in teacher_qs}
        for teacher_id in teacher_ids:
            teacher = teachers_by_id[teacher_id]
            result = day_status(tenant, target_date, by_teacher[teacher_id].get('clock_in_at'),
                                 by_teacher[teacher_id].get('clock_out_at'), gate_settings=gate_settings, now=now)
            rows.append(_register_row(
                row_id=f"teacher:{teacher_id}", name=teacher.get_full_name(), identifier=getattr(teacher, 'email', ''),
                group_label='Teaching', record=by_teacher[teacher_id], result=result, tenant=tenant,
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
        for staff in staff_profiles:
            cutoff = cutoff_passed_for_day(tenant, target_date, gate_settings=gate_settings, now=now)
            result = day_status_from_manual_status(by_staff[staff.id].get('status'), target_date, cutoff)
            rows.append(_register_row(
                row_id=f"staff:{staff.id}", name=staff.full_name, identifier=staff.staff_code,
                group_label=staff.department or 'Non-teaching', record={}, result=result, tenant=tenant,
            ))

    if status_filter:
        rows = [r for r in rows if r['status'] == status_filter]

    count = len(rows)
    start = (page - 1) * page_size
    return {'count': count, 'page': page, 'page_size': page_size, 'results': rows[start:start + page_size]}


def _register_row(*, row_id, name, identifier, group_label, record, result, tenant):
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
        rows.append(_register_row(row_id=str(day), name='', identifier='', group_label='', record=record, result=result, tenant=tenant))
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
    rows = []
    for day in expected_working_days(tenant, period_start, period_end):
        records = fetch_student_day_records([student_id], day, day)
        record = records.get((student_id, day), {})
        result = day_status(tenant, day, record.get('clock_in_at'), record.get('clock_out_at'), gate_settings=gate_settings)
        row = _register_row(row_id=str(day), name='', identifier='', group_label='', record=record, result=result, tenant=tenant)
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
