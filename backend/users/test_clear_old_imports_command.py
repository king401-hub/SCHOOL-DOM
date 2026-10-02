from io import StringIO

from django.core.management import call_command
from django.test import TestCase


class ClearOldImportsCommandTests(TestCase):
    """Smoke test for the cron-callable wrapper around users.tasks.clear_old_database_imports."""

    def test_runs_cleanly_with_no_import_jobs(self):
        out = StringIO()
        call_command("clear_old_imports", stdout=out)
        self.assertIn("deleted=0", out.getvalue())
