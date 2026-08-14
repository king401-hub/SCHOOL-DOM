import json
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from academic.models import Subject
from exams.models import Question, QuestionBank
from tenants.models import Tenant
from users.models import User

# A dedicated, non-school Tenant that owns platform-wide CBT question banks (JAMB, WAEC,
# ...) so every real school sees the same bank without it belonging to any one of them.
# cbt_question_bank() in users/app_views.py looks up banks under this same tenant by
# matching subject NAME (school Subject rows are separate database rows per school, even
# for the "same" subject, so there's no single subject_id that could match every school).
GLOBAL_TENANT_SLUG = "schooldom-global-question-bank"
GLOBAL_TENANT_NAME = "SchoolDom Global Question Bank"
GLOBAL_TEACHER_EMAIL = "global-question-bank@schooldom.academy"


class Command(BaseCommand):
    help = (
        "Import a JSON question set into a platform-wide CBT question bank (every school "
        "sees it when building an exam), e.g. JAMB/WAEC past questions. Creates the "
        "dedicated global content tenant/subject/bank the first time it's run for a given "
        "board+subject, and safely re-runs on top of itself afterwards (matching "
        "questions are reused, not duplicated)."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "source",
            help="Path to a JSON file: a list of {prompt, options, correct_answer, explanation?, points?} objects.",
        )
        parser.add_argument("--board", required=True, help='Exam board label, e.g. "JAMB" or "WAEC".')
        parser.add_argument("--subject", required=True, help='Subject name, e.g. "Mathematics".')
        parser.add_argument("--subject-code", default="", help="Optional short subject code, e.g. MTH.")
        parser.add_argument(
            "--replace",
            action="store_true",
            help="Replace this specific board+subject bank's existing questions instead of adding to them.",
        )
        parser.add_argument("--dry-run", action="store_true", help="Parse and report without saving.")

    def handle(self, *args, **options):
        source = Path(options["source"]).resolve()
        if not source.exists():
            raise CommandError(f"Source not found: {source}")

        with open(source, encoding="utf-8") as handle:
            records = json.load(handle)
        if not isinstance(records, list) or not records:
            raise CommandError("Source JSON must be a non-empty list of question objects.")

        board = options["board"].strip()
        subject_name = options["subject"].strip()
        if not board or not subject_name:
            raise CommandError("--board and --subject are required.")

        cleaned = []
        skipped = 0
        for index, record in enumerate(records, start=1):
            prompt = str(record.get("prompt") or record.get("text") or "").strip()
            options_list = [str(option).strip() for option in (record.get("options") or []) if str(option).strip()]
            correct_answer = str(record.get("correct_answer") or "").strip()
            if not prompt or len(options_list) < 2 or not correct_answer:
                self.stdout.write(self.style.WARNING(f"Skipping record {index}: missing prompt/options/correct_answer."))
                skipped += 1
                continue
            if correct_answer not in options_list:
                self.stdout.write(self.style.WARNING(f"Skipping record {index}: correct_answer does not match any option."))
                skipped += 1
                continue
            cleaned.append(
                {
                    "prompt": prompt,
                    "options": options_list,
                    "correct_answer": correct_answer,
                    "explanation": str(record.get("explanation") or "").strip(),
                    "points": int(record.get("points") or 1),
                }
            )

        if not cleaned:
            raise CommandError("No usable questions found in the source file.")

        self.stdout.write(f"{source.name}: {len(cleaned)} usable question(s) parsed ({skipped} skipped).")

        if options["dry_run"]:
            self.stdout.write(self.style.SUCCESS("Dry run complete. No database changes were made."))
            return

        bank_name = f"{board} {subject_name} Question Bank"

        with transaction.atomic():
            tenant, tenant_created = Tenant.objects.get_or_create(
                slug=GLOBAL_TENANT_SLUG,
                defaults={"name": GLOBAL_TENANT_NAME},
            )
            if tenant_created:
                self.stdout.write(self.style.SUCCESS(f"Created global content tenant #{tenant.id}."))

            teacher = User.objects.filter(email__iexact=GLOBAL_TEACHER_EMAIL).first()
            if not teacher:
                teacher = User(
                    email=GLOBAL_TEACHER_EMAIL,
                    first_name="SchoolDom",
                    last_name="Content Team",
                    role="teacher",
                    tenant=None,
                    is_active=True,
                )
                teacher.set_unusable_password()
                teacher.save()
                self.stdout.write(self.style.SUCCESS("Created global content system user."))

            subject = Subject.objects.filter(tenant=tenant, name__iexact=subject_name).first()
            if not subject:
                subject = Subject.objects.create(
                    tenant=tenant,
                    name=subject_name,
                    code=options["subject_code"] or subject_name[:20],
                )
                self.stdout.write(self.style.SUCCESS(f"Created global subject '{subject.name}'."))

            bank, bank_created = QuestionBank.objects.get_or_create(
                tenant=tenant,
                name=bank_name,
                defaults={"subject": subject, "teacher": teacher, "is_shared": True},
            )
            if not bank_created:
                bank.subject = subject
                bank.teacher = teacher
                bank.is_shared = True
                bank.save(update_fields=["subject", "teacher", "is_shared", "updated_at"])
            if options["replace"]:
                bank.questions.clear()

            imported_questions = []
            for record in cleaned:
                question = Question.objects.filter(
                    tenant=tenant,
                    text=record["prompt"],
                    options=record["options"],
                    correct_answer=record["correct_answer"],
                ).first()
                if question:
                    question.explanation = record["explanation"]
                    question.points = record["points"]
                    question.question_type = "mcq"
                    question.save(update_fields=["explanation", "points", "question_type", "updated_at"])
                else:
                    question = Question.objects.create(
                        tenant=tenant,
                        text=record["prompt"],
                        question_type="mcq",
                        points=record["points"],
                        options=record["options"],
                        correct_answer=record["correct_answer"],
                        explanation=record["explanation"],
                    )
                imported_questions.append(question)

            for question in imported_questions:
                bank.questions.add(question)

        self.stdout.write(
            self.style.SUCCESS(
                f"{'Replaced with' if options['replace'] else 'Added'} {len(imported_questions)} question(s) in "
                f"'{bank_name}' (bank #{bank.id}, now {bank.questions.count()} total)."
            )
        )
