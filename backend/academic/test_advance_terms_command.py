from io import StringIO

from django.core.management import call_command
from django.test import TestCase


class AdvanceTermsCommandTests(TestCase):
    """Smoke test for the cron-callable wrapper around academic.tasks.advance_terms."""

    def test_runs_cleanly_with_no_terms(self):
        out = StringIO()
        call_command("advance_terms", stdout=out)
        self.assertIn("advanced=0", out.getvalue())
