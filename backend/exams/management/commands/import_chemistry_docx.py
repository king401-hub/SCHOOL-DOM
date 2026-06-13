import re
import zipfile
from datetime import timedelta
from xml.etree import ElementTree

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone
from django.utils.dateparse import parse_datetime

from academic.models import Class, Subject
from exams.models import Exam, ExamType, Question, QuestionBank
from tenants.models import Tenant
from users.models import User


WORD_NS = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}
QUESTION_RE = re.compile(r"^(\d+)\.\s*(.+)")
OPTION_RE = re.compile(r"^/?([A-D])\.\s*(.+)")
INLINE_OPTION_RE = re.compile(r"\s/?([A-D])\.\s*")
ANSWER_RE = re.compile(r"^Answer:\s*([A-D])(?:\s*\((.*?)(?:\)\.?)?)?\s*$", re.IGNORECASE)
INLINE_ANSWER_MARKER_RE = re.compile(r"Answer\s*:\s*([A-D])", re.IGNORECASE)
OPTION_MARKER_RE = re.compile(r"([A-D])\.\s*")
INLINE_QUESTION_PREFIX = "__INLINE_QUESTION__"


class Command(BaseCommand):
    help = "Import Chemistry MCQ questions and answers from the Schooldom senior class DOCX."

    def add_arguments(self, parser):
        parser.add_argument("docx_path")
        parser.add_argument("--tenant-id", type=int)
        parser.add_argument("--tenant-slug")
        parser.add_argument("--subject-code", default="CHEM")
        parser.add_argument("--teacher-email")
        parser.add_argument("--bank-name", default="Chemistry Test Questions for Schooldom Senior Class")
        parser.add_argument("--exam-title")
        parser.add_argument("--class-id", type=int)
        parser.add_argument("--duration-minutes", type=int, default=120)
        parser.add_argument("--start-date")
        parser.add_argument("--end-date")
        parser.add_argument("--publish", action="store_true")
        parser.add_argument("--dry-run", action="store_true")

    def handle(self, *args, **options):
        questions, warnings = parse_docx_questions(options["docx_path"])

        if not questions:
            raise CommandError("No questions were found in the DOCX.")

        tenant = self._resolve_tenant(options)
        subject = self._resolve_subject(tenant, options["subject_code"])
        teacher = self._resolve_teacher(options.get("teacher_email"))
        class_group = self._resolve_class(tenant, options.get("class_id"))

        validation_warnings = validate_questions(questions)
        warnings.extend(validation_warnings)

        self.stdout.write(f"Parsed {len(questions)} questions from DOCX.")
        self.stdout.write(f"Tenant: {tenant.name} ({tenant.id})")
        self.stdout.write(f"Subject: {subject.name} ({subject.code})")
        self.stdout.write(f"Teacher: {teacher.get_full_name() or teacher.email}")
        if class_group:
            self.stdout.write(f"Class: {class_group}")
        if warnings:
            self.stdout.write(self.style.WARNING("Warnings:"))
            for warning in warnings:
                self.stdout.write(self.style.WARNING(f"- {warning}"))

        if options["dry_run"]:
            self.stdout.write(self.style.SUCCESS("Dry run complete. No database changes were made."))
            return

        with transaction.atomic():
            imported_questions = []
            for item in questions:
                question = Question.objects.filter(
                    tenant=tenant,
                    text=item["text"],
                    options=item["options"],
                    correct_answer=item["correct_answer"],
                ).first()
                if question:
                    question.question_type = "mcq"
                    question.points = 1
                    question.explanation = item["explanation"]
                    question.save(update_fields=["question_type", "points", "explanation", "updated_at"])
                else:
                    question = Question.objects.create(
                        tenant=tenant,
                        text=item["text"],
                        question_type="mcq",
                        points=1,
                        options=item["options"],
                        correct_answer=item["correct_answer"],
                        explanation=item["explanation"],
                    )
                imported_questions.append(question)

            bank, _created = QuestionBank.objects.update_or_create(
                tenant=tenant,
                name=options["bank_name"],
                defaults={
                    "subject": subject,
                    "teacher": teacher,
                    "is_shared": True,
                },
            )
            bank.questions.set(imported_questions)

            self.stdout.write(self.style.SUCCESS(f"Imported {len(imported_questions)} questions into bank #{bank.id}."))

            if options.get("exam_title"):
                exam = self._create_or_update_exam(options, tenant, subject, teacher, class_group, imported_questions)
                self.stdout.write(self.style.SUCCESS(f"Attached questions to exam #{exam.id}: {exam.title}"))

    def _resolve_tenant(self, options):
        query = Tenant.objects.all()
        if options.get("tenant_id"):
            query = query.filter(id=options["tenant_id"])
        elif options.get("tenant_slug"):
            query = query.filter(slug__iexact=options["tenant_slug"])
        tenant = query.order_by("id").first()
        if not tenant:
            raise CommandError("Could not resolve tenant. Pass --tenant-id or --tenant-slug.")
        return tenant

    def _resolve_subject(self, tenant, code):
        subject = Subject.objects.filter(tenant=tenant, code__iexact=code).first()
        if not subject:                   
            subject = Subject.objects.filter(tenant=tenant, name__iexact="Chemistry").first()
        if not subject:
            raise CommandError(f"Could not find Chemistry subject for tenant {tenant.id}.")
        return subject

    def _resolve_teacher(self, email):
        users = User.objects.filter(role="teacher", is_active=True)
        if email:
            users = users.filter(email__iexact=email)
        teacher = users.order_by("created_at").first()
        if not teacher:
            raise CommandError("Could not resolve teacher. Pass --teacher-email.")
        return teacher

    def _resolve_class(self, tenant, class_id):
        if not class_id:
            return None
        class_group = Class.objects.filter(tenant=tenant, id=class_id).first()
        if not class_group:
            raise CommandError(f"Could not find class {class_id} for tenant {tenant.id}.")
        return class_group

    def _create_or_update_exam(self, options, tenant, subject, teacher, class_group, questions):
        exam_type, _created = ExamType.objects.get_or_create(tenant=tenant, name="MCQ")
        start_date = parse_datetime(options["start_date"]) if options.get("start_date") else timezone.now()
        end_date = parse_datetime(options["end_date"]) if options.get("end_date") else start_date + timedelta(days=30)
        if timezone.is_naive(start_date):
            start_date = timezone.make_aware(start_date)
        if timezone.is_naive(end_date):
            end_date = timezone.make_aware(end_date)

        exam, _created = Exam.objects.update_or_create(
            tenant=tenant,
            title=options["exam_title"],
            subject=subject,
            class_group=class_group,
            defaults={
                "teacher": teacher,
                "exam_type": exam_type,
                "instructions": "Answer all questions.",
                "start_date": start_date,
                "end_date": end_date,
                "duration_minutes": options["duration_minutes"],
                "shuffle_questions": False,
                "show_results_immediately": False,
                "allow_retake": False,
                "max_attempts": 1,
                "is_published": options["publish"],
            },
        )
        exam.questions.set(questions)
        return exam


def parse_docx_questions(docx_path):
    paragraphs = extract_docx_paragraphs(docx_path)
    normalized_lines = []
    warnings = []

    for paragraph in paragraphs:
        text = normalize_text(paragraph)
        if not text:
            continue
        normalized_lines.extend(split_inline_options(text))

    questions = []
    current = None
    expected_number = 1

    for line in normalized_lines:
        if line.startswith(INLINE_QUESTION_PREFIX):
            inline_text = line[len(INLINE_QUESTION_PREFIX):]
            if current:
                questions.append(finalize_question(current, warnings))
            warnings.append(f"Recovered missing question number {expected_number}.")
            current = inline_question_from_text(inline_text, expected_number, warnings)
            expected_number += 1
            continue

        question_match = QUESTION_RE.match(line)
        option_match = OPTION_RE.match(line)
        answer_match = ANSWER_RE.match(line)

        if question_match:
            if current:
                questions.append(finalize_question(current, warnings))
            number = int(question_match.group(1))
            if number != expected_number:
                warnings.append(f"Expected question {expected_number}, found {number}.")
                expected_number = number
            current = {
                "number": number,
                "text_parts": [question_match.group(2).strip()],
                "options_by_letter": {},
                "answer_letter": "",
                "explanation": "",
            }
            expected_number += 1
            continue

        if current and current["answer_letter"] and not option_match and not answer_match:
            if line.lower().startswith("the correct answer for your sample question"):
                warnings.append(f"Ignored loose line: {line[:90]}")
                continue
            if not INLINE_OPTION_RE.search(line):
                warnings.append(f"Ignored loose line: {line[:90]}")
                continue
            if current:
                questions.append(finalize_question(current, warnings))
            warnings.append(f"Recovered missing question number {expected_number}.")
            current = {
                "number": expected_number,
                "text_parts": [line.strip()],
                "options_by_letter": {},
                "answer_letter": "",
                "explanation": "",
            }
            expected_number += 1
            continue

        if option_match and current:
            current["options_by_letter"][option_match.group(1).upper()] = option_match.group(2).strip()
            continue

        if answer_match and current:
            current["answer_letter"] = answer_match.group(1).upper()
            current["explanation"] = (answer_match.group(2) or "").strip()
            continue

        if current and not current["answer_letter"]:
            current["text_parts"].append(line)
        else:
            warnings.append(f"Ignored loose line: {line[:90]}")

    if current:
        questions.append(finalize_question(current, warnings))

    if not questions:
        questions, inline_warnings = parse_unnumbered_inline_questions(paragraphs)
        warnings = inline_warnings

    return questions, warnings


def parse_unnumbered_inline_questions(paragraphs):
    content = " ".join(
        normalize_text(paragraph)
        for paragraph in paragraphs
        if "schooldom" not in paragraph.casefold() or "question" not in paragraph.casefold()
    )
    chunks = [match.group(0).strip() for match in re.finditer(r".+?Answer\s*:\s*[A-D]", content, re.IGNORECASE)]
    questions = []
    warnings = []

    for index, chunk in enumerate(chunks, start=1):
        answer_match = INLINE_ANSWER_MARKER_RE.search(chunk)
        if not answer_match:
            warnings.append(f"Question {index} is missing an inline answer.")
            continue

        body = chunk[: answer_match.start()].strip()
        answer_letter = answer_match.group(1).upper()
        markers = find_ordered_option_markers(body)
        if not markers:
            warnings.append(f"Question {index} does not have ordered A-D options.")
            continue

        options_by_letter = {}
        for marker_index, marker in enumerate(markers):
            letter = marker.group(1).upper()
            end = markers[marker_index + 1].start() if marker_index + 1 < len(markers) else len(body)
            options_by_letter[letter] = body[marker.end():end].strip()

        question_text = body[: markers[0].start()].strip(" :")
        questions.append(
            finalize_question(
                {
                    "number": index,
                    "text_parts": [question_text],
                    "options_by_letter": options_by_letter,
                    "answer_letter": answer_letter,
                    "explanation": "",
                },
                warnings,
            )
        )

    if content and not chunks:
        warnings.append("No inline Answer: A-D markers were found.")
    return questions, warnings


def find_ordered_option_markers(text):
    markers = list(OPTION_MARKER_RE.finditer(text))
    selected = []
    search_start = 0
    for expected_letter in ("A", "B", "C", "D"):
        marker = next(
            (
                item
                for item in markers
                if item.start() >= search_start and item.group(1).upper() == expected_letter
            ),
            None,
        )
        if marker is None:
            return []
        selected.append(marker)
        search_start = marker.end()
    return selected


def extract_docx_paragraphs(docx_path):
    try:
        with zipfile.ZipFile(docx_path) as archive:
            xml_bytes = archive.read("word/document.xml")
    except (FileNotFoundError, KeyError, zipfile.BadZipFile) as exc:
        raise CommandError(f"Could not read DOCX file: {exc}")

    root = ElementTree.fromstring(xml_bytes)
    paragraphs = []
    w_ns = WORD_NS["w"]
    for paragraph in root.findall(".//w:p", WORD_NS):
        parts = []
        for run in paragraph.findall("w:r", WORD_NS):
            run_properties = run.find("w:rPr", WORD_NS)
            underline = run_properties.find("w:u", WORD_NS) if run_properties is not None else None
            underline_value = underline.get(f"{{{w_ns}}}val") if underline is not None else None
            is_underlined = underline is not None and underline_value != "none"
            vertical_align = run_properties.find("w:vertAlign", WORD_NS) if run_properties is not None else None
            vertical_value = vertical_align.get(f"{{{w_ns}}}val") if vertical_align is not None else None

            run_text = "".join(node.text or "" for node in run.findall("w:t", WORD_NS))
            if run_text:
                if vertical_value == "subscript":
                    run_text = f"<sub>{run_text}</sub>"
                elif vertical_value == "superscript":
                    run_text = f"<sup>{run_text}</sup>"
                if is_underlined:
                    run_text = f"<u>{run_text}</u>"
                parts.append(run_text)
        text = "".join(parts)
        if text.strip():
            paragraphs.append(text)
    return paragraphs


def normalize_text(text):
    text = text.replace("\u00a0", " ")
    text = re.sub(r"\s+", " ", text).strip()
    return text


def split_inline_options(text):
    if not ANSWER_RE.match(text) and len(INLINE_OPTION_RE.findall(text)) >= 2:
        if not QUESTION_RE.match(text):
            return [f"{INLINE_QUESTION_PREFIX}{text}"]
        answer_line = ""
        answer_match = re.search(r"\sAnswer:\s*[A-D].*$", text, flags=re.IGNORECASE)
        if answer_match:
            answer_line = answer_match.group(0).strip()
            text = text[: answer_match.start()].strip()
        first_option = INLINE_OPTION_RE.search(text)
        lines = [text[: first_option.start()].strip()]
        option_text = text[first_option.start() :].strip()
        parts = INLINE_OPTION_RE.split(" " + option_text)
        for i in range(1, len(parts), 2):
            letter = parts[i].upper()
            body = parts[i + 1].strip() if i + 1 < len(parts) else ""
            lines.append(f"{letter}. {body}")
        if answer_line:
            lines.append(answer_line)
        return [line for line in lines if line]
    return [text]


def inline_question_from_text(text, number, warnings):
    answer_line = ""
    answer_match = re.search(r"\sAnswer:\s*[A-D].*$", text, flags=re.IGNORECASE)
    if answer_match:
        answer_line = answer_match.group(0).strip()
        text = text[: answer_match.start()].strip()

    first_option = INLINE_OPTION_RE.search(text)
    question_text = text[: first_option.start()].strip() if first_option else text.strip()
    option_text = text[first_option.start():].strip() if first_option else ""
    parts = INLINE_OPTION_RE.split(" " + option_text) if option_text else []
    options_by_letter = {}
    for i in range(1, len(parts), 2):
        letter = parts[i].upper()
        body = parts[i + 1].strip() if i + 1 < len(parts) else ""
        options_by_letter[letter] = body

    answer_match = ANSWER_RE.match(answer_line) if answer_line else None
    return {
        "number": number,
        "text_parts": [question_text],
        "options_by_letter": options_by_letter,
        "answer_letter": answer_match.group(1).upper() if answer_match else "",
        "explanation": (answer_match.group(2) or "").strip() if answer_match else "",
    }


def finalize_question(question, warnings):
    number = question["number"]
    options = []
    for letter in ("A", "B", "C", "D"):
        option = question["options_by_letter"].get(letter)
        if option is None:
            warnings.append(f"Question {number} is missing option {letter}.")
            option = ""
        options.append(option)

    answer_letter = question["answer_letter"]
    correct_answer = ""
    if answer_letter in ("A", "B", "C", "D"):
        correct_answer = options[ord(answer_letter) - ord("A")]
    else:
        warnings.append(f"Question {number} is missing a valid answer letter.")

    return {
        "number": number,
        "text": " ".join(question["text_parts"]).strip(),
        "options": options,
        "answer_letter": answer_letter,
        "correct_answer": correct_answer,
        "explanation": question["explanation"],
    }


def validate_questions(questions):
    warnings = []
    seen_numbers = set()
    for question in questions:
        number = question["number"]
        if number in seen_numbers:
            warnings.append(f"Duplicate question number {number}.")
        seen_numbers.add(number)
        if len(question["options"]) != 4 or any(not option for option in question["options"]):
            warnings.append(f"Question {number} does not have four complete options.")
        if not question["correct_answer"]:
            warnings.append(f"Question {number} has no correct answer text.")
    return warnings
