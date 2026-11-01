"""SchoolGate's weekly attendance SMS digest, and the daily no-show backstop
that marks a student absent once their school's gate clock-out window has
closed with nothing recorded for them.

Both are split out as plain functions (rather than being inlined into a
Celery task or a view) so each can be run two ways: a management command - a
real OS cron entry on the VPS, or by hand - and a dry run of that same
command with no other effect, which is also how to see exactly what would
happen before trusting it to run for real. See
[[project-no-celery-in-production]] for why a cron entry, not Celery beat, is
what actually runs these in production.
"""
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from django.db import IntegrityError
from django.utils import timezone

from academic.models import AttendanceRecord
from core.schoolgate import schoolgate_current_term
from core.tenant import SchoolTenant
from users.models import StudentProfile, resolve_legacy_tenant_for_school

from .models import GateSettings

# A school week is assumed to be 5 days (Monday-Friday) - the report goes out
# Friday evening, so the week is treated as complete by send time.
SCHOOL_WEEK_DAYS = 5


def weekly_summary_text(school_name, student_name, present_days, late_days):
    absent_days = max(SCHOOL_WEEK_DAYS - present_days, 0)
    attendance_pct = round((present_days / SCHOOL_WEEK_DAYS) * 100) if SCHOOL_WEEK_DAYS else 0
    return (
        f"{school_name}: {student_name} was present {present_days}/{SCHOOL_WEEK_DAYS} days this week. "
        f"Absent: {absent_days}. Late: {late_days}. Attendance: {attendance_pct}%."
    )


def weekly_report_rows(school, week_start, today):
    """One row per active student of `school`, covering every currently
    enrolled student (not just ones with a scan this week) - a student who
    never showed up all week is exactly the case this report should surface
    as "Absent: 5". Each row: {profile, phone, message, skip_reason}, where
    skip_reason is set (and message is "") when there is no guardian phone on
    file, and is "" (message is set) when there is."""
    from django.db.models import Count, Q

    legacy_tenant = resolve_legacy_tenant_for_school(school)
    counts_by_student = {}
    if legacy_tenant:
        counts_by_student = {
            row["student_id"]: row
            for row in AttendanceRecord.objects.filter(
                tenant=legacy_tenant, date__gte=week_start, date__lte=today,
            )
            .values("student_id")
            .annotate(
                present_days=Count("id", filter=Q(status__in=["present", "late", "excused"])),
                late_days=Count("id", filter=Q(status="late")),
            )
        }

    from finance.services import guardian_contacts_for_student

    profiles = StudentProfile.objects.select_related("user").filter(
        user__tenant=school, user__is_active=True,
    ).order_by("user__last_name", "user__first_name")

    rows = []
    for profile in profiles:
        counts = counts_by_student.get(profile.user_id) or {}
        phone, _email = guardian_contacts_for_student(profile)
        if not phone:
            rows.append({"profile": profile, "phone": "", "message": "", "skip_reason": "no guardian phone on file"})
            continue
        message = weekly_summary_text(
            school.name,
            profile.user.get_full_name() or profile.user.email,
            counts.get("present_days", 0),
            counts.get("late_days", 0),
        )
        rows.append({"profile": profile, "phone": phone, "message": message, "skip_reason": ""})
    return rows


def send_weekly_reports_for_school(school, *, week_start, today, send_sms, dry_run=False):
    """Send (or, with dry_run, merely describe) this week's report for every
    active student of one school. Returns {sent, skipped, failed, rows}: rows
    is every weekly_report_rows() row, each with an added "outcome" of "sent",
    "dry_run", "skipped" (no phone) or "failed: <error>" - the detail a test,
    or a person reading the command's output, needs to see exactly what
    happened without re-deriving it from the counts."""
    rows = weekly_report_rows(school, week_start, today)
    sent = skipped = failed = 0
    for row in rows:
        if not row["phone"]:
            row["outcome"] = f"skipped ({row['skip_reason']})"
            skipped += 1
            continue
        if dry_run:
            row["outcome"] = "dry_run"
            continue
        try:
            send_sms(row["phone"], row["message"])
            row["outcome"] = "sent"
            sent += 1
        except Exception as exc:
            row["outcome"] = f"failed: {exc}"
            failed += 1
    return {"sent": sent, "skipped": skipped, "failed": failed, "rows": rows}


def send_weekly_reports(*, school_code="", today=None, dry_run=False):
    """Run the digest for every active SchoolGate school, or just `school_code`.
    Returns {school.schema_name: send_weekly_reports_for_school() result}."""
    from django.conf import settings
    from django.utils import timezone

    from finance.services import send_ebulksms, send_kudisms

    send_sms = send_kudisms if settings.SCHOOLGATE_SMS_PROVIDER == "kudisms" else send_ebulksms

    today = today or timezone.localdate()
    week_start = today - timezone.timedelta(days=today.weekday())

    schools = SchoolTenant.objects.filter(product=SchoolTenant.PRODUCT_SCHOOLGATE, is_active=True)
    if school_code:
        schools = schools.filter(schema_name__iexact=school_code)

    return {
        school.schema_name: send_weekly_reports_for_school(
            school, week_start=week_start, today=today, send_sms=send_sms, dry_run=dry_run
        )
        for school in schools
    }


def _school_localtime(school, moment=None):
    """timezone.localtime(moment) converts to Django's single global
    TIME_ZONE setting (Africa/Lagos) regardless of which school is asking -
    every gate SMS, clock-in/out message, and the classify_event window
    check itself all went through that, silently ignoring
    SchoolTenant.timezone (an admin-editable per-school field, see
    _school_payload/the school settings update view) entirely. A school
    whose configured timezone differs from the platform default got SMS
    times that didn't match their own clock, and - worse - clock-in/late/
    clock-out window classification computed against the wrong "now".
    Falls back to the Django default for an empty/unrecognized zone
    string (e.g. still the field's own 'UTC' default) rather than
    raising, since a bad per-school setting must never break a scan.

    Moved here from rfid_attendance.views (which imports it back) so the
    absence-marking functions below - which have no HTTP request to hang
    off of - can use the exact same "what time is it for this school right
    now" logic as every gate scan already does, rather than a second,
    possibly-diverging copy."""
    moment = moment or timezone.now()
    tz_name = str(getattr(school, 'timezone', '') or '').strip()
    # 'UTC' is the field's own blank-state default (every school that has
    # never touched this setting sits at exactly that value) - treating it
    # as "not configured" and falling through to the platform default
    # (Africa/Lagos) avoids silently shifting every untouched school back
    # an hour. Only a school that picked something else gets honored here.
    if tz_name and tz_name != 'UTC':
        try:
            return moment.astimezone(ZoneInfo(tz_name))
        except (ZoneInfoNotFoundError, ValueError):
            pass
    return timezone.localtime(moment)


def _legacy_tenant_for_attendance(school):
    """The same slug -> tenants.Tenant mapping users.app_views._tenant_for_model
    does for a signed-in request, duplicated here (not imported) because that
    helper needs a `user` to resolve the school from - there is no user in
    this cron/management-command context, only the school itself. Auto-creates
    the legacy row exactly like _tenant_for_model does, so a school whose gate
    has never actually produced a live scan yet (and so never triggered that
    auto-create) still gets a writable AttendanceRecord.tenant value here."""
    from tenants.models import Tenant

    tenant = Tenant.objects.filter(slug__iexact=school.schema_name).first()
    if not tenant:
        tenant = Tenant.objects.create(slug=school.schema_name, name=school.name)
    return tenant


def absentee_profiles_for_school(school, today):
    """Every active student at `school` with no AttendanceRecord at all for
    `today` - one already marked present/late/excused by a real scan or a
    teacher, or already marked absent (by a teacher, or an earlier cron pass
    the same day - see mark_schoolgate_absentees), is correctly left alone;
    only a student the gate never saw and nobody else touched either is a
    candidate for this backstop."""
    marked_today = AttendanceRecord.objects.filter(
        student__tenant=school, date=today,
    ).values_list('student_id', flat=True)
    return (
        StudentProfile.objects.select_related('user', 'current_class')
        .filter(user__tenant=school, user__is_active=True)
        .exclude(user_id__in=marked_today)
        .order_by('user__last_name', 'user__first_name')
    )


def mark_absent_students_for_school(school, *, today, dry_run=False):
    """One school's pass of the SchoolGate no-show backstop (see
    mark_schoolgate_absentees for the full picture): every active student
    with no attendance record at all for `today` gets one created with
    status='absent', then the same parent SMS a teacher's manual
    absent-marking sends (users.app_views.mark_attendance's own call to
    _notify_parents_on_attendance) - except this one also passes `school=`,
    so a parent with no paid Kids Monitor subscription still gets it,
    wallet-billed, matching how every other SchoolGate gate notification
    (_send_gate_sms/_send_gate_sms_from_wallet) already guarantees a text
    either way rather than silently saying nothing.

    Returns one row per candidate student: {"profile", "outcome"}, outcome
    one of "dry_run" (dry_run=True, nothing written or sent),
    "marked_absent", or "skipped (record appeared concurrently)" for the
    rare case a real scan or manual mark lands on this exact student/date
    between the query above and this write - left alone rather than
    overwritten, and not treated as an error for everyone else still to go.
    dry_run never writes to the DB or sends SMS, so it also never triggers
    the legacy-tenant auto-create _legacy_tenant_for_attendance can do."""
    from users.app_views import _notify_parents_on_attendance

    term = schoolgate_current_term(school)
    tenant_obj = None if dry_run else _legacy_tenant_for_attendance(school)

    rows = []
    for profile in absentee_profiles_for_school(school, today):
        if dry_run:
            rows.append({'profile': profile, 'outcome': 'dry_run'})
            continue
        try:
            AttendanceRecord.objects.create(
                student=profile.user,
                date=today,
                status='absent',
                class_group=profile.current_class,
                tenant=tenant_obj,
                term=term,
                academic_year=term.academic_year if term else None,
                idempotency_key=None,
                remarks='Auto-marked absent: no attendance recorded by clock-out time.',
            )
        except IntegrityError:
            rows.append({'profile': profile, 'outcome': 'skipped (record appeared concurrently)'})
            continue
        _notify_parents_on_attendance(profile.user, 'absent', today, school.name, school=school)
        rows.append({'profile': profile, 'outcome': 'marked_absent'})
    return rows


def mark_schoolgate_absentees(*, school_code='', now=None, dry_run=False):
    """Server-side backstop for every school running an RFID gate terminal -
    anyone with a GateSettings row (see get_or_create_gate_settings in
    views.py), not limited to SchoolTenant.PRODUCT_SCHOOLGATE, since a
    full-product school with the optional gate hardware has exactly the same
    gap otherwise. Without this, a student the gate never saw, and nobody
    marked by hand either, simply has no AttendanceRecord at all for the
    day - "present by silence" rather than a true account of who actually
    came to school.

    Runs entirely on the backend, on its own schedule (see the
    mark_absentees management command's cron wiring, and
    [[project-no-celery-in-production]] for why a cron entry rather than
    Celery beat) - it never depends on the gate terminal itself being
    online, having synced its offline queue, or even being powered on; it
    only ever reads whatever attendance has already made it to the server.

    Each school is only acted on once its own clockout_end has passed in its
    own local time (_school_localtime) - a school whose window is still open
    is left alone. That makes this safe, and intended, to run often (e.g.
    every 15-30 minutes via cron) rather than needing one precisely-timed
    job per school: whichever run first finds a given day past that
    school's clockout_end is the one that does the marking, and every later
    run that same day finds nothing left to do (absentee_profiles_for_school
    excludes anyone already marked, absent included). Weekends (Saturday/
    Sunday in the school's own local time) are skipped outright - the same
    Monday-Friday assumption send_weekly_reports already makes
    (SCHOOL_WEEK_DAYS=5); there is no school-calendar/holiday model yet to
    consult for anything finer than that.

    Returns {school.schema_name: {"ran": bool, "reason": str, "rows": [...]}}."""
    now = now or timezone.now()
    gate_schools = GateSettings.objects.select_related('tenant').filter(tenant__is_active=True)
    if school_code:
        gate_schools = gate_schools.filter(tenant__schema_name__iexact=school_code)

    results = {}
    for gate_settings in gate_schools:
        school = gate_settings.tenant
        school_now = _school_localtime(school, now)
        if school_now.weekday() >= 5:
            results[school.schema_name] = {'ran': False, 'reason': 'weekend', 'rows': []}
            continue
        if school_now.time() < gate_settings.clockout_end:
            results[school.schema_name] = {'ran': False, 'reason': 'clock-out window still open', 'rows': []}
            continue
        rows = mark_absent_students_for_school(school, today=school_now.date(), dry_run=dry_run)
        results[school.schema_name] = {'ran': True, 'reason': '', 'rows': rows}
    return results
