"""Preview or run the term-close/arrears-carry-forward step by hand.

close_term_finance normally runs on its own, from two places: academic.models.
check_and_advance_term_transition calls it the moment a term's end_date passes
(checked nightly and on every admin dashboard load - see
[[project-no-celery-in-production]] for why dashboard-load matters here too),
and users.app_views.school_settings calls it the moment an admin switches the
active term by hand from School Settings (creating/activating a different
Term row there - just editing the current term's own dates does not count).
This command exists for the cases neither automatic path covers:

    python manage.py close_term_finance --term <term-id> --next-term <term-id>
        Dry run: prints exactly which students would get an arrears fee, and
        how much, without writing anything or deactivating any class fee.
        Use this to see what closing a term would do before trusting it.

    python manage.py close_term_finance --term <term-id> --next-term <term-id> --commit
        Does it for real. Needed when a term's transition already happened
        before this feature existed (or its automatic call failed and was
        logged rather than raised - see check_and_advance_term_transition),
        leaving that term's unpaid balances never carried forward.

Both --term and --next-term accept a Term's UUID.
"""
from django.core.management.base import BaseCommand, CommandError

from academic.models import Term
from finance.services import close_term_finance


class Command(BaseCommand):
    help = "Close one term's finance and carry unpaid balances forward as arrears (dry run unless --commit is given)."

    def add_arguments(self, parser):
        parser.add_argument("--term", required=True, help="UUID of the term to close.")
        parser.add_argument("--next-term", required=True, help="UUID of the term its arrears should carry into.")
        parser.add_argument("--commit", action="store_true", help="Actually create arrears fees and deactivate class fees. Without this it only prints what would happen.")

    def handle(self, *args, **options):
        try:
            closing_term = Term.objects.get(id=options["term"])
        except (Term.DoesNotExist, ValueError, TypeError) as exc:
            raise CommandError(f"--term {options['term']!r} is not a real term: {exc}")
        try:
            next_term = Term.objects.get(id=options["next_term"])
        except (Term.DoesNotExist, ValueError, TypeError) as exc:
            raise CommandError(f"--next-term {options['next_term']!r} is not a real term: {exc}")

        from core.tenant import SchoolTenant

        school = SchoolTenant.objects.filter(schema_name__iexact=closing_term.tenant.slug).first() if closing_term.tenant else None

        result = close_term_finance(closing_term, next_term, school=school, dry_run=not options["commit"])

        self.stdout.write(f"Closing: {closing_term.name}  ->  Next: {next_term.name}")
        self.stdout.write(f"Class fees to deactivate: {result['class_fees_deactivated']}")
        self.stdout.write(f"Students with arrears: {result['students_with_arrears']}  (total ₦{result['total_arrears']:,.2f})")
        for row in result["rows"]:
            name = row["profile"].user.get_full_name() or row["profile"].user.email
            self.stdout.write(f"  {name}: ₦{row['amount']:,.2f}")

        if not options["commit"]:
            self.stdout.write(self.style.WARNING("\nDry run - nothing was written. Add --commit to run for real."))
