"""Tests for ai_chat.services.openrouter_client.OpenRouterClient. Every
`requests.post` call is mocked - no real network calls are made (and no
real API key is needed to run these)."""
from unittest.mock import MagicMock, patch

from django.test import TestCase

from ai_chat.services.openrouter_client import (
    OpenRouterClient,
    OpenRouterError,
    OpenRouterTimeout,
)

try:
    import requests
except ImportError:  # pragma: no cover - requests is a hard dependency here
    requests = None


def _client(**overrides):
    defaults = {
        "api_key": "sk-or-v1-test-key-do-not-log-me",
        "base_url": "https://openrouter.ai/api/v1",
        "model": "qwen/qwen3.8-27b",
        "timeout": 5,
        "max_retries": 2,
    }
    defaults.update(overrides)
    return OpenRouterClient(**defaults)


def _response(status_code, json_body=None):
    resp = MagicMock()
    resp.status_code = status_code
    resp.json.return_value = json_body or {}
    return resp


class ChatCompletionTests(TestCase):
    @patch("ai_chat.services.openrouter_client.requests.post")
    def test_successful_completion_returns_content_and_usage(self, mock_post):
        mock_post.return_value = _response(
            200,
            {
                "id": "gen-abc123",
                "choices": [{"message": {"role": "assistant", "content": "Hello there!"}}],
                "usage": {"prompt_tokens": 5, "completion_tokens": 3, "total_tokens": 8, "cost": 0.0},
            },
        )

        result = _client().chat([{"role": "user", "content": "Hi"}])

        self.assertEqual(result["content"], "Hello there!")
        self.assertEqual(result["usage"]["total_tokens"], 8)
        self.assertEqual(result["raw"]["id"], "gen-abc123")
        self.assertEqual(mock_post.call_count, 1)

        # The request itself must be well-formed and never leak the key to a log.
        _, call_kwargs = mock_post.call_args
        self.assertEqual(call_kwargs["headers"]["Authorization"], "Bearer sk-or-v1-test-key-do-not-log-me")
        self.assertEqual(call_kwargs["json"]["model"], "qwen/qwen3.8-27b")
        self.assertEqual(call_kwargs["json"]["stream"], False)

    @patch("ai_chat.services.openrouter_client.requests.post")
    def test_unauthorized_raises_without_retrying(self, mock_post):
        mock_post.return_value = _response(401, {"error": {"code": 401, "message": "Invalid API key"}})

        with self.assertLogs("ai_chat.services.openrouter_client", level="ERROR") as logs:
            with self.assertRaises(OpenRouterError) as ctx:
                _client().chat([{"role": "user", "content": "Hi"}])

        self.assertEqual(ctx.exception.status_code, 401)
        self.assertEqual(ctx.exception.code, 401)
        self.assertIn("Invalid API key", str(ctx.exception))
        self.assertEqual(mock_post.call_count, 1, "401 is not retryable - must fail on the first attempt.")
        self.assertTrue(any("401" in message for message in logs.output))
        self.assertFalse(
            any("sk-or-v1-test-key-do-not-log-me" in message for message in logs.output),
            "The API key must never appear in a log line.",
        )

    @patch("ai_chat.services.openrouter_client.time.sleep")
    @patch("ai_chat.services.openrouter_client.requests.post")
    def test_rate_limit_retries_then_raises(self, mock_post, mock_sleep):
        mock_post.return_value = _response(429, {"error": {"code": "rate_limited", "message": "Too many requests"}})

        with self.assertRaises(OpenRouterError) as ctx:
            _client(max_retries=2).chat([{"role": "user", "content": "Hi"}])

        self.assertEqual(ctx.exception.status_code, 429)
        self.assertEqual(mock_post.call_count, 3, "max_retries=2 must mean 3 total attempts (1 + 2 retries).")
        self.assertEqual(mock_sleep.call_count, 2, "A sleep happens between attempts, not after the last one.")

    @patch("ai_chat.services.openrouter_client.time.sleep")
    @patch("ai_chat.services.openrouter_client.requests.post")
    def test_timeout_retries_then_raises_openrouter_timeout(self, mock_post, mock_sleep):
        mock_post.side_effect = requests.exceptions.Timeout("read timed out")

        with self.assertRaises(OpenRouterTimeout):
            _client(max_retries=2).chat([{"role": "user", "content": "Hi"}])

        self.assertEqual(mock_post.call_count, 3)
        self.assertEqual(mock_sleep.call_count, 2)

    @patch("ai_chat.services.openrouter_client.requests.post")
    def test_missing_api_key_raises_before_any_request(self, mock_post):
        with self.assertRaises(OpenRouterError) as ctx:
            _client(api_key="").chat([{"role": "user", "content": "Hi"}])

        self.assertEqual(ctx.exception.code, "MISSING_API_KEY")
        mock_post.assert_not_called()

    def test_unsupported_parameter_is_rejected_before_any_request(self):
        with patch("ai_chat.services.openrouter_client.requests.post") as mock_post:
            with self.assertRaises(OpenRouterError) as ctx:
                _client().chat([{"role": "user", "content": "Hi"}], not_a_real_param=True)
            mock_post.assert_not_called()
        self.assertEqual(ctx.exception.code, "UNSUPPORTED_PARAM")


def _sse_response(lines):
    """A fake `requests.Response` for a streaming request: status 200 and
    an iter_lines() that yields exactly the given raw SSE lines."""
    resp = MagicMock()
    resp.status_code = 200
    resp.iter_lines.return_value = iter(lines)
    return resp


class StreamChatTests(TestCase):
    @patch("ai_chat.services.openrouter_client.requests.post")
    def test_streaming_yields_each_content_delta_in_order(self, mock_post):
        mock_post.return_value = _sse_response(
            [
                ": OPENROUTER PROCESSING",
                'data: {"choices":[{"delta":{"content":"Hel"}}]}',
                "",
                'data: {"choices":[{"delta":{"content":"lo"}}]}',
                "",
                'data: {"choices":[{"delta":{}}]}',  # no content key - must be skipped, not crash
                "data: [DONE]",
            ]
        )

        chunks = list(_client().stream_chat([{"role": "user", "content": "Hi"}]))

        self.assertEqual(chunks, ["Hel", "lo"])
        _, call_kwargs = mock_post.call_args
        self.assertTrue(call_kwargs["stream"])
        self.assertEqual(call_kwargs["json"]["stream"], True)

    @patch("ai_chat.services.openrouter_client.requests.post")
    def test_streaming_handles_a_json_payload_split_across_lines(self, mock_post):
        # A defensive case the client must not choke on, even though a real
        # OpenRouter event is one JSON object per `data:` line in practice.
        mock_post.return_value = _sse_response(
            [
                'data: {"choices":[{"delta":{"content":',
                'data: "split"}}]}',
                "data: [DONE]",
            ]
        )

        chunks = list(_client().stream_chat([{"role": "user", "content": "Hi"}]))
        self.assertEqual(chunks, ["split"])

    @patch("ai_chat.services.openrouter_client.time.sleep")
    @patch("ai_chat.services.openrouter_client.requests.post")
    def test_streaming_retries_a_429_before_any_content_then_raises(self, mock_post, mock_sleep):
        mock_post.return_value = _response(429, {"error": {"code": "rate_limited", "message": "Too many requests"}})

        with self.assertRaises(OpenRouterError) as ctx:
            list(_client(max_retries=1).stream_chat([{"role": "user", "content": "Hi"}]))

        self.assertEqual(ctx.exception.status_code, 429)
        self.assertEqual(mock_post.call_count, 2)

    @patch("ai_chat.services.openrouter_client.requests.post")
    def test_streaming_timeout_raises_openrouter_timeout(self, mock_post):
        mock_post.side_effect = requests.exceptions.Timeout("read timed out")

        with self.assertRaises(OpenRouterTimeout):
            list(_client(max_retries=0).stream_chat([{"role": "user", "content": "Hi"}]))
