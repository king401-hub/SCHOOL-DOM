import json
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from quizzes.models import PersonalQuizFolder, PersonalQuizFolderQuestion

DEFAULT_SOURCE = Path(__file__).resolve().parent.parent.parent / "data" / "math_question_bank.json"
FOLDER_NAME = "Mathematics Personal Quiz Pool"


class Command(BaseCommand):
    help = "Import the bundled Mathematics personal quiz question bank (JAMB/WAEC style) into a global folder."

    def add_arguments(self, parser):
        parser.add_argument(
            "--source",
            default=str(DEFAULT_SOURCE),
            help="Path to the question bank JSON file.",
        )
        parser.add_argument("--replace", action="store_true", help="Replace existing questions in the folder.")
        parser.add_argument("--dry-run", action="store_true", help="Parse and report without saving.")

    def handle(self, *args, **options):
        source = Path(options["source"]).resolve()
        if not source.exists():
            raise CommandError(f"Source not found: {source}")

        with open(source, encoding="utf-8") as handle:
            records = json.load(handle)

        rows = []
        for record in records:
            options_list = record["options"]
            question_type = (
                PersonalQuizFolderQuestion.TRUE_FALSE
                if len(options_list) == 2
                else PersonalQuizFolderQuestion.OBJECTIVE
            )
            rows.append((record, question_type))

        self.stdout.write(f"{source.name}: parsed {len(rows)} usable questions")

        with transaction.atomic():
            if options["dry_run"]:
                transaction.set_rollback(True)
            else:
                folder, _created = PersonalQuizFolder.objects.get_or_create(
                    tenant=None,
                    name=FOLDER_NAME,
                    subject=None,
                    class_group=None,
                    defaults={
                        "description": f"Imported from {source.name}.",
                        "subject_code": "MTH",
                        "subject_name": "Mathematics",
                    },
                )
                if options["replace"]:
                    folder.folder_questions.all().delete()
                start_order = folder.folder_questions.count()
                PersonalQuizFolderQuestion.objects.bulk_create(
                    [
                        PersonalQuizFolderQuestion(
                            folder=folder,
                            question_type=question_type,
                            prompt=record["prompt"],
                            options=record["options"],
                            correct_answer=record["correct_answer"],
                            order=start_order + index + 1,
                            points=1,
                            is_active=True,
                        )
                        for index, (record, question_type) in enumerate(rows)
                    ]
                )

        suffix = "checked" if options["dry_run"] else "imported"
        self.stdout.write(self.style.SUCCESS(f"{len(rows)} math personal quiz questions {suffix}."))
