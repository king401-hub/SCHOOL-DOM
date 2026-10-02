from django.core.management.base import BaseCommand

from finance.models import SchoolFee
from finance.services import bulk_fee_paid_amounts


class Command(BaseCommand):
    """One-time cleanup for debris left behind by the bill-delete bug fixed in
    b235515: before that fix, deleting a Bill orphaned every invoice it had
    generated (bill set to NULL), paid or not, instead of clearing the ones
    nobody had paid anything toward. An unpaid orphan represents nothing -
    the bill that created it is gone and no money is attached to it - so it
    is always safe to delete, exactly like the DELETE endpoint now does for
    new deletes. A part-paid or fully paid orphan is left untouched; that is
    a real receipt and stays exactly where the original fix leaves it."""

    help = "Delete orphaned (bill=NULL), zero-paid SchoolFee invoices left over from before the bill-delete fix. Dry-run by default."

    def add_arguments(self, parser):
        parser.add_argument("--school", help="SchoolTenant schema_name to scope to (omit to scan every school).")
        parser.add_argument("--commit", action="store_true", help="Actually delete. Without this, only reports what would be deleted.")

    def handle(self, *args, **options):
        school = options.get("school")
        commit = options.get("commit", False)

        orphans = SchoolFee.objects.filter(bill__isnull=True).select_related("student__user__tenant")
        if school:
            orphans = orphans.filter(student__user__tenant__schema_name=school)
        orphans = list(orphans)
        if not orphans:
            self.stdout.write("No orphaned invoices found for that scope.")
            return

        paid_amounts = bulk_fee_paid_amounts(orphans)
        to_delete = [fee for fee in orphans if paid_amounts.get(fee.id, 0) <= 0]
        kept = len(orphans) - len(to_delete)

        if not to_delete:
            self.stdout.write(f"No unpaid orphans to delete ({kept} orphan(s) found, all have payments and are kept as-is).")
            return

        self.stdout.write(f"{'Deleting' if commit else 'Would delete'} {len(to_delete)} unpaid orphaned invoice(s) "
                           f"({kept} other orphan(s) have payments and are left untouched):\n")
        for fee in to_delete:
            student = fee.student
            tenant_name = getattr(student.user.tenant, "name", "?") if student.user_id else "?"
            name = student.user.get_full_name() if student.user_id else str(student.student_id)
            self.stdout.write(
                f"  {name} ({tenant_name}) - \"{fee.title}\" amount={fee.amount} "
                f"created={fee.created_at:%Y-%m-%d} fee={fee.id}"
            )

        if commit:
            SchoolFee.objects.filter(id__in=[fee.id for fee in to_delete]).delete()
            self.stdout.write(self.style.SUCCESS(f"\nDeleted {len(to_delete)} invoice(s)."))
        else:
            self.stdout.write("\nDry run only - re-run with --commit to actually delete these.")
