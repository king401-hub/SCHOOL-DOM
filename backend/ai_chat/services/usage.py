"""Server-side, concurrency-safe AI usage quota.

Each user gets USAGE_LIMIT_SECONDS of actual AI processing time per
RESET_WINDOW_SECONDS cycle, where the cycle's window starts at that user's
FIRST AI request of the cycle - not when the allowance runs out, and not at
any calendar boundary. The 1-hour allowance and 3-hour reset timer run
concurrently from that same starting instant (see the module docstring in
ai_chat/models.py and the spec this was built from for worked examples).

Shared by ai_chat (plain chat) and ai_secretary (tool-calling Secretary) -
a user has ONE combined pool across both surfaces, not a separate budget
each, since both ultimately call the same AI providers.

"Actual AI processing time" = wall-clock duration of a real call to the AI
provider, start to resolution, whatever the outcome (success, error after
exhausting internal retries, or the client disconnecting mid-stream).
Requests rejected before any provider call is attempted (quota already
exhausted, a role/auth check, a deterministic non-AI fast path) consume
zero seconds - callers are responsible for only timing the portion of their
work that is an actual provider call (see ai_chat/views.py and
ai_secretary/agent.py for how each wraps its provider call(s)).

All reads/writes here are atomic (transaction.atomic + select_for_update),
so concurrent requests from the same user - two tabs, two devices, a retry
after a dropped connection - can never race on usage_seconds or both reset
the same cycle.
"""
from datetime import timedelta

from django.db import transaction
from django.db.models import F
from django.utils import timezone

from ai_chat.models import AIUsageCycle

USAGE_LIMIT_SECONDS = 3600        # 1 hour of AI processing time per cycle
RESET_WINDOW_SECONDS = 3 * 3600   # cycle resets 3 hours after it started


class AIUsageExhausted(Exception):
    """Raised by check_quota() when the user has no time left this cycle.
    Callers must not call the AI provider at all when this is raised."""

    def __init__(self, cycle: AIUsageCycle):
        self.cycle = cycle
        super().__init__("AI usage allowance exhausted for this cycle.")


def _get_or_reset_cycle(user, tenant) -> AIUsageCycle:
    """The only place a cycle is created or rolled over - always under its
    own row lock, so two concurrent requests from the same user can never
    both create/reset the cycle or both see "no cycle yet"."""
    now = timezone.now()
    with transaction.atomic():
        cycle, created = AIUsageCycle.objects.select_for_update().get_or_create(
            user=user,
            defaults={
                "tenant": tenant,
                "cycle_started_at": now,
                "cycle_resets_at": now + timedelta(seconds=RESET_WINDOW_SECONDS),
                "usage_seconds": 0,
                "usage_limit_seconds": USAGE_LIMIT_SECONDS,
            },
        )
        if not created and now >= cycle.cycle_resets_at:
            cycle.cycle_started_at = now
            cycle.cycle_resets_at = now + timedelta(seconds=RESET_WINDOW_SECONDS)
            cycle.usage_seconds = 0
            cycle.save(update_fields=["cycle_started_at", "cycle_resets_at", "usage_seconds", "updated_at"])
        return cycle


def check_quota(user, tenant) -> AIUsageCycle:
    """Call immediately before starting an AI request - this is what starts
    the 3-hour timer on a user's first request of a cycle. Returns the live
    cycle. Raises AIUsageExhausted if there's no time left; the caller must
    not call the AI provider in that case."""
    cycle = _get_or_reset_cycle(user, tenant)
    if cycle.remaining_seconds <= 0:
        raise AIUsageExhausted(cycle)
    return cycle


def consume_usage(user, seconds: float) -> None:
    """Call after an AI provider call resolves (success, error, or client
    disconnect) with the real wall-clock seconds it took. An atomic F()
    increment - concurrent calls for the same user never clobber each
    other. A non-positive duration is a no-op (nothing to charge)."""
    whole_seconds = int(round(seconds))
    if whole_seconds <= 0:
        return
    with transaction.atomic():
        AIUsageCycle.objects.select_for_update().filter(user=user).update(
            usage_seconds=F("usage_seconds") + whole_seconds,
            updated_at=timezone.now(),
        )


def usage_snapshot(user) -> dict:
    """Read-only, for a status endpoint - must NEVER create a cycle or
    start the timer (only an actual AI request via check_quota does that).
    If there's no cycle yet, or the existing one's window already elapsed,
    reports a full, not-yet-started allowance without writing anything."""
    cycle = AIUsageCycle.objects.filter(user=user).first()
    now = timezone.now()
    if cycle is None or now >= cycle.cycle_resets_at:
        return {
            "cycle_started_at": None,
            "cycle_resets_at": None,
            "usage_seconds": 0,
            "usage_limit_seconds": USAGE_LIMIT_SECONDS,
            "remaining_seconds": USAGE_LIMIT_SECONDS,
            "status": "active",
        }
    return {
        "cycle_started_at": cycle.cycle_started_at.isoformat(),
        "cycle_resets_at": cycle.cycle_resets_at.isoformat(),
        "usage_seconds": cycle.usage_seconds,
        "usage_limit_seconds": cycle.usage_limit_seconds,
        "remaining_seconds": cycle.remaining_seconds,
        "status": cycle.status,
    }


def usage_dict(cycle: AIUsageCycle) -> dict:
    """Shape a live cycle object the same way usage_snapshot() does, for
    callers (the 429 response paths) that already have the cycle in hand
    from check_quota()/AIUsageExhausted and don't need a fresh query."""
    return {
        "cycle_started_at": cycle.cycle_started_at.isoformat(),
        "cycle_resets_at": cycle.cycle_resets_at.isoformat(),
        "usage_seconds": cycle.usage_seconds,
        "usage_limit_seconds": cycle.usage_limit_seconds,
        "remaining_seconds": cycle.remaining_seconds,
        "status": cycle.status,
    }
