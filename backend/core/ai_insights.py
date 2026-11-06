"""Short, AI-phrased one-liners for proactive admin notifications (e.g. "4
students have overdue fees totalling X") - a thin wrapper around OpenRouter
that never raises: on any failure it returns None so the caller falls back to
a plain templated message instead of losing the underlying alert to an AI
hiccup. Only produces text under AI_PROVIDER=openrouter (see
ai_chat/README_openrouter.md); there is no Ollama equivalent wired up for
this one-shot use case.
"""
import logging

from django.conf import settings

logger = logging.getLogger(__name__)


def generate_ai_opinion(prompt, *, system_prompt=None, max_tokens=120, temperature=0.6):
    """Returns a short AI-written string, or None if OpenRouter isn't the
    configured provider, or every configured model (default + fallbacks)
    failed. Mirrors the model-fallback loop in ai_chat.views._chat_via_openrouter."""
    if getattr(settings, "AI_PROVIDER", "ollama") != "openrouter":
        return None

    from ai_chat.services.openrouter_client import (
        OpenRouterClient,
        OpenRouterError,
        OpenRouterTimeout,
        fallback_model_candidates,
        is_model_fallback_worthy,
    )

    messages = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    messages.append({"role": "user", "content": prompt})

    candidates = fallback_model_candidates(getattr(settings, "OPENROUTER_DEFAULT_MODEL", "qwen/qwen3.8-27b"))
    for index, candidate_model in enumerate(candidates):
        try:
            result = OpenRouterClient(model=candidate_model).chat(
                messages, max_tokens=max_tokens, temperature=temperature
            )
            content = (result.get("content") or "").strip()
            return content or None
        except (OpenRouterTimeout, OpenRouterError) as exc:
            if index == len(candidates) - 1 or not is_model_fallback_worthy(exc):
                logger.warning("AI opinion generation failed (model=%s): %s", candidate_model, exc)
                return None
            logger.warning(
                "AI opinion generation: model %s unavailable (%s) - trying next configured model.",
                candidate_model, exc,
            )
    return None
