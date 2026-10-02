from django.core.management.base import BaseCommand

from inventory.tasks import (
    check_expiring_warranties,
    check_low_stock_levels,
    check_overdue_borrowed_items,
    check_scheduled_maintenance,
)


class Command(BaseCommand):
    help = "Run all four inventory alert sweeps (low stock, warranties, overdue items, maintenance). Intended to run daily via cron."

    def handle(self, *args, **options):
        low_stock = check_low_stock_levels()
        warranties = check_expiring_warranties()
        overdue = check_overdue_borrowed_items()
        maintenance = check_scheduled_maintenance()
        self.stdout.write(f"low_stock: notified={low_stock['notified']}")
        self.stdout.write(f"warranties: expired={warranties['expired']} warned={warranties['warned']}")
        self.stdout.write(f"overdue_items: flagged={overdue['flagged']}")
        self.stdout.write(f"maintenance: notified={maintenance['notified']}")
