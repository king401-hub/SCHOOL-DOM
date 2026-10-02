from django.core.management.base import BaseCommand

from academic.tasks import advance_terms


class Command(BaseCommand):
    help = "Advance any tenant whose active term has passed its end date. Intended to run daily via cron."

    def handle(self, *args, **options):
        result = advance_terms()
        self.stdout.write(
            f"advanced={result['advanced']} skipped_unresolved={result['skipped_unresolved']} errors={result['errors']}"
        )
