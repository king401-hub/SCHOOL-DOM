"""Weekly SchoolGate SMS digest - both plans get this (Basic's only SMS,
since it has no daily clock-in/out notifications; Premium gets this in
addition to those - see the gate in rfid_attendance/views.py's
_record_student_scan). Normally sent via KudiSMS, same as SchoolGate's
other SMS - see finance.services.send_kudisms for why SchoolGate uses a
separate provider from the rest of the platform's eBulkSMS - but actually
follows settings.SCHOOLGATE_SMS_PROVIDER like the other SchoolGate SMS
call sites, so the whole product can be rotated onto eBulkSMS at once
(e.g. while KudiSMS's sender ID is still pending approval).

The actual work is in services.send_weekly_reports - this task is kept as a
thin wrapper for config/celery.py's beat schedule, in case a Celery
worker/beat is ever confirmed running in production. Do not depend on this
task actually firing: see [[project-no-celery-in-production]] - beat_schedule
entries are unconfirmed in prod. The `send_weekly_reports` management command
runs the same function without needing Celery at all, and is what an OS cron
entry on the VPS should call instead."""
from celery import shared_task
from celery.utils.log import get_task_logger

from .services import send_weekly_reports

logger = get_task_logger(__name__)


@shared_task
def send_schoolgate_weekly_reports():
    """Runs Friday evening (see config/celery.py's beat schedule)."""
    results = send_weekly_reports()
    for schema_name, result in results.items():
        logger.info("Weekly SchoolGate report: %s sent %s SMS", schema_name, result["sent"])
