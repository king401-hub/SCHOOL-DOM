"""Tests for ai_chat.services.usage - the backend-enforced AI usage quota
(1 hour of actual AI processing time per 3-hour cycle, reset timer starting
at the user's first AI request of that cycle)."""
from datetime import timedelta
from unittest.mock import patch

from django.test import TestCase
from django.utils import timezone

from core.models import SchoolTenant
from users.models import User

from ai_chat.models import AIUsageCycle
from ai_chat.services.usage import (
    RESET_WINDOW_SECONDS,
    USAGE_LIMIT_SECONDS,
    AIUsageExhausted,
    check_quota,
    consume_usage,
    usage_snapshot,
)


class UsageQuotaTests(TestCase):
    def setUp(self):
        self.school = SchoolTenant.objects.create(name="Usage School", schema_name="usage_school", is_active=True)
        self.user = User.objects.create_user(
            email="user@usage.test",
            password="Pass12345",
            first_name="Usage",
            last_name="Tester",
            role="school_admin",
            tenant=self.school,
            is_active=True,
            is_verified=True,
        )

    def test_first_request_starts_a_fresh_cycle(self):
        before = timezone.now()
        cycle = check_quota(self.user, self.school)
        after = timezone.now()

        self.assertTrue(before <= cycle.cycle_started_at <= after)
        expected_reset = cycle.cycle_started_at + timedelta(seconds=RESET_WINDOW_SECONDS)
        self.assertEqual(cycle.cycle_resets_at, expected_reset)
        self.assertEqual(cycle.usage_seconds, 0)
        self.assertEqual(cycle.usage_limit_seconds, USAGE_LIMIT_SECONDS)
        self.assertEqual(cycle.remaining_seconds, USAGE_LIMIT_SECONDS)
        self.assertEqual(cycle.status, "active")

    def test_consume_usage_deducts_from_the_allowance(self):
        check_quota(self.user, self.school)
        consume_usage(self.user, 20 * 60)  # 20 minutes, matching the spec's worked example

        cycle = AIUsageCycle.objects.get(user=self.user)
        self.assertEqual(cycle.usage_seconds, 1200)
        self.assertEqual(cycle.remaining_seconds, 2400)  # 40 minutes left

    def test_consume_usage_accumulates_across_multiple_requests(self):
        check_quota(self.user, self.school)
        consume_usage(self.user, 600)
        consume_usage(self.user, 900)

        cycle = AIUsageCycle.objects.get(user=self.user)
        self.assertEqual(cycle.usage_seconds, 1500)

    def test_consume_usage_ignores_non_positive_durations(self):
        check_quota(self.user, self.school)
        consume_usage(self.user, 0)
        consume_usage(self.user, -5)

        cycle = AIUsageCycle.objects.get(user=self.user)
        self.assertEqual(cycle.usage_seconds, 0)

    def test_check_quota_raises_once_allowance_is_exhausted(self):
        check_quota(self.user, self.school)
        consume_usage(self.user, USAGE_LIMIT_SECONDS)

        with self.assertRaises(AIUsageExhausted) as ctx:
            check_quota(self.user, self.school)
        self.assertEqual(ctx.exception.cycle.remaining_seconds, 0)
        self.assertEqual(ctx.exception.cycle.status, "exhausted")

    def test_task_that_overruns_remaining_time_is_simply_allowed_to_finish(self):
        """Matches the spec's worked example exactly: a task is never cut
        off mid-flight for exceeding what was left when it started - it
        just leaves the cycle at (or past) zero afterward."""
        check_quota(self.user, self.school)
        consume_usage(self.user, 3500)  # 100s remaining
        consume_usage(self.user, 400)   # this single "task" overruns it

        cycle = AIUsageCycle.objects.get(user=self.user)
        self.assertEqual(cycle.usage_seconds, 3900)
        self.assertEqual(cycle.remaining_seconds, 0)
        self.assertEqual(cycle.status, "exhausted")

    def test_cycle_resets_after_the_3_hour_window_even_if_allowance_remains(self):
        """Matches the spec: unused time does not carry over, and the reset
        fires relative to when the cycle STARTED, not when it was exhausted."""
        cycle = check_quota(self.user, self.school)
        consume_usage(self.user, 1200)  # only 20 minutes used, 40 remaining

        future = cycle.cycle_resets_at + timedelta(seconds=1)
        with patch("ai_chat.services.usage.timezone.now", return_value=future):
            fresh = check_quota(self.user, self.school)

        self.assertEqual(fresh.usage_seconds, 0)
        self.assertEqual(fresh.cycle_started_at, future)
        self.assertEqual(fresh.cycle_resets_at, future + timedelta(seconds=RESET_WINDOW_SECONDS))

    def test_reset_timer_starts_at_first_request_not_at_exhaustion(self):
        """The 10:00/10:20/11:00/13:00 worked example from the spec: usage
        can hit zero well before the 3-hour mark, but the reset still only
        happens at cycle_started_at + 3h, not earlier."""
        cycle = check_quota(self.user, self.school)
        consume_usage(self.user, USAGE_LIMIT_SECONDS)  # fully exhausted at "11:00"

        almost_reset = cycle.cycle_resets_at - timedelta(seconds=1)
        with patch("ai_chat.services.usage.timezone.now", return_value=almost_reset):
            with self.assertRaises(AIUsageExhausted):
                check_quota(self.user, self.school)

        at_reset = cycle.cycle_resets_at
        with patch("ai_chat.services.usage.timezone.now", return_value=at_reset):
            fresh = check_quota(self.user, self.school)
        self.assertEqual(fresh.remaining_seconds, USAGE_LIMIT_SECONDS)

    def test_usage_snapshot_is_read_only_and_never_starts_the_timer(self):
        """A status/usage poll must not create a cycle or start the 3-hour
        clock - only an actual AI request (check_quota) may do that."""
        snapshot = usage_snapshot(self.user)

        self.assertEqual(snapshot["remaining_seconds"], USAGE_LIMIT_SECONDS)
        self.assertEqual(snapshot["status"], "active")
        self.assertIsNone(snapshot["cycle_started_at"])
        self.assertFalse(AIUsageCycle.objects.filter(user=self.user).exists())

    def test_usage_snapshot_reflects_an_active_cycle(self):
        check_quota(self.user, self.school)
        consume_usage(self.user, 300)

        snapshot = usage_snapshot(self.user)
        self.assertEqual(snapshot["usage_seconds"], 300)
        self.assertEqual(snapshot["remaining_seconds"], USAGE_LIMIT_SECONDS - 300)
        self.assertIsNotNone(snapshot["cycle_started_at"])

    def test_two_users_have_independent_allowances(self):
        other = User.objects.create_user(
            email="other@usage.test", password="Pass12345", first_name="Other", last_name="User",
            role="school_admin", tenant=self.school, is_active=True, is_verified=True,
        )
        check_quota(self.user, self.school)
        check_quota(other, self.school)
        consume_usage(self.user, USAGE_LIMIT_SECONDS)

        with self.assertRaises(AIUsageExhausted):
            check_quota(self.user, self.school)
        # The other user's allowance is untouched.
        check_quota(other, self.school)
