from django.core.management.base import BaseCommand

from finance.services import generate_due_subscription_invoices


class Command(BaseCommand):
    """Runs the anniversary billing engine's daily job: bills every student
    subscription whose own next_billing_date has arrived, and cancels any
    subscription belonging to a withdrawn student. Meant to run once a day
    from cron - this project runs no Celery in production - e.g.:
        0 1 * * * cd /root/SCHOOL-DOM && ./venv/bin/python manage.py generate_due_subscription_invoices --commit
    Safe to run more than once a day or to overlap with another run: each
    subscription is locked and re-checked before billing, and the database
    itself refuses a second invoice for the same (subscription, due_date)."""

    help = "Generate due recurring-subscription invoices. Dry-run by default."

    def add_arguments(self, parser):
        parser.add_argument("--commit", action="store_true", help="Actually generate invoices. Without this, only reports what would be generated.")

    def handle(self, *args, **options):
        commit = options.get("commit", False)
        result = generate_due_subscription_invoices(dry_run=not commit)

        generated = result["generated"]
        cancelled = result["cancelled"]

        if not generated and not cancelled:
            self.stdout.write("No subscriptions due - nothing to do.")
            return

        verb = "Generated" if commit else "Would generate"
        self.stdout.write(f"{verb} {len(generated)} invoice(s) for due subscription(s).")
        if cancelled:
            self.stdout.write(f"Cancelled {len(cancelled)} subscription(s) belonging to withdrawn student(s).")
        if not commit:
            self.stdout.write("\nDry run only - re-run with --commit to actually generate these invoices.")
