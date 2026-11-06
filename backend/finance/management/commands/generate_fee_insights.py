from django.core.management.base import BaseCommand

from finance.services import generate_fee_insight_notifications


class Command(BaseCommand):
    help = (
        "Notify each school's admins (via the in-app notification bell) when students have fees "
        "past their due date, with a short AI-phrased heads-up. Deduped per school for 7 days. "
        "Intended to run daily via cron."
    )

    def handle(self, *args, **options):
        created = generate_fee_insight_notifications()
        self.stdout.write(f"notifications_created={created}")
