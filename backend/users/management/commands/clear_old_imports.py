from django.core.management.base import BaseCommand

from users.tasks import clear_old_database_imports


class Command(BaseCommand):
    help = "Delete DatabaseImportJob records (and uploaded files) older than 7 days. Intended to run daily via cron."

    def handle(self, *args, **options):
        result = clear_old_database_imports()
        self.stdout.write(f"deleted={result['deleted']}")
