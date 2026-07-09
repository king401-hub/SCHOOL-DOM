"""Periodic Celery tasks for school compliance reminders and suspensions."""
from celery import shared_task
from celery.utils.log import get_task_logger

logger = get_task_logger(__name__)

# (days since signup, reminder stage) — stage is stored on the school so a re-run
# the same day (or a late run) doesn't resend a reminder already sent.
REMINDER_MILESTONES = [(7, 1), (14, 2), (21, 3), (28, 4)]
SUSPENSION_DAYS = 30


@shared_task
def send_compliance_reminders():
    """
    Daily check: nudge schools that haven't finished their compliance documents,
    and suspend sign-in for any that hit the 30-day deadline without completing them.
    Schools that have submitted (or been approved) are excluded — the clock is only
    about getting the documents in, not about how long review takes.
    """
    from django.conf import settings
    from django.core.mail import send_mail
    from django.utils import timezone

    from core.models import SchoolTenant
    from users.models import User

    now = timezone.now()
    support_email = str(getattr(settings, "SCHOOLDOM_SUPPORT_EMAIL", "") or "support@schooldom.academy").strip()
    reminders_sent = 0
    suspended = 0
    skipped_no_recipient = 0

    schools = SchoolTenant.objects.filter(is_active=True, compliance_status__in=["not_submitted", "rejected"])
    for school in schools:
        director = (
            User.objects.filter(tenant=school, role__in=["school_admin", "principal", "school_superadmin"])
            .order_by("created_at")
            .first()
        )
        recipient = (director.email if director else "") or school.email or ""
        if not recipient:
            skipped_no_recipient += 1
            continue

        days = (now - school.compliance_deadline_reference()).days

        if days >= SUSPENSION_DAYS:
            school.is_active = False
            school.compliance_suspended_at = now
            school.save(update_fields=["is_active", "compliance_suspended_at"])
            try:
                send_mail(
                    "Your SchoolDom account has been suspended",
                    (
                        f"Hello,\n\nYour school ({school.name}) has not completed its compliance documents "
                        f"{SUSPENSION_DAYS} days after signing up, so sign-in for your school has been suspended.\n\n"
                        "Please contact support@schooldom.academy to resolve this and regain access."
                    ),
                    settings.DEFAULT_FROM_EMAIL,
                    [recipient],
                    fail_silently=True,
                )
                send_mail(
                    f"School suspended for missing compliance documents: {school.name}",
                    f"{school.name} ({school.schema_name}) was auto-suspended after {SUSPENSION_DAYS} days without completing compliance documents.",
                    settings.DEFAULT_FROM_EMAIL,
                    [support_email],
                    fail_silently=True,
                )
            except Exception:
                logger.warning("Suspension email failed for school %s.", school.schema_name, exc_info=True)
            suspended += 1
            continue

        stage_due = 0
        for milestone_days, stage in REMINDER_MILESTONES:
            if days >= milestone_days:
                stage_due = stage
        if stage_due and school.compliance_reminder_stage < stage_due:
            days_left = max(SUSPENSION_DAYS - days, 0)
            try:
                send_mail(
                    "Action required: complete your SchoolDom compliance documents",
                    (
                        f"Hello,\n\nYour school ({school.name}) still needs to upload its compliance documents "
                        "(CAC certificate, school entrance photo, proof of address, and the director's ID/address/passport photo) "
                        "in School Settings.\n\n"
                        f"You have {days_left} day(s) left before sign-in for your school is suspended.\n\n"
                        "Log in and open Settings to finish this."
                    ),
                    settings.DEFAULT_FROM_EMAIL,
                    [recipient],
                    fail_silently=True,
                )
            except Exception:
                logger.warning("Compliance reminder email failed for school %s.", school.schema_name, exc_info=True)
            school.compliance_reminder_stage = stage_due
            school.save(update_fields=["compliance_reminder_stage"])
            reminders_sent += 1

    return {"reminders_sent": reminders_sent, "suspended": suspended, "skipped_no_recipient": skipped_no_recipient}
