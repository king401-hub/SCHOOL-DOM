"""Periodic Celery tasks for the finance module."""
from celery import shared_task
from celery.utils.log import get_task_logger

logger = get_task_logger(__name__)


@shared_task(bind=True, max_retries=5, default_retry_delay=120)
def provision_parent_dva_task(self, parent_user_id):
    """
    Auto-provision a Paystack dedicated virtual account for a newly created parent.
    Retries up to 5 times (every 2 min) if Paystack is temporarily unavailable.
    Silently skips if the parent already has a DVA or the school has no subaccount yet.
    """
    from users.models import User
    from finance.models import ParentVirtualAccount
    from finance.services import provision_parent_virtual_account

    try:
        parent_user = User.objects.select_related("tenant").get(id=parent_user_id, role="parent")
    except User.DoesNotExist:
        logger.warning("provision_parent_dva_task: user %s not found or not a parent", parent_user_id)
        return {"status": "skipped", "reason": "user_not_found"}

    if ParentVirtualAccount.objects.filter(parent=parent_user, is_active=True).exists():
        return {"status": "skipped", "reason": "already_has_dva"}

    if not getattr(parent_user, "tenant", None):
        logger.warning("provision_parent_dva_task: parent %s has no tenant", parent_user_id)
        return {"status": "skipped", "reason": "no_tenant"}

    try:
        vac, created = provision_parent_virtual_account(parent_user, actor=None)
        logger.info(
            "provision_parent_dva_task: %s DVA %s for parent %s",
            "created" if created else "found",
            vac.account_number,
            parent_user.email,
        )
        return {"status": "ok", "created": created, "account_number": vac.account_number}
    except RuntimeError as exc:
        msg = str(exc)
        if "no Paystack subaccount" in msg or "PAYSTACK_SECRET_KEY" in msg:
            # School not configured yet — don't retry, admin must set up subaccount first
            logger.info("provision_parent_dva_task: skipped for %s — %s", parent_user.email, msg)
            return {"status": "skipped", "reason": msg}
        logger.warning("provision_parent_dva_task: retrying for %s — %s", parent_user.email, msg)
        raise self.retry(exc=exc)
    except Exception as exc:
        logger.error("provision_parent_dva_task: error for %s — %s", parent_user_id, exc)
        raise self.retry(exc=exc)


@shared_task(bind=True, max_retries=3, default_retry_delay=300)
def auto_assign_monthly_credits(self):
    """
    Run on the 1st of each month.
    For every school that has auto-assignment enabled, deduct tokens from
    the pool and extend active_until for eligible inactive students.
    """
    from core.models import SchoolTenant
    from finance.services import run_configured_monthly_auto_assignment

    tenants = SchoolTenant.objects.filter(is_active=True)
    total_assigned = 0
    errors = []

    for tenant in tenants:
        try:
            result = run_configured_monthly_auto_assignment(tenant)
            if result.get("ran"):
                logger.info("auto_assign_monthly_credits: tenant=%s assigned=%d", tenant.schema_name, result["assigned"])
                total_assigned += result["assigned"]
        except Exception as exc:
            logger.error("auto_assign_monthly_credits: tenant=%s error=%s", tenant.schema_name, exc)
            errors.append({"tenant": tenant.schema_name, "error": str(exc)})

    logger.info("auto_assign_monthly_credits complete: total_assigned=%d errors=%d", total_assigned, len(errors))
    return {"total_assigned": total_assigned, "errors": errors}


@shared_task(bind=True, max_retries=3, default_retry_delay=600)
def send_overdue_fee_reminders(self):
    """
    Run weekly. Send WhatsApp/SMS reminders to guardians of students with
    overdue or pending fees that have passed their due date.
    """
    from finance.services import send_fee_reminders

    try:
        sent = send_fee_reminders()
        logger.info("send_overdue_fee_reminders complete: sent=%d", len(sent))
        return {"total_sent": len(sent)}
    except Exception as exc:
        logger.error("send_overdue_fee_reminders error: %s", exc)
        raise self.retry(exc=exc)


@shared_task(bind=True, max_retries=2, default_retry_delay=120)
def flag_inactive_students(self):
    """
    Run daily. Flag students whose activation credit has expired and
    notify school admins. Mirrors update_student_activation_alerts
    so it runs even on days no admin opens the finance dashboard.
    """
    from core.models import SchoolTenant
    from finance.services import update_student_activation_alerts

    tenants = SchoolTenant.objects.filter(is_active=True)
    total_flagged = 0

    for tenant in tenants:
        try:
            flagged = update_student_activation_alerts(tenant)
            total_flagged += flagged
        except Exception as exc:
            logger.error("flag_inactive_students: tenant=%s error=%s", tenant.schema_name, exc)

    logger.info("flag_inactive_students complete: total_flagged=%d", total_flagged)
    return {"total_flagged": total_flagged}


# (days left threshold, milestone name) — checked most-urgent first; only the
# highest-urgency milestone that's due AND not yet sent fires on any given run,
# so a short-lived allocation created with 2 days left gets the "1 day" notice
# and never a redundant "7 days" one. Mirrors core.tasks.send_compliance_reminders.
@shared_task
def process_token_allocation_expirations():
    """
    Run daily. For every open (non-expired, non-revoked) TokenAllocation:
    - past its expiry date: revoke it (deduct its credits from the pool
      balance - this is what actually removes the school's access, since that
      balance is what gates student activation), notify the school + the
      SchoolDom team once.
    - within 1 day of expiry and not yet warned at that stage: send the
      "expires tomorrow" notice.
    - else within 7 days and not yet warned at that stage: send the
      "expires in a week" notice.
    """
    from django.conf import settings
    from django.core.mail import send_mail
    from django.utils import timezone

    from finance.models import TokenAllocation
    from finance.services import record_finance_activity
    from notifications.models import Notification
    from users.models import User

    today = timezone.localdate()
    now = timezone.now()
    support_email = str(getattr(settings, "SCHOOLDOM_SUPPORT_EMAIL", "") or "support@schooldom.academy").strip()

    expired_count = 0
    notified_7d = 0
    notified_1d = 0

    allocations = (
        TokenAllocation.objects.filter(expires_at__isnull=False, revoked_at__isnull=True)
        .select_related("tenant", "pool")
    )
    for allocation in allocations:
        school = allocation.tenant
        days_left = (allocation.expires_at - today).days
        admins = list(
            User.objects.filter(
                tenant=school, role__in=["school_admin", "principal", "school_superadmin"], is_active=True,
            )
        )
        recipient = (admins[0].email if admins else "") or school.email or ""

        if days_left < 0:
            pool = allocation.pool
            pool.balance = max(0, pool.balance - allocation.credits)
            pool.save(update_fields=["balance", "updated_at"])
            allocation.revoked_at = now
            allocation.notified_expired_at = now
            allocation.save(update_fields=["revoked_at", "notified_expired_at", "updated_at"])
            record_finance_activity(
                school, None, "token_allocation_expired",
                f"{allocation.credits} tokens expired and were revoked from the pool balance.",
                reference=str(allocation.id),
                metadata={"credits": allocation.credits},
            )
            expired_count += 1

            if recipient:
                try:
                    send_mail(
                        "Your SchoolDom token allocation has expired",
                        (
                            f"Hello,\n\nThe {allocation.credits}-token allocation for {school.name} "
                            f"(started {allocation.start_date}) expired on {allocation.expires_at} and has "
                            "been removed from your balance. Students may lose activation access.\n\n"
                            "Log in to the school-superadmin token page or contact support to renew it."
                        ),
                        settings.DEFAULT_FROM_EMAIL, [recipient], fail_silently=True,
                    )
                except Exception:
                    logger.warning("Token expiry email failed for school %s.", school.schema_name, exc_info=True)
            try:
                send_mail(
                    f"Token allocation expired: {school.name}",
                    f"{school.name} ({school.schema_name}) had a {allocation.credits}-token allocation expire "
                    f"on {allocation.expires_at} and it was revoked from the pool balance.",
                    settings.DEFAULT_FROM_EMAIL, [support_email], fail_silently=True,
                )
            except Exception:
                logger.warning("Token expiry support email failed for school %s.", school.schema_name, exc_info=True)

            for admin in admins:
                try:
                    Notification.objects.create(
                        tenant=school, user=admin,
                        title="Token allocation expired",
                        message=f"Your {allocation.credits}-token allocation expired on {allocation.expires_at} and needs to be renewed.",
                        notification_type="alert", priority=4, channel="in_app",
                        event_type="token_allocation_expired", action_text="Renew tokens",
                        is_delivered=True, delivered_at=now,
                    )
                except Exception:
                    logger.warning("Token expiry in-app notice failed for school %s.", school.schema_name, exc_info=True)
            continue

        if days_left <= 1 and not allocation.notified_1d_at:
            stage, subject_days = "1d", "tomorrow"
        elif days_left <= TokenAllocation.EXPIRING_SOON_WINDOW_DAYS and not allocation.notified_7d_at:
            stage, subject_days = "7d", f"in {days_left} day(s)"
        else:
            continue

        if recipient:
            try:
                send_mail(
                    f"Your SchoolDom tokens expire {subject_days}",
                    (
                        f"Hello,\n\nThe {allocation.credits}-token allocation for {school.name} expires "
                        f"{subject_days} (on {allocation.expires_at}). Renew it before then to avoid students "
                        "losing activation access."
                    ),
                    settings.DEFAULT_FROM_EMAIL, [recipient], fail_silently=True,
                )
            except Exception:
                logger.warning("Token %s reminder email failed for school %s.", stage, school.schema_name, exc_info=True)
        for admin in admins:
            try:
                Notification.objects.create(
                    tenant=school, user=admin,
                    title="Tokens expiring soon",
                    message=f"Your {allocation.credits}-token allocation expires {subject_days}.",
                    notification_type="reminder", priority=3, channel="in_app",
                    event_type="token_allocation_expiring", action_text="Renew tokens",
                    is_delivered=True, delivered_at=now,
                )
            except Exception:
                logger.warning("Token %s reminder in-app notice failed for school %s.", stage, school.schema_name, exc_info=True)

        if stage == "1d":
            allocation.notified_1d_at = now
            allocation.save(update_fields=["notified_1d_at"])
            notified_1d += 1
        else:
            allocation.notified_7d_at = now
            allocation.save(update_fields=["notified_7d_at"])
            notified_7d += 1

    logger.info(
        "process_token_allocation_expirations complete: expired=%d notified_7d=%d notified_1d=%d",
        expired_count, notified_7d, notified_1d,
    )
    return {"expired": expired_count, "notified_7d": notified_7d, "notified_1d": notified_1d}
