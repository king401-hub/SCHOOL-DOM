"""Weekly SchoolGate SMS digest - both plans get this (Basic's only SMS,
since it has no daily clock-in/out notifications; Premium gets this in
addition to those - see the gate in rfid_attendance/views.py's
_record_student_scan)."""
from celery import shared_task
from celery.utils.log import get_task_logger

logger = get_task_logger(__name__)


# A school week is assumed to be 5 days (Monday-Friday) - the report goes
# out Friday evening, so the week is treated as complete by send time.
SCHOOL_WEEK_DAYS = 5


def _weekly_summary_text(school_name, student_name, present_days, late_days):
    absent_days = max(SCHOOL_WEEK_DAYS - present_days, 0)
    attendance_pct = round((present_days / SCHOOL_WEEK_DAYS) * 100) if SCHOOL_WEEK_DAYS else 0
    return (
        f"{school_name}: {student_name} was present {present_days}/{SCHOOL_WEEK_DAYS} days this week. "
        f"Absent: {absent_days}. Late: {late_days}. Attendance: {attendance_pct}%."
    )


@shared_task
def send_schoolgate_weekly_reports():
    """Runs Friday evening (see config/celery.py's beat schedule) - one SMS
    per active student, per SchoolGate school, covering every currently
    enrolled student (not just ones with a scan this week), since a student
    who never showed up all week is exactly the case this report should
    surface as "Absent: 5"."""
    from django.db.models import Count, Q
    from django.utils import timezone

    from academic.models import AttendanceRecord
    from core.tenant import SchoolTenant
    from finance.services import guardian_contacts_for_student, send_ebulksms
    from users.models import StudentProfile, resolve_legacy_tenant_for_school

    today = timezone.localdate()
    week_start = today - timezone.timedelta(days=today.weekday())

    schools = SchoolTenant.objects.filter(product=SchoolTenant.PRODUCT_SCHOOLGATE, is_active=True)
    for school in schools:
        legacy_tenant = resolve_legacy_tenant_for_school(school)
        if not legacy_tenant:
            continue

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

        profiles = StudentProfile.objects.select_related("user").filter(
            user__tenant=school, user__is_active=True,
        )
        sent = 0
        for profile in profiles:
            counts = counts_by_student.get(profile.user_id) or {}
            phone, _email = guardian_contacts_for_student(profile)
            if not phone:
                continue
            message = _weekly_summary_text(
                school.name,
                profile.user.get_full_name() or profile.user.email,
                counts.get("present_days", 0),
                counts.get("late_days", 0),
            )
            try:
                send_ebulksms(phone, message, sender="SchoolDom")
                sent += 1
            except Exception:
                logger.exception("Weekly SchoolGate SMS to %s failed", phone)
        logger.info("Weekly SchoolGate report: %s sent %s SMS", school.schema_name, sent)
