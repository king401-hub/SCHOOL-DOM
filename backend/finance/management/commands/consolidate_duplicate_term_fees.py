from collections import defaultdict
from decimal import Decimal

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from finance.models import SchoolFee
from finance.services import fee_paid_amount


class Command(BaseCommand):
    """One-off cleanup for a school that re-billed the same obligation more
    than once under slightly different titles - e.g. 'FIRST TERM 26/27',
    'FIRST TERM 2026/2027' and 'FIRST TERM 26/27 2026/2027' for what was
    meant to be one First Term fee per student. Unlike merge_duplicate_bills
    (which only merges invoices attached to a duplicate Bill), this also
    catches a standalone fee with no Bill at all (bill=None) - exactly the
    shape find_duplicate_bill's guard in admin_bills can never see, since it
    only checks for a reused Bill title, and exactly the shape
    find_duplicate_invoices's exact-title match misses once the titles
    drift even slightly.

    Groups a student's fees - among those whose title contains
    --title-contains - by (student, amount), since the real signal that two
    fees are the same re-billed obligation is that they charge the same
    amount, not that their titles match exactly. Keeps whichever fee in the
    group has the most money actually paid against it (via fee_paid_amount,
    the ledger truth - never the raw status/amount_paid columns, which can
    disagree with it) as canonical; ties go to a Bill-linked fee, then the
    most recent. For every other fee in the group:
      - zero paid: delete outright (nothing to lose)
      - paid, but the current canonical has zero paid: swap - the unpaid
        canonical is deleted and this fee becomes the survivor instead
      - both sides have payment: left untouched and reported as a conflict
        for manual review

    Dry-run by default."""

    help = "Merge a student's re-billed/duplicate fees (same amount, similar title) into one. Dry-run by default."

    def add_arguments(self, parser):
        parser.add_argument("--school", required=True, help="SchoolTenant schema_name to scope to.")
        parser.add_argument(
            "--title-contains",
            required=True,
            help="Case-insensitive substring every candidate fee's title must contain, e.g. 'FIRST TERM'.",
        )
        parser.add_argument("--commit", action="store_true", help="Actually merge. Without this, only reports what would happen.")

    def handle(self, *args, **options):
        from core.tenant import SchoolTenant

        school = SchoolTenant.objects.filter(schema_name=options["school"]).first()
        if not school:
            raise CommandError(f'No school with schema_name "{options["school"]}".')
        title_contains = options["title_contains"]
        commit = options["commit"]

        fees = list(
            SchoolFee.objects.filter(
                student__user__tenant_id=school.id,
                title__icontains=title_contains,
            )
            .select_related("student__user")
            .order_by("student_id", "amount", "created_at")
        )
        if not fees:
            self.stdout.write("No matching fees found for that scope.")
            return

        paid_amounts = {f.id: fee_paid_amount(f) for f in fees}

        groups = defaultdict(list)
        for f in fees:
            groups[(f.student_id, f.amount)].append(f)

        duplicate_groups = {key: group for key, group in groups.items() if len(group) > 1}
        if not duplicate_groups:
            self.stdout.write("No duplicate fees found for that scope.")
            return

        totals = {"deleted_zero_paid": 0, "swapped": 0, "conflicts": 0}

        for (student_id, amount), group in duplicate_groups.items():
            student = group[0].student
            name = student.user.get_full_name() if student.user_id else str(student_id)

            canonical = max(
                group,
                key=lambda f: (paid_amounts[f.id], f.bill_id is not None, f.created_at),
            )
            duplicates = [f for f in group if f.id != canonical.id]

            self.stdout.write(f"--- {name} (amount={amount}) ---")
            self.stdout.write(
                f"    keeping fee={canonical.id} title={canonical.title!r} bill={canonical.bill_id} "
                f"paid={paid_amounts[canonical.id]} created={canonical.created_at:%Y-%m-%d}"
            )

            with transaction.atomic():
                for dup in duplicates:
                    dup_paid = paid_amounts[dup.id]
                    canonical_paid = paid_amounts[canonical.id]

                    if dup_paid <= Decimal("0.00"):
                        self.stdout.write(
                            f"    delete  fee={dup.id} title={dup.title!r} bill={dup.bill_id} (zero paid)"
                        )
                        if commit:
                            dup.delete()
                        totals["deleted_zero_paid"] += 1
                    elif canonical_paid <= Decimal("0.00"):
                        self.stdout.write(
                            f"    swap    keeping fee={dup.id} title={dup.title!r} (paid={dup_paid}) instead, "
                            f"dropping fee={canonical.id} title={canonical.title!r} (unpaid)"
                        )
                        if commit:
                            canonical.delete()
                        canonical = dup
                        totals["swapped"] += 1
                    else:
                        self.stdout.write(
                            f"    CONFLICT fee={dup.id} title={dup.title!r} (paid={dup_paid}) and "
                            f"fee={canonical.id} title={canonical.title!r} (paid={canonical_paid}) both have "
                            "payments - left untouched, review manually"
                        )
                        totals["conflicts"] += 1
            self.stdout.write("")

        self.stdout.write(
            f"Totals: deleted_zero_paid={totals['deleted_zero_paid']} swapped={totals['swapped']} "
            f"conflicts={totals['conflicts']}"
        )
        if not commit:
            self.stdout.write("\nDry run only - re-run with --commit to actually merge these.")
        if totals["conflicts"]:
            self.stdout.write(self.style.WARNING(
                f"\n{totals['conflicts']} fee(s) have payments on both twins and were left untouched - "
                "resolve those by hand (e.g. in the admin Finance screen) before or after running --commit."
            ))
