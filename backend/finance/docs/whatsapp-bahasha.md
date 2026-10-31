# WhatsApp via Bahasha

SchoolDom sends parent WhatsApp messages through [Bahasha](https://developers.bahasha.app)
when it is configured, and falls back to Termii when it is not. This page covers
setup, how the code is wired, and what Bahasha's docs do not say.

Source of truth for the API: https://developers.bahasha.app. The details below
were read from those docs on 2026-10-31; re-check them before relying on a gap.

## Setup

1. In the Bahasha dashboard: **Settings > API Keys > Create key**. Keys are shown
   once. `bh_test_...` is the sandbox (simulated sends, no webhooks);
   `bh_live_...` is production.
2. Get the phone number's **id** (not the number): `GET /v1/whatsapp/phone_numbers`.
3. Set these environment variables (see `.env.example`):

   | Variable | Meaning |
   |---|---|
   | `BAHASHA_API_KEY` | Bearer key. Bahasha is used only when this **and** the number id are set |
   | `BAHASHA_PHONE_NUMBER_ID` | `id` from the phone numbers endpoint |
   | `BAHASHA_API_BASE` | Defaults to `https://api.bahasha.app` |
   | `BAHASHA_WEBHOOK_VERIFY_TOKEN` | Token for Bahasha's one-time GET handshake |
   | `BAHASHA_WEBHOOK_SECRET` | Shared secret, sent as `?token=` on the webhook URL |

4. Register the webhook in **Settings > Webhooks**:
   `https://<your-domain>/api/finance/whatsapp/bahasha/webhook/?token=<BAHASHA_WEBHOOK_SECRET>`
   with the verify token above. Bahasha requires public HTTPS.
5. Create message templates in the Bahasha dashboard (template creation is not
   exposed by their API). Messages we start need an **approved** template.

Never use a live key in local runs; the repo `.env` already holds live provider
credentials, so blank them or use a `bh_test_` key.

## How the code is wired

All in `backend/finance`:

| Piece | Where |
|---|---|
| `send_bahasha_whatsapp(to, text)` | `services.py`, `POST /v1/whatsapp/send/text` |
| `send_bahasha_whatsapp_template(to, name, language, variables)` | `services.py`, `POST /v1/whatsapp/send` |
| `send_whatsapp_message(to, text, template=None)` | `services.py`, the entry point the webhook replies use. Bahasha if configured, else Termii. Raises `RuntimeError` on error |
| Webhook | `views.bahasha_whatsapp_webhook`, route `whatsapp/bahasha/webhook/` |
| Shared reply logic | `views._handle_whatsapp_inbound` (BALANCE / help), also used by the Meta webhook |
| Tests | `tests.py`: `BahashaWhatsAppSenderTests`, `BahashaWhatsAppWebhookTests` (mocked, no network) |

Sender notes:

- Numbers are normalised with `normalize_phone_number` and sent as E.164 (`+2348012345678`).
- A success response means Bahasha **accepted** the request, not that it was delivered.
- Closed 24-hour window: Bahasha answers HTTP 400 `Customer service window is closed...`.
  `_bahasha_post` returns `window_closed: True` in that case.
- Pass `template={"name": ..., "language": "en_US", "variables": {"body": {"param": "value"}}}`
  to `send_whatsapp_message` for anything SchoolDom starts.

## The 24-hour window (important)

Free-form text only works for 24 hours after the parent's last message to us.
Sending a template does not open it. So:

- **Replying to a parent's BALANCE message** works as plain text, because their
  message just opened the window. This is what the webhook does.
- **Fee reminders and notices we start** need an approved template.

**What uses Bahasha today:** only code that goes through `send_whatsapp_message`,
which is the webhook's BALANCE and help replies (`send_parent_balance_response`).

**What still uses Termii directly, unchanged:** the preferred-channel fee reminder
(`send_parent_virtual_account_fee_reminder`) and the admin bulk WhatsApp send both
call `send_termii_whatsapp` and fall back to paid wallet SMS when it fails, and
`ai_secretary/tools.py` does the same. They were left alone on purpose: pointing
them at Bahasha as plain text would fail outside the 24-hour window and push most
parents onto paid SMS. **Follow-up:** get templates approved, then route those
callers through `send_whatsapp_message(..., template=...)`.

## Webhook behaviour

- `GET`: handshake. Echoes `hub.challenge` when `hub.mode == subscribe` and
  `hub.verify_token` matches `BAHASHA_WEBHOOK_VERIFY_TOKEN`; otherwise 403.
  Fails closed when the token is unset.
- `POST`: requires `?token=` equal to `BAHASHA_WEBHOOK_SECRET` (constant-time
  compare). Fails closed (401) when the secret is unset.
- **No signature.** Bahasha documents no HMAC or signature header, so the URL
  secret is the only authenticity gate. Treat the full URL as a secret; query
  strings can show up in proxy and access logs. Ask Bahasha whether they sign
  requests, and switch to that if they do.
- Events: `statuses` (sent / delivered / read / failed; failures are logged as
  warnings) and `messages` (parent replies; BALANCE gets the balance and payment
  links, anything else gets the help line).
- Bahasha retries without a fast 200, with an undocumented schedule. Message ids
  are de-duplicated for 24 hours in the shared cache (database cache in
  production, so it holds across gunicorn workers). The existing
  `IdempotencyMiddleware` also replays byte-identical POSTs.
- Replies run inline in the request, like the Meta webhook. If Bahasha times out
  on slow balance lookups, move the reply into `core.background.run_in_background`
  (not Celery; there is none in production).

## Not documented by Bahasha (ask them)

- Webhook signature, and the retry count and schedule
- Numeric rate limits (only a 429 status is mentioned)
- Idempotency keys on send endpoints (none found, so a client retry can double-send)
- Opt-in rules, and test phone numbers for sandbox
- Template creation over the API
- Whether 402 means insufficient wallet balance (the docs are ambiguous)

Pages not read: OTP, buttons, media, locations, carousels, product carousels,
contacts, Zapier, and template media upload.

## Before going live

1. Confirm Bahasha's Meta Business Partner status in Meta's partner directory
   (their site claims it; it was not independently checked).
2. Send to your own number with a `bh_test_` key, then a `bh_live_` key.
3. Get templates approved, then wire `template=` into the reminder callers.
4. Check wallet balance handling: a drained Bahasha wallet will surface as send errors.
