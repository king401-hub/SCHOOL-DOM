"""
Import personal quiz questions from a Myschool CBT 5 SQLite database.

Usage:
    python manage.py import_myschool_db /path/to/database.db [--replace] [--dry-run]

The database.db file lives at:
    Windows: C:/Users/<user>/AppData/Roaming/com.myschool.cbt/my_school/database.db
    Android: /data/data/com.myschool.cbt/databases/my_school/database.db

Copy this file to the server then run the command.  All imported pools are
created as global (tenant=None) so every school can use them.
"""

import html
import re
import sqlite3

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from quizzes.models import PersonalQuizFolder, PersonalQuizFolderQuestion


# Map Myschool subject names → (subject_code, canonical_subject_name)
# The code is matched case-insensitively against school subject codes.
SUBJECT_MAP = {
    "Mathematics": ("MATH", "Mathematics"),
    "English Language": ("ENG", "English Language"),
    "Chemistry": ("CHEM", "Chemistry"),
    "Physics": ("PHY", "Physics"),
    "Biology": ("BIO", "Biology"),
    "Geography": ("GEO", "Geography"),
    "Literature in English": ("LIT", "Literature in English"),
    "Economics": ("ECO", "Economics"),
    "Commerce": ("COM", "Commerce"),
    "Accounts - Principles of Accounts": ("ACC", "Financial Accounting"),
    "Government": ("GOV", "Government"),
    "Christian Religious Knowledge (CRK)": ("CRS", "Christian Religious Studies"),
    "Agricultural Science": ("AGRIC", "Agricultural Science"),
    "Islamic Religious Knowledge (IRK)": ("IRS", "Islamic Religious Studies"),
    "History": ("HIST", "History"),
    "Fine Arts": ("ART", "Fine Arts"),
    "Music": ("MUS", "Music"),
    "French": ("FRENCH", "French"),
    "Animal Husbandry": ("ANIMAL", "Animal Husbandry"),
    "Insurance": ("INS", "Insurance"),
    "Civic Education": ("CIV", "Civic Education"),
    "Further Mathematics": ("FMATH", "Further Mathematics"),
    "Yoruba": ("YOR", "Yoruba"),
    "Igbo": ("IGBO", "Igbo"),
    "Arabic": ("ARABIC", "Arabic"),
    "Home Economics": ("HOME", "Home Economics"),
    "Hausa": ("HAUSA", "Hausa"),
    "Book Keeping": ("BK", "Book Keeping"),
    "Data Processing": ("DATA", "Data Processing"),
    "Catering Craft Practice": ("CCP", "Catering Craft Practice"),
    "Computer Studies": ("COMP", "Computer Studies"),
    "Marketing": ("MKT", "Marketing"),
    "Physical Education": ("PHE", "Physical Health Education"),
    "Office Practice": ("OFF", "Office Practice"),
    "Technical Drawing": ("TD", "Technical Drawing"),
    "Food and Nutrition": ("FN", "Food and Nutrition"),
    "Home Management": ("HM", "Home Management"),
}

LETTER_TO_INDEX = {"a": 0, "b": 1, "c": 2, "d": 3, "e": 4}


def _strip_html(text):
    """Convert HTML question text to plain text."""
    if not text:
        return ""
    text = html.unescape(str(text))
    # Line breaks
    text = re.sub(r"<br\s*/?>", " ", text, flags=re.IGNORECASE)
    text = re.sub(r"</p>", " ", text, flags=re.IGNORECASE)
    # Strip all tags
    text = re.sub(r"<[^>]+>", "", text)
    # Normalize whitespace
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _load_subjects(conn):
    cursor = conn.cursor()
    cursor.execute("SELECT id, title FROM subject")
    return {row[0]: row[1] for row in cursor.fetchall()}


def _load_questions(conn, cat_id):
    cursor = conn.cursor()
    cursor.execute(
        "SELECT question, option_a, option_b, option_c, option_d, option_e, correct_answer, explanation "
        "FROM questions WHERE cat_id = ?",
        (cat_id,),
    )
    return cursor.fetchall()


class Command(BaseCommand):
    help = "Import Myschool CBT 5 questions into global personal quiz pools."

    def add_arguments(self, parser):
        parser.add_argument("db_path", help="Path to the Myschool CBT database.db file.")
        parser.add_argument("--replace", action="store_true", help="Delete and replace existing imported questions.")
        parser.add_argument("--dry-run", action="store_true", help="Parse and report without saving to the database.")

    def handle(self, *args, **options):
        db_path = options["db_path"]
        is_dry_run = options["dry_run"]
        is_replace = options["replace"]

        try:
            conn = sqlite3.connect(db_path)
            conn.text_factory = str
        except Exception as exc:
            raise CommandError(f"Could not open database: {exc}") from exc

        subjects = _load_subjects(conn)
        if not subjects:
            raise CommandError("No subjects found in the database.")

        total_imported = 0

        with transaction.atomic():
            for cat_id, myschool_subject_name in subjects.items():
                subject_code, canonical_name = SUBJECT_MAP.get(
                    myschool_subject_name,
                    (myschool_subject_name[:40].upper(), myschool_subject_name),
                )

                rows = _load_questions(conn, cat_id)
                if not rows:
                    continue

                valid_rows = []
                for row in rows:
                    question_html, opt_a, opt_b, opt_c, opt_d, opt_e, correct_letter, explanation_html = row
                    prompt = _strip_html(question_html)
                    if not prompt:
                        continue

                    choices = [_strip_html(o) for o in [opt_a, opt_b, opt_c, opt_d, opt_e] if o and str(o).strip()]
                    if len(choices) < 2:
                        continue

                    idx = LETTER_TO_INDEX.get(str(correct_letter or "").strip().lower())
                    if idx is None or idx >= len(choices):
                        continue

                    correct_answer = choices[idx]
                    explanation = _strip_html(explanation_html)
                    valid_rows.append((prompt, choices, correct_answer, explanation))

                self.stdout.write(
                    f"{canonical_name} ({subject_code}): {len(valid_rows)} usable questions out of {len(rows)}"
                )
                total_imported += len(valid_rows)

                if is_dry_run:
                    continue

                folder_name = f"{canonical_name} Personal Quiz Pool"
                folder, _created = PersonalQuizFolder.objects.get_or_create(
                    tenant=None,
                    name=folder_name,
                    defaults={
                        "description": "Imported from Myschool CBT 5 question bank.",
                        "subject": None,
                        "subject_code": subject_code,
                        "subject_name": canonical_name,
                        "class_group": None,
                        "is_active": True,
                    },
                )
                if not _created:
                    updated = False
                    if not folder.subject_code:
                        folder.subject_code = subject_code
                        updated = True
                    if not folder.subject_name:
                        folder.subject_name = canonical_name
                        updated = True
                    if updated:
                        folder.save(update_fields=["subject_code", "subject_name"])

                if is_replace:
                    folder.folder_questions.all().delete()

                existing_prompts = set(folder.folder_questions.values_list("prompt", flat=True))
                start_order = folder.folder_questions.count()

                new_questions = [
                    PersonalQuizFolderQuestion(
                        folder=folder,
                        question_type=PersonalQuizFolderQuestion.OBJECTIVE,
                        prompt=prompt,
                        options=opts,
                        correct_answer=correct_answer,
                        explanation=explanation,
                        order=start_order + q_idx + 1,
                        points=1,
                        is_active=True,
                    )
                    for q_idx, (prompt, opts, correct_answer, explanation) in enumerate(valid_rows)
                    if prompt not in existing_prompts
                ]
                PersonalQuizFolderQuestion.objects.bulk_create(new_questions)

            if is_dry_run:
                transaction.set_rollback(True)

        suffix = "would be imported" if is_dry_run else "imported"
        self.stdout.write(self.style.SUCCESS(f"\n{total_imported} questions total {suffix}."))
