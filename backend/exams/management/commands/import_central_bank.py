import json
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from exams.bulk_import import clean_question_record, import_central_bank_topics
from exams.models import QuestionBank


class Command(BaseCommand):
    help = (
        "Import a JSON file into the central JAMB/WAEC/NECO question bank, organized by "
        "topic within a single board+subject. Source shape: "
        '{"board": "WAEC", "subject": "English Language", "topics": {"Synonyms": '
        '[{"text", "options", "correct_answer", "explanation"?}, ...], "Antonyms": [...]}}. '
        "Safe to re-run on top of itself (matching questions are reused, not duplicated) - "
        "so sending more topics for the same board+subject later is just running this again "
        "with a new/extended source file. Also available from the Control Panel as "
        "'Question Banks' > 'Bulk upload CSV', for a spreadsheet instead of hand-written JSON."
    )

    def add_arguments(self, parser):
        parser.add_argument("source", help="Path to the topic-organized JSON file.")
        parser.add_argument(
            "--replace-topics",
            action="store_true",
            help="For any topic present in the source, remove its existing questions first instead of adding to them.",
        )
        parser.add_argument("--dry-run", action="store_true", help="Parse and validate without saving.")

    def handle(self, *args, **options):
        source = Path(options["source"]).resolve()
        if not source.exists():
            raise CommandError(f"Source not found: {source}")

        with open(source, encoding="utf-8") as handle:
            data = json.load(handle)

        board = str(data.get("board") or "").strip().upper()
        subject_name = str(data.get("subject") or "").strip()
        topics_data = data.get("topics") or {}
        valid_boards = dict(QuestionBank.BOARD_CHOICES)
        if board not in valid_boards:
            raise CommandError(f"board must be one of {list(valid_boards)}, got {board!r}.")
        if not subject_name:
            raise CommandError("subject is required.")
        if not isinstance(topics_data, dict) or not topics_data:
            raise CommandError('"topics" must be a non-empty object of {topic_name: [questions...]}.')

        cleaned_topics = {}
        total_skipped = 0
        for topic_name, records in topics_data.items():
            topic_name = str(topic_name).strip()
            if not topic_name:
                raise CommandError("Every topic needs a non-empty name.")
            if not isinstance(records, list) or not records:
                raise CommandError(f'Topic "{topic_name}" must be a non-empty list of questions.')
            cleaned = []
            for index, record in enumerate(records, start=1):
                cleaned_record, error = clean_question_record(record, label=f'"{topic_name}" #{index}')
                if error:
                    self.stdout.write(self.style.WARNING(error))
                    total_skipped += 1
                    continue
                cleaned.append(cleaned_record)
            if not cleaned:
                raise CommandError(f'Topic "{topic_name}" had no usable questions.')
            cleaned_topics[topic_name] = cleaned

        total_questions = sum(len(v) for v in cleaned_topics.values())
        self.stdout.write(
            f"{source.name}: {board} / {subject_name} - {len(cleaned_topics)} topic(s), "
            f"{total_questions} usable question(s) ({total_skipped} skipped)."
        )

        if options["dry_run"]:
            self.stdout.write(self.style.SUCCESS("Dry run complete. No database changes were made."))
            return

        result = import_central_bank_topics(
            board=board,
            subject_name=subject_name,
            topics_data=cleaned_topics,
            replace_topics=options["replace_topics"],
        )

        self.stdout.write(
            self.style.SUCCESS(
                f"Done: {result['created_questions']} new question(s) created, {result['reused_questions']} "
                f"matched/updated existing ones, across {result['topics_total']} topic(s) in "
                f"'{result['bank_name']}' (bank #{result['bank_id']})."
            )
        )
