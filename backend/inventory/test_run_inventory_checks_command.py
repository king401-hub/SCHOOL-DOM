from io import StringIO

from django.core.management import call_command
from django.test import TestCase


class RunInventoryChecksCommandTests(TestCase):
    """Smoke test for the cron-callable wrapper bundling the four inventory.tasks checks."""

    def test_runs_cleanly_with_no_items(self):
        out = StringIO()
        call_command("run_inventory_checks", stdout=out)
        output = out.getvalue()
        self.assertIn("low_stock: notified=0", output)
        self.assertIn("warranties: expired=0 warned=0", output)
        self.assertIn("overdue_items: flagged=0", output)
        self.assertIn("maintenance: notified=0", output)
