from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from core.models import SchoolTenant
from finance.models import BankPayment, FinanceLedgerLog, Transaction


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
    """The Platform Overview page's stat cards. Money IN is sourced from the
    real payment tables (Transaction for bills/DVA, BankPayment for
    admin-recorded cash/bank/POS) rather than FinanceLedgerLog, which only
    logs a narrow slice of events and badly understated the real total -
    see superadmin_dashboard.services._payment_channel_querysets. Money OUT
    still reads FinanceLedgerLog, since salary/payroll disbursal has no
    other table of its own."""

    def setUp(self):
        User = get_user_model()
        self.super_admin = User.objects.create_user(
            email="platform-admin2@schooldom.academy", password="testpass123", is_staff=True, is_superuser=True,
        )
        self.client.force_login(self.super_admin)
        self.school_a = SchoolTenant.objects.create(name="Ledger School A", schema_name="ledger_school_a", is_active=True)
        self.school_b = SchoolTenant.objects.create(name="Ledger School B", schema_name="ledger_school_b", is_active=True)

    def test_the_dashboard_shows_bills_dva_recorded_and_out(self):
        # Bills: paid via direct Paystack checkout - reference prefix SPL.
        Transaction.objects.create(
            tx_type=Transaction.SPLIT_PAYMENT, status=Transaction.STATUS_SUCCESS, reference="SPL-A1",
            school_id=self.school_a.id, amount=Decimal("1500.00"),
        )
        # DVA: paid into a virtual account - reference prefix DVA.
        Transaction.objects.create(
            tx_type=Transaction.SPLIT_PAYMENT, status=Transaction.STATUS_SUCCESS, reference="DVA-B1",
            school_id=self.school_b.id, amount=Decimal("1000.00"),
        )
        # A failed/pending transaction must never count.
        Transaction.objects.create(
            tx_type=Transaction.SPLIT_PAYMENT, status=Transaction.STATUS_FAILED, reference="SPL-A2",
            school_id=self.school_a.id, amount=Decimal("99999.00"),
        )
        # Payment recorded: admin-entered cash/bank/POS.
        BankPayment.objects.create(
            tenant=self.school_a, amount=Decimal("300.00"), narration="Cash", bank_reference="CASH-A1",
            status=BankPayment.STATUS_CONFIRMED,
        )
        # Out: salary paid out.
        FinanceLedgerLog.objects.create(tenant=self.school_a, action="salary_payment_sent", description="Salary A", amount=Decimal("750.50"))

        response = self.client.get(reverse("superadmin_dashboard:dashboard"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["stats"]["bills_total"], "₦1,500")
        self.assertEqual(response.context["stats"]["dva_total"], "₦1,000")
        self.assertEqual(response.context["stats"]["payments_recorded_total"], "₦300")
        # Decimal's :.0f formatting rounds half-to-even - 750.50 rounds down to 750.
        self.assertEqual(response.context["stats"]["finance_ledger_out_amount"], "₦750")
        self.assertContains(response, "Bills")
        self.assertContains(response, "DVA Payments")
        self.assertContains(response, "Payments Recorded")
        self.assertContains(response, "Finance Ledger Out")
        self.assertNotContains(response, "Finance Ledger In")
        self.assertNotContains(response, "Finance Ledger Total")
        self.assertNotContains(response, "Transactions")

    def test_zero_payments_shows_a_formatted_zero_not_an_error(self):
        response = self.client.get(reverse("superadmin_dashboard:dashboard"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["stats"]["bills_total"], "₦0")
        self.assertEqual(response.context["stats"]["dva_total"], "₦0")
        self.assertEqual(response.context["stats"]["payments_recorded_total"], "₦0")
        self.assertEqual(response.context["stats"]["finance_ledger_out_amount"], "₦0")

    def test_the_test_school_is_excluded_from_users_and_finance(self):
        User = get_user_model()
        test_school = SchoolTenant.objects.create(name="Happy Academy", schema_name="happy_academy_2", is_active=True)
        User.objects.create_user(email="admin@happyacademy.test", password="testpass123", tenant=test_school, is_active=True)
        Transaction.objects.create(
            tx_type=Transaction.SPLIT_PAYMENT, status=Transaction.STATUS_SUCCESS, reference="SPL-TEST1",
            school_id=test_school.id, amount=Decimal("5000.00"),
        )
        Transaction.objects.create(
            tx_type=Transaction.SPLIT_PAYMENT, status=Transaction.STATUS_SUCCESS, reference="SPL-REAL1",
            school_id=self.school_a.id, amount=Decimal("1000.00"),
        )

        before_response = self.client.get(reverse("superadmin_dashboard:dashboard"))
        users_excluding_test_school = before_response.context["stats"]["users"]

        self.assertEqual(before_response.context["stats"]["bills_total"], "₦1,000")
        # The test school's admin user is real in the database (the account
        # itself isn't deleted or hidden), just excluded from this count.
        self.assertTrue(User.objects.filter(tenant=test_school).exists())
        self.assertEqual(users_excluding_test_school, User.objects.exclude(tenant__schema_name="happy_academy_2").count())
        self.assertLess(users_excluding_test_school, User.objects.count())


class PaymentsBreakdownPageTests(TestCase):
    """The Payments page (per-school Bills/DVA/Payments Recorded breakdown)
    replaced a list view built against fee_collections.FeePayment, a model
    nothing in the live product ever writes to - see
    superadmin_dashboard.services.per_school_payment_breakdown."""

    def setUp(self):
        User = get_user_model()
        self.super_admin = User.objects.create_user(
            email="platform-admin3@schooldom.academy", password="testpass123", is_staff=True, is_superuser=True,
        )
        self.client.force_login(self.super_admin)
        self.school_a = SchoolTenant.objects.create(name="Breakdown School A", schema_name="breakdown_school_a", is_active=True)
        self.school_b = SchoolTenant.objects.create(name="Breakdown School B", schema_name="breakdown_school_b", is_active=True)

        Transaction.objects.create(
            tx_type=Transaction.SPLIT_PAYMENT, status=Transaction.STATUS_SUCCESS, reference="SPL-PA1",
            school_id=self.school_a.id, amount=Decimal("2000.00"),
        )
        Transaction.objects.create(
            tx_type=Transaction.SPLIT_PAYMENT, status=Transaction.STATUS_SUCCESS, reference="DVA-PA1",
            school_id=self.school_a.id, amount=Decimal("500.00"),
        )
        BankPayment.objects.create(
            tenant=self.school_b, amount=Decimal("1200.00"), narration="Bank transfer", bank_reference="BANK-PB1",
            status=BankPayment.STATUS_CONFIRMED,
        )

    def test_each_school_shows_its_own_breakdown_and_total(self):
        response = self.client.get(reverse("superadmin_dashboard:payments"))
        self.assertEqual(response.status_code, 200)

        rows_by_name = {row["school_name"]: row for row in response.context["rows"]}
        self.assertEqual(rows_by_name["Breakdown School A"]["bills"], Decimal("2000.00"))
        self.assertEqual(rows_by_name["Breakdown School A"]["dva"], Decimal("500.00"))
        self.assertEqual(rows_by_name["Breakdown School A"]["recorded"], Decimal("0.00"))
        self.assertEqual(rows_by_name["Breakdown School A"]["total"], Decimal("2500.00"))
        self.assertEqual(rows_by_name["Breakdown School B"]["recorded"], Decimal("1200.00"))
        self.assertEqual(rows_by_name["Breakdown School B"]["total"], Decimal("1200.00"))

        self.assertEqual(response.context["totals"]["grand_total"], Decimal("3700.00"))

    def test_searching_narrows_the_rows_and_the_totals_footer(self):
        response = self.client.get(reverse("superadmin_dashboard:payments"), {"q": "School A"})
        self.assertEqual(response.status_code, 200)
        names = [row["school_name"] for row in response.context["rows"]]
        self.assertEqual(names, ["Breakdown School A"])
        self.assertEqual(response.context["totals"]["grand_total"], Decimal("2500.00"))

    def test_a_failed_transaction_never_counts(self):
        Transaction.objects.create(
            tx_type=Transaction.SPLIT_PAYMENT, status=Transaction.STATUS_FAILED, reference="SPL-FAILED1",
            school_id=self.school_a.id, amount=Decimal("99999.00"),
        )
        response = self.client.get(reverse("superadmin_dashboard:payments"))
        rows_by_name = {row["school_name"]: row for row in response.context["rows"]}
        self.assertEqual(rows_by_name["Breakdown School A"]["bills"], Decimal("2000.00"))

    def test_the_test_school_never_appears(self):
        test_school = SchoolTenant.objects.create(name="Happy Academy", schema_name="happy_academy_2", is_active=True)
        Transaction.objects.create(
            tx_type=Transaction.SPLIT_PAYMENT, status=Transaction.STATUS_SUCCESS, reference="SPL-HAPPY1",
            school_id=test_school.id, amount=Decimal("8000.00"),
        )
        response = self.client.get(reverse("superadmin_dashboard:payments"))
        names = [row["school_name"] for row in response.context["rows"]]
        self.assertNotIn("Happy Academy", names)
