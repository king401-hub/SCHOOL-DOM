from django.test import TestCase
from unittest.mock import patch

from django.test import TestCase

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


class PhaseOneAdminAgentTests(TestCase):
    def setUp(self):
        self.school = SchoolTenant.objects.create(name="Phase One School", schema_name="phase_one_school", is_active=True)
        self.admin = User.objects.create_user(
            email="admin@phaseone.test",
            password="AdminPass123",
            first_name="Phase",
            last_name="Admin",
            role="school_admin",
            tenant=self.school,
            is_active=True,
            is_verified=True,
        )
        self.tools = SecretaryTools(self.school, self.admin)

    def test_simple_nlu_routes_core_admin_commands(self):
        from ai_secretary.agent import parse_phase_one_command

        self.assertEqual(parse_phase_one_command("Create a timetable for SS2A for the first term")["tool"], "generate_timetable")
        self.assertEqual(parse_phase_one_command("Generate report cards for all JSS3 students")["tool"], "generate_report_cards")
        self.assertEqual(parse_phase_one_command("What's the fee status of the school?")["tool"], "get_fee_status")
        self.assertEqual(parse_phase_one_command("Create a CBT for Biology with 50 questions")["tool"], "create_cbt_exam")
        self.assertEqual(parse_phase_one_command("Take me to the fee management page")["tool"], "navigate_to_page")

    def test_core_tools_execute_with_auto_execute_permissions(self):
        timetable = self.tools.dispatch("generate_timetable", {"class_name": "SS2A", "term": "First Term"})
        self.assertEqual(timetable["status"], "success")
        self.assertIn("SS2A", timetable["message"])

        fees = self.tools.dispatch("get_fee_status", {})
        self.assertEqual(fees["status"], "success")
        self.assertIn("school", fees["summary"].lower())

        report = self.tools.dispatch("generate_report_cards", {"class_name": "JSS3", "term": "First Term"})
        self.assertEqual(report["status"], "success")
        self.assertIn("report", report["message"].lower())

        cbt = self.tools.dispatch("create_cbt_exam", {"subject": "Biology", "class_name": "SS2", "question_count": 50, "time_limit_minutes": 60})
        self.assertEqual(cbt["status"], "success")
        self.assertEqual(cbt["question_count"], 50)

        nav = self.tools.dispatch("navigate_to_page", {"page": "fee management"})
        self.assertEqual(nav["status"], "success")
        self.assertIn("fee", nav["page"].lower())

    def test_navigation_command_returns_route_for_client_navigation(self):
        from ai_secretary.agent import run_agent

        result = run_agent("Take me to the fee management page", [], self.school, self.admin)
        self.assertEqual(result["tools_called"], ["navigate_to_page"])
        self.assertEqual(result["route"], "/finance")

    def test_navigation_supports_every_admin_section(self):
        routes = {
            "Open the students page": "/students",
            "Navigate to parent directory": "/parents",
            "Take me to non-teaching staff": "/non-teaching-staff",
            "Open performance analytics": "/performance-heatmap",
            "Go to attendance": "/attendance",
            "Open expenses": "/expenses",
            "Take me to the SMS wallet": "/sms-wallet",
            "Navigate to payroll": "/hr-self-service",
            "Open loan application": "/loan-application",
            "Go to transcripts": "/documents",
            "Open database import": "/database-import",
            "Take me to compliance": "/compliance",
            "Open service agreement": "/service-agreement",
        }
        for request, expected_route in routes.items():
            with self.subTest(request=request):
                result = self.tools.dispatch("navigate_to_page", {"page": request})
                self.assertEqual(result["status"], "success")
                self.assertEqual(result["route"], expected_route)


class PhaseTwoAdminAgentTests(TestCase):
    def setUp(self):
        self.school = SchoolTenant.objects.create(name="Phase Two School", schema_name="phase_two_school", is_active=True)
        self.admin = User.objects.create_user(
            email="admin@phasetwo.test",
            password="AdminPass123",
            first_name="Phase",
            last_name="Two",
            role="school_admin",
            tenant=self.school,
            is_active=True,
            is_verified=True,
        )
        self.tools = SecretaryTools(self.school, self.admin)

    def test_context_management_uses_recent_class_reference(self):
        from ai_secretary.agent import parse_phase_one_command

        history = [
            {"role": "user", "content": "Show me SS2A students"},
            {"role": "assistant", "content": "Here are the SS2A students."},
        ]

        result = parse_phase_one_command("Generate their report cards", history=history)
        self.assertEqual(result["tool"], "generate_report_cards")
        self.assertEqual(result["params"]["class_name"], "SS2A")

    def test_workflow_and_monitoring_tools_are_available(self):
        workflow = self.tools.dispatch("run_workflow", {"workflow_name": "new_term_launch"})
        self.assertEqual(workflow["status"], "success")
        self.assertIn("timetable", workflow["tasks"][0]["task"].lower())

        alerts = self.tools.dispatch("get_monitoring_alerts", {})
        self.assertEqual(alerts["status"], "success")
        self.assertTrue(alerts["alerts"])

    def test_bulk_actions_require_explicit_confirmation(self):
        from ai_secretary.agent import run_agent

        blocked = run_agent("Send a reminder to all SS2 parents about the PTA meeting.", [], self.school, self.admin)
        self.assertIn("Please confirm", blocked["reply"])
        self.assertEqual(blocked["tools_called"], [])

        confirmed = run_agent("I confirm the bulk parent reminder for SS2.", [], self.school, self.admin)
        self.assertIn("confirmed", confirmed["reply"].lower())


class PhaseFourAdvancedFeaturesTests(TestCase):
    def setUp(self):
        self.school = SchoolTenant.objects.create(name="Phase Four School", schema_name="phase_four_school", is_active=True)
        self.admin = User.objects.create_user(
            email="admin@phasefour.test",
            password="AdminPass123",
            first_name="Phase",
            last_name="Four",
            role="school_admin",
            tenant=self.school,
            is_active=True,
            is_verified=True,
        )
        self.tools = SecretaryTools(self.school, self.admin)

    def test_predictive_analytics_tool_identifies_risk(self):
        result = self.tools.dispatch("get_predictive_insights", {"metric": "fee_default_risk", "class_name": "SS2"})
        self.assertEqual(result["status"], "success")
        self.assertIn("risk", result["summary"].lower())
        self.assertEqual(result["class_name"], "SS2")

    def test_custom_tool_and_api_access_tools_are_available(self):
        custom_tool = self.tools.dispatch("create_custom_tool", {
            "tool_name": "fee_alerts",
            "description": "Alert when fees are overdue",
            "trigger": "overdue_balance",
        })
        self.assertEqual(custom_tool["status"], "success")
        self.assertIn("fee_alerts", custom_tool["tool_name"])

        api_access = self.tools.dispatch("get_api_access_status", {"service": "schooldom_core"})
        self.assertEqual(api_access["status"], "success")
        self.assertIn("enabled", api_access["status_text"].lower())

    def test_third_party_integrations_have_status_and_sync_actions(self):
        status = self.tools.dispatch("get_integration_status", {"provider": "google_classroom"})
        self.assertEqual(status["status"], "success")
        self.assertIn("google", status["provider"].lower())

        sync = self.tools.dispatch("sync_third_party_integration", {"provider": "google_classroom", "mode": "sync"})
        self.assertEqual(sync["status"], "success")
        self.assertIn("sync", sync["action"].lower())
