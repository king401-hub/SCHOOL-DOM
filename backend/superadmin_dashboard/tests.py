from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from core.models import SchoolTenant
from finance.models import FinanceLedgerLog


class ComplianceApprovalTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.super_admin = User.objects.create_user(
            email="platform-admin@schooldom.academy",
            password="testpass123",
            is_staff=True,
            is_superuser=True,
        )
        self.client.force_login(self.super_admin)

        self.school = SchoolTenant.objects.create(
            name="No Documents Yet School",
            schema_name="no_docs_yet_school",
            is_active=True,
        )

    def test_school_with_no_documents_is_not_complete(self):
        self.assertFalse(self.school.compliance_documents_complete())

    def test_compliance_list_flags_missing_documents(self):
        response = self.client.get(reverse("superadmin_dashboard:compliance"), {"status": "not_submitted"})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "No documents submitted")
        self.assertContains(response, "Approve without documents")

    def test_approve_without_documents_approves_a_school_with_no_documents(self):
        self.assertEqual(self.school.compliance_status, "not_submitted")
        response = self.client.post(
            reverse("superadmin_dashboard:compliance_action", args=[self.school.pk, "approve_no_documents"])
        )
        self.assertRedirects(response, reverse("superadmin_dashboard:compliance"))
        self.school.refresh_from_db()
        self.assertEqual(self.school.compliance_status, "approved")
        self.assertEqual(self.school.compliance_reviewed_by, self.super_admin)
        self.assertIsNotNone(self.school.compliance_reviewed_at)
        # still true afterwards - approving does not require or fabricate documents
        self.assertFalse(self.school.compliance_documents_complete())

    def test_non_super_admin_cannot_approve(self):
        User = get_user_model()
        regular_user = User.objects.create_user(email="teacher@example.com", password="testpass123")
        self.client.force_login(regular_user)
        response = self.client.post(
            reverse("superadmin_dashboard:compliance_action", args=[self.school.pk, "approve_no_documents"])
        )
        self.assertEqual(response.status_code, 403)
        self.school.refresh_from_db()
        self.assertEqual(self.school.compliance_status, "not_submitted")


class DashboardFinanceLedgerStatTests(TestCase):
    """The Platform Overview page's stat cards, including the Finance Ledger
    Logs count and the Finance Ledger In/Out amounts added here - platform-
    wide totals across every school, not scoped to any one tenant (see
    superadmin_dashboard.services.dashboard_context). The in/out split
    replaced a single blended "Finance Ledger Total" (itself a replacement
    for the old "Transactions" card), since mixing money received with
    money paid out made neither figure the real amount either direction."""

    def setUp(self):
        User = get_user_model()
        self.super_admin = User.objects.create_user(
            email="platform-admin2@schooldom.academy", password="testpass123", is_staff=True, is_superuser=True,
        )
        self.client.force_login(self.super_admin)
        self.school_a = SchoolTenant.objects.create(name="Ledger School A", schema_name="ledger_school_a", is_active=True)
        self.school_b = SchoolTenant.objects.create(name="Ledger School B", schema_name="ledger_school_b", is_active=True)

    def test_the_dashboard_splits_money_in_from_money_out(self):
        # In: real payments received.
        FinanceLedgerLog.objects.create(tenant=self.school_a, action="paystack_split_payment", description="Payment A", amount=Decimal("1500.00"))
        FinanceLedgerLog.objects.create(tenant=self.school_b, action="paystack_dva_payment", description="Payment B", amount=Decimal("1000.00"))
        # Out: salary paid out.
        FinanceLedgerLog.objects.create(tenant=self.school_a, action="salary_payment_sent", description="Salary A", amount=Decimal("750.50"))
        # Neither - bookkeeping/anomaly entries, must not land in either total.
        FinanceLedgerLog.objects.create(tenant=self.school_a, action="overpayment_uncredited", description="Stray A", amount=Decimal("99999.00"))

        response = self.client.get(reverse("superadmin_dashboard:dashboard"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["stats"]["finance_ledger_logs"], 4)
        self.assertEqual(response.context["stats"]["finance_ledger_in_amount"], "₦2,500")
        # Decimal's :.0f formatting rounds half-to-even - 750.50 rounds down to 750.
        self.assertEqual(response.context["stats"]["finance_ledger_out_amount"], "₦750")
        self.assertContains(response, "Finance Ledger Logs")
        self.assertContains(response, "Finance Ledger In")
        self.assertContains(response, "Finance Ledger Out")
        self.assertNotContains(response, "Finance Ledger Total")
        self.assertNotContains(response, "Transactions")

    def test_zero_logs_shows_a_formatted_zero_not_an_error(self):
        response = self.client.get(reverse("superadmin_dashboard:dashboard"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["stats"]["finance_ledger_logs"], 0)
        self.assertEqual(response.context["stats"]["finance_ledger_in_amount"], "₦0")
        self.assertEqual(response.context["stats"]["finance_ledger_out_amount"], "₦0")

    def test_the_test_school_is_excluded_from_users_and_finance(self):
        User = get_user_model()
        test_school = SchoolTenant.objects.create(name="Happy Academy", schema_name="happy_academy_2", is_active=True)
        User.objects.create_user(email="admin@happyacademy.test", password="testpass123", tenant=test_school, is_active=True)
        FinanceLedgerLog.objects.create(tenant=test_school, action="paystack_split_payment", description="Test payment", amount=Decimal("5000.00"))
        FinanceLedgerLog.objects.create(tenant=self.school_a, action="paystack_split_payment", description="Real payment", amount=Decimal("1000.00"))

        before_response = self.client.get(reverse("superadmin_dashboard:dashboard"))
        users_excluding_test_school = before_response.context["stats"]["users"]

        self.assertEqual(before_response.context["stats"]["finance_ledger_logs"], 1)
        self.assertEqual(before_response.context["stats"]["finance_ledger_in_amount"], "₦1,000")
        # The test school's admin user is real in the database (the account
        # itself isn't deleted or hidden), just excluded from this count.
        self.assertTrue(User.objects.filter(tenant=test_school).exists())
        self.assertEqual(users_excluding_test_school, User.objects.exclude(tenant__schema_name="happy_academy_2").count())
        self.assertLess(users_excluding_test_school, User.objects.count())
