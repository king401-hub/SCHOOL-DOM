from django.test import TestCase
from unittest.mock import patch

from django.test import TestCase

from academic.models import AcademicYear, Class, ResultBatch, StudentSubjectScore, Subject, Term, TimetableEntry
from core.models import SchoolTenant
from finance.models import SchoolFee, SmsMessageLog
from finance.services import get_or_create_sms_wallet
from tenants.models import Tenant
from users.models import StudentProfile, User

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
        self.assertEqual(parse_phase_one_command("Show me the roster for JSS2")["tool"], "get_class_roster")
        self.assertEqual(parse_phase_one_command("Who is in SS2A?")["tool"], "get_class_roster")

    def test_core_tools_execute_with_auto_execute_permissions(self):
        # generate_timetable/generate_report_cards now touch real Class/term
        # data and are covered with proper fixtures in PhaseCRealToolsTests
        # below - this class has no seeded Class, so only the tools that
        # don't require one are exercised here.
        fees = self.tools.dispatch("get_fee_status", {})
        self.assertEqual(fees["status"], "success")
        self.assertIn("school", fees["summary"].lower())

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


class LegacyTenantResolutionTests(TestCase):
    """_get_class() (and everything built on it) has to bridge from
    core.SchoolTenant to the legacy tenants.Tenant that academic.Class is
    actually keyed to - filtering Class.objects on self.tenant directly
    compares two unrelated ID spaces and silently finds nothing. Uses a
    deliberately mismatched PK between the two tenant rows so this test can
    only pass if the bridge (_get_legacy_tenant) is actually used."""

    def setUp(self):
        self.school = SchoolTenant.objects.create(name="Legacy Bridge School", schema_name="legacy_bridge_school", is_active=True)
        # Deliberately NOT the same PK as self.school, to prove a naive
        # `tenant=self.tenant` filter (comparing SchoolTenant PKs against
        # tenants.Tenant PKs) could never have matched this row by accident.
        self.legacy_tenant = Tenant.objects.create(name="Legacy Bridge School (legacy)", slug="legacy_bridge_school")
        self.admin = User.objects.create_user(
            email="admin@legacybridge.test",
            password="AdminPass123",
            first_name="Legacy",
            last_name="Admin",
            role="school_admin",
            tenant=self.school,
            is_active=True,
            is_verified=True,
        )
        self.class_obj = Class.objects.create(tenant=self.legacy_tenant, name="SS2A")
        self.tools = SecretaryTools(self.school, self.admin)

    def test_get_class_resolves_via_legacy_tenant_bridge(self):
        found = self.tools._get_class("SS2A")
        self.assertIsNotNone(found)
        self.assertEqual(found.id, self.class_obj.id)


class PhaseTwoAdminAgentTests(TestCase):
    def setUp(self):
        self.school = SchoolTenant.objects.create(name="Phase Two School", schema_name="phase_two_school", is_active=True)
        self.legacy_tenant = Tenant.objects.create(name="Phase Two School (legacy)", slug="phase_two_school")
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
        self.class_obj = Class.objects.create(tenant=self.legacy_tenant, name="JSS2")

    def _make_student(self, email, guardian_phone, guardian_name="Guardian"):
        user = User.objects.create_user(
            email=email, password="StudentPass123", first_name="Student", last_name=email.split("@")[0],
            role="student", tenant=self.school, is_active=True, is_verified=True,
        )
        return StudentProfile.objects.create(
            user=user, student_id=f"STU-{email}", admission_number=f"ADM-{email}",
            admission_date="2026-01-01", current_class=self.class_obj,
            guardian_name=guardian_name, guardian_phone=guardian_phone, guardian_relation="Parent",
        )

    def test_context_management_uses_recent_class_reference(self):
        from ai_secretary.agent import parse_phase_one_command

        history = [
            {"role": "user", "content": "Show me SS2A students"},
            {"role": "assistant", "content": "Here are the SS2A students."},
        ]

        result = parse_phase_one_command("Generate their report cards", history=history)
        self.assertEqual(result["tool"], "generate_report_cards")
        self.assertEqual(result["params"]["class_name"], "SS2A")

    def test_bulk_actions_require_explicit_confirmation(self):
        from ai_secretary.agent import run_agent

        self._make_student("parent1@jss2.test", "08010000010")

        blocked = run_agent("Send a reminder to all JSS2 parents about the PTA meeting.", [], self.school, self.admin)
        self.assertIn("Please confirm", blocked["reply"])
        self.assertEqual(blocked["tools_called"], [])

        history = [
            {"role": "user", "content": "Send a reminder to all JSS2 parents about the PTA meeting."},
            {"role": "assistant", "content": blocked["reply"]},
        ]
        with patch("finance.services.send_termii_whatsapp", return_value={"status": "success", "data": {"id": "wa-1"}}):
            confirmed = run_agent("I confirm the bulk parent message for JSS2.", history, self.school, self.admin)
        self.assertEqual(confirmed["tools_called"], ["send_bulk_parent_message"])
        self.assertIn("jss2", confirmed["reply"].lower())

    def test_bulk_confirm_uses_the_original_request_not_a_hardcoded_default(self):
        """Regression test: the confirmed-send branch used to always dispatch
        class_name="SS2" and a canned "PTA meeting reminder" message
        regardless of what was actually typed - assert the real class and
        message content from the ORIGINAL request survive the confirmation
        round-trip."""
        from ai_secretary.agent import run_agent

        self._make_student("parent2@jss2.test", "08010000011")

        original_text = "Send a bulk message to all JSS2 parents: School closes early on Friday for staff training."
        blocked = run_agent(original_text, [], self.school, self.admin)
        history = [
            {"role": "user", "content": original_text},
            {"role": "assistant", "content": blocked["reply"]},
        ]

        with patch("ai_secretary.tools.SecretaryTools.send_bulk_parent_message") as mock_send:
            mock_send.return_value = {"status": "success", "message": "sent", "delivered_count": 1, "failed_count": 0}
            run_agent("I confirm the bulk parent message for JSS2.", history, self.school, self.admin)

        mock_send.assert_called_once()
        _args, kwargs = mock_send.call_args
        self.assertEqual(kwargs["class_name"], "JSS2")
        self.assertNotEqual(kwargs["class_name"], "SS2")
        self.assertIn("staff training", kwargs["message"].lower())
        self.assertNotEqual(kwargs["message"], "PTA meeting reminder")


class PhaseCRealToolsTests(TestCase):
    """generate_timetable, generate_report_cards, and get_fee_status (class
    scope) all used to fabricate success ("10 entries created", "82%
    collected") regardless of what data existed. These fixtures seed a real
    legacy Tenant, Class, Subject, active Term/AcademicYear, and fee/score
    rows so the assertions below check genuine computed numbers instead of
    passing by coincidence against an empty test DB."""

    def setUp(self):
        self.school = SchoolTenant.objects.create(name="Phase C School", schema_name="phase_c_school", is_active=True)
        self.legacy_tenant = Tenant.objects.create(name="Phase C School (legacy)", slug="phase_c_school")
        self.admin = User.objects.create_user(
            email="admin@phasec.test",
            password="AdminPass123",
            first_name="Phase",
            last_name="C",
            role="school_admin",
            tenant=self.school,
            is_active=True,
            is_verified=True,
        )
        self.tools = SecretaryTools(self.school, self.admin)

        self.academic_year = AcademicYear.objects.create(
            tenant=self.legacy_tenant, name="2025/2026", start_date="2025-09-01", end_date="2026-07-31", is_active=True,
        )
        self.term = Term.objects.create(
            tenant=self.legacy_tenant, name="First Term", start_date="2025-09-01", end_date="2025-12-15",
            is_active=True, academic_year=self.academic_year,
        )
        self.subject = Subject.objects.create(tenant=self.legacy_tenant, name="Mathematics", code="MTH")
        self.class_obj = Class.objects.create(tenant=self.legacy_tenant, name="SS2A")
        self.class_obj.subjects.set([self.subject])

    def _make_student(self, email, guardian_phone="08010000000"):
        user = User.objects.create_user(
            email=email, password="StudentPass123", first_name="Student", last_name=email.split("@")[0],
            role="student", tenant=self.school, is_active=True, is_verified=True,
        )
        return StudentProfile.objects.create(
            user=user, student_id=f"STU-{email}", admission_number=f"ADM-{email}",
            admission_date="2026-01-01", current_class=self.class_obj,
            guardian_name="Guardian", guardian_phone=guardian_phone, guardian_relation="Parent",
        )

    def test_generate_timetable_creates_real_entries(self):
        result = self.tools.dispatch("generate_timetable", {"class_name": "SS2A", "term": "First Term"})
        self.assertEqual(result["status"], "success")
        self.assertGreater(result["entries_created"], 0)
        self.assertEqual(TimetableEntry.objects.filter(class_group=self.class_obj).count(), result["entries_created"])

    def test_generate_timetable_is_idempotent(self):
        first = self.tools.dispatch("generate_timetable", {"class_name": "SS2A"})
        second = self.tools.dispatch("generate_timetable", {"class_name": "SS2A"})
        self.assertGreater(first["entries_created"], 0)
        self.assertEqual(second["entries_created"], 0)
        self.assertGreater(second["skipped_existing_count"], 0)

    def test_generate_timetable_unknown_class_reports_not_found(self):
        result = self.tools.dispatch("generate_timetable", {"class_name": "GhostClass"})
        self.assertEqual(result["status"], "error")
        self.assertEqual(result["error_code"], "NOT_FOUND")

    def test_generate_report_cards_reports_real_readiness(self):
        published = self._make_student("ready@ssa.test")
        self._make_student("pending@ssa.test")
        StudentSubjectScore.objects.create(
            student=published, subject=self.subject, class_group=self.class_obj, term=self.term,
            score=80, max_score=100, approval_status=ResultBatch.PUBLISHED,
        )

        result = self.tools.dispatch("generate_report_cards", {"class_name": "SS2A"})
        self.assertEqual(result["status"], "success")
        self.assertEqual(result["class_size"], 2)
        self.assertEqual(result["ready_count"], 1)
        self.assertEqual(result["pending_count"], 1)
        self.assertIn("1 of 2", result["message"])

    def test_generate_report_cards_unknown_class_reports_not_found(self):
        result = self.tools.dispatch("generate_report_cards", {"class_name": "GhostClass"})
        self.assertEqual(result["status"], "error")
        self.assertEqual(result["error_code"], "NOT_FOUND")

    def test_get_fee_status_reports_real_percentages_for_a_class(self):
        student = self._make_student("feestudent@ssa.test")
        SchoolFee.objects.create(student=student, title="Tuition", amount=10000, due_date="2026-01-01", status=SchoolFee.STATUS_PAID)
        SchoolFee.objects.create(student=student, title="Books", amount=5000, due_date="2026-01-01", status=SchoolFee.STATUS_PENDING)

        result = self.tools.dispatch("get_fee_status", {"class_name": "SS2A"})
        self.assertEqual(result["status"], "success")
        self.assertAlmostEqual(result["collected_percent"], 66.7, places=1)
        self.assertEqual(result["total_due"], 15000.0)
        self.assertEqual(result["total_paid"], 10000.0)
