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
   | `BAHASHA_MENU_TEMPLATE` | Approved quick-reply menu template name (blank = plain-text menu) |
   | `BAHASHA_MENU_TEMPLATE_LANGUAGE` | Defaults to `en_US` |
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

## Parent menu

A parent messages the school's WhatsApp number. The phone number alone identifies
them: `students_for_parent_phone` matches it against each student's guardian phone,
second guardian phone or own phone, which gives the school(s) and child(ren).

1. Any message that is not a topic gets the **menu**: the approved quick-reply
   template named in `BAHASHA_MENU_TEMPLATE`, or plain text ("reply FEES,
   ATTENDANCE or RESULTS...") when no template is set or sending it fails.
2. The parent taps a button (or types the word). Taps arrive as `type: "button"`
   (`button.text`); `interactive` replies are handled too. Mapping is in
   `parent_topic_from_message`.
3. SchoolDom replies with text, grouped by school then child, ending with the
   school's phone/email. **No payment links.**

| Topic | Words / button | Source |
|---|---|---|
| Fees | `Fee balance`, balance, bal, fee, fees | `outstanding_amount_for_student` |
| Attendance | `Attendance` | `academic.AttendanceRecord`, last 30 days, counts per status |
| Results | `Results`, result, report | newest term with **published** scores, via `_student_result_report` (average and class position) |
| Receipts | receipt, receipts, payment, payments (typed only; the menu template has three buttons) | each child's last five successful payments: date, amount, fee, reference. Read from wallet debits, bank credits and split/virtual-account allocations. No links |
| Contact | help, contact, school | each school's phone and email |
| (ignored) | stop | no reply |

**Unknown numbers get no automatic reply.** If the sender matches no student, SchoolDom
sends nothing (no menu, no "not linked" text) and logs `unrecognized_ignored`. The
message stays in Bahasha's Team Inbox for staff, like a normal WhatsApp number.

**Typed questions.** A typed message of four or more words, or with a "?", is treated
as a question, not a menu word ("what time does school close?" is not the contact
reply). With `WHATSAPP_AI_ENABLED=true` and `OPENROUTER_API_KEY` set, an OpenRouter
model answers it using only the school's name, contacts, address, motto and the
**`parent_faq`** text the school admin fills in (School Settings API field
`parent_faq`, also editable in Django admin). The model is given no child data; it is
told to send fees, attendance and results questions to the buttons, and to say it is
unsure when the FAQ does not cover the answer. Limit: `WHATSAPP_AI_HOURLY_LIMIT`
(default 10) per parent per hour; over the limit, or if the model call fails, the
parent gets the menu. Greetings and one-word messages always get the menu.

**Fee reply.** Per child: the balance, then what makes it up (up to six fee lines),
then where to pay, with no links:
1. the parent's own virtual account (`ParentVirtualAccount`: number, bank, name), else
2. the school's bank account from `AdminWallet` (account name, number, bank name) plus
   a narration per child, else
3. "please contact the school office".

`AdminWallet.bank_code` holds a CBN code, so common codes are mapped to names in
`_CBN_BANK_NAMES`; a code that is not in the map is left out rather than shown as a
number. Add codes there as schools use other banks.

### Create the menu template in Bahasha

WhatsApp allows at most **three** quick-reply buttons per template (WhatsApp's
limit, not stated in Bahasha's docs; confirm it), so Contact has no button: every
reply ends with the school contact line and typing "help" returns it.

- Name: `schooldom_parent_menu` (any name; put it in `BAHASHA_MENU_TEMPLATE`)
- Language: `en_US` (or set `BAHASHA_MENU_TEMPLATE_LANGUAGE`)
- Category: Utility
- Body: `Hello! What would you like to see about your child at school?`
- Buttons, type **Quick reply**, titles exactly: `Fee balance`, `Attendance`, `Results`
- No variables (the code sends none)

Optional school name: WhatsApp footers cannot hold variables, so put it in the body,
e.g. `Hello! What would you like to see about your child at {{school}}?`, give the
variable a sample value when creating the template, and set
`BAHASHA_MENU_TEMPLATE_SCHOOL_PARAM=school` (the variable's name). The code sends
`{"body": {"school": "<school name>"}}`; parents at several schools get the names
joined with "and". If Bahasha expects positional variables instead, adjust
`send_parent_menu`.

Wait for Meta's approval, then set `BAHASHA_MENU_TEMPLATE=schooldom_parent_menu`
and restart. Until then (or if the template is rejected) parents get the
plain-text menu.

Bahasha does not document the JSON for a tapped button, so the first live tap
may need a small adjustment. If a tap gets the menu again instead of a reply,
read the real payload from the logs and adjust `parent_topic_from_message`.

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
  warnings) and `messages` (parent messages, answered as described under
  "Parent menu" below).
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
