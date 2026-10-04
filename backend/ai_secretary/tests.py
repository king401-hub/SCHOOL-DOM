import time

from django.test import TestCase
from unittest.mock import patch

from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from academic.models import AcademicYear, Class, ResultBatch, StudentSubjectScore, Subject, Term, TimetableEntry
from core.models import SchoolTenant
from finance.models import SchoolFee, SmsMessageLog
from finance.services import get_or_create_sms_wallet
from tenants.models import Tenant
from users.models import StudentProfile, User

from ai_chat.models import AIUsageCycle
from ai_chat.services.usage import USAGE_LIMIT_SECONDS, check_quota, consume_usage
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

    @patch("finance.services._dispatch_wallet_sms")
    def test_send_sms_charges_wallet_only_after_provider_confirms(self, mock_send):
        mock_send.return_value = {"response": {"status": "SUCCESS", "totalsent": 1, "cost": 4}}
        wallet = get_or_create_sms_wallet(self.school)
        starting_balance = wallet.balance

        result = self.tools.send_sms("08010000001", "Reminder: PTA meeting tomorrow.")

        self.assertEqual(result["status"], "success")
        wallet.refresh_from_db()
        self.assertEqual(wallet.balance, starting_balance - 1)
        self.assertTrue(SmsMessageLog.objects.filter(category=SmsMessageLog.OTHER, delivery_status=SmsMessageLog.SENT).exists())

    @patch("finance.services._dispatch_wallet_sms")
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
        self.assertEqual(parse_phase_one_command("List my classes")["tool"], "list_classes")
        self.assertEqual(parse_phase_one_command("Name the classes")["tool"], "list_classes")
        self.assertEqual(parse_phase_one_command("What classes do I have?")["tool"], "list_classes")

    def test_core_tools_execute_with_auto_execute_permissions(self):
        # generate_timetable/generate_report_cards now touch real Class/term
        # data and are covered with proper fixtures in PhaseCRealToolsTests
        # below - this class has no seeded Class, so only the tools that
        # don't require one are exercised here. create_cbt_exam WITH real
        # question-bank fixtures is also covered there now - here it's just
        # proving an unresolvable subject reports NOT_FOUND instead of
        # fabricating a "50 questions" success like an earlier draft did.
        fees = self.tools.dispatch("get_fee_status", {})
        self.assertEqual(fees["status"], "success")
        self.assertIn("school", fees["summary"].lower())

        cbt = self.tools.dispatch("create_cbt_exam", {"subject": "Biology", "class_name": "SS2", "question_count": 50, "time_limit_minutes": 60})
        self.assertEqual(cbt["status"], "error")
        self.assertEqual(cbt["error_code"], "NOT_FOUND")

        nav = self.tools.dispatch("navigate_to_page", {"page": "fee management"})
        self.assertEqual(nav["status"], "success")
        self.assertIn("fee", nav["page"].lower())

    def test_navigation_command_returns_route_for_client_navigation(self):
        from ai_secretary.agent import run_agent

        result = run_agent("Take me to the fee management page", [], self.school, self.admin)
        self.assertEqual(result["tools_called"], ["navigate_to_page"])
        self.assertEqual(result["route"], "/finance")

    def test_code_signal_backstop_applies_to_the_admin_agent_path(self):
        """Regression test for the Phase D unification: the code-signal
        kill-switch used to exist only in ai_chat's Phoenix persona - the
        Secretary agent ran the same local model with zero backstop of its
        own. A free-text request (not routed to any Phase 1 tool) that gets a
        code-shaped reply back from Ollama must be refused, not shown as-is."""
        from ai_secretary.agent import run_agent
        from ai_secretary.code_guard import CODE_REFUSAL_MESSAGE

        fake_response = {"message": {"content": "Sure:\n```python\nprint('hi')\n```", "tool_calls": []}}
        with patch("ai_secretary.agent._call_ollama", return_value=fake_response):
            result = run_agent("Can you write me a Python script for attendance?", [], self.school, self.admin)

        self.assertIn(CODE_REFUSAL_MESSAGE.strip(), result["reply"])
        self.assertNotIn("```", result["reply"])

    def test_fake_tool_call_in_plain_content_is_recovered_and_executed(self):
        """Regression test: llama3.2:3b sometimes fails to use Ollama's
        native tool_calls field and instead writes out a hand-rolled
        imitation of its own TOOL_SCHEMAS definition as plain content -
        using "parameters" (the schema's own key name) instead of
        "arguments" (what a real tool_calls entry uses). This used to leak
        straight to the admin as raw JSON instead of creating anything -
        it must now be recovered and actually executed."""
        from ai_secretary.agent import run_agent

        fake_call_text = (
            '{"type":"function","function":{"name": "create_cbt_exam", '
            '"parameters": {"subject": "Maths", "class_name": "SS2A", '
            '"question_count": 20, "time_limit_minutes": 120}}}'
        )
        responses = [
            {"message": {"content": fake_call_text, "tool_calls": []}},
            {"message": {"content": "Done! I've created the CBT exam.", "tool_calls": []}},
        ]
        with patch("ai_secretary.agent._call_ollama", side_effect=responses):
            result = run_agent(
                "Please set up an exam for Maths in SS2A, 20 questions, 120 minutes.",
                [], self.school, self.admin,
            )

        self.assertEqual(result["tools_called"], ["create_cbt_exam"])
        self.assertNotIn("{", result["reply"])
        self.assertIn("created", result["reply"].lower())

    def test_fake_tool_call_for_unknown_tool_is_not_leaked(self):
        """A tool-call-shaped blob that doesn't match any real tool (bad
        name, or JSON too malformed to recover) must still never reach the
        admin as raw JSON, same principle as the code-signal backstop."""
        from ai_secretary.agent import run_agent
        from ai_secretary.code_guard import TOOL_CALL_LEAK_MESSAGE

        fake_call_text = '{"name": "delete_the_whole_database", "arguments": {}}'
        with patch(
            "ai_secretary.agent._call_ollama",
            return_value={"message": {"content": fake_call_text, "tool_calls": []}},
        ):
            result = run_agent("Can you tidy up the records for me?", [], self.school, self.admin)

        self.assertEqual(result["tools_called"], [])
        self.assertIn(TOOL_CALL_LEAK_MESSAGE.strip(), result["reply"])
        self.assertNotIn("{", result["reply"])

    @override_settings(AI_PROVIDER="openrouter")
    def test_openrouter_tool_call_is_executed_and_summarized(self):
        """With AI_PROVIDER=openrouter, run_agent must route through
        OpenRouterClient instead of Ollama, execute a real tool_calls entry
        the same way the Ollama path does, and feed its result back for a
        natural-language summary."""
        from ai_secretary.agent import run_agent

        responses = [
            {"content": "", "tool_calls": [
                {"id": "call_1", "type": "function", "function": {"name": "count_students", "arguments": "{}"}},
            ]},
            {"content": "There are 0 students enrolled.", "tool_calls": []},
        ]
        with patch("ai_secretary.agent.OpenRouterClient") as mock_client_cls:
            mock_client_cls.return_value.chat.side_effect = responses
            result = run_agent(
                "Give me a full report on enrollment, attendance and fees for this term.",
                [], self.school, self.admin,
            )

        self.assertEqual(result["tools_called"], ["count_students"])
        self.assertIn("0 students", result["reply"])

    @override_settings(AI_PROVIDER="openrouter")
    def test_openrouter_timeout_returns_friendly_message(self):
        from ai_secretary.agent import run_agent
        from ai_chat.services.openrouter_client import OpenRouterTimeout

        with patch("ai_secretary.agent.OpenRouterClient") as mock_client_cls:
            mock_client_cls.return_value.chat.side_effect = OpenRouterTimeout("timed out")
            result = run_agent("What's the best way to plan next term's curriculum?", [], self.school, self.admin)

        self.assertIn("taking too long", result["reply"])
        self.assertEqual(result["tools_called"], [])

    @override_settings(AI_PROVIDER="openrouter")
    def test_openrouter_insufficient_credit_returns_friendly_message(self):
        from ai_secretary.agent import run_agent
        from ai_chat.services.openrouter_client import OpenRouterError

        with patch("ai_secretary.agent.OpenRouterClient") as mock_client_cls:
            mock_client_cls.return_value.chat.side_effect = OpenRouterError("no credit", status_code=402)
            result = run_agent("What's the best way to plan next term's curriculum?", [], self.school, self.admin)

        self.assertIn("out of credits", result["reply"])

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

    def test_list_classes_returns_real_names_and_live_student_counts(self):
        """Regression test: the admin agent used to have no way to discover
        real class names at all - only count_classes (a bare number), which
        made it guess ("SS2" instead of the real "SS2A") and fail every
        class-specific tool call. list_classes must report the exact name."""
        self._make_student("one@ssa.test")
        self._make_student("two@ssa.test")

        result = self.tools.dispatch("list_classes", {})

        self.assertEqual(result["status"], "success")
        self.assertEqual(result["total"], 1)
        self.assertEqual(result["classes"][0]["name"], "SS2A")
        self.assertEqual(result["classes"][0]["student_count"], 2)
        self.assertIn("SS2A", result["message"])

    def _full_name(self, student_profile):
        # Matches get_daily_briefing's own "first last" construction - not
        # User.get_full_name(), which orders names differently in this codebase.
        return f"{student_profile.user.first_name} {student_profile.user.last_name}".strip()

    def test_daily_briefing_reports_defaulters_and_yesterdays_payments(self):
        from datetime import timedelta

        from django.utils import timezone as dj_timezone

        from finance.models import Transaction
        from finance.services import get_or_create_admin_wallet

        defaulter = self._make_student("defaulter@ssa.test")
        SchoolFee.objects.create(student=defaulter, title="Tuition", amount=8000, due_date="2026-01-01", status=SchoolFee.STATUS_PENDING)
        paid_up = self._make_student("paidup@ssa.test")
        SchoolFee.objects.create(student=paid_up, title="Tuition", amount=8000, due_date="2026-01-01", status=SchoolFee.STATUS_PAID)

        wallet = get_or_create_admin_wallet(self.school)
        tx = Transaction.objects.create(
            admin_wallet=wallet, amount=5000, tx_type=Transaction.FEE_CREDIT,
            status=Transaction.STATUS_SUCCESS, reference="briefing-test-1",
        )
        yesterday = dj_timezone.now() - timedelta(days=1)
        Transaction.objects.filter(pk=tx.pk).update(created_at=yesterday)

        result = self.tools.get_daily_briefing()

        self.assertEqual(result["status"], "success")
        names = [d["name"] for d in result["defaulters"]]
        self.assertIn(self._full_name(defaulter), names)
        self.assertNotIn(self._full_name(paid_up), names)
        self.assertEqual(result["total_outstanding"], 8000.0)
        self.assertEqual(result["yesterday_total"], 5000.0)
        self.assertEqual(result["yesterday_count"], 1)

    def test_create_student_builds_a_real_profile_that_other_tools_can_see(self):
        """Regression test: create_student used to make a bare User with no
        StudentProfile at all, so an AI-registered student was silently
        invisible to get_class_roster/count_students/send_bulk_parent_message
        (all of which query StudentProfile, not User, for class/guardian
        data) - this proves the round trip actually works now."""
        from users.models import StudentProfile

        result = self.tools.dispatch("create_student", {
            "name": "New Student",
            "phone": "08011112222",
            "class_name": "SS2A",
            "guardian_name": "Mrs Guardian",
        })

        self.assertEqual(result["status"], "success")
        self.assertEqual(result["guardian_phone"], "+2348011112222")

        profile = StudentProfile.objects.get(user__first_name="New", user__last_name="Student")
        self.assertEqual(profile.current_class, self.class_obj)
        self.assertEqual(profile.guardian_name, "Mrs Guardian")
        self.assertEqual(profile.guardian_relation, "Guardian")
        self.assertTrue(profile.student_id)
        self.assertTrue(profile.admission_number)

        roster = self.tools.dispatch("get_class_roster", {"class_name": "SS2A"})
        self.assertEqual(roster["status"], "success")
        self.assertIn(profile.user.get_full_name(), [s["name"] for s in roster["roster"]])

        count = self.tools.dispatch("count_students", {"class_name": "SS2A"})
        self.assertEqual(count["total"], 1)

    def test_create_student_requires_guardian_name(self):
        result = self.tools.dispatch("create_student", {
            "name": "No Guardian", "phone": "08011112222", "class_name": "SS2A", "guardian_name": "",
        })
        self.assertEqual(result["status"], "error")
        self.assertEqual(result["error_code"], "BAD_ARGS")

    def test_create_student_unknown_class_reports_not_found(self):
        result = self.tools.dispatch("create_student", {
            "name": "Ghost Class Student", "phone": "08011112222", "class_name": "GhostClass", "guardian_name": "Someone",
        })
        self.assertEqual(result["status"], "error")
        self.assertEqual(result["error_code"], "NOT_FOUND")

    def test_create_teacher_needs_only_name_phone_email(self):
        from users.models import TeacherProfile

        result = self.tools.dispatch("create_teacher", {
            "name": "New Teacher", "phone": "08033334444", "email": "new.teacher@ssa.test",
        })

        self.assertEqual(result["status"], "success")
        self.assertTrue(result["employee_id"])
        profile = TeacherProfile.objects.get(user__email="new.teacher@ssa.test")
        self.assertEqual(profile.user.role, "teacher")
        self.assertEqual(profile.qualification, "Not specified")
        self.assertEqual(profile.emergency_contact_name, "Not provided")

    def test_create_teacher_requires_email(self):
        result = self.tools.dispatch("create_teacher", {"name": "No Email", "phone": "08033334444", "email": ""})
        self.assertEqual(result["status"], "error")
        self.assertEqual(result["error_code"], "BAD_ARGS")

    def test_create_teacher_rejects_duplicate_email(self):
        self.tools.dispatch("create_teacher", {"name": "First", "phone": "08033334444", "email": "dupe@ssa.test"})
        result = self.tools.dispatch("create_teacher", {"name": "Second", "phone": "08055556666", "email": "dupe@ssa.test"})
        self.assertEqual(result["status"], "error")
        self.assertEqual(result["error_code"], "DUPLICATE")

    def test_create_class_creates_a_real_class(self):
        result = self.tools.dispatch("create_class", {"name": "JSS1", "section": "B"})

        self.assertEqual(result["status"], "success")
        self.assertTrue(Class.objects.filter(tenant=self.legacy_tenant, name__iexact="JSS1", section__iexact="B").exists())

    def test_create_class_rejects_duplicate(self):
        result = self.tools.dispatch("create_class", {"name": "SS2A"})
        self.assertEqual(result["status"], "error")
        self.assertEqual(result["error_code"], "DUPLICATE")

    def test_create_class_requires_name(self):
        result = self.tools.dispatch("create_class", {"name": ""})
        self.assertEqual(result["status"], "error")
        self.assertEqual(result["error_code"], "BAD_ARGS")

    def test_create_cbt_exam_pulls_real_questions_from_the_bank(self):
        """Regression test: create_cbt_exam used to create an empty exam
        shell and just claim "{question_count} questions" in its message
        regardless of whether any existed - same shape of bug create_student
        had for StudentProfile."""
        from exams.models import Exam, Question, QuestionBank

        bank = QuestionBank.objects.create(tenant=self.legacy_tenant, name="Math Bank", subject=self.subject, teacher=self.admin)
        bank.questions.set([
            Question.objects.create(tenant=self.legacy_tenant, question_type="mcq", text=f"Q{i}", options=["A", "B", "C"], correct_answer="A")
            for i in range(3)
        ])

        result = self.tools.dispatch("create_cbt_exam", {
            "subject": "Mathematics", "class_name": "SS2A", "question_count": 2, "time_limit_minutes": 30,
        })

        self.assertEqual(result["status"], "success")
        self.assertEqual(result["question_count"], 2)
        exam = Exam.objects.get(id=result["exam_id"])
        self.assertEqual(exam.questions.count(), 2)
        self.assertEqual(exam.subject, self.subject)
        self.assertEqual(exam.exam_format, "objective")

    def test_create_cbt_exam_uses_fewer_questions_when_bank_is_short(self):
        from exams.models import Question, QuestionBank

        bank = QuestionBank.objects.create(tenant=self.legacy_tenant, name="Math Bank", subject=self.subject, teacher=self.admin)
        bank.questions.set([
            Question.objects.create(tenant=self.legacy_tenant, question_type="mcq", text="Only one", options=["A", "B"], correct_answer="A"),
        ])

        result = self.tools.dispatch("create_cbt_exam", {"subject": "Mathematics", "class_name": "SS2A", "question_count": 10})

        self.assertEqual(result["status"], "success")
        self.assertEqual(result["question_count"], 1)
        self.assertEqual(result["requested_question_count"], 10)
        self.assertIn("Only 1 question", result["message"])

    def test_create_cbt_exam_unknown_subject_reports_not_found(self):
        result = self.tools.dispatch("create_cbt_exam", {"subject": "Astrophysics", "class_name": "SS2A"})
        self.assertEqual(result["status"], "error")
        self.assertEqual(result["error_code"], "NOT_FOUND")

    def test_create_cbt_exam_with_empty_bank_reports_clearly_instead_of_fabricating(self):
        result = self.tools.dispatch("create_cbt_exam", {"subject": "Mathematics", "class_name": "SS2A"})
        self.assertEqual(result["status"], "error")
        self.assertEqual(result["error_code"], "NO_QUESTIONS")


class SecretaryUsageQuotaTests(TestCase):
    """The /api/secretary/chat/ view must enforce the same AI usage quota
    pool ai_chat uses, but only for turns that actually reach an AI
    provider - deterministic Phase 1 commands (keyword-matched, zero AI
    involvement) must stay free even once the quota is exhausted."""

    def setUp(self):
        from django.core.cache import cache
        cache.clear()  # parse_phase_one_command caches dispatch decisions by
        # message text alone (ai_secretary/agent.py's _cache_key_for_command) -
        # LocMemCache is process-global and not reset between TestCase methods,
        # so a prior test's cached entry for the same message text can leak in.
        self.school = SchoolTenant.objects.create(
            name="Secretary Quota School", schema_name="secretary_quota_school", is_active=True,
        )
        self.admin = User.objects.create_user(
            email="admin@secretaryquota.test", password="AdminPass123", first_name="Quota", last_name="Admin",
            role="school_admin", tenant=self.school, is_active=True, is_verified=True,
        )
        self.client = APIClient()
        self.client.force_authenticate(user=self.admin)

    def test_phase_one_fast_path_is_free_even_when_quota_exhausted(self):
        check_quota(self.admin, self.school)
        consume_usage(self.admin, USAGE_LIMIT_SECONDS)

        response = self.client.post(
            "/api/secretary/chat/", data={"message": "How many students are there?", "history": []}, format="json",
        )

        self.assertEqual(response.status_code, 200)

    @patch("ai_secretary.agent._call_ollama")
    def test_general_chat_returns_429_when_quota_exhausted(self, mock_call_ollama):
        check_quota(self.admin, self.school)
        consume_usage(self.admin, USAGE_LIMIT_SECONDS)

        response = self.client.post(
            "/api/secretary/chat/",
            data={"message": "What's the best way to plan next term's curriculum?", "history": []},
            format="json",
        )

        self.assertEqual(response.status_code, 429)
        self.assertEqual(response.json()["usage"]["remaining_seconds"], 0)
        mock_call_ollama.assert_not_called()

    @patch("ai_secretary.agent._call_ollama")
    def test_general_chat_charges_real_usage_time(self, mock_call_ollama):
        def slow_call(*args, **kwargs):
            time.sleep(1.1)  # forces measured elapsed time to round to >= 1s
            return {"message": {"content": "Here's some curriculum advice.", "tool_calls": []}}

        mock_call_ollama.side_effect = slow_call

        response = self.client.post(
            "/api/secretary/chat/",
            data={"message": "What's the best way to plan next term's curriculum?", "history": []},
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        cycle = AIUsageCycle.objects.get(user=self.admin)
        self.assertGreaterEqual(cycle.usage_seconds, 1)
