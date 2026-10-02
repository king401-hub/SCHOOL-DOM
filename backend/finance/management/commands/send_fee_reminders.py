from django.core.management.base import BaseCommand

from finance.services import send_fee_reminders


class Command(BaseCommand):
    help = "Send reminders to guardians of students with overdue/pending fees past their due date. Intended to run weekly via cron."

    def handle(self, *args, **options):
        # Calls the service directly rather than finance.tasks.send_overdue_fee_reminders:
        # that task is bind=True and calls self.retry() on failure, which needs a
        # live Celery broker to actually reschedule - without one it would just
        # raise a fresh connection error instead of the real exception.
        sent = send_fee_reminders()
        self.stdout.write(f"sent={len(sent)}")
