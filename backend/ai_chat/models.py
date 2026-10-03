"""Backend-enforced AI usage quota: each user gets a fixed amount of actual
AI processing time per rolling cycle, where the cycle's reset window starts
at that user's FIRST AI request of the cycle (not at exhaustion, not at a
calendar boundary). One shared pool per user across both AI surfaces
(ai_chat's plain chat and ai_secretary's tool-calling Secretary) - see
services/usage.py for the atomic check/consume logic both call into.
"""
from django.db import models


class AIUsageCycle(models.Model):
    user = models.OneToOneField(
        "users.User", on_delete=models.CASCADE, related_name="ai_usage_cycle",
    )
    tenant = models.ForeignKey(
        "core.SchoolTenant", on_delete=models.CASCADE, related_name="ai_usage_cycles",
    )
    cycle_started_at = models.DateTimeField()
    cycle_resets_at = models.DateTimeField()
    usage_seconds = models.PositiveIntegerField(default=0)
    usage_limit_seconds = models.PositiveIntegerField(default=3600)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [models.Index(fields=["cycle_resets_at"])]

    @property
    def remaining_seconds(self) -> int:
        return max(0, self.usage_limit_seconds - self.usage_seconds)

    @property
    def status(self) -> str:
        return "exhausted" if self.remaining_seconds <= 0 else "active"

    def __str__(self):
        return f"{self.user} — {self.usage_seconds}/{self.usage_limit_seconds}s"
