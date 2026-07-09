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
