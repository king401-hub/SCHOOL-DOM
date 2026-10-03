"""python manage.py test_openrouter --prompt "Hello" [--stream] [--model ...]"""
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from ai_chat.services.openrouter_client import OpenRouterClient, OpenRouterError, OpenRouterTimeout


class Command(BaseCommand):
    help = "Send one test message to OpenRouter and print the reply, token usage, and cost."

    def add_arguments(self, parser):
        parser.add_argument("--prompt", default="Hello!", help="The user message to send.")
        parser.add_argument("--stream", action="store_true", help="Use streaming mode instead of a single response.")
        parser.add_argument("--model", default=None, help="Override OPENROUTER_DEFAULT_MODEL for this run only.")

    def handle(self, *args, **options):
        if not getattr(settings, "OPENROUTER_API_KEY", ""):
            raise CommandError(
                "OPENROUTER_API_KEY is not set. Add it to your .env file, e.g.\n"
                "  OPENROUTER_API_KEY=sk-or-v1-...\n"
                "Get a key at https://openrouter.ai/keys - see backend/ai_chat/README_openrouter.md."
            )

        client = OpenRouterClient(model=options.get("model"))
        messages = [{"role": "user", "content": options["prompt"]}]

        self.stdout.write(self.style.NOTICE(f"Model:  {client.model}"))
        self.stdout.write(self.style.NOTICE(f"Prompt: {options['prompt']}"))
        self.stdout.write("")

        try:
            if options["stream"]:
                self.stdout.write(self.style.NOTICE("Streaming response:"))
                full_text = ""
                for chunk in client.stream_chat(messages):
                    full_text += chunk
                    self.stdout.write(chunk, ending="")
                self.stdout.write("\n")
                self.stdout.write(self.style.SUCCESS(f"[{len(full_text)} characters received]"))
            else:
                result = client.chat(messages)
                self.stdout.write(result["content"])
                self.stdout.write("")
                usage = result.get("usage") or {}
                self.stdout.write(
                    self.style.SUCCESS(
                        f"Prompt tokens: {usage.get('prompt_tokens', '?')}  "
                        f"Completion tokens: {usage.get('completion_tokens', '?')}  "
                        f"Total: {usage.get('total_tokens', '?')}  "
                        f"Cost: {usage.get('cost', '?')}"
                    )
                )
        except OpenRouterTimeout as exc:
            raise CommandError(str(exc))
        except OpenRouterError as exc:
            raise CommandError(f"OpenRouter error (status={exc.status_code}, code={exc.code}): {exc}")
