from django.core.management.base import BaseCommand

from finance.tasks import process_token_allocation_expirations


class Command(BaseCommand):
    help = "Revoke expired token allocations and send expiry warnings. Intended to run daily via cron."

    def handle(self, *args, **options):
        result = process_token_allocation_expirations()
        self.stdout.write(
            f"expired={result['expired']} notified_7d={result['notified_7d']} notified_1d={result['notified_1d']}"
        )
