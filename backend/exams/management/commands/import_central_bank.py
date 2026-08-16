import json
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.db.models import Q

from academic.models import Subject
from exams.models import Question, QuestionBank, Topic
from tenants.models import Tenant
from users.models import User

# Same global (non-school) tenant/teacher used by import_global_question_bank.py - see that
# file's module docstring for why a dedicated tenant is needed instead of any real school's.
GLOBAL_TENANT_SLUG = "schooldom-global-question-bank"
GLOBAL_TENANT_NAME = "SchoolDom Global Question Bank"
GLOBAL_TEACHER_EMAIL = "global-question-bank@schooldom.academy"


class Command(BaseCommand):
    help = (
        "Import a JSON file into the central JAMB/WAEC/NECO question bank, organized by "
        "topic within a single board+subject. Source shape: "
        '{"board": "WAEC", "subject": "English Language", "topics": {"Synonyms": '
        '[{"text", "options", "correct_answer", "explanation"?}, ...], "Antonyms": [...]}}. '
        "Safe to re-run on top of itself (matching questions are reused, not duplicated) - "
        "so sending more topics for the same board+subject later is just running this again "
        "with a new/extended source file."
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
                text = str(record.get("text") or record.get("prompt") or "").strip()
                option_list = [str(option).strip() for option in (record.get("options") or []) if str(option).strip()]
                correct_answer = str(record.get("correct_answer") or "").strip()
                if not text or len(option_list) < 2 or not correct_answer:
                    self.stdout.write(self.style.WARNING(f'Skipping "{topic_name}" #{index}: missing text/options/correct_answer.'))
                    total_skipped += 1
                    continue
                if correct_answer not in option_list:
                    self.stdout.write(self.style.WARNING(f'Skipping "{topic_name}" #{index}: correct_answer does not match any option.'))
                    total_skipped += 1
                    continue
                cleaned.append(
                    {
                        "text": text,
                        "options": option_list,
                        "correct_answer": correct_answer,
                        "explanation": str(record.get("explanation") or "").strip(),
                        "points": int(record.get("points") or 1),
                    }
                )
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
                subject = Subject.objects.create(tenant=tenant, name=subject_name, code=subject_name[:20])
                self.stdout.write(self.style.SUCCESS(f"Created global subject '{subject.name}'."))

            bank, bank_created = QuestionBank.objects.get_or_create(
                tenant=tenant,
                name=bank_name,
                defaults={"subject": subject, "teacher": teacher, "is_shared": True, "board": board},
            )
            if not bank_created:
                bank.subject = subject
                bank.teacher = teacher
                bank.is_shared = True
                bank.board = board
                bank.save(update_fields=["subject", "teacher", "is_shared", "board", "updated_at"])

            existing_topic_orders = list(bank.topics.values_list("order", flat=True))
            next_order = (max(existing_topic_orders) + 1) if existing_topic_orders else 0

            created_questions = 0
            reused_questions = 0
            for topic_name, records in cleaned_topics.items():
                topic = Topic.objects.filter(tenant=tenant, bank=bank, name=topic_name).first()
                if not topic:
                    topic = Topic.objects.create(tenant=tenant, bank=bank, name=topic_name, order=next_order)
                    next_order += 1
                    self.stdout.write(self.style.SUCCESS(f'Created topic "{topic_name}" under "{bank_name}".'))
                elif options["replace_topics"]:
                    Question.objects.filter(tenant=tenant, topic=topic).update(topic=None)

                for record in records:
                    # Scoped to this topic (or unclaimed) so that identical question
                    # text/options belonging to a *different* board/topic - e.g. JAMB and
                    # WAEC legitimately sharing source content - isn't stolen away from the
                    # topic it already belongs to. Only a question with no topic yet, or
                    # already in this exact topic, is safe to reuse; otherwise a fresh row
                    # is created for this topic.
                    question = Question.objects.filter(
                        tenant=tenant,
                        text=record["text"],
                        options=record["options"],
                        correct_answer=record["correct_answer"],
                    ).filter(Q(topic=topic) | Q(topic__isnull=True)).first()
                    if question:
                        question.explanation = record["explanation"]
                        question.points = record["points"]
                        question.question_type = "mcq"
                        question.topic = topic
                        question.save(update_fields=["explanation", "points", "question_type", "topic", "updated_at"])
                        reused_questions += 1
                    else:
                        question = Question.objects.create(
                            tenant=tenant,
                            text=record["text"],
                            question_type="mcq",
                            points=record["points"],
                            options=record["options"],
                            correct_answer=record["correct_answer"],
                            explanation=record["explanation"],
                            topic=topic,
                        )
                        created_questions += 1
                    bank.questions.add(question)

        self.stdout.write(
            self.style.SUCCESS(
                f"Done: {created_questions} new question(s) created, {reused_questions} matched/updated existing "
                f"ones, across {len(cleaned_topics)} topic(s) in '{bank_name}' (bank #{bank.id})."
            )
        )
