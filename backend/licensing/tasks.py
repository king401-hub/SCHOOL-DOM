"""Periodic sweep that flips lapsed licenses to 'expired'.

This keeps the `status` field accurate for list views/notifications, but is
NOT what actually gates access - CBTLicense.is_currently_active and
services.has_active_cbt_license() both re-check expires_at against the live
clock on every request regardless of whether this sweep has run yet, so a
license is never usable past its expiry just because this task hasn't
caught up. Mirrors core/tasks.py:13 send_compliance_reminders's shape.
"""
from celery import shared_task
from celery.utils.log import get_task_logger

logger = get_task_logger(__name__)


@shared_task
def sweep_expired_licenses():
    from django.utils import timezone

    from .models import CBTLicense

    updated = CBTLicense.objects.filter(
        status=CBTLicense.STATUS_ACTIVE, expires_at__lte=timezone.now(),
    ).update(status=CBTLicense.STATUS_EXPIRED, updated_at=timezone.now())
    if updated:
        logger.info("Marked %d CBT license(s) expired.", updated)
    return {"expired": updated}
