"""Weekly SchoolGate SMS digest - both plans get this (Basic's only SMS,
since it has no daily clock-in/out notifications; Premium gets this in
addition to those - see the gate in rfid_attendance/views.py's
_record_student_scan)."""
from celery import shared_task
from celery.utils.log import get_task_logger

logger = get_task_logger(__name__)


def _weekly_summary_text(student_name, present_days, late_days):
    if present_days == 0 and late_days == 0:
        return None
    parts = [f"present {present_days} day(s)"]
    if late_days:
        parts.append(f"late {late_days} day(s)")
    return f"Weekly attendance for {student_name}: {', '.join(parts)} this week. -SchoolDom"


@shared_task
def send_schoolgate_weekly_reports():
    """Runs Friday evening (see config/celery.py's beat schedule) - one SMS
    per student, per SchoolGate school, summarizing this week's (Monday to
    today) clock-ins. Built from actual AttendanceRecord rows only - there's
    no school-calendar concept to know how many days the school was even
    open this week, so "absent" is deliberately not reported (it would be
    guesswork), only what the gate actually recorded."""
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
                present_days=Count("id", filter=Q(status__in=["present", "excused"])),
                late_days=Count("id", filter=Q(status="late")),
            )
        }
        if not counts_by_student:
            continue

        profiles = StudentProfile.objects.select_related("user").filter(user_id__in=counts_by_student.keys())
        sent = 0
        for profile in profiles:
            counts = counts_by_student.get(profile.user_id) or {}
            message = _weekly_summary_text(
                profile.user.get_full_name() or profile.user.email,
                counts.get("present_days", 0),
                counts.get("late_days", 0),
            )
            if not message:
                continue
            phone, _email = guardian_contacts_for_student(profile)
            if not phone:
                continue
            try:
                send_ebulksms(phone, message, sender="SchoolDom")
                sent += 1
            except Exception:
                logger.exception("Weekly SchoolGate SMS to %s failed", phone)
        logger.info("Weekly SchoolGate report: %s sent %s SMS", school.schema_name, sent)
