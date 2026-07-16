import json

from django.test import TestCase

from ai_chat.views import CODE_REFUSAL_MESSAGE, _looks_like_code, _stream_ollama_reply


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
