from django.core.management.base import BaseCommand

from core.models import SchoolTenant
from finance.services import (
    ensure_monthly_credit_reminder,
    run_configured_monthly_auto_assignment,
    update_student_activation_alerts,
)


class Command(BaseCommand):
    help = "Process student activation credit alerts, reminders, and monthly auto-assignment."

    def handle(self, *args, **options):
        schools = SchoolTenant.objects.filter(is_active=True)
        for school in schools:
            flagged = update_student_activation_alerts(school)
            ensure_monthly_credit_reminder(school)
            try:
                auto_result = run_configured_monthly_auto_assignment(school)
            except ValueError as exc:
                self.stdout.write(self.style.WARNING(f"{school.schema_name}: auto-assignment skipped: {exc}"))
                auto_result = {"assigned": 0, "ran": False}
            self.stdout.write(
                f"{school.schema_name}: flagged={flagged}, auto_assigned={auto_result.get('assigned', 0)}"
            )
