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
    Logs count added here - a platform-wide total across every school, not
    scoped to any one tenant (see superadmin_dashboard.services.dashboard_context)."""

    def setUp(self):
        User = get_user_model()
        self.super_admin = User.objects.create_user(
            email="platform-admin2@schooldom.academy", password="testpass123", is_staff=True, is_superuser=True,
        )
        self.client.force_login(self.super_admin)
        self.school_a = SchoolTenant.objects.create(name="Ledger School A", schema_name="ledger_school_a", is_active=True)
        self.school_b = SchoolTenant.objects.create(name="Ledger School B", schema_name="ledger_school_b", is_active=True)

    def test_the_dashboard_shows_the_total_across_every_school(self):
        FinanceLedgerLog.objects.create(tenant=self.school_a, action="payment", description="Payment A")
        FinanceLedgerLog.objects.create(tenant=self.school_a, action="refund", description="Refund A")
        FinanceLedgerLog.objects.create(tenant=self.school_b, action="payment", description="Payment B")

        response = self.client.get(reverse("superadmin_dashboard:dashboard"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["stats"]["finance_ledger_logs"], 3)
        self.assertContains(response, "Finance Ledger Logs")

    def test_zero_logs_shows_zero_not_an_error(self):
        response = self.client.get(reverse("superadmin_dashboard:dashboard"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["stats"]["finance_ledger_logs"], 0)
