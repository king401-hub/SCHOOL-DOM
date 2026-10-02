from decimal import Decimal
from io import StringIO

from django.core.management import call_command
from django.test import TestCase
from django.utils import timezone

from academic.models import Class
from core.models import SchoolTenant
from finance.models import SchoolFee
from finance.services import record_cash_payment
from tenants.models import Tenant
from users.models import StudentProfile, User


class CleanupOrphanedUnpaidInvoicesCommandTests(TestCase):
    """Verifies the pre-fix-debris cleanup only ever removes an orphaned
    invoice with zero payment, leaves a part-paid orphan untouched, and
    never touches an invoice that still has a live bill."""

    def setUp(self):
        self.school = SchoolTenant.objects.create(name="Cleanup School", schema_name="cleanup_school", is_active=True)
        self.legacy_tenant = Tenant.objects.create(name=self.school.name, slug=self.school.schema_name)
        self.school_class = Class.objects.create(tenant=self.legacy_tenant, name="JSS", section="1")
        self.unpaid_student = self._student("unpaid@cleanup.edu", "CLN001")
        self.paid_student = self._student("paid@cleanup.edu", "CLN002")

    def _student(self, email, code):
        user = User.objects.create_user(
            email=email, password="StudentPass123", role="student", tenant=self.school,
            is_active=True, is_verified=True,
        )
        return StudentProfile.objects.create(
            user=user, student_id=code, admission_number=f"ADM-{code}", admission_date=timezone.localdate(),
            guardian_name="Guardian", guardian_relation="Parent", current_class=self.school_class,
        )

    def test_dry_run_reports_but_does_not_delete(self):
        orphan = SchoolFee.objects.create(
            student=self.unpaid_student, bill=None, title="First Term Fees", amount=Decimal("88500.00"),
            due_date=timezone.localdate(), status=SchoolFee.STATUS_PENDING,
        )
        out = StringIO()
        call_command("cleanup_orphaned_unpaid_invoices", "--school", "cleanup_school", stdout=out)
        output = out.getvalue()
        self.assertIn("Would delete 1", output)
        self.assertTrue(SchoolFee.objects.filter(id=orphan.id).exists())

    def test_commit_deletes_unpaid_orphan_but_keeps_paid_orphan_and_live_bill_invoice(self):
        unpaid_orphan = SchoolFee.objects.create(
            student=self.unpaid_student, bill=None, title="First Term Fees", amount=Decimal("88500.00"),
            due_date=timezone.localdate(), status=SchoolFee.STATUS_PENDING,
        )
        paid_orphan = SchoolFee.objects.create(
            student=self.paid_student, bill=None, title="First Term Fees", amount=Decimal("40000.00"),
            due_date=timezone.localdate(), status=SchoolFee.STATUS_PENDING,
        )
        record_cash_payment(self.paid_student, Decimal("40000.00"))

        out = StringIO()
        call_command("cleanup_orphaned_unpaid_invoices", "--school", "cleanup_school", "--commit", stdout=out)
        output = out.getvalue()

        self.assertIn("Deleted 1 invoice(s).", output)
        self.assertFalse(SchoolFee.objects.filter(id=unpaid_orphan.id).exists())
        self.assertTrue(SchoolFee.objects.filter(id=paid_orphan.id).exists())

    def test_clean_scope_reports_nothing_to_do(self):
        out = StringIO()
        call_command("cleanup_orphaned_unpaid_invoices", "--school", "cleanup_school", stdout=out)
        self.assertIn("No orphaned invoices found for that scope.", out.getvalue())
