import json
from unittest.mock import MagicMock, patch

from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from core.models import SchoolTenant
from users.models import User

from ai_chat.models import AIUsageCycle
from ai_chat.services.usage import USAGE_LIMIT_SECONDS, check_quota, consume_usage
from ai_chat.views import (
    CODE_REFUSAL_MESSAGE,
    TOOL_CALL_LEAK_MESSAGE,
    _looks_like_code,
    _looks_like_leaked_tool_call,
    _stream_ollama_reply,
)


class FakeOllamaStream:
    """Minimal stand-in for the requests.Response object _stream_ollama_reply consumes."""

    def __init__(self, chunks):
        self._lines = [json.dumps(chunk).encode() for chunk in chunks]
        self.closed = False

    def iter_lines(self):
        return iter(self._lines)

    def close(self):
        self.closed = True


class LooksLikeCodeTests(TestCase):
    def test_detects_markdown_code_fence(self):
        self.assertTrue(_looks_like_code("Sure, here you go:\n```python\nprint('hi')\n```"))

    def test_detects_sql(self):
        self.assertTrue(_looks_like_code("You could run SELECT * FROM students;"))

    def test_detects_html_script_tag(self):
        self.assertTrue(_looks_like_code("<script>alert(1)</script>"))

    def test_does_not_flag_ordinary_school_admin_text(self):
        message = (
            "Please select your class from the Classes page, then click Add Student. "
            "This is important - make sure the guardian phone is correct."
        )
        self.assertFalse(_looks_like_code(message))

    def test_does_not_flag_lesson_plan_text(self):
        message = (
            "Lesson Plan: Introduction to Photosynthesis\n"
            "1. Objective: Students will explain how plants make food.\n"
            "2. Materials: Textbook, diagrams.\n"
            "3. Activity: Group discussion on class observations."
        )
        self.assertFalse(_looks_like_code(message))


class LooksLikeLeakedToolCallTests(TestCase):
    def test_detects_openai_style_function_call(self):
        self.assertTrue(_looks_like_leaked_tool_call(
            '{"type":"function","function":{"name": "create_cbt_exam", "parameters": {"subject": "Maths"}}}'
        ))

    def test_detects_flat_name_arguments_shape(self):
        self.assertTrue(_looks_like_leaked_tool_call('{"name": "send_message", "arguments": {"text": "hi"}}'))

    def test_does_not_flag_ordinary_text(self):
        self.assertFalse(_looks_like_leaked_tool_call("Go to Students and click Add Student."))


class StreamOllamaReplyTests(TestCase):
    def test_cuts_stream_and_refuses_when_model_starts_a_code_fence(self):
        upstream = FakeOllamaStream([
            {"message": {"content": "Sure, here is a script:\n"}},
            {"message": {"content": "```python\n"}},
            {"message": {"content": "print('should never reach the client')"}},
            {"done": True},
        ])

        output = "".join(_stream_ollama_reply(upstream))

        self.assertIn("Sure, here is a script:", output)
        self.assertIn(CODE_REFUSAL_MESSAGE, output)
        self.assertNotIn("should never reach the client", output)
        self.assertTrue(upstream.closed)

    def test_normal_response_streams_through_untouched(self):
        upstream = FakeOllamaStream([
            {"message": {"content": "Go to "}},
            {"message": {"content": "Students and click Add Student."}},
            {"done": True},
        ])

        output = "".join(_stream_ollama_reply(upstream))

        self.assertEqual(output, "Go to Students and click Add Student.")
        self.assertNotIn(CODE_REFUSAL_MESSAGE, output)

    def test_code_signal_split_across_stream_chunks_is_still_caught(self):
        upstream = FakeOllamaStream([
            {"message": {"content": "Here: ``"}},
            {"message": {"content": "`js\nconsole.log('leaked')"}},
            {"done": True},
        ])

        output = "".join(_stream_ollama_reply(upstream))

        self.assertIn(CODE_REFUSAL_MESSAGE, output)
        self.assertNotIn("leaked", output)

    def test_cuts_stream_and_apologizes_when_model_emits_a_fake_tool_call(self):
        """Regression test: a model can emit a tool-call-shaped JSON blob as
        plain content on this zero-tools surface too (ai_chat has no
        TOOL_SCHEMAS to recover a real call against, unlike ai_secretary) -
        it must never reach the user as raw JSON either way."""
        upstream = FakeOllamaStream([
            {"message": {"content": '{"type":"function","function":'}},
            {"message": {"content": '{"name": "create_cbt_exam", "parameters": {}}}'}},
            {"done": True},
        ])

        output = "".join(_stream_ollama_reply(upstream))

        self.assertIn(TOOL_CALL_LEAK_MESSAGE, output)
        self.assertNotIn("create_cbt_exam", output)


class ChatViewUsageQuotaTests(TestCase):
    """The /api/ai/chat/ view must enforce the backend AI usage quota
    before ever calling the AI provider, and must charge real usage time
    for a request that does go through."""

    def setUp(self):
        self.school = SchoolTenant.objects.create(name="Quota School", schema_name="quota_school", is_active=True)
        self.user = User.objects.create_user(
            email="student@quota.test", password="Pass12345", first_name="Quota", last_name="Student",
            role="student", tenant=self.school, is_active=True, is_verified=True,
        )
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)

    @patch("ai_chat.views.requests.post")
    def test_exhausted_quota_returns_429_without_calling_ollama(self, mock_post):
        check_quota(self.user, self.school)
        consume_usage(self.user, USAGE_LIMIT_SECONDS)

        response = self.client.post(
            "/api/ai/chat/", data={"messages": [{"role": "user", "content": "Hi"}]}, format="json",
        )

        self.assertEqual(response.status_code, 429)
        self.assertEqual(response.json()["usage"]["remaining_seconds"], 0)
        mock_post.assert_not_called()

    @patch("ai_chat.views.requests.post")
    @patch("ai_chat.views.time.monotonic", side_effect=[1000.0, 1005.0])
    def test_successful_chat_charges_real_usage_time(self, mock_monotonic, mock_post):
        # time.monotonic() is called exactly twice on this path: once for
        # ai_start in chat(), once in _timed_stream's finally - fixing both
        # readings makes the 5s "elapsed" deterministic instead of relying
        # on a real (sub-millisecond, rounds to 0) mocked-response duration.
        fake_response = MagicMock()
        fake_response.iter_lines.return_value = iter([
            json.dumps({"message": {"content": "Hello"}}).encode(),
            json.dumps({"done": True}).encode(),
        ])
        mock_post.return_value = fake_response

        response = self.client.post(
            "/api/ai/chat/", data={"messages": [{"role": "user", "content": "Hi"}]}, format="json",
        )
        self.assertEqual(response.status_code, 200)
        b"".join(response.streaming_content)  # drive the generator to completion

        cycle = AIUsageCycle.objects.get(user=self.user)
        self.assertEqual(cycle.usage_seconds, 5)


class OpenRouterImageSupportTests(TestCase):
    """The default OPENROUTER_DEFAULT_MODEL is text-only - an attached image
    used to be silently dropped on this path (OpenRouter's content format
    differs from Ollama's `images` field). An image now switches the call
    to OPENROUTER_VISION_MODEL and reshapes the turn's content into
    OpenRouter's multimodal block format."""

    def setUp(self):
        self.school = SchoolTenant.objects.create(name="Vision School", schema_name="vision_school", is_active=True)
        self.user = User.objects.create_user(
            email="admin@vision.test", password="Pass12345", first_name="Vision", last_name="Admin",
            role="school_admin", tenant=self.school, is_active=True, is_verified=True,
        )
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)

    @override_settings(AI_PROVIDER="openrouter")
    @patch("ai_chat.views.OpenRouterClient")
    def test_an_attached_image_switches_to_the_vision_model(self, mock_client_cls):
        mock_client_cls.return_value.stream_chat.return_value = iter(["I see a timetable."])

        response = self.client.post(
            "/api/ai/chat/",
            data={"messages": [{
                "role": "user", "content": "What's in this image?",
                "images": ["data:image/png;base64,ZmFrZWJhc2U2NA=="],
            }]},
            format="json",
        )
        self.assertEqual(response.status_code, 200)
        b"".join(response.streaming_content)  # drive the generator to completion

        mock_client_cls.assert_called_once_with(model="qwen/qwen2.5-vl-72b-instruct")
        sent_messages = mock_client_cls.return_value.stream_chat.call_args.args[0]
        user_content = sent_messages[-1]["content"]
        self.assertIsInstance(user_content, list)
        self.assertEqual(user_content[0], {"type": "text", "text": "What's in this image?"})
        self.assertEqual(user_content[1]["image_url"]["url"], "data:image/png;base64,ZmFrZWJhc2U2NA==")

    @override_settings(AI_PROVIDER="openrouter")
    @patch("ai_chat.views.OpenRouterClient")
    def test_no_image_keeps_the_default_model_and_plain_string_content(self, mock_client_cls):
        mock_client_cls.return_value.stream_chat.return_value = iter(["Hello!"])

        response = self.client.post(
            "/api/ai/chat/", data={"messages": [{"role": "user", "content": "Hi"}]}, format="json",
        )
        self.assertEqual(response.status_code, 200)
        b"".join(response.streaming_content)

        mock_client_cls.assert_called_once_with(model=None)
        sent_messages = mock_client_cls.return_value.stream_chat.call_args.args[0]
        self.assertIsInstance(sent_messages[-1]["content"], str)


class TranscribeViewTests(TestCase):
    def setUp(self):
        self.school = SchoolTenant.objects.create(name="Voice School", schema_name="voice_school", is_active=True)
        self.user = User.objects.create_user(
            email="admin@voice.test", password="Pass12345", first_name="Voice", last_name="Admin",
            role="school_admin", tenant=self.school, is_active=True, is_verified=True,
        )
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)

    @override_settings(AI_PROVIDER="openrouter")
    @patch("ai_chat.views.OpenRouterClient")
    def test_transcribes_a_recording_into_text(self, mock_client_cls):
        mock_client_cls.return_value.transcribe.return_value = "Mark attendance for SS2A."

        response = self.client.post(
            "/api/ai/transcribe/",
            data={"audio": "data:audio/webm;base64,ZmFrZWF1ZGlv", "format": "webm"},
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["text"], "Mark attendance for SS2A.")
        mock_client_cls.return_value.transcribe.assert_called_once_with("ZmFrZWF1ZGlv", audio_format="webm")

    @override_settings(AI_PROVIDER="openrouter")
    def test_missing_audio_is_rejected(self):
        response = self.client.post("/api/ai/transcribe/", data={}, format="json")
        self.assertEqual(response.status_code, 400)

    def test_unavailable_when_not_on_openrouter(self):
        response = self.client.post(
            "/api/ai/transcribe/", data={"audio": "ZmFrZQ=="}, format="json",
        )
        self.assertEqual(response.status_code, 503)

    @override_settings(AI_PROVIDER="openrouter")
    @patch("ai_chat.views.OpenRouterClient")
    def test_no_speech_detected_reports_clearly(self, mock_client_cls):
        mock_client_cls.return_value.transcribe.return_value = ""

        response = self.client.post(
            "/api/ai/transcribe/", data={"audio": "ZmFrZQ=="}, format="json",
        )
        self.assertEqual(response.status_code, 422)
