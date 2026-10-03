# OpenRouter provider for SchoolDom AI

`ai_chat` (the "SchoolDom AI" assistant on the admin dashboard and the
`/api/ai/chat/` + `/api/ai/status/` endpoints) can talk to either:

- **Ollama** (default, unchanged) - a local model on the same server.
- **OpenRouter** (`AI_PROVIDER=openrouter`) - a hosted API, currently
  configured for the free `qwen/qwen3.8-27b` model.

`ai_secretary` (the admin "Secretary" assistant that can take actions -
mark attendance, create exams, send messages, etc.) is **not** covered by
this - it still talks to Ollama only. Wiring tool-calling through
OpenRouter is a separate piece of work (tool-call response shapes differ
between providers); this change only touches plain chat.

## Setup

1. Get a key at <https://openrouter.ai/keys>.
2. Add it to the repo's `.env` file (**repo root**, next to this project's
   `manage.py` parent folder - not inside `backend/`; that's where
   `config/settings.py`'s `BASE_DIR` resolves to, and it's the file your
   production systemd service already loads via `EnvironmentFile=`):

   ```
   AI_PROVIDER=openrouter
   OPENROUTER_API_KEY=sk-or-v1-...
   ```

   Leaving `AI_PROVIDER` unset (or `ollama`) keeps today's behaviour
   exactly as it is - nothing else to do, nothing else changes.

3. **Local `manage.py` runs don't auto-load `.env`** - this project has no
   `python-dotenv`/`django-environ` call anywhere, so outside of
   production (where systemd injects it) you need the variables in your
   shell's own environment before running anything, e.g.:

   ```bash
   export OPENROUTER_API_KEY=sk-or-v1-...
   export AI_PROVIDER=openrouter   # only if you want to test the OpenRouter path specifically
   python manage.py test_openrouter --prompt "Hello"
   ```

## Switching models

Change `OPENROUTER_DEFAULT_MODEL` (in `.env`, or your shell for a local
run) to any model string from <https://openrouter.ai/models> - no code
change needed. `qwen/qwen3.8-27b` is free but see the caveat below.

## Running the test command

```bash
python manage.py test_openrouter --prompt "Hello"
python manage.py test_openrouter --prompt "Hello" --stream
python manage.py test_openrouter --prompt "Hello" --model qwen/qwen3.8-27b
```

Prints the reply, then prompt/completion/total tokens and cost (non-stream
mode only - OpenRouter's streaming chunks don't carry per-request usage).
With no `OPENROUTER_API_KEY` set, it fails immediately with a clear message
instead of a traceback.

## Running the automated tests

Same runner as the rest of the project (Django's, not pytest - there's no
pytest config in this repo):

```bash
python manage.py test ai_chat
python manage.py test ai_chat.test_openrouter_client   # just the client
```

Every test mocks `requests.post` - none of them make a real network call or
need a real API key.

## Error codes

| HTTP status | Meaning | What this client does |
|---|---|---|
| 200 | Success | Returns `{"content", "usage", "raw"}` from `chat()`, or yields content deltas from `stream_chat()`. |
| 400 | Malformed request / unsupported parameter | Raises `OpenRouterError` immediately. (A parameter outside the documented list is actually caught client-side before any request is sent - see `SUPPORTED_PARAMS` in `openrouter_client.py`.) |
| 401 | Missing or invalid API key | Raises `OpenRouterError` immediately. `ai_chat`'s `/api/ai/chat/` surfaces this as its own 401 with a friendly message, never the raw OpenRouter text. |
| 402 | Insufficient credits | Raises `OpenRouterError` immediately. Surfaced to the chat user as "...the AI provider account is out of credits." |
| 403 | Spend limit / key disabled / blocked | Raises `OpenRouterError` immediately. Surfaced as "...access was denied by the AI provider." |
| 404 | Unknown model / no provider available | Raises `OpenRouterError` immediately - check `OPENROUTER_DEFAULT_MODEL` is spelled exactly as OpenRouter lists it. |
| 429 | Rate limited | Retried with exponential backoff (0.5s, 1s, 2s, ... up to `OPENROUTER_MAX_RETRIES` times) before raising. |
| 502 | Upstream failure (OpenRouter says this is never billed) | Retried the same way as 429. |
| (timeout) | No response within `OPENROUTER_TIMEOUT` seconds | Retried the same way as 429/502, then raises `OpenRouterTimeout`. |

Every error is logged via `logging.getLogger(__name__)` in
`ai_chat.services.openrouter_client` with the model name, HTTP status, and
OpenRouter's own error code/message - **never the API key**.

## Known limitation: no vision support on this path

`ai_chat`'s Ollama path supports image attachments (via a separate
`llava` model). The OpenRouter path does not - an attached image is
silently dropped and only the text is sent, since `qwen/qwen3.8-27b` isn't
a vision model and OpenRouter's image-message format differs from
Ollama's. Swap in a vision-capable OpenRouter model and extend
`_chat_via_openrouter` in `ai_chat/views.py` if you need this later.

## Free tier, production readiness

`qwen/qwen3.8-27b` is free on OpenRouter as of writing, but:

- Free-tier models are rate-limited (expect more 429s under real traffic
  than a paid model) and OpenRouter can withdraw or change free models at
  any time without notice.
- There's no SLA on a free model's latency or availability.

For production traffic at any real volume, budget for a paid OpenRouter
model (just change `OPENROUTER_DEFAULT_MODEL`) rather than relying on the
free tier long-term.
