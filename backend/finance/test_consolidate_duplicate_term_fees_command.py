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


class ConsolidateDuplicateTermFeesCommandTests(TestCase):
    """Against the exact shape found in production: the same obligation
    re-billed under slightly different titles, some of it a standalone fee
    with no Bill at all - a shape find_duplicate_invoices's exact-title
    match and the Bill-title duplicate guard in admin_bills both miss."""

    def setUp(self):
        self.school = SchoolTenant.objects.create(name="Consolidate School", schema_name="consolidate_school", is_active=True)
        self.legacy_tenant = Tenant.objects.create(name=self.school.name, slug=self.school.schema_name)
        self.school_class = Class.objects.create(tenant=self.legacy_tenant, name="JSS", section="1")
        user = User.objects.create_user(
            email="student@consolidate.edu", password="StudentPass123", role="student",
            tenant=self.school, is_active=True, is_verified=True,
        )
        self.student = StudentProfile.objects.create(
            user=user, student_id="CONS001", admission_number="ADM-CONS001", admission_date=timezone.localdate(),
            guardian_name="Guardian", guardian_relation="Parent", current_class=self.school_class,
        )

    def _run(self, *extra_args):
        out = StringIO()
        call_command("consolidate_duplicate_term_fees", "--school", "consolidate_school", "--title-contains", "FIRST TERM", *extra_args, stdout=out)
        return out.getvalue()

    def test_keeps_the_paid_fee_and_deletes_the_unpaid_retitled_duplicate(self):
        paid = SchoolFee.objects.create(
            student=self.student, bill=None, title="FIRST TERM 2026/2027", amount=Decimal("90500.00"),
            due_date=timezone.localdate(), status=SchoolFee.STATUS_PENDING,
        )
        record_cash_payment(self.student, Decimal("90500.00"))
        bill = Bill.objects.create(tenant=self.school, title="FIRST TERM 26/27 2026/2027", status=Bill.STATUS_PUBLISHED)
        rebilled = SchoolFee.objects.create(
            student=self.student, bill=bill, title="FIRST TERM 26/27 2026/2027", amount=Decimal("90500.00"),
            due_date=timezone.localdate(), status=SchoolFee.STATUS_PENDING,
        )

        output = self._run()

        self.assertIn(f"keeping fee={paid.id}", output)
        self.assertIn(f"delete  fee={rebilled.id}", output)
        self.assertIn("deleted_zero_paid=1", output)
        self.assertIn("Dry run only", output)
        self.assertTrue(SchoolFee.objects.filter(id=paid.id).exists())
        self.assertTrue(SchoolFee.objects.filter(id=rebilled.id).exists())  # dry run: nothing actually deleted

        output = self._run("--commit")
        self.assertTrue(SchoolFee.objects.filter(id=paid.id).exists())
        self.assertFalse(SchoolFee.objects.filter(id=rebilled.id).exists())

    def test_three_title_variants_same_amount_all_unpaid_keeps_the_bill_linked_one(self):
        SchoolFee.objects.create(
            student=self.student, bill=None, title="FIRST TERM 26/27", amount=Decimal("33500.00"),
            due_date=timezone.localdate(), status=SchoolFee.STATUS_PENDING,
        )
        SchoolFee.objects.create(
            student=self.student, bill=None, title="FIRST TERM 2026/2027", amount=Decimal("33500.00"),
            due_date=timezone.localdate(), status=SchoolFee.STATUS_PENDING,
        )
        bill = Bill.objects.create(tenant=self.school, title="FIRST TERM 26/27 2026/2027", status=Bill.STATUS_PUBLISHED)
        rebilled = SchoolFee.objects.create(
            student=self.student, bill=bill, title="FIRST TERM 26/27 2026/2027", amount=Decimal("33500.00"),
            due_date=timezone.localdate(), status=SchoolFee.STATUS_PENDING,
        )

        output = self._run("--commit")

        self.assertIn("deleted_zero_paid=2", output)
        self.assertEqual(SchoolFee.objects.filter(student=self.student).count(), 1)
        self.assertTrue(SchoolFee.objects.filter(id=rebilled.id).exists())

    def test_payments_on_both_sides_is_left_as_a_conflict(self):
        # record_cash_payment auto-allocates to a student's outstanding fees,
        # so each fee is fully settled before the next is created - the only
        # way to guarantee which fee each payment actually lands on.
        first = SchoolFee.objects.create(
            student=self.student, bill=None, title="FIRST TERM 26/27", amount=Decimal("50000.00"),
            due_date=timezone.localdate(), status=SchoolFee.STATUS_PENDING,
        )
        record_cash_payment(self.student, Decimal("50000.00"))
        second = SchoolFee.objects.create(
            student=self.student, bill=None, title="FIRST TERM 2026/2027", amount=Decimal("50000.00"),
            due_date=timezone.localdate(), status=SchoolFee.STATUS_PENDING,
        )
        record_cash_payment(self.student, Decimal("50000.00"))

        output = self._run("--commit")

        self.assertIn("CONFLICT", output)
        self.assertIn("conflicts=1", output)
        self.assertTrue(SchoolFee.objects.filter(id=first.id).exists())
        self.assertTrue(SchoolFee.objects.filter(id=second.id).exists())

    def test_no_matching_titles_reports_clean(self):
        SchoolFee.objects.create(
            student=self.student, title="Excursion Fee", amount=Decimal("5000.00"),
            due_date=timezone.localdate(), status=SchoolFee.STATUS_PENDING,
        )
        output = self._run()
        self.assertIn("No matching fees found for that scope.", output)

    def test_unknown_school_raises(self):
        from django.core.management.base import CommandError

        with self.assertRaises(CommandError):
            call_command("consolidate_duplicate_term_fees", "--school", "does-not-exist", "--title-contains", "FIRST TERM")
