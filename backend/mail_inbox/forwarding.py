"""Forward mail received by Resend (support@, enquiry@, billing@ ...) to a
personal mailbox.

Resend's `email.received` webhook carries only metadata. This module fetches
the full message, downloads the raw RFC 5322 file, and re-sends it through
Resend's REST API. It is the REST equivalent of the Node SDK's `forward()`.

Everything is done inside the webhook request, not in a background thread:
a failure returns a 5xx, Resend retries the webhook, and the Idempotency-Key
(the received email's id) stops a retry that follows a half-success from
sending the same message twice.
"""
import base64
import hashlib
import hmac
import html as html_lib
import logging
import time
from email import message_from_bytes, policy
from email.utils import parseaddr

import requests
from django.conf import settings

logger = logging.getLogger(__name__)

RESEND_API_BASE = "https://api.resend.com"
FORWARDED_HEADER = "X-SchoolDom-Forwarded"
# Resend caps a sent email at 40 MB *after* base64 encoding; stay well under.
MAX_ATTACHMENT_BYTES = 38 * 1024 * 1024
SIGNATURE_TOLERANCE_SECONDS = 5 * 60
HTTP_TIMEOUT = 20


class ForwardError(Exception):
    """The message could not be forwarded; the webhook should be retried."""


def _recipients():
    raw = getattr(settings, "MAIL_FORWARD_TO", "") or ""
    return [item.strip() for item in raw.split(",") if item.strip()]


def _api_key():
    """Reading received mail needs a full-access Resend key; the site's normal
    sending key is usually send-only. RESEND_FORWARD_API_KEY keeps the two
    apart, and falls back to the sending key if it is not set."""
    return getattr(settings, "RESEND_FORWARD_API_KEY", "") or (
        (getattr(settings, "ANYMAIL", {}) or {}).get("RESEND_API_KEY", "")
    )


def _headers():
    return {
        "Authorization": f"Bearer {_api_key()}",
        "User-Agent": "schooldom-mail-forwarder/1.0",
    }


def signature_valid(body, headers):
    """Verify a Resend (Svix) webhook signature.

    Signed content is `<svix-id>.<svix-timestamp>.<raw body>`, HMAC-SHA256 with
    the base64-decoded part of the `whsec_...` secret. The header can carry
    several space-separated `v1,<base64>` signatures (key rotation). Fails
    closed: an unconfigured secret rejects everything, because this endpoint
    makes outbound sends.
    """
    secret = getattr(settings, "RESEND_WEBHOOK_SECRET", "") or ""
    if not secret:
        return False
    msg_id = headers.get("svix-id", "")
    timestamp = headers.get("svix-timestamp", "")
    signatures = headers.get("svix-signature", "")
    if not (msg_id and timestamp and signatures):
        return False
    try:
        if abs(time.time() - int(timestamp)) > SIGNATURE_TOLERANCE_SECONDS:
            return False
        key = base64.b64decode(secret.split("_", 1)[1] if secret.startswith("whsec_") else secret)
    except (ValueError, TypeError, IndexError):
        return False
    signed = f"{msg_id}.{timestamp}.".encode("utf-8") + body
    expected = base64.b64encode(hmac.new(key, signed, hashlib.sha256).digest()).decode()
    for candidate in signatures.split():
        version, _, value = candidate.partition(",")
        if version == "v1" and hmac.compare_digest(value, expected):
            return True
    return False


def _fetch_received(email_id):
    response = requests.get(
        f"{RESEND_API_BASE}/emails/receiving/{email_id}",
        headers=_headers(),
        timeout=HTTP_TIMEOUT,
    )
    if response.status_code != 200:
        raise ForwardError(f"retrieve received email {email_id}: HTTP {response.status_code} {response.text[:200]}")
    return response.json()


def _download_raw(received):
    url = ((received.get("raw") or {}).get("download_url")) or ""
    if not url:
        raise ForwardError("received email has no raw download_url")
    response = requests.get(url, timeout=HTTP_TIMEOUT * 3)
    if response.status_code != 200:
        raise ForwardError(f"raw download: HTTP {response.status_code}")
    return response.content


def _part_bytes(part):
    if part.get_content_type() == "message/rfc822":
        inner = part.get_payload(0) if part.is_multipart() else None
        return inner.as_bytes() if inner is not None else None
    return part.get_payload(decode=True)


def _split_message(raw_bytes):
    """-> (html, text, attachments) from a raw RFC 5322 message."""
    msg = message_from_bytes(raw_bytes, policy=policy.default)
    html_part = msg.get_body(preferencelist=("html",))
    text_part = msg.get_body(preferencelist=("plain",))
    html_body = html_part.get_content() if html_part is not None else ""
    text_body = text_part.get_content() if text_part is not None else ""
    body_ids = {id(p) for p in (html_part, text_part) if p is not None}

    attachments = []
    for part in msg.walk():
        if part.is_multipart() or id(part) in body_ids:
            continue
        content_id = (part.get("Content-ID") or "").strip().strip("<>")
        filename = part.get_filename()
        if not filename and not content_id:
            continue
        data = _part_bytes(part)
        if not data:
            continue
        item = {
            "filename": filename or f"{content_id}",
            "content": base64.b64encode(data).decode("ascii"),
            "content_type": part.get_content_type(),
        }
        if content_id:
            item["content_id"] = content_id
        attachments.append(item)
    return html_body, text_body, attachments, msg


def _banner(sender, inbox):
    return f"Forwarded from {sender} → {inbox}"


def build_payload(received, raw_bytes):
    html_body, text_body, attachments, msg = _split_message(raw_bytes)

    sender = received.get("from") or msg.get("From") or "unknown sender"
    inbox = ", ".join(received.get("to") or []) or str(msg.get("To") or "")
    subject = received.get("subject") or msg.get("Subject") or "(no subject)"
    reply_to = parseaddr(str(msg.get("Reply-To") or ""))[1] or parseaddr(str(sender))[1]

    notes = []
    total = sum(len(a["content"]) for a in attachments)
    if total > MAX_ATTACHMENT_BYTES:
        notes.append(f"{len(attachments)} attachment(s) were too large to forward - open the original in Resend.")
        attachments = []

    banner = _banner(sender, inbox)
    note_text = "".join(f"\n{n}" for n in notes)
    text = f"{banner}{note_text}\n\n{text_body}".rstrip() + "\n"
    payload = {
        "from": getattr(settings, "MAIL_FORWARD_FROM", "") or settings.DEFAULT_FROM_EMAIL,
        "to": _recipients(),
        "subject": f"Fwd: {subject}",
        "text": text,
        "headers": {FORWARDED_HEADER: "1"},
    }
    if reply_to:
        payload["reply_to"] = reply_to
    if html_body:
        note_html = "".join(f"<br>{html_lib.escape(n)}" for n in notes)
        payload["html"] = (
            '<div style="font:12px sans-serif;color:#666;border-bottom:1px solid #ddd;'
            f'padding-bottom:8px;margin-bottom:12px">{html_lib.escape(banner)}{note_html}</div>{html_body}'
        )
    if attachments:
        payload["attachments"] = attachments
    return payload


def forward_received_email(email_id):
    """Forward one received email. Raises ForwardError on a retryable failure;
    returns a short status string otherwise."""
    if not _recipients():
        logger.warning("MAIL_FORWARD_TO is empty; not forwarding received email %s", email_id)
        return "no-recipients"
    if not _api_key():
        raise ForwardError("RESEND_API_KEY is not configured")

    received = _fetch_received(email_id)
    sender_addr = parseaddr(str(received.get("from") or ""))[1].lower()
    own_addr = parseaddr(getattr(settings, "MAIL_FORWARD_FROM", "") or settings.DEFAULT_FROM_EMAIL)[1].lower()
    if own_addr and sender_addr == own_addr:
        return "skipped-own-mail"
    received_headers = {str(k).lower(): str(v) for k, v in (received.get("headers") or {}).items()}
    if received_headers.get(FORWARDED_HEADER.lower()) == "1":
        return "skipped-already-forwarded"

    payload = build_payload(received, _download_raw(received))
    response = requests.post(
        f"{RESEND_API_BASE}/emails",
        json=payload,
        headers={**_headers(), "Idempotency-Key": f"fwd-{email_id}"},
        timeout=HTTP_TIMEOUT * 2,
    )
    if response.status_code >= 400:
        raise ForwardError(f"send forward of {email_id}: HTTP {response.status_code} {response.text[:300]}")
    logger.info("Forwarded received email %s to %s", email_id, payload["to"])
    return "forwarded"
