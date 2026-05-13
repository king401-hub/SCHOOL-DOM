import re
import zipfile
from xml.etree import ElementTree

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from quizzes.models import PersonalQuizFolder, PersonalQuizFolderQuestion


WORD_NS = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}
ANSWER_RE = re.compile(r"Answer\s*:\s*([A-D])", re.IGNORECASE)
OPTION_RE = re.compile(r"([A-D])\.\s*")


class Command(BaseCommand):
    help = "Import inline objective questions into a global student personal quiz pool."

    def add_arguments(self, parser):
        parser.add_argument("docx_path")
        parser.add_argument("--folder-name", default="Government Personal Quiz Pool")
        parser.add_argument("--subject-code", default="GOV")
        parser.add_argument("--subject-name", default="Government")
        parser.add_argument("--replace", action="store_true")
        parser.add_argument("--dry-run", action="store_true")

    def handle(self, *args, **options):
        questions = parse_docx_questions(options["docx_path"])
        if not questions:
            raise CommandError("No usable Government questions were found in the DOCX.")

        self.stdout.write(f"Parsed {len(questions)} personal quiz questions.")
        if options["dry_run"]:
            self.stdout.write(self.style.SUCCESS("Dry run complete. No database changes were made."))
            return

        with transaction.atomic():
            folder, _created = PersonalQuizFolder.objects.update_or_create(
                tenant=None,
                name=options["folder_name"],
                defaults={
                    "description": "Global Government question pool used only for student daily personal quizzes.",
                    "subject": None,
                    "subject_code": options["subject_code"].strip().upper(),
                    "subject_name": options["subject_name"].strip(),
                    "class_group": None,
                    "is_active": True,
                },
            )
            if options["replace"]:
                folder.folder_questions.all().delete()

            existing_prompts = set(folder.folder_questions.values_list("prompt", flat=True))
            start_order = folder.folder_questions.count()
            rows = [
                PersonalQuizFolderQuestion(
                    folder=folder,
                    question_type=PersonalQuizFolderQuestion.OBJECTIVE,
                    prompt=item["prompt"],
                    options=item["options"],
                    correct_answer=item["correct_answer"],
                    explanation="",
                    order=start_order + index + 1,
                    points=1,
                    is_active=True,
                )
                for index, item in enumerate(questions)
                if item["prompt"] not in existing_prompts
            ]
            PersonalQuizFolderQuestion.objects.bulk_create(rows)

        self.stdout.write(self.style.SUCCESS(f"Imported {len(rows)} questions into global folder #{folder.id}."))


def parse_docx_questions(docx_path):
    paragraphs = extract_docx_paragraphs(docx_path)
    content = " ".join(
        normalize_text(paragraph)
        for paragraph in paragraphs
        if "schooldom" not in paragraph.casefold() or "question" not in paragraph.casefold()
    )
    questions = []
    chunk_re = re.compile(r".+?Answer\s*:\s*[A-D](?:\s*\([^)]*\))?", re.IGNORECASE)
    for chunk in [match.group(0).strip() for match in chunk_re.finditer(content)]:
        answer_match = ANSWER_RE.search(chunk)
        if not answer_match:
            continue
        body = chunk[: answer_match.start()].strip()
        markers = find_ordered_option_markers(body)
        if not markers:
            continue
        options = []
        for index, marker in enumerate(markers):
            end = markers[index + 1].start() if index + 1 < len(markers) else len(body)
            options.append(body[marker.end():end].strip())
        answer_index = ord(answer_match.group(1).upper()) - ord("A")
        if not all(options) or answer_index not in range(len(options)):
            continue
        questions.append(
            {
                "prompt": body[: markers[0].start()].strip(" :"),
                "options": options,
                "correct_answer": options[answer_index],
            }
        )
    return questions


def extract_docx_paragraphs(docx_path):
    try:
        with zipfile.ZipFile(docx_path) as archive:
            xml_bytes = archive.read("word/document.xml")
    except (FileNotFoundError, KeyError, zipfile.BadZipFile) as exc:
        raise CommandError(f"Could not read DOCX file: {exc}") from exc

    root = ElementTree.fromstring(xml_bytes)
    paragraphs = []
    w_ns = WORD_NS["w"]
    for paragraph in root.findall(".//w:p", WORD_NS):
        parts = []
        for node in paragraph.iter():
            if node.tag == f"{{{w_ns}}}t" and node.text:
                parts.append(node.text)
            elif node.tag == f"{{{w_ns}}}tab":
                parts.append(" ")
        text = "".join(parts)
        if text.strip():
            paragraphs.append(text)
    return paragraphs


def normalize_text(text):
    text = text.replace("\u00a0", " ")
    return re.sub(r"\s+", " ", text).strip()


def find_ordered_option_markers(text):
    markers = list(OPTION_RE.finditer(text))
    selected = []
    search_start = 0
    for letter in ("A", "B", "C", "D"):
        marker = next(
            (item for item in markers if item.start() >= search_start and item.group(1).upper() == letter),
            None,
        )
        if marker is None:
            return []
        selected.append(marker)
        search_start = marker.end()
    return selected
