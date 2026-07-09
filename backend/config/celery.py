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
}
