import os

from celery import Celery
from celery.schedules import crontab


os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

app = Celery("schooldom")
app.config_from_object("django.conf:settings", namespace="CELERY")
app.autodiscover_tasks()

app.conf.beat_schedule = {
    # 1st of every month at 00:05 — assign credits to eligible inactive students
    "auto-assign-monthly-credits": {
        "task": "finance.tasks.auto_assign_monthly_credits",
        "schedule": crontab(day_of_month=1, hour=0, minute=5),
    },
    # Every Monday at 08:00 — send overdue fee reminders via WhatsApp/SMS
    "send-overdue-fee-reminders": {
        "task": "finance.tasks.send_overdue_fee_reminders",
        "schedule": crontab(day_of_week=1, hour=8, minute=0),
    },
    # Daily at 01:00 — flag students whose activation credit has expired
    "flag-inactive-students": {
        "task": "finance.tasks.flag_inactive_students",
        "schedule": crontab(hour=1, minute=0),
    },
    # Daily at 07:00 — remind schools with incomplete compliance docs, suspend at 30 days
    "send-compliance-reminders": {
        "task": "core.tasks.send_compliance_reminders",
        "schedule": crontab(hour=7, minute=0),
    },
    # Daily at 02:00 — purge database import records older than 7 days
    "clear-old-database-imports": {
        "task": "users.tasks.clear_old_database_imports",
        "schedule": crontab(hour=2, minute=0),
    },
    # Daily at 00:30 — advance any school whose active term has ended into
    # its next term (if one is already configured), flag it if not, and
    # queue a school-wide transition popup either way.
    "advance-terms": {
        "task": "academic.tasks.advance_terms",
        "schedule": crontab(hour=0, minute=30),
    },
    # Daily at 06:00 — expire due token allocations (revokes pool credits) and
    # send staged 7-day/1-day/expired notices
    "process-token-allocation-expirations": {
        "task": "finance.tasks.process_token_allocation_expirations",
        "schedule": crontab(hour=6, minute=0),
    },
    # Every 15 minutes — re-send payment receipts that never reached the parent
    # (SMS gateway down, mail server refused, worker died mid-send). Channels
    # that already delivered are skipped, so this can never double-notify.
    "retry-failed-payment-receipts": {
        "task": "finance.tasks.retry_failed_payment_receipts",
        "schedule": crontab(minute="*/15"),
    },
    # Every 5 minutes — re-dispatch any queued request stuck without a live
    # Celery task (e.g. Redis was restarted and lost in-flight task state).
    # QueuedRequest rows live in Postgres, so this is the safety net that
    # guarantees no pending request is lost even if broker state is.
    "reconcile-stuck-requests": {
        "task": "request_queue.tasks.reconcile_stuck_requests",
        "schedule": crontab(minute="*/5"),
    },
    # Daily at 03:00 — notify admins once when an item's available quantity
    # drops to/below its reorder level.
    "inventory-check-low-stock": {
        "task": "inventory.tasks.check_low_stock_levels",
        "schedule": crontab(hour=3, minute=0),
    },
    # Daily at 03:15 — 7-day warning + expired notice for item warranties.
    "inventory-check-expiring-warranties": {
        "task": "inventory.tasks.check_expiring_warranties",
        "schedule": crontab(hour=3, minute=15),
    },
    # Daily at 03:30 — flag borrowed items past their expected return date.
    "inventory-check-overdue-borrowed-items": {
        "task": "inventory.tasks.check_overdue_borrowed_items",
        "schedule": crontab(hour=3, minute=30),
    },
    # Daily at 03:45 — notify when scheduled maintenance is due or overdue.
    "inventory-check-scheduled-maintenance": {
        "task": "inventory.tasks.check_scheduled_maintenance",
        "schedule": crontab(hour=3, minute=45),
    },
}
