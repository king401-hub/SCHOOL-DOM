"""Shared logic for adding questions to the central (JAMB/WAEC/NECO) question
bank - used by both the `import_central_bank` management command and the
Control Panel's "Upload CSV" admin action (QuestionBankAdmin.upload_csv_view),
so the two paths can never drift apart. See import_central_bank.py's help
text for the source shape this was originally built around.
"""
from django.db import transaction
from django.db.models import Q

from academic.models import Subject
from tenants.models import Tenant
from users.models import User

from .models import Question, QuestionBank, Topic

# Same global (non-school) tenant/teacher used everywhere central-bank content is
# attributed - never a real school's tenant, since every school's own Subject rows
# are separate database rows even for the "same" subject name.
GLOBAL_TENANT_SLUG = "schooldom-global-question-bank"
GLOBAL_TENANT_NAME = "SchoolDom Global Question Bank"
GLOBAL_TEACHER_EMAIL = "global-question-bank@schooldom.academy"


def clean_question_record(record, label=None):
    """Validate/normalize one raw question dict into the canonical shape
    {"text","options","correct_answer","explanation","points"}. Returns
    (cleaned_dict, None) on success or (None, error_message) if it's unusable
    - the same rules import_central_bank.py always enforced, just shared."""
    label = label or "question"
    text = str(record.get("text") or record.get("prompt") or "").strip()
    option_list = [str(option).strip() for option in (record.get("options") or []) if str(option).strip()]
    correct_answer = str(record.get("correct_answer") or "").strip()
    if not text or len(option_list) < 2 or not correct_answer:
        return None, f"Skipping {label}: missing text/options/correct_answer."
    if correct_answer not in option_list:
        return None, f"Skipping {label}: correct_answer does not match any option."
    try:
        points = int(record.get("points") or 1)
    except (TypeError, ValueError):
        points = 1
    return (
        {
            "text": text,
            "options": option_list,
            "correct_answer": correct_answer,
            "explanation": str(record.get("explanation") or "").strip(),
            "points": points,
        },
        None,
    )


def import_central_bank_topics(*, board, subject_name, topics_data, replace_topics=False):
    """topics_data: {topic_name: [cleaned_question_dict, ...]} - every record
    must already be cleaned via clean_question_record(). Safe to re-run on top
    of itself: a question matching an existing one (by text/options/correct
    answer) within the same topic is reused and updated, not duplicated.
    Returns a summary dict."""
    bank_name = f"{board} {subject_name} Question Bank"

    with transaction.atomic():
        tenant, _tenant_created = Tenant.objects.get_or_create(
            slug=GLOBAL_TENANT_SLUG,
            defaults={"name": GLOBAL_TENANT_NAME},
        )

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

        subject = Subject.objects.filter(tenant=tenant, name__iexact=subject_name).first()
        if not subject:
            subject = Subject.objects.create(tenant=tenant, name=subject_name, code=subject_name[:20])

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
        topics_created = 0
        for topic_name, records in topics_data.items():
            topic = Topic.objects.filter(tenant=tenant, bank=bank, name=topic_name).first()
            if not topic:
                topic = Topic.objects.create(tenant=tenant, bank=bank, name=topic_name, order=next_order)
                next_order += 1
                topics_created += 1
            elif replace_topics:
                Question.objects.filter(tenant=tenant, topic=topic).update(topic=None)

            for record in records:
                # Scoped to this topic (or unclaimed) so identical question text/options
                # belonging to a *different* topic (e.g. JAMB and WAEC legitimately sharing
                # source content) isn't stolen away from the topic it already belongs to.
                question = (
                    Question.objects.filter(
                        tenant=tenant,
                        text=record["text"],
                        options=record["options"],
                        correct_answer=record["correct_answer"],
                    )
                    .filter(Q(topic=topic) | Q(topic__isnull=True))
                    .first()
                )
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

    return {
        "bank_id": bank.id,
        "bank_name": bank_name,
        "created_questions": created_questions,
        "reused_questions": reused_questions,
        "topics_created": topics_created,
        "topics_total": len(topics_data),
    }
