from collections import defaultdict
from decimal import Decimal

from django.core.management.base import BaseCommand
from django.db import transaction

from finance.models import Bill, SchoolFee
from finance.services import fee_paid_amount


class Command(BaseCommand):
    """One-time cleanup for the duplicate-Bill-creation bug fixed alongside
    this command: nothing used to stop "Create Bill" being used again for a
    class that already had one, so admins repeatedly ended up with several
    Bill rows sharing the same title/term/year, each independently fanning
    out its own SchoolFee invoice per student. For every such group this
    keeps the earliest bill as canonical and, per student, either:
      - relinks their invoice onto the canonical bill (no sibling there yet)
      - deletes the duplicate invoice outright (it has zero payment on it -
        exactly the same "always safe" bar cleanup_orphaned_unpaid_invoices
        already uses)
      - swaps in the duplicate invoice and drops the empty canonical twin,
        when the MONEY landed on the duplicate side instead
    A student with a recorded payment on BOTH twins is never auto-resolved -
    that split is reported and left untouched for manual review. A duplicate
    Bill is only deleted once every one of its invoices has been moved off
    it. Dry-run by default."""

    help = "Merge duplicate Bill rows (same title/term/year) into one, keeping every recorded payment. Dry-run by default."

    def add_arguments(self, parser):
        parser.add_argument("--school", help="SchoolTenant schema_name to scope to (omit to scan every school).")
        parser.add_argument("--commit", action="store_true", help="Actually merge. Without this, only reports what would happen.")

    def handle(self, *args, **options):
        school = options.get("school")
        commit = options.get("commit", False)

        bills = Bill.objects.exclude(status=Bill.STATUS_CANCELLED).select_related("tenant", "academic_year", "term")
        if school:
            bills = bills.filter(tenant__schema_name=school)
        bills = list(bills.prefetch_related("classes").order_by("created_at"))
        if not bills:
            self.stdout.write("No bills found for that scope.")
            return

        coarse_groups = defaultdict(list)
        for bill in bills:
            key = (bill.tenant_id, bill.title.strip().lower(), bill.academic_year_id, bill.term_id)
            coarse_groups[key].append(bill)

        # Same title/term/year alone isn't enough - two bills legitimately
        # cover different classes under one name (e.g. separate "Term Fees"
        # bills per arm). Only cluster bills that actually share a class,
        # transitively, so a real duplicate chain groups together without
        # sweeping in an unrelated bill that merely reused the same title.
        duplicate_groups = []
        for coarse in coarse_groups.values():
            if len(coarse) < 2:
                continue
            clusters = []
            for bill in coarse:
                bill_class_ids = {c.id for c in bill.classes.all()}
                placed = False
                for cluster in clusters:
                    if cluster["class_ids"] & bill_class_ids:
                        cluster["bills"].append(bill)
                        cluster["class_ids"] |= bill_class_ids
                        placed = True
                        break
                if not placed:
                    clusters.append({"bills": [bill], "class_ids": bill_class_ids})
            duplicate_groups.extend(cluster["bills"] for cluster in clusters if len(cluster["bills"]) > 1)

        if not duplicate_groups:
            self.stdout.write("No duplicate bills found for that scope.")
            return

        totals = {"relinked": 0, "deleted_zero_paid": 0, "swapped": 0, "conflicts": 0, "bills_removed": 0}

        for group in duplicate_groups:
            canonical, *duplicates = group
            tenant_name = getattr(canonical.tenant, "name", canonical.tenant_id)
            self.stdout.write(f"--- {tenant_name} - \"{canonical.title}\" ---")
            self.stdout.write(f"    keeping bill={canonical.id} (created {canonical.created_at:%Y-%m-%d %H:%M})")

            with transaction.atomic():
                for dup in duplicates:
                    self.stdout.write(f"    merging bill={dup.id} (created {dup.created_at:%Y-%m-%d %H:%M}):")
                    dup_fees = list(SchoolFee.objects.filter(bill=dup).select_related("student__user"))
                    dup_classes = list(dup.classes.all())
                    leftover = 0

                    for fee in dup_fees:
                        student_name = fee.student.user.get_full_name() if fee.student.user_id else str(fee.student.student_id)
                        sibling = SchoolFee.objects.filter(
                            bill=canonical, student=fee.student, title__iexact=fee.title
                        ).first()

                        if sibling is None:
                            self.stdout.write(f"        relink  {student_name}: fee={fee.id} -> bill={canonical.id}")
                            if commit:
                                fee.bill = canonical
                                fee.save(update_fields=["bill"])
                            totals["relinked"] += 1
                            continue

                        dup_paid = fee_paid_amount(fee)
                        sibling_paid = fee_paid_amount(sibling)

                        if dup_paid <= Decimal("0.00"):
                            self.stdout.write(f"        delete  {student_name}: fee={fee.id} (zero paid, sibling fee={sibling.id} kept)")
                            if commit:
                                fee.delete()
                            totals["deleted_zero_paid"] += 1
                        elif sibling_paid <= Decimal("0.00"):
                            self.stdout.write(
                                f"        swap    {student_name}: keeping fee={fee.id} (paid={dup_paid}), "
                                f"dropping empty sibling fee={sibling.id}, relinking to bill={canonical.id}"
                            )
                            if commit:
                                sibling.delete()
                                fee.bill = canonical
                                fee.save(update_fields=["bill"])
                            totals["swapped"] += 1
                        else:
                            self.stdout.write(
                                f"        CONFLICT {student_name}: fee={fee.id} (paid={dup_paid}) and "
                                f"sibling fee={sibling.id} (paid={sibling_paid}) both have payments - left untouched, review manually"
                            )
                            totals["conflicts"] += 1
                            leftover += 1

                    if commit:
                        if not leftover and not SchoolFee.objects.filter(bill=dup).exists():
                            dup_id = dup.id
                            canonical.classes.add(*dup_classes)
                            dup.delete()
                            self.stdout.write(f"        removed empty duplicate bill={dup_id}")
                            totals["bills_removed"] += 1
                        else:
                            self.stdout.write(f"        kept duplicate bill={dup.id} - unresolved conflict(s) still attached")
                    elif not leftover:
                        self.stdout.write(f"        (would remove empty duplicate bill={dup.id})")
            self.stdout.write("")

        self.stdout.write(
            f"Totals: relinked={totals['relinked']} deleted_zero_paid={totals['deleted_zero_paid']} "
            f"swapped={totals['swapped']} conflicts={totals['conflicts']} "
            f"bills_removed={totals['bills_removed'] if commit else 'n/a (dry run)'}"
        )
        if not commit:
            self.stdout.write("\nDry run only - re-run with --commit to actually merge these.")
        if totals["conflicts"]:
            self.stdout.write(self.style.WARNING(
                f"\n{totals['conflicts']} invoice(s) have payments on both twins and were left untouched - "
                "resolve those by hand (e.g. in the admin Finance screen) before or after running --commit."
            ))
