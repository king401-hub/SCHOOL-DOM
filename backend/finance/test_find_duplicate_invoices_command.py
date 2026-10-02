from decimal import Decimal
from io import StringIO

from django.core.management import call_command
from django.test import TestCase
from django.utils import timezone

from academic.models import Class
from core.models import SchoolTenant
from finance.models import Bill, SchoolFee
from finance.services import record_cash_payment
from tenants.models import Tenant
from users.models import StudentProfile, User


class FindDuplicateInvoicesCommandTests(TestCase):
    """Smoke test for the read-only duplicate-invoice finder, against the
    exact shape the bill-delete bug (fixed in b235515) used to leave behind:
    one paid, orphaned invoice plus one unpaid duplicate under a live bill."""

    def setUp(self):
        self.school = SchoolTenant.objects.create(name="Dup Finder School", schema_name="dup_finder_school", is_active=True)
        self.legacy_tenant = Tenant.objects.create(name=self.school.name, slug=self.school.schema_name)
        self.school_class = Class.objects.create(tenant=self.legacy_tenant, name="JSS", section="1")
        user = User.objects.create_user(
            email="dup@findduplicate.edu", password="StudentPass123", role="student",
            tenant=self.school, is_active=True, is_verified=True,
        )
        self.student = StudentProfile.objects.create(
            user=user, student_id="DUP001", admission_number="ADM-DUP001", admission_date=timezone.localdate(),
            guardian_name="Guardian", guardian_relation="Parent", current_class=self.school_class,
        )

    def test_reports_a_paid_orphan_alongside_an_unpaid_duplicate(self):
        orphan = SchoolFee.objects.create(
            student=self.student, bill=None, title="Term Fee", amount=Decimal("20000.00"),
            due_date=timezone.localdate(), status=SchoolFee.STATUS_PENDING,
        )
        record_cash_payment(self.student, Decimal("20000.00"))
        SchoolFee.objects.create(
            student=self.student, bill=None, title="Term Fee", amount=Decimal("20000.00"),
            due_date=timezone.localdate(), status=SchoolFee.STATUS_PENDING,
        )

        out = StringIO()
        call_command("find_duplicate_invoices", "--school", "dup_finder_school", stdout=out)
        output = out.getvalue()

        self.assertIn("Term Fee", output)
        self.assertIn(f"fee={orphan.id}", output)
        self.assertIn("paid=20000.00", output)
        self.assertIn("paid=0", output)

    def test_no_duplicates_reports_clean(self):
        SchoolFee.objects.create(
            student=self.student, title="Single Fee", amount=Decimal("5000.00"),
            due_date=timezone.localdate(), status=SchoolFee.STATUS_PENDING,
        )
        out = StringIO()
        call_command("find_duplicate_invoices", "--school", "dup_finder_school", stdout=out)
        output = out.getvalue()
        self.assertIn("No bills found for that scope.", output)
        self.assertIn("No duplicate invoices found.", output)

    def test_reports_two_live_bills_sharing_a_title(self):
        first = Bill.objects.create(tenant=self.school, title="Term 1 Fees", status=Bill.STATUS_PUBLISHED)
        second = Bill.objects.create(tenant=self.school, title="Term 1 Fees", status=Bill.STATUS_PUBLISHED)
        SchoolFee.objects.create(
            student=self.student, bill=first, title="Term 1 Fees", amount=Decimal("10000.00"),
            due_date=timezone.localdate(), status=SchoolFee.STATUS_PENDING,
        )

        out = StringIO()
        call_command("find_duplicate_invoices", "--school", "dup_finder_school", stdout=out)
        output = out.getvalue()

        self.assertIn("Found 1 duplicate bill title group(s)", output)
        self.assertIn(f"bill={first.id} status=published invoices=1", output)
        self.assertIn(f"bill={second.id} status=published invoices=0", output)
