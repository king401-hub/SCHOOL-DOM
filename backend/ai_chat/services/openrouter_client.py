"""Synchronous client for OpenRouter's Chat Completions API
(https://openrouter.ai/api/v1/chat/completions - OpenAI-compatible).

Used by ai_chat.views (plain-chat "SchoolDom AI") and ai_secretary.agent
(tool-calling "Secretary") when AI_PROVIDER=openrouter (see
config/settings.py's "OpenRouter" section) as an alternative to the local
Ollama instance - see backend/ai_chat/README_openrouter.md.
"""
import json
import logging
import time
from typing import Iterator, Optional

import requests
from django.conf import settings

logger = logging.getLogger(__name__)

CHAT_COMPLETIONS_PATH = "/chat/completions"
TRANSCRIPTIONS_PATH = "/audio/transcriptions"


DEFAULT_MAX_IMAGE_BYTES = 8_000_000  # ~6 MB decoded; reject anything larger


def clean_data_url_images(raw_images, max_images: int = 2, max_bytes: int = DEFAULT_MAX_IMAGE_BYTES):
    """Parse a list of data: URL (or bare base64) image strings into
    (bare_base64_list, mime_type_list) - shared by ai_chat's and
    ai_secretary's request parsing so both validate/strip attached images
    the same way before either Ollama's `images` field (which wants bare
    base64, nothing else) or build_multimodal_content (which wants the
    MIME type back) gets them."""
    cleaned, mime_types = [], []
    for img in (raw_images or [])[:max_images]:
        if not isinstance(img, str):
            continue
        mime_type = "image/jpeg"
        payload = img
        if ";base64," in img:
            header, payload = img.split(";base64,", 1)
            if header.startswith("data:") and header[len("data:"):]:
                mime_type = header[len("data:"):]
        if len(payload) <= max_bytes:
            cleaned.append(payload)
            mime_types.append(mime_type)
    return cleaned, mime_types


def build_multimodal_content(text: str, images: Optional[list] = None, mime_types: Optional[list] = None):
    """Build an OpenRouter/OpenAI-shaped message `content` value.

    A plain string when there are no images - every existing text-only
    call site is unaffected - or a list of content blocks (one text block
    plus one image_url block per image) when there are. `images` is a list
    of bare base64 strings with no data: prefix (see
    ai_chat.views._clean_messages, which strips it before storing);
    `mime_types` is the matching list of original MIME types the prefix
    carried, falling back to image/jpeg for any entry that's missing one.
    """
    if not images:
        return text
    blocks = [{"type": "text", "text": text}] if text else []
    for index, image_b64 in enumerate(images):
        mime_type = (mime_types[index] if mime_types and index < len(mime_types) else None) or "image/jpeg"
        blocks.append({"type": "image_url", "image_url": {"url": f"data:{mime_type};base64,{image_b64}"}})
    return blocks

# Every field OpenRouter's chat/completions body accepts besides the
# required model/messages (which this client always supplies itself - see
# _build_payload). Anything else is rejected up front rather than silently
# dropped or forwarded to a confusing 400 from OpenRouter itself.
SUPPORTED_PARAMS = frozenset(
    {
        "stream",
        "max_tokens",
        "temperature",
        "top_p",
        "presence_penalty",
        "frequency_penalty",
        "repetition_penalty",
        "stop",
        "tools",
        "tool_choice",
        "reasoning",
        "reasoning_effort",
    }
)

# 429 (rate limited) and 502 (upstream failure - OpenRouter's own docs say
# this is never billed) are worth retrying; every other 4xx/5xx means
# retrying with the same request can't succeed (bad key, no credit, bad
# model name, malformed body) so those raise immediately instead.
_RETRYABLE_STATUS_CODES = frozenset({429, 502})


class OpenRouterError(Exception):
    """A non-retryable (or retry-exhausted) OpenRouter error. `status_code`
    is the HTTP status; `code` is OpenRouter's own error.code when present
    (its shape is {"error": {"code": ..., "message": ...}})."""

    def __init__(self, message: str, *, code=None, status_code: Optional[int] = None):
        super().__init__(message)
        self.code = code
        self.status_code = status_code


class OpenRouterTimeout(Exception):
    """Every attempt (1 + OPENROUTER_MAX_RETRIES) timed out contacting OpenRouter."""


def _backoff_sleep(attempt: int, base: float = 0.5, cap: float = 8.0) -> None:
    """0.5s, 1s, 2s, 4s, ... capped - called between retry attempts."""
    time.sleep(min(cap, base * (2**attempt)))


class OpenRouterClient:
    """One client = one model/config. Cheap to construct per request; holds
    no connection state between calls."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        model: Optional[str] = None,
        timeout: Optional[float] = None,
        max_retries: Optional[int] = None,
        site_url: Optional[str] = None,
        site_name: Optional[str] = None,
    ):
        self.api_key = api_key if api_key is not None else getattr(settings, "OPENROUTER_API_KEY", "")
        self.base_url = (
            base_url or getattr(settings, "OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1")
        ).rstrip("/")
        self.model = model or getattr(settings, "OPENROUTER_DEFAULT_MODEL", "qwen/qwen3.8-27b")
        self.timeout = timeout if timeout is not None else getattr(settings, "OPENROUTER_TIMEOUT", 60)
        self.max_retries = max_retries if max_retries is not None else getattr(settings, "OPENROUTER_MAX_RETRIES", 3)
        self.site_url = site_url if site_url is not None else getattr(settings, "OPENROUTER_SITE_URL", "")
        self.site_name = site_name if site_name is not None else getattr(settings, "OPENROUTER_SITE_NAME", "")

    # ------------------------------------------------------------ helpers

    def _headers(self) -> dict:
        if not self.api_key:
            # Caught by callers the same way a 401 would be - see
            # OpenRouterError.code == "MISSING_API_KEY" in ai_chat/views.py.
            raise OpenRouterError("OPENROUTER_API_KEY is not configured.", code="MISSING_API_KEY")
        headers = {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}
        if self.site_url:
            headers["HTTP-Referer"] = self.site_url
        if self.site_name:
            headers["X-Title"] = self.site_name
        return headers

    def _build_payload(self, messages: list, **kwargs) -> dict:
        unsupported = set(kwargs) - SUPPORTED_PARAMS
        if unsupported:
            raise OpenRouterError(
                f"Unsupported parameter(s): {', '.join(sorted(unsupported))}",
                code="UNSUPPORTED_PARAM",
            )
        payload = {"model": self.model, "messages": messages}
        payload.update(kwargs)
        return payload

    @staticmethod
    def _error_from_response(response) -> "OpenRouterError":
        try:
            body = response.json()
        except ValueError:
            return OpenRouterError(
                f"OpenRouter returned HTTP {response.status_code} with a non-JSON body.",
                status_code=response.status_code,
            )
        error = body.get("error") or {}
        message = error.get("message") or f"OpenRouter request failed with status {response.status_code}."
        return OpenRouterError(message, code=error.get("code"), status_code=response.status_code)

    def _log_error(self, error: "OpenRouterError", *, attempt: int, exhausted: bool) -> None:
        # Model name, status, and code only - never the API key or headers.
        logger.error(
            "OpenRouter error (model=%s, status=%s, code=%s, attempt=%d/%d, retries_exhausted=%s): %s",
            self.model, error.status_code, error.code, attempt + 1, self.max_retries + 1, exhausted, error,
        )

    # --------------------------------------------------------- non-stream

    def chat(self, messages: list, **kwargs) -> dict:
        """POST a non-streaming chat completion.

        Returns {"content": str, "tool_calls": list, "usage": dict, "raw": dict}.
        "tool_calls" is OpenRouter's OpenAI-shaped
        [{"id", "type": "function", "function": {"name", "arguments" (a
        JSON string)}}] list, or [] when the model didn't call one - pass
        tools=[...] (OpenAI/TOOL_SCHEMAS-style function schemas) as a kwarg
        to enable them. Raises OpenRouterError for any non-2xx response
        other than a retried-out 429/502, and OpenRouterTimeout if every
        attempt timed out.
        """
        url = f"{self.base_url}{CHAT_COMPLETIONS_PATH}"
        payload = self._build_payload(messages, **kwargs)
        payload["stream"] = False
        headers = self._headers()

        for attempt in range(self.max_retries + 1):
            try:
                response = requests.post(url, json=payload, headers=headers, timeout=self.timeout)
            except requests.exceptions.Timeout as exc:
                if attempt < self.max_retries:
                    logger.warning(
                        "OpenRouter request timed out (model=%s, attempt=%d/%d) - retrying.",
                        self.model, attempt + 1, self.max_retries + 1,
                    )
                    _backoff_sleep(attempt)
                    continue
                logger.error(
                    "OpenRouter request timed out (model=%s) - retries exhausted.", self.model,
                )
                raise OpenRouterTimeout(
                    f"OpenRouter did not respond within {self.timeout}s after {self.max_retries + 1} attempt(s)."
                ) from exc
            except requests.exceptions.RequestException as exc:
                logger.error("OpenRouter request failed (model=%s): %s", self.model, exc)
                raise OpenRouterError(f"Could not reach OpenRouter: {exc}") from exc

            if response.status_code == 200:
                try:
                    data = response.json()
                except ValueError as exc:
                    raise OpenRouterError("OpenRouter returned a non-JSON success response.") from exc
                choice = (data.get("choices") or [{}])[0]
                message = choice.get("message") or {}
                return {
                    "content": message.get("content") or "",
                    "tool_calls": message.get("tool_calls") or [],
                    "usage": data.get("usage") or {},
                    "raw": data,
                }

            if response.status_code in _RETRYABLE_STATUS_CODES and attempt < self.max_retries:
                logger.warning(
                    "OpenRouter HTTP %s (model=%s, attempt=%d/%d) - retrying.",
                    response.status_code, self.model, attempt + 1, self.max_retries + 1,
                )
                _backoff_sleep(attempt)
                continue

            error = self._error_from_response(response)
            self._log_error(error, attempt=attempt, exhausted=response.status_code in _RETRYABLE_STATUS_CODES)
            raise error

        # Unreachable - the loop above always returns or raises.
        raise OpenRouterError("OpenRouter request failed for an unknown reason.")

    # --------------------------------------------------------- transcribe

    def transcribe(self, audio_base64: str, audio_format: str = "webm", model: Optional[str] = None) -> str:
        """POST a recorded clip to OpenRouter's speech-to-text endpoint and
        return the transcribed text.

        A different endpoint shape from chat/completions entirely (no
        "messages", no streaming, and a model of its own rather than
        self.model) - voice input, not a chat turn, so this bypasses
        _build_payload/_headers' chat-specific assumptions and builds its
        own minimal request. Single attempt, no retry loop: a dropped
        recording is cheap for the admin to just record again, unlike a
        chat turn whose prompt took real typing to compose.
        """
        url = f"{self.base_url}{TRANSCRIPTIONS_PATH}"
        payload = {
            "model": model or getattr(settings, "OPENROUTER_TRANSCRIPTION_MODEL", "elevenlabs/scribe-v2"),
            "input_audio": {"data": audio_base64, "format": audio_format},
        }
        try:
            response = requests.post(url, json=payload, headers=self._headers(), timeout=self.timeout)
        except requests.exceptions.Timeout as exc:
            raise OpenRouterTimeout(f"OpenRouter transcription did not respond within {self.timeout}s.") from exc
        except requests.exceptions.RequestException as exc:
            raise OpenRouterError(f"Could not reach OpenRouter for transcription: {exc}") from exc

        if response.status_code != 200:
            error = self._error_from_response(response)
            self._log_error(error, attempt=0, exhausted=True)
            raise error

        try:
            data = response.json()
        except ValueError as exc:
            raise OpenRouterError("OpenRouter returned a non-JSON transcription response.") from exc
        return (data.get("text") or "").strip()

    # ------------------------------------------------------------- stream

    def stream_chat(self, messages: list, **kwargs) -> Iterator[str]:
        """POST a streaming chat completion and yield content deltas as they
        arrive. A connect-time failure (timeout, 429, 502) is retried the
        same way as chat(); once the connection is open and bytes are
        flowing, a drop is raised to the caller as-is rather than silently
        retried (OpenRouter only ever sends 429/502 as a plain JSON error
        response, never mid-SSE, so "connected" reliably means "this
        request's own error, if any, already happened").
        """
        url = f"{self.base_url}{CHAT_COMPLETIONS_PATH}"
        payload = self._build_payload(messages, **kwargs)
        payload["stream"] = True
        headers = self._headers()

        for attempt in range(self.max_retries + 1):
            try:
                response = requests.post(url, json=payload, headers=headers, timeout=self.timeout, stream=True)
            except requests.exceptions.Timeout as exc:
                if attempt < self.max_retries:
                    logger.warning(
                        "OpenRouter stream request timed out (model=%s, attempt=%d/%d) - retrying.",
                        self.model, attempt + 1, self.max_retries + 1,
                    )
                    _backoff_sleep(attempt)
                    continue
                logger.error("OpenRouter stream request timed out (model=%s) - retries exhausted.", self.model)
                raise OpenRouterTimeout(
                    f"OpenRouter did not respond within {self.timeout}s after {self.max_retries + 1} attempt(s)."
                ) from exc
            except requests.exceptions.RequestException as exc:
                logger.error("OpenRouter stream request failed (model=%s): %s", self.model, exc)
                raise OpenRouterError(f"Could not reach OpenRouter: {exc}") from exc

            if response.status_code in _RETRYABLE_STATUS_CODES and attempt < self.max_retries:
                logger.warning(
                    "OpenRouter HTTP %s (model=%s, attempt=%d/%d) - retrying.",
                    response.status_code, self.model, attempt + 1, self.max_retries + 1,
                )
                response.close()
                _backoff_sleep(attempt)
                continue

            if response.status_code != 200:
                error = self._error_from_response(response)
                self._log_error(error, attempt=attempt, exhausted=response.status_code in _RETRYABLE_STATUS_CODES)
                response.close()
                raise error

            try:
                yield from self._iter_sse_content(response)
            finally:
                response.close()
            return

    @staticmethod
    def _iter_sse_content(response) -> Iterator[str]:
        """Parse `data: {...}` / `data: [DONE]` SSE lines. requests'
        iter_lines() already reassembles a single logical line that arrived
        split across TCP reads, but a JSON payload OpenRouter itself splits
        across more than one `data:` line (not expected in practice, but
        not guaranteed against) is handled too: incomplete JSON is held in
        `pending` until it parses. `:`-prefixed lines are SSE comments
        (OpenRouter sends periodic ": OPENROUTER PROCESSING" keepalives)."""
        pending = ""
        for raw_line in response.iter_lines(decode_unicode=True):
            if raw_line is None:
                continue
            line = raw_line.strip()
            if not line or line.startswith(":"):
                continue
            if not line.startswith("data:"):
                continue
            chunk = line[len("data:"):].strip()
            if chunk == "[DONE]":
                return
            pending = pending + chunk if pending else chunk
            try:
                event = json.loads(pending)
            except ValueError:
                continue  # wait for the rest of a payload split across lines
            pending = ""
            choices = event.get("choices") or []
            if not choices:
                continue
            content = (choices[0].get("delta") or {}).get("content")
            if content:
                yield content
