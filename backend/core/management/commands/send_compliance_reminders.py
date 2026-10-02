from django.core.management.base import BaseCommand

from core.tasks import send_compliance_reminders


class Command(BaseCommand):
    help = "Nudge schools with outstanding compliance documents and suspend any past the 30-day deadline. Intended to run daily via cron."

    def handle(self, *args, **options):
        result = send_compliance_reminders()
        self.stdout.write(
            f"reminders_sent={result['reminders_sent']} suspended={result['suspended']} "
            f"skipped_no_recipient={result['skipped_no_recipient']}"
        )
