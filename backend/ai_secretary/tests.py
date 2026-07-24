from django.test import TestCase
from unittest.mock import patch

from core.models import SchoolTenant
from finance.models import SmsMessageLog
from finance.services import get_or_create_sms_wallet
from users.models import User

from ai_secretary.tools import SecretaryTools


class SecretarySendSmsToolTests(TestCase):
    def setUp(self):
        self.school = SchoolTenant.objects.create(name="Secretary School", schema_name="secretary_school", is_active=True)
        self.admin = User.objects.create_user(
            email="admin@secretary.test",
            password="AdminPass123",
            first_name="Sec",
            last_name="Admin",
            role="school_admin",
            tenant=self.school,
            is_active=True,
            is_verified=True,
        )
        self.tools = SecretaryTools(self.school, self.admin)

    @patch("finance.services.send_ebulksms")
    def test_send_sms_charges_wallet_only_after_provider_confirms(self, mock_send):
        mock_send.return_value = {"response": {"status": "SUCCESS", "totalsent": 1, "cost": 4}}
        wallet = get_or_create_sms_wallet(self.school)
        starting_balance = wallet.balance

        result = self.tools.send_sms("08010000001", "Reminder: PTA meeting tomorrow.")

        self.assertEqual(result["status"], "success")
        wallet.refresh_from_db()
        self.assertEqual(wallet.balance, starting_balance - 1)
        self.assertTrue(SmsMessageLog.objects.filter(category=SmsMessageLog.OTHER, delivery_status=SmsMessageLog.SENT).exists())

    @patch("finance.services.send_ebulksms")
    def test_send_sms_provider_failure_charges_nothing_and_reports_reason(self, mock_send):
        mock_send.return_value = {"response": {"status": "FAILED", "totalsent": 0}}
        wallet = get_or_create_sms_wallet(self.school)
        starting_balance = wallet.balance

        result = self.tools.send_sms("08010000002", "Reminder: PTA meeting tomorrow.")

        self.assertEqual(result["status"], "error")
        self.assertEqual(result["error_code"], "SMS_DELIVERY_FAILED")
        self.assertIn("FAILED", result["message"])
        wallet.refresh_from_db()
        self.assertEqual(wallet.balance, starting_balance)

    def test_send_sms_with_empty_wallet_returns_clear_error(self):
        wallet = get_or_create_sms_wallet(self.school)
        wallet.balance = 0
        wallet.save(update_fields=["balance", "updated_at"])

        result = self.tools.send_sms("08010000003", "Reminder: PTA meeting tomorrow.")

        self.assertEqual(result["status"], "error")
        self.assertEqual(result["error_code"], "INSUFFICIENT_CREDITS")
