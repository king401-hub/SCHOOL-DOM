from collections import defaultdict

from django.core.management.base import BaseCommand

from finance.models import Bill, SchoolFee
from finance.services import bulk_fee_paid_amounts


class Command(BaseCommand):
    """Read-only report: find students with more than one SchoolFee invoice
    sharing the same title - the exact shape left behind by the bill-delete
    duplication bug fixed in b235515 (deleting a bill used to orphan every
    invoice it generated, paid or not, so recreating the same bill created a
    second invoice instead of reattaching to the orphan). Never writes
    anything; use this to see what a school's duplicates actually look like
    before deciding how to merge them."""

    help = "Report students with duplicate (same title) fee invoices. Read-only."

    def add_arguments(self, parser):
        parser.add_argument("--school", help="SchoolTenant schema_name to scope to (omit to scan every school).")

    def handle(self, *args, **options):
        school = options.get("school")
        self._report_duplicate_bills(school)
        self._report_duplicate_invoices(school)

    def _report_duplicate_bills(self, school):
        """Two separate Bill rows with the same title - a different shape of
        duplicate than the per-invoice one below (e.g. a bill that looked
        like it failed to save and was recreated, or a genuine double-click),
        each potentially with its own set of invoices."""
        bills = Bill.objects.select_related("tenant").order_by("tenant_id", "title", "created_at")
        if school:
            bills = bills.filter(tenant__schema_name=school)
        bills = list(bills)
        if not bills:
            self.stdout.write("No bills found for that scope.\n")
            return

        groups = defaultdict(list)
        for bill in bills:
            groups[(bill.tenant_id, bill.title)].append(bill)
        duplicate_groups = {key: group for key, group in groups.items() if len(group) > 1}

        if not duplicate_groups:
            self.stdout.write("No duplicate bills (same title) found.\n")
            return

        self.stdout.write(f"Found {len(duplicate_groups)} duplicate bill title group(s):\n")
        for (tenant_id, title), group in duplicate_groups.items():
            tenant_name = getattr(group[0].tenant, "name", tenant_id)
            self.stdout.write(f"--- {tenant_name} - \"{title}\" ---")
            for bill in group:
                invoice_count = bill.invoices.count()
                self.stdout.write(
                    f"    bill={bill.id} status={bill.status} invoices={invoice_count} "
                    f"due={bill.due_date} created={bill.created_at:%Y-%m-%d %H:%M}"
                )
            self.stdout.write("")

    def _report_duplicate_invoices(self, school):
        fees = SchoolFee.objects.select_related("student__user__tenant", "bill").order_by(
            "student_id", "title", "created_at"
        )
        if school:
            fees = fees.filter(student__user__tenant__schema_name=school)
        fees = list(fees)
        if not fees:
            self.stdout.write("No invoices found for that scope.")
            return

        paid_amounts = bulk_fee_paid_amounts(fees)

        groups = defaultdict(list)
        for fee in fees:
            groups[(fee.student_id, fee.title)].append(fee)

        duplicate_groups = {key: group for key, group in groups.items() if len(group) > 1}
        if not duplicate_groups:
            self.stdout.write("No duplicate invoices found.")
            return

        self.stdout.write(f"Found {len(duplicate_groups)} student/title group(s) with duplicate invoices:\n")
        for (student_id, title), group in duplicate_groups.items():
            student = group[0].student
            tenant_name = getattr(student.user.tenant, "name", "?") if student.user_id else "?"
            self.stdout.write(f"--- {student.user.get_full_name() if student.user_id else student_id} ({tenant_name}) - \"{title}\" ---")
            for fee in group:
                paid = paid_amounts.get(fee.id, 0)
                self.stdout.write(
                    f"    fee={fee.id} bill={fee.bill_id} amount={fee.amount} paid={paid} "
                    f"status={fee.status} customized={fee.is_customized} created={fee.created_at:%Y-%m-%d %H:%M}"
                )
            self.stdout.write("")
