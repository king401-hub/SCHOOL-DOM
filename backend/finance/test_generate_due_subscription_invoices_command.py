from datetime import date, timedelta
from decimal import Decimal
from io import StringIO

from django.core.management import call_command
from django.test import TestCase
from django.utils import timezone

from academic.models import Class
from core.models import SchoolTenant
from finance.models import RecurringBillingPlan, SchoolFee
from finance.services import enroll_student_in_recurring_plan
from tenants.models import Tenant
from users.models import StudentProfile, User


class GenerateDueSubscriptionInvoicesCommandTests(TestCase):
    """Dry-run by default, --commit actually generates, re-running on the
    same day never double-bills a cycle."""

    def setUp(self):
        self.school = SchoolTenant.objects.create(name="Command School", schema_name="command_school", is_active=True)
        self.legacy_tenant = Tenant.objects.create(name=self.school.name, slug=self.school.schema_name)
        self.school_class = Class.objects.create(tenant=self.legacy_tenant, name="JSS1", section="A")
        self.plan = RecurringBillingPlan.objects.create(
            tenant=self.school, title="Monthly Tuition", amount=Decimal("10000.00"),
            applies_to_all_classes=True, effective_start_date=date(2020, 1, 1),
        )
        user = User.objects.create_user(
            email="cmd@command.edu", password="StudentPass123", role="student", tenant=self.school,
            is_active=True, is_verified=True,
        )
        self.student = StudentProfile.objects.create(
            user=user, student_id="CMD001", admission_number="ADM-CMD-001", admission_date=date(2026, 9, 15),
            guardian_name="Guardian", guardian_relation="Parent", current_class=self.school_class,
        )
        self.subscription = enroll_student_in_recurring_plan(self.student, self.plan)

    def test_dry_run_reports_but_does_not_generate(self):
        # Push next_billing_date out to well beyond "today" so dry-run truly
        # finds nothing due - the fixture subscription from setUp (anchored
        # 2026-09-15) would otherwise already be overdue by the time these
        # tests run.
        self.subscription.next_billing_date = timezone.localdate() + timedelta(days=400)
        self.subscription.save(update_fields=["next_billing_date"])

        out = StringIO()
        call_command("generate_due_subscription_invoices", stdout=out)
        self.assertIn("No subscriptions due", out.getvalue())
        self.assertEqual(SchoolFee.objects.filter(subscription=self.subscription).count(), 1)

    def test_commit_generates_due_invoice(self):
        self.subscription.next_billing_date = date(2026, 10, 15)
        self.subscription.save(update_fields=["next_billing_date"])

        out = StringIO()
        call_command("generate_due_subscription_invoices", "--commit", stdout=out)

        self.assertIn("Generated 1 invoice(s)", out.getvalue())
        self.assertEqual(SchoolFee.objects.filter(subscription=self.subscription).count(), 2)

    def test_rerunning_on_the_same_day_does_not_double_bill(self):
        self.subscription.next_billing_date = date(2026, 10, 15)
        self.subscription.save(update_fields=["next_billing_date"])

        call_command("generate_due_subscription_invoices", "--commit", stdout=StringIO())
        call_command("generate_due_subscription_invoices", "--commit", stdout=StringIO())

        self.assertEqual(SchoolFee.objects.filter(subscription=self.subscription).count(), 2)
