import re
import zipfile
from dataclasses import dataclass
from pathlib import Path
from xml.etree import ElementTree

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from academic.models import Class, Subject
from tenants.models import Tenant
from quizzes.models import PersonalQuizFolder, PersonalQuizFolderQuestion


QUESTION_WORDS = {"question", "questions", "ques", "qns", "qs"}
ANSWER_WORDS = {"answer", "answers", "ans", "key", "keys", "marking", "scheme", "solution", "solutions"}
OPTION_RE = re.compile(r"^\s*/?\{?\s*([A-Ha-h])[\).\:-]\s+(.+?)\s*$")
OPTION_MARKER_RE = re.compile(r"(?<!\w)/?\{?\s*([A-H])\.\s*")
QUESTION_RE = re.compile(r"^\s*(?:q(?:uestion)?\s*)?(\d{1,4})(?:[\).\:-]|\s+)\s*(.+?)\s*$", re.IGNORECASE)
ANSWER_RE = re.compile(
    r"^\s*(?:q(?:uestion)?\s*)?(\d{1,4})[\).\:-]?\s*(?:answer\s*)?[:\-]?\s*(.+?)\s*$",
    re.IGNORECASE,
)
ANSWER_FIRST_RE = re.compile(r"^\s*answer\s*(\d{1,4})\s*[:\-]\s*(.+?)\s*$", re.IGNORECASE)
INLINE_ANSWER_RE = re.compile(r"^\s*answer\s*[:\-]\s*(.+?)\s*$", re.IGNORECASE)


@dataclass
class ParsedQuestion:
    number: int
    prompt: str
    options: list
    answer: str = ""


def _slug_words(value):
    return [part for part in re.split(r"[^a-z0-9]+", value.lower()) if part]


def _pair_key(path):
    words = [word for word in _slug_words(path.stem) if word not in QUESTION_WORDS and word not in ANSWER_WORDS]
    if not words and path.parent.name:
        words = _slug_words(path.parent.name)
    return " ".join(words) or path.stem.lower()


def _file_kind(path):
    words = set(_slug_words(path.stem))
    if words & ANSWER_WORDS:
        return "answer"
    if words & QUESTION_WORDS:
        return "question"
    return ""


def _docx_paragraphs(path):
    try:
        with zipfile.ZipFile(path) as archive:
            xml_bytes = archive.read("word/document.xml")
    except (KeyError, zipfile.BadZipFile) as exc:
        raise CommandError(f"{path} is not a readable .docx file.") from exc

    root = ElementTree.fromstring(xml_bytes)
    namespace = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}
    paragraphs = []
    w_ns = namespace["w"]
    for paragraph in root.findall(".//w:p", namespace):
        parts = []
        for run in paragraph.findall("w:r", namespace):
            run_properties = run.find("w:rPr", namespace)
            underline = run_properties.find("w:u", namespace) if run_properties is not None else None
            underline_value = underline.get(f"{{{w_ns}}}val") if underline is not None else None
            is_underlined = underline is not None and underline_value != "none"
            vertical_align = run_properties.find("w:vertAlign", namespace) if run_properties is not None else None
            vertical_value = vertical_align.get(f"{{{w_ns}}}val") if vertical_align is not None else None
            run_parts = []
            for node in run:
                if node.tag == f"{{{w_ns}}}t" and node.text:
                    run_parts.append(node.text)
                elif node.tag == f"{{{w_ns}}}tab":
                    run_parts.append(" ")
            run_text = "".join(run_parts)
            if run_text:
                if vertical_value == "subscript":
                    run_text = f"<sub>{run_text}</sub>"
                elif vertical_value == "superscript":
                    run_text = f"<sup>{run_text}</sup>"
                if is_underlined:
                    run_text = f"<u>{run_text}</u>"
                parts.append(run_text)
        for node in paragraph:
            if node.tag == f"{{{w_ns}}}tab":
                parts.append(" ")
        text = _clean_import_text("".join(parts).strip())
        if text:
            paragraphs.append(re.sub(r"\s+", " ", text))
    return paragraphs


def _clean_import_text(text):
    text = text.replace("\u00a0", " ")
    text = text.replace("$", "")
    text = re.sub(r"\\frac\{([^{}]+)\}\{([^{}]+)\}", r" \1/\2", text)
    text = re.sub(r"\^\s*\\circ", " degrees", text)
    text = re.sub(r"\\text\{([^{}]+)\}", r"\1", text)
    text = re.sub(r"\\times", "x", text)
    text = re.sub(r"\\rightarrow", "->", text)
    text = re.sub(r"\s+degrees", " degrees", text)
    return text


def _parse_questions(lines):
    questions = []
    current = None
    current_option = None
    pending_intro = ""
    next_number = 1

    def finish_current():
        nonlocal next_number
        if current and current["prompt"] and len(current["options"]) >= 2:
            questions.append(
                ParsedQuestion(
                    number=current["number"],
                    prompt=" ".join(current["prompt"]).strip(),
                    options=[item["text"].strip() for item in current["options"] if item["text"].strip()],
                )
            )
            next_number = max(next_number, current["number"] + 1)

    def add_embedded_question(number, prompt, options):
        nonlocal next_number
        clean_options = [option.strip() for option in options if option.strip()]
        if prompt.strip() and len(clean_options) >= 2:
            questions.append(ParsedQuestion(number=number, prompt=prompt.strip(), options=clean_options))
            next_number = max(next_number, number + 1)

    for line in lines:
        question_match = QUESTION_RE.match(line)
        option_match = OPTION_RE.match(line)
        embedded_prompt, embedded_options = _split_embedded_options(line)
        if question_match and not option_match:
            finish_current()
            number = int(question_match.group(1))
            body = question_match.group(2)
            embedded_prompt, embedded_options = _split_embedded_options(body)
            if embedded_options:
                prompt = " ".join(part for part in [pending_intro, embedded_prompt] if part).strip()
                add_embedded_question(number, prompt, embedded_options)
                pending_intro = ""
                current = None
                current_option = None
                continue
            current = {"number": number, "prompt": [" ".join(part for part in [pending_intro, body] if part).strip()], "options": []}
            pending_intro = ""
            current_option = None
            continue
        if embedded_options and current and not embedded_prompt:
            current["options"] = [{"letter": chr(ord("A") + index), "text": option} for index, option in enumerate(embedded_options)]
            finish_current()
            current = None
            current_option = None
            continue
        if option_match and current:
            current_option = {"letter": option_match.group(1).upper(), "text": option_match.group(2)}
            current["options"].append(current_option)
            continue
        if embedded_options:
            finish_current()
            prompt = " ".join(part for part in [pending_intro, embedded_prompt] if part).strip()
            add_embedded_question(next_number, prompt, embedded_options)
            pending_intro = ""
            current = None
            current_option = None
            continue
        if current_option:
            current_option["text"] = f"{current_option['text']} {line}"
        elif current:
            current["prompt"].append(line)
        else:
            if not questions and not pending_intro and "schooldom" in line.casefold() and "question" in line.casefold():
                continue
            pending_intro = " ".join(part for part in [pending_intro, line] if part).strip()

    finish_current()
    return questions


def _parse_answers(lines):
    answers = {}
    sequential_number = 1
    for line in lines:
        if re.fullmatch(r"[A-Ha-h]", line.strip()):
            answers[sequential_number] = line.strip().upper()
            sequential_number += 1
            continue
        match = ANSWER_FIRST_RE.match(line) or ANSWER_RE.match(line)
        if not match:
            continue
        value = re.sub(r"^\s*answer\s*[:\-]?\s*", "", match.group(2), flags=re.IGNORECASE).strip()
        if value:
            answers[int(match.group(1))] = value
    return answers


def _parse_inline_answer_questions(lines):
    questions = []
    current = None
    current_option = None
    pending_intro = ""
    next_number = 1

    def finish_current():
        nonlocal current, current_option, next_number
        if current and current["prompt"] and len(current["options"]) >= 2 and current.get("answer"):
            questions.append(
                ParsedQuestion(
                    number=current["number"],
                    prompt=" ".join(current["prompt"]).strip(),
                    options=[item["text"].strip() for item in current["options"] if item["text"].strip()],
                    answer=current["answer"],
                )
            )
            next_number = max(next_number, current["number"] + 1)
        current = None
        current_option = None

    def start_question(number, prompt, options=None, answer=""):
        nonlocal current, current_option, pending_intro, next_number
        finish_current()
        current = {
            "number": number,
            "prompt": [prompt.strip()],
            "options": [
                {"letter": chr(ord("A") + index), "text": option.strip()}
                for index, option in enumerate(options or [])
                if option.strip()
            ],
            "answer": answer,
        }
        pending_intro = ""
        current_option = None
        next_number = max(next_number, number + 1)
        if answer:
            finish_current()

    for line in lines:
        if "schooldom" in line.casefold() and "question" in line.casefold() and not questions and not current:
            continue
        if not current and _is_loose_intro_line(line):
            pending_intro = ""
            continue

        inline_answer_match = INLINE_ANSWER_RE.match(line)
        if inline_answer_match and current:
            current["answer"] = inline_answer_match.group(1).strip()
            finish_current()
            continue

        question_match = QUESTION_RE.match(line)
        option_match = OPTION_RE.match(line)
        line_without_answer, inline_answer = _strip_inline_answer(line)
        embedded_prompt, embedded_options = _split_embedded_options(line_without_answer)

        if question_match and not option_match:
            number = int(question_match.group(1))
            body, inline_answer = _strip_inline_answer(question_match.group(2))
            embedded_prompt, embedded_options = _split_embedded_options(body)
            start_question(number, embedded_prompt, embedded_options, inline_answer)
            continue

        if option_match and current:
            current_option = {"letter": option_match.group(1).upper(), "text": option_match.group(2)}
            current["options"].append(current_option)
            continue

        if embedded_options:
            start_question(next_number, embedded_prompt, embedded_options, inline_answer)
            continue

        if current_option:
            current_option["text"] = f"{current_option['text']} {line}"
        elif current:
            current["prompt"].append(line)
        else:
            pending_intro = " ".join(part for part in [pending_intro, line] if part).strip()

    finish_current()
    return questions


def _split_embedded_options(line):
    markers = list(OPTION_MARKER_RE.finditer(line))
    if len(markers) < 2:
        return line.strip(), []

    prompt = line[: markers[0].start()].strip()
    options = []
    for index, marker in enumerate(markers):
        start = marker.end()
        end = markers[index + 1].start() if index + 1 < len(markers) else len(line)
        options.append(line[start:end].strip())
    return prompt, options


def _is_loose_intro_line(line):
    value = line.strip().casefold()
    return (
        value.startswith("the correct answer")
        or value.startswith("explanation:")
        or value.startswith("geography:")
        or value.startswith("practice set")
        or value.startswith("answer key")
    )


def _strip_inline_answer(line):
    match = re.search(r"\s+answer\s*[:\-]\s*(.+?)\s*$", line, flags=re.IGNORECASE)
    if not match:
        return line, ""
    return line[: match.start()].strip(), match.group(1).strip()


def _answer_to_text(answer_value, options):
    cleaned = str(answer_value or "").strip()
    letter_match = re.match(r"^([A-Ha-h])(?:[\).\:-]|\s*$)", cleaned)
    if letter_match:
        index = ord(letter_match.group(1).upper()) - ord("A")
        if 0 <= index < len(options):
            return options[index]
    for option in options:
        if option.casefold() == cleaned.casefold():
            return option
    return cleaned


def _find_subject(tenant, name_or_code):
    if not name_or_code:
        return None
    return (
        Subject.objects.filter(tenant=tenant)
        .filter(reduce_or_name_code(name_or_code))
        .order_by("name")
        .first()
    )


def reduce_or_name_code(value):
    from django.db.models import Q

    return Q(name__iexact=value) | Q(code__iexact=value)


def _find_class(tenant, value):
    if not value:
        return None
    return (
        Class.objects.filter(tenant=tenant)
        .filter(reduce_or_class(value))
        .order_by("name", "section")
        .first()
    )


def reduce_or_class(value):
    from django.db.models import Q

    return Q(name__iexact=value) | Q(section__iexact=value)


class Command(BaseCommand):
    help = "Import personal quiz objective question pools from paired .docx files or one inline-answer .docx."

    def add_arguments(self, parser):
        parser.add_argument("source", help="Folder containing paired .docx files, or one .docx with inline Answer: lines.")
        parser.add_argument("--tenant-slug", default="", help="School tenant slug to attach imported folders to.")
        parser.add_argument("--global", dest="is_global", action="store_true", help="Import into a global pool available to every tenant.")
        parser.add_argument("--subject", default="", help="Subject name or code. If omitted, importer tries the filename.")
        parser.add_argument("--class", dest="class_name", default="", help="Class/department name or section.")
        parser.add_argument("--replace", action="store_true", help="Replace existing imported questions in matched folders.")
        parser.add_argument("--dry-run", action="store_true", help="Parse and report without saving.")

    def handle(self, *args, **options):
        source = Path(options["source"]).resolve()
        if not source.exists():
            raise CommandError(f"Source not found: {source}")

        if options["is_global"]:
            tenant = None
        else:
            if not options["tenant_slug"]:
                raise CommandError("--tenant-slug is required unless --global is used.")
            tenant = Tenant.objects.filter(slug__iexact=options["tenant_slug"]).first()
        if not tenant and not options["is_global"]:
            raise CommandError(f"Tenant with slug '{options['tenant_slug']}' was not found.")

        total_imported = 0
        class_group = None if options["is_global"] else _find_class(tenant, options["class_name"])
        if options["class_name"] and not class_group:
            raise CommandError("Class/department imports are tenant-specific. Remove --global or omit --class.")

        if source.is_file():
            if source.suffix.lower() != ".docx" or source.name.startswith("~$"):
                raise CommandError(f"Source file is not a .docx file: {source}")
            subject = None if options["is_global"] else (_find_subject(tenant, options["subject"]) or _find_subject(tenant, _pair_key(source)))
            questions = _parse_inline_answer_questions(_docx_paragraphs(source))
            rows = []
            for question in questions:
                correct_answer = _answer_to_text(question.answer, question.options)
                if correct_answer:
                    rows.append((question, correct_answer))

            label_subject = subject.name if subject else _pair_key(source).title()
            label_class = f" - {class_group.name}" if class_group else ""
            folder_name = f"{label_subject}{label_class} Personal Quiz Pool"
            self.stdout.write(f"{source.name}: parsed {len(rows)} usable questions")

            with transaction.atomic():
                total_imported = len(rows)
                if options["dry_run"]:
                    transaction.set_rollback(True)
                else:
                    folder, _created = PersonalQuizFolder.objects.get_or_create(
                        tenant=tenant,
                        name=folder_name,
                        subject=subject,
                        class_group=class_group,
                        defaults={
                            "description": f"Imported from {source.name}.",
                            "subject_code": str(options["subject"] or _pair_key(source)).strip().upper() if options["is_global"] else "",
                            "subject_name": label_subject if options["is_global"] else "",
                        },
                    )
                    if options["replace"]:
                        folder.folder_questions.all().delete()
                    start_order = folder.folder_questions.count()
                    PersonalQuizFolderQuestion.objects.bulk_create(
                        [
                            PersonalQuizFolderQuestion(
                                folder=folder,
                                question_type=PersonalQuizFolderQuestion.OBJECTIVE,
                                prompt=question.prompt,
                                options=question.options,
                                correct_answer=correct_answer,
                                order=start_order + index + 1,
                                points=1,
                                is_active=True,
                            )
                            for index, (question, correct_answer) in enumerate(rows)
                        ]
                    )

            suffix = "checked" if options["dry_run"] else "imported"
            self.stdout.write(self.style.SUCCESS(f"{total_imported} personal quiz questions {suffix}."))
            return

        if not source.is_dir():
            raise CommandError(f"Source is neither a folder nor a .docx file: {source}")

        files = sorted(path for path in source.rglob("*.docx") if not path.name.startswith("~$"))
        pairs = {}
        for path in files:
            kind = _file_kind(path)
            if not kind:
                continue
            pairs.setdefault(_pair_key(path), {})[kind] = path

        ready_pairs = {key: pair for key, pair in pairs.items() if pair.get("question") and pair.get("answer")}
        if not ready_pairs:
            question_files = [path for path in files if _file_kind(path) == "question"]
            answer_files = [path for path in files if _file_kind(path) == "answer"]
            if len(question_files) == 1 and len(answer_files) == 1:
                ready_pairs = {
                    _pair_key(question_files[0]): {
                        "question": question_files[0],
                        "answer": answer_files[0],
                    }
                }
        if not ready_pairs:
            raise CommandError("No matching question/answer .docx pairs were found. Use names like Biology Questions.docx and Biology Answers.docx.")

        with transaction.atomic():
            for key, pair in ready_pairs.items():
                subject = None if options["is_global"] else (_find_subject(tenant, options["subject"]) or _find_subject(tenant, key))
                questions = _parse_questions(_docx_paragraphs(pair["question"]))
                answers = _parse_answers(_docx_paragraphs(pair["answer"]))
                rows = []
                for question in questions:
                    correct_answer = _answer_to_text(answers.get(question.number, ""), question.options)
                    if not correct_answer:
                        continue
                    rows.append((question, correct_answer))

                label_subject = subject.name if subject else key.title()
                label_class = f" - {class_group.name}" if class_group else ""
                folder_name = f"{label_subject}{label_class} Personal Quiz Pool"

                self.stdout.write(
                    f"{pair['question'].name} + {pair['answer'].name}: parsed {len(rows)} usable questions"
                )
                total_imported += len(rows)
                if options["dry_run"]:
                    continue

                folder, _created = PersonalQuizFolder.objects.get_or_create(
                    tenant=tenant,
                    name=folder_name,
                    subject=subject,
                    class_group=class_group,
                    defaults={
                        "description": f"Imported from {pair['question'].name} and {pair['answer'].name}.",
                        "subject_code": str(options["subject"] or key).strip().upper() if options["is_global"] else "",
                        "subject_name": label_subject if options["is_global"] else "",
                    },
                )
                if options["replace"]:
                    folder.folder_questions.all().delete()

                start_order = folder.folder_questions.count()
                PersonalQuizFolderQuestion.objects.bulk_create(
                    [
                        PersonalQuizFolderQuestion(
                            folder=folder,
                            question_type=PersonalQuizFolderQuestion.OBJECTIVE,
                            prompt=question.prompt,
                            options=question.options,
                            correct_answer=correct_answer,
                            order=start_order + index + 1,
                            points=1,
                            is_active=True,
                        )
                        for index, (question, correct_answer) in enumerate(rows)
                    ]
                )

            if options["dry_run"]:
                transaction.set_rollback(True)

        suffix = "checked" if options["dry_run"] else "imported"
        self.stdout.write(self.style.SUCCESS(f"{total_imported} personal quiz questions {suffix}."))
