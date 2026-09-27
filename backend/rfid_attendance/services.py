"""SchoolGate's weekly attendance SMS digest.

Split out of tasks.py as a plain function so it can be run three ways:
Celery beat (rfid_attendance.tasks.send_schoolgate_weekly_reports, if a
worker/beat is ever actually running - see [[project-no-celery-in-production]]
for why that is not something to depend on in this project), the
`send_weekly_reports` management command (a real OS cron entry on the VPS, or
by hand), and a dry run of that same command with no other effect - which is
also how to see exactly what a parent would be sent before trusting it to
actually go out.
"""
from academic.models import AttendanceRecord
from core.tenant import SchoolTenant
from users.models import StudentProfile, resolve_legacy_tenant_for_school

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
