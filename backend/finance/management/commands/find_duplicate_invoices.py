from collections import defaultdict

from django.core.management.base import BaseCommand

from finance.models import SchoolFee
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
        fees = SchoolFee.objects.select_related("student__user__tenant", "bill").order_by(
            "student_id", "title", "created_at"
        )
        school = options.get("school")
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
