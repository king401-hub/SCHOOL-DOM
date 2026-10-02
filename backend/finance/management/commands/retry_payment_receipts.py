from django.core.management.base import BaseCommand

from finance.tasks import retry_failed_payment_receipts


class Command(BaseCommand):
    help = "Re-attempt payment receipts that never reached the parent (SMS/email). Intended to run every 15 minutes via cron."

    def handle(self, *args, **options):
        result = retry_failed_payment_receipts()
        self.stdout.write(str(result))
