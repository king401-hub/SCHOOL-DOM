import base64
import hashlib
import hmac
import json
import time
from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase, override_settings

from . import forwarding

SECRET_BYTES = b"super-secret-signing-key"
SECRET = "whsec_" + base64.b64encode(SECRET_BYTES).decode()
URL = "/api/mail-inbox/resend-webhook/"

RAW = (
    b"From: Parent <parent@example.com>\r\n"
    b"To: support@schooldom.academy\r\n"
    b"Subject: Cannot log in\r\n"
    b"MIME-Version: 1.0\r\n"
    b"Content-Type: multipart/mixed; boundary=XX\r\n\r\n"
    b"--XX\r\nContent-Type: multipart/alternative; boundary=YY\r\n\r\n"
    b"--YY\r\nContent-Type: text/plain; charset=utf-8\r\n\r\nMy child is locked out.\r\n"
    b"--YY\r\nContent-Type: text/html; charset=utf-8\r\n\r\n<p>My child is locked out.</p>\r\n"
    b"--YY--\r\n"
    b"--XX\r\nContent-Type: application/pdf; name=\"fee.pdf\"\r\n"
    b"Content-Disposition: attachment; filename=\"fee.pdf\"\r\n"
    b"Content-Transfer-Encoding: base64\r\n\r\n" + base64.b64encode(b"%PDF-1.4 hello") + b"\r\n"
    b"--XX--\r\n"
)

RECEIVED = {
    "id": "em_1",
    "from": "Parent <parent@example.com>",
    "to": ["support@schooldom.academy"],
    "subject": "Cannot log in",
    "headers": {},
    "raw": {"download_url": "https://files.example/raw.eml"},
}


def _sign(body, msg_id="msg_1", timestamp=None, secret_bytes=SECRET_BYTES):
    timestamp = str(int(time.time()) if timestamp is None else timestamp)
    signed = f"{msg_id}.{timestamp}.".encode() + body
    sig = base64.b64encode(hmac.new(secret_bytes, signed, hashlib.sha256).digest()).decode()
    return {"svix-id": msg_id, "svix-timestamp": timestamp, "svix-signature": f"v1,{sig}"}


def _response(status=200, json_data=None, content=b""):
    r = MagicMock()
    r.status_code = status
    r.json.return_value = json_data
    r.content = content
    r.text = ""
    return r


SETTINGS = dict(
    RESEND_WEBHOOK_SECRET=SECRET,
    MAIL_FORWARD_TO="me@example.com",
    MAIL_FORWARD_FROM="SchoolDom Mail <forward@schooldom.academy>",
    ANYMAIL={"RESEND_API_KEY": "re_test"},
)


@override_settings(**SETTINGS)
class SignatureTests(SimpleTestCase):
    def test_valid(self):
        body = b'{"a":1}'
        self.assertTrue(forwarding.signature_valid(body, _sign(body)))

    def test_tampered_body(self):
        headers = _sign(b'{"a":1}')
        self.assertFalse(forwarding.signature_valid(b'{"a":2}', headers))

    def test_wrong_key(self):
        body = b"{}"
        self.assertFalse(forwarding.signature_valid(body, _sign(body, secret_bytes=b"other")))

    def test_stale_timestamp(self):
        body = b"{}"
        self.assertFalse(forwarding.signature_valid(body, _sign(body, timestamp=int(time.time()) - 3600)))

    def test_missing_headers(self):
        self.assertFalse(forwarding.signature_valid(b"{}", {}))

    def test_rotated_signature_list(self):
        body = b"{}"
        headers = _sign(body)
        headers["svix-signature"] = "v1,AAAA " + headers["svix-signature"]
        self.assertTrue(forwarding.signature_valid(body, headers))

    @override_settings(RESEND_WEBHOOK_SECRET="")
    def test_unconfigured_secret_fails_closed(self):
        body = b"{}"
        self.assertFalse(forwarding.signature_valid(body, _sign(body)))


@override_settings(**SETTINGS)
class ForwardTests(SimpleTestCase):
    def _run(self, received=None, post_status=200):
        gets = [_response(200, received or RECEIVED), _response(200, content=RAW)]
        with patch("mail_inbox.forwarding.requests.get", side_effect=gets) as get, patch(
            "mail_inbox.forwarding.requests.post", return_value=_response(post_status, {"id": "x"})
        ) as post:
            outcome = forwarding.forward_received_email("em_1")
        return outcome, get, post

    def test_forwards_body_attachment_and_reply_to(self):
        outcome, _get, post = self._run()
        self.assertEqual(outcome, "forwarded")
        kwargs = post.call_args.kwargs
        payload = kwargs["json"]
        self.assertEqual(payload["to"], ["me@example.com"])
        self.assertEqual(payload["from"], "SchoolDom Mail <forward@schooldom.academy>")
        self.assertEqual(payload["subject"], "Fwd: Cannot log in")
        self.assertEqual(payload["reply_to"], "parent@example.com")
        self.assertIn("My child is locked out.", payload["text"])
        self.assertIn("<p>My child is locked out.</p>", payload["html"])
        self.assertIn("Forwarded from Parent", payload["html"])
        self.assertEqual(payload["attachments"][0]["filename"], "fee.pdf")
        self.assertEqual(base64.b64decode(payload["attachments"][0]["content"]), b"%PDF-1.4 hello")
        self.assertEqual(kwargs["headers"]["Idempotency-Key"], "fwd-em_1")
        self.assertEqual(kwargs["headers"]["Authorization"], "Bearer re_test")

    def test_send_failure_raises_for_retry(self):
        with self.assertRaises(forwarding.ForwardError):
            self._run(post_status=500)

    def test_retrieve_failure_raises(self):
        with patch("mail_inbox.forwarding.requests.get", return_value=_response(401)):
            with self.assertRaises(forwarding.ForwardError):
                forwarding.forward_received_email("em_1")

    def test_own_mail_is_not_forwarded(self):
        received = dict(RECEIVED, **{"from": "SchoolDom Mail <forward@schooldom.academy>"})
        with patch("mail_inbox.forwarding.requests.get", return_value=_response(200, received)), patch(
            "mail_inbox.forwarding.requests.post"
        ) as post:
            self.assertEqual(forwarding.forward_received_email("em_1"), "skipped-own-mail")
        post.assert_not_called()

    def test_already_forwarded_header_is_not_forwarded_again(self):
        received = dict(RECEIVED, headers={"x-schooldom-forwarded": "1"})
        with patch("mail_inbox.forwarding.requests.get", return_value=_response(200, received)), patch(
            "mail_inbox.forwarding.requests.post"
        ) as post:
            self.assertEqual(forwarding.forward_received_email("em_1"), "skipped-already-forwarded")
        post.assert_not_called()

    @override_settings(MAIL_FORWARD_TO="")
    def test_no_recipients_does_nothing(self):
        with patch("mail_inbox.forwarding.requests.get") as get:
            self.assertEqual(forwarding.forward_received_email("em_1"), "no-recipients")
        get.assert_not_called()

    def test_oversized_attachments_are_dropped_with_a_note(self):
        with patch.object(forwarding, "MAX_ATTACHMENT_BYTES", 5):
            _outcome, _get, post = self._run()
        payload = post.call_args.kwargs["json"]
        self.assertNotIn("attachments", payload)
        self.assertIn("too large to forward", payload["text"])


@override_settings(**SETTINGS)
class WebhookViewTests(SimpleTestCase):
    def _post(self, event, headers=None):
        body = json.dumps(event).encode()
        headers = _sign(body) if headers is None else headers
        extra = {"HTTP_" + k.upper().replace("-", "_"): v for k, v in headers.items()}
        return self.client.post(URL, data=body, content_type="application/json", **extra)

    def test_bad_signature_is_403(self):
        response = self._post({"type": "email.received"}, headers={"svix-id": "a", "svix-timestamp": "1", "svix-signature": "v1,x"})
        self.assertEqual(response.status_code, 403)

    def test_get_is_not_allowed(self):
        self.assertEqual(self.client.get(URL).status_code, 405)

    def test_other_events_are_ignored(self):
        response = self._post({"type": "email.sent", "data": {}})
        self.assertEqual(response.json(), {"status": "ignored"})

    def test_received_event_forwards(self):
        with patch("mail_inbox.views.forward_received_email", return_value="forwarded") as fwd:
            response = self._post({"type": "email.received", "data": {"email_id": "em_9"}})
        fwd.assert_called_once_with("em_9")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"status": "forwarded"})

    def test_forward_error_is_502_so_resend_retries(self):
        with patch("mail_inbox.views.forward_received_email", side_effect=forwarding.ForwardError("boom")):
            response = self._post({"type": "email.received", "data": {"email_id": "em_9"}})
        self.assertEqual(response.status_code, 502)
