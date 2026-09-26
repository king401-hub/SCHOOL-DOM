"""Bulk student import from a spreadsheet (CSV).

Flow: the admin uploads a CSV (Excel: File > Save As > CSV), we check every row
without saving anything (the preview), the admin fixes any class that could not
be matched, then the browser sends the rows back in small batches to commit.
Batches keep each request well inside the gunicorn worker timeout - hashing a
password per student is the slow part of creating one.

Each committed student goes through the same steps as create_student: profile,
wallet, class assignment, fee/bill sync, guardian directory, activation token.
"""
import csv
import io
import re
import secrets
import string
import unicodedata
from datetime import datetime

from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from django.db import transaction

MAX_UPLOAD_BYTES = 2 * 1024 * 1024
MAX_ROWS = 1000
MAX_COMMIT_BATCH = 25
DEFAULT_EMAIL_DOMAIN = "gmail.com"

TEMPLATE_COLUMNS = [
    "first_name",
    "middle_name",
    "last_name",
    "class",
    "gender",
    "date_of_birth",
    "guardian_name",
    "guardian_phone",
    "second_guardian_name",
    "second_guardian_phone",
    "guardian_email",
    "home_address",
    "student_email",
    "password",
]

# Header spellings we accept for each column, compared with every non-letter and
# non-digit stripped and lower-cased ("Date of Birth" -> "dateofbirth").
HEADER_ALIASES = {
    "first_name": {"firstname", "first", "givenname", "forename"},
    "middle_name": {"middlename", "middle", "othername", "othernames"},
    "last_name": {"lastname", "surname", "familyname", "last"},
    "class": {"class", "classname", "classroom", "level", "grade", "currentclass", "classlevel"},
    "gender": {"gender", "sex"},
    "date_of_birth": {"dateofbirth", "dob", "birthdate", "birthday"},
    "guardian_name": {"guardianname", "guardian", "parentname", "parent", "parentguardian"},
    "guardian_phone": {
        "guardianphone", "phone", "phonenumber", "parentphone", "guardiannumber", "parentnumber",
        "contact", "contactnumber", "phone1", "fathernumber", "fatherphone", "fathersnumber",
        "fathermothernumber", "fathermotherphone",
    },
    "second_guardian_name": {"secondguardianname", "guardian2", "secondguardian"},
    "second_guardian_phone": {
        "secondguardianphone", "phone2", "secondphone", "secondphonenumber", "mothernumber",
        "motherphone", "mothersnumber",
    },
    "guardian_email": {"guardianemail", "parentemail"},
    "home_address": {"homeaddress", "address", "residence", "residentialaddress"},
    "student_email": {"studentemail", "email", "emailaddress"},
    "password": {"password", "studentpassword"},
}
ALIAS_TO_COLUMN = {alias: column for column, aliases in HEADER_ALIASES.items() for alias in aliases}

_NUMBER_WORDS = {
    "one": "1", "two": "2", "three": "3", "four": "4", "five": "5", "six": "6",
    "seven": "7", "eight": "8", "nine": "9", "ten": "10", "eleven": "11", "twelve": "12",
    "first": "1", "second": "2", "third": "3", "fourth": "4", "fifth": "5", "sixth": "6",
}
_CLASS_WORD_ALIASES = {"primary": "pry", "pri": "pry", "prim": "pry", "sss": "ss", "kindergarten": "kg"}
_CLASS_NOISE_WORDS = {"department", "dept", "class", "the"}

_DATE_FORMATS = (
    "%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y", "%d.%m.%Y", "%d/%m/%y", "%d-%m-%y",
    "%d %B %Y", "%d %b %Y", "%B %d %Y", "%b %d %Y",
)
_GENDER_WORDS = {"m": "M", "male": "M", "boy": "M", "f": "F", "female": "F", "girl": "F"}

_PW_LOWER = "abcdefghjkmnpqrstuvwxyz"
_PW_UPPER = "ABCDEFGHJKLMNPQRSTUVWXYZ"
_PW_DIGITS = "23456789"


class ImportFileError(ValueError):
    """The upload cannot be read at all (as opposed to a single bad row)."""


def _header_key(value):
    return re.sub(r"[^a-z0-9]", "", str(value or "").lower())


def read_upload(uploaded_file):
    """Parse an uploaded CSV into a list of {"line": n, <column>: value} dicts."""
    raw = uploaded_file.read(MAX_UPLOAD_BYTES + 1)
    if len(raw) > MAX_UPLOAD_BYTES:
        raise ImportFileError("The file is larger than 2 MB. Split it and import the parts one at a time.")
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        text = raw.decode("cp1252", errors="replace")
    sample = text[:4096]
    delimiter = ","
    if sample.count(";") > sample.count(","):
        delimiter = ";"
    elif sample.count("\t") > sample.count(","):
        delimiter = "\t"

    table = [cells for cells in csv.reader(io.StringIO(text), delimiter=delimiter) if any(c.strip() for c in cells)]
    if not table:
        raise ImportFileError("The file is empty.")
    columns = [ALIAS_TO_COLUMN.get(_header_key(cell)) for cell in table[0]]
    if "first_name" not in columns or "last_name" not in columns:
        raise ImportFileError(
            "The first row must be a header with at least a first name and a surname column "
            "(first_name and last_name in the template)."
        )
    if len(table) - 1 > MAX_ROWS:
        raise ImportFileError(f"The file has more than {MAX_ROWS} students. Split it and import the parts one at a time.")

    rows = []
    for line, cells in enumerate(table[1:], start=2):
        row = {"line": line}
        for column, cell in zip(columns, cells):
            value = cell.strip()
            if column and value and column not in row:
                row[column] = value
        rows.append(row)
    return rows


def template_csv():
    """A ready-to-fill template with one example row."""
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(TEMPLATE_COLUMNS)
    writer.writerow([
        "Ada", "", "Okafor", "JSS 1", "F", "2013-05-14", "", "08012345678", "", "", "",
        "12 Example Street, Lagos", "", "",
    ])
    return buffer.getvalue()


# ---- normalising individual values -----------------------------------------


def tidy_name(value):
    text = re.sub(r"\s+", " ", str(value or "")).strip(" ,.")
    if text and (text.isupper() or text.islower()):
        text = text.title()
    return text


def class_key(text):
    """Comparable form of a class label: "SS2/SCIENCE DEPARTMENT" -> "ss2science"."""
    words = re.sub(r"[^a-z0-9]+", " ", str(text or "").lower()).split()
    words = [_CLASS_WORD_ALIASES.get(_NUMBER_WORDS.get(w, w), _NUMBER_WORDS.get(w, w)) for w in words]
    return "".join(w for w in words if w not in _CLASS_NOISE_WORDS)


def source_key(text):
    return re.sub(r"\s+", " ", str(text or "")).strip().casefold()


def parse_gender(value):
    return _GENDER_WORDS.get(str(value or "").strip().lower(), "")


def parse_birth_date(value):
    text = re.sub(r"(?<=\d)(st|nd|rd|th)\b", "", str(value or "").strip(), flags=re.IGNORECASE)
    text = re.sub(r"\bsept\b", "Sep", text, flags=re.IGNORECASE)
    text = re.sub(r"(?<=[A-Za-z])\.", "", text)  # "Sep." / "Jan."
    text = re.sub(r"[,]+", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    for fmt in _DATE_FORMATS:
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            continue
    return None


def split_phone_numbers(cell):
    """Every number in a cell, e.g. "0801 234 5678 / 0902 345 6789" -> two."""
    numbers = []
    for piece in re.split(r"[/,;&\n]|\band\b", str(cell or ""), flags=re.IGNORECASE):
        digits = re.sub(r"\D", "", piece)
        if digits:
            numbers.append((piece.strip().startswith("+"), digits))
    return numbers


def canonical_phone(is_international, digits):
    """"+234..." for a valid Nigerian number, "+<digits>" for other international
    numbers typed with a leading +, "" if it cannot be a real phone number."""
    from finance.services import normalize_phone_number

    normalized = normalize_phone_number(digits)
    # A 10-digit number that already starts with 0 has lost a digit; the
    # normaliser would turn it into "234" + 10 digits with a 0 after the code.
    if len(normalized) == 13 and normalized.startswith("234") and normalized[3] != "0":
        return f"+{normalized}"
    if is_international and 8 <= len(digits) <= 15:
        return f"+{digits}"
    return ""


def _email_local_part(name):
    ascii_name = unicodedata.normalize("NFKD", str(name or "")).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]", "", ascii_name.lower())


def email_candidates(first_name, middle_name, last_name, domain):
    """One of the student's names first, then the others, then first+last, then
    first+last+number - the caller takes the first one that is still free."""
    seen = set()
    for name in [first_name, *str(middle_name or "").split(), last_name]:
        local = _email_local_part(name)
        if local and local not in seen:
            seen.add(local)
            yield f"{local}@{domain}"
    base = _email_local_part(first_name) + _email_local_part(last_name)
    if base and base not in seen:
        yield f"{base}@{domain}"
    number = 2
    while number < 1000:
        yield f"{base or 'student'}{number}@{domain}"
        number += 1


def generate_password():
    """8 characters, at least one lower/upper/digit, no look-alike characters."""
    pool = _PW_LOWER + _PW_UPPER + _PW_DIGITS
    chars = [secrets.choice(_PW_LOWER), secrets.choice(_PW_UPPER), secrets.choice(_PW_DIGITS)]
    chars += [secrets.choice(pool) for _ in range(5)]
    secrets.SystemRandom().shuffle(chars)
    return "".join(chars)


# ---- the plan for one file --------------------------------------------------


class ImportContext:
    """Everything a row is checked against, loaded once per request."""

    def __init__(self, user, *, default_class_id="", class_map=None, email_domain=DEFAULT_EMAIL_DOMAIN):
        from academic.models import Class
        from users.app_views import _scope_to_user_tenant
        from users.models import StudentProfile, User

        self.user = user
        self.User = User
        self.email_domain = (str(email_domain or "").strip().lower().lstrip("@")) or DEFAULT_EMAIL_DOMAIN

        self.classes = list(_scope_to_user_tenant(Class.objects.all(), user).order_by("name", "section"))
        self.classes_by_id = {str(item.id): item for item in self.classes}
        self.class_index = {}
        self.name_index = {}
        for item in self.classes:
            section = (item.section or "").strip()
            self.name_index.setdefault(class_key(item.name), []).append(item)
            self.class_index.setdefault(class_key(f"{item.name} {section}" if section else item.name), []).append(item)

        self.class_map = {source_key(k): str(v) for k, v in (class_map or {}).items() if v not in (None, "")}
        self.default_class = self.classes_by_id.get(str(default_class_id)) if default_class_id else None

        self.taken_keys = {
            (str(first).casefold(), str(last).casefold(), class_id)
            for first, last, class_id in StudentProfile.objects.filter(user__tenant=user.tenant).values_list(
                "user__first_name", "user__last_name", "current_class_id"
            )
        }
        self.used_emails = set()

    def class_label(self, class_obj):
        if not class_obj:
            return ""
        section = (class_obj.section or "").strip()
        return f"{class_obj.name} - {section}" if section else class_obj.name

    def resolve_class(self, source):
        """(Class or None, message) for the text in a row's class column."""
        source = str(source or "").strip()
        if not source:
            if self.default_class:
                return self.default_class, ""
            return None, "No class given. Add a class column or pick a class for the whole file."
        mapped = self.class_map.get(source_key(source))
        if mapped:
            found = self.classes_by_id.get(mapped)
            return (found, "") if found else (None, f'The class chosen for "{source}" no longer exists.')
        key = class_key(source)
        for index in (self.class_index, self.name_index):
            matches = index.get(key, [])
            if len(matches) == 1:
                return matches[0], ""
            if len(matches) > 1:
                labels = ", ".join(self.class_label(item) for item in matches)
                return None, f'"{source}" matches more than one class ({labels}). Choose the right one.'
        return None, f'No class called "{source}". Choose one of your classes for it.'

    def free_email(self, first_name, middle_name, last_name):
        for candidate in email_candidates(first_name, middle_name, last_name, self.email_domain):
            if candidate in self.used_emails:
                continue
            if self.User.objects.filter(email__iexact=candidate).exists():
                continue
            return candidate
        return ""

    def email_is_free(self, email):
        return email not in self.used_emails and not self.User.objects.filter(email__iexact=email).exists()


def plan_row(ctx, row):
    """Validate one parsed row and work out what would be created. Never saves."""
    plan = {
        "line": row.get("line"),
        "status": "create",
        "message": "",
        "warnings": [],
    }
    first_name = tidy_name(row.get("first_name"))
    middle_name = tidy_name(row.get("middle_name"))
    last_name = tidy_name(row.get("last_name"))
    plan.update(first_name=first_name, middle_name=middle_name, last_name=last_name)
    if not first_name or not last_name:
        plan.update(status="error", message="A first name and a surname are both required.")
        return plan

    class_source = str(row.get("class") or "").strip()
    class_obj, class_message = ctx.resolve_class(class_source)
    plan.update(
        class_source=class_source,
        class_id=str(class_obj.id) if class_obj else "",
        class_label=ctx.class_label(class_obj),
    )
    if not class_obj:
        plan.update(status="error", message=class_message)
        return plan

    duplicate_key = (first_name.casefold(), last_name.casefold(), class_obj.id)
    if duplicate_key in ctx.taken_keys:
        plan.update(status="skip", message="Already in this class - skipped.")
        return plan
    ctx.taken_keys.add(duplicate_key)

    # Phones: any mix of one cell holding two numbers and a second phone column.
    phones = []
    for cell in (row.get("guardian_phone"), row.get("second_guardian_phone")):
        for is_international, digits in split_phone_numbers(cell):
            phone = canonical_phone(is_international, digits)
            if not phone:
                plan["warnings"].append(f"{digits} is not a valid phone number and was left out.")
            elif phone not in phones:
                phones.append(phone)
    if len(phones) > 2:
        plan["warnings"].append("More than two phone numbers were given; only the first two are used.")
        phones = phones[:2]

    # Guardian names default to the child's surname; two numbers read as Mr and Mrs.
    guardian_name = tidy_name(row.get("guardian_name"))
    second_guardian_name = tidy_name(row.get("second_guardian_name"))
    if len(phones) == 2:
        guardian_name = guardian_name or f"Mr {last_name}"
        second_guardian_name = second_guardian_name or f"Mrs {last_name}"
    else:
        guardian_name = guardian_name or last_name
    plan.update(
        guardian_name=guardian_name,
        guardian_phone=phones[0] if phones else "",
        second_guardian_name=second_guardian_name,
        second_guardian_phone=phones[1] if len(phones) > 1 else "",
        guardian_email=str(row.get("guardian_email") or "").strip(),
        home_address=str(row.get("home_address") or "").strip(),
    )
    if plan["guardian_email"]:
        try:
            validate_email(plan["guardian_email"])
        except ValidationError:
            plan["warnings"].append(f'Guardian email "{plan["guardian_email"]}" is not valid and was left out.')
            plan["guardian_email"] = ""

    gender_text = str(row.get("gender") or "").strip()
    plan["gender"] = parse_gender(gender_text)
    if gender_text and not plan["gender"]:
        plan["warnings"].append(f'Gender "{gender_text}" was not recognised (use M or F) and was left out.')

    birth_text = str(row.get("date_of_birth") or "").strip()
    birth_date = parse_birth_date(birth_text) if birth_text else None
    plan["date_of_birth"] = birth_date.isoformat() if birth_date else ""
    if birth_text and not birth_date:
        plan["warnings"].append(f'Date of birth "{birth_text}" was not understood (use DD/MM/YYYY) and was left out.')

    given_email = str(row.get("student_email") or "").strip().lower()
    if given_email:
        try:
            validate_email(given_email)
        except ValidationError:
            plan.update(status="error", message=f'"{given_email}" is not a valid email address.')
            return plan
        if not ctx.email_is_free(given_email):
            plan.update(status="error", message=f"{given_email} is already used by another account.")
            return plan
        email = given_email
        plan["email_generated"] = False
    else:
        email = ctx.free_email(first_name, middle_name, last_name)
        plan["email_generated"] = True
        if not email:
            plan.update(status="error", message="Could not find a free email address for this student.")
            return plan
    ctx.used_emails.add(email)
    plan["email"] = email
    plan["password"] = str(row.get("password") or "").strip()
    return plan


def _public_plan(plan):
    """A plan as sent to the browser: a supplied password is never echoed back."""
    public = {key: value for key, value in plan.items() if key != "password"}
    public["password_given"] = bool(plan.get("password"))
    return public


def summarize_classes(plans):
    """One entry per distinct class text in the file, so unmatched ones can be mapped."""
    groups = {}
    for plan in plans:
        if "class_source" not in plan:
            continue  # rejected before its class was looked at (no name)
        source = plan["class_source"]
        group = groups.setdefault(
            source_key(source),
            {"source": source, "count": 0, "class_id": plan.get("class_id", ""), "class_label": plan.get("class_label", "")},
        )
        group["count"] += 1
    return sorted(groups.values(), key=lambda item: item["source"].casefold())


def build_preview(user, rows, *, default_class_id="", class_map=None, email_domain=DEFAULT_EMAIL_DOMAIN):
    ctx = ImportContext(user, default_class_id=default_class_id, class_map=class_map, email_domain=email_domain)
    plans = [plan_row(ctx, row) for row in rows]
    counts = {"create": 0, "skip": 0, "error": 0}
    for plan in plans:
        counts[plan["status"]] += 1
    return {
        "rows": [_public_plan(plan) for plan in plans],
        "counts": counts,
        "classes": summarize_classes(plans),
        "email_domain": ctx.email_domain,
        "available_classes": [{"id": str(item.id), "label": ctx.class_label(item)} for item in ctx.classes],
    }


# ---- committing a batch -------------------------------------------------------


def commit_rows(user, rows, *, default_class_id="", class_map=None, email_domain=DEFAULT_EMAIL_DOMAIN, assign_tokens=False):
    """Create the students in one batch. Returns created/skipped/failed lists; a
    failure on one row never rolls back the others."""
    from django.utils.dateparse import parse_date

    from academic.models import Class
    from finance.models import Bill
    from finance.services import (
        assign_monthly_activation_credits,
        ensure_student_wallet,
        sync_bill_invoices,
        sync_student_class_fees,
    )
    from users import app_views

    if len(rows) > MAX_COMMIT_BATCH:
        raise ImportFileError(f"Send at most {MAX_COMMIT_BATCH} students per request.")

    ctx = ImportContext(user, default_class_id=default_class_id, class_map=class_map, email_domain=email_domain)
    created, skipped, failed, warnings = [], [], [], []
    new_profiles = []
    tokens_assigned = 0
    token_message = ""

    for row in rows:
        plan = plan_row(ctx, row)
        label = f'{plan.get("first_name", "")} {plan.get("last_name", "")}'.strip() or f'line {plan.get("line")}'
        if plan["status"] == "skip":
            skipped.append({"line": plan["line"], "name": label, "message": plan["message"]})
            continue
        if plan["status"] == "error":
            failed.append({"line": plan["line"], "name": label, "message": plan["message"]})
            continue

        password = plan["password"] or generate_password()
        try:
            with transaction.atomic():
                profile = app_views._ensure_student_profile_for_tenant(
                    user=user,
                    email=plan["email"],
                    first_name=plan["first_name"],
                    middle_name=plan["middle_name"],
                    last_name=plan["last_name"],
                    guardian_name=plan["guardian_name"],
                    guardian_phone=plan["guardian_phone"],
                    guardian_email=plan["guardian_email"],
                    guardian_relation="Guardian",
                    second_guardian_name=plan["second_guardian_name"],
                    second_guardian_phone=plan["second_guardian_phone"],
                    second_guardian_relation="Guardian" if plan["second_guardian_name"] else "",
                    home_address=plan["home_address"],
                    student_password=password,
                    confirm_student_password=password,
                )
                student_user = profile.user
                user_fields = []
                if plan["gender"]:
                    student_user.gender = plan["gender"]
                    user_fields.append("gender")
                if plan["date_of_birth"]:
                    student_user.date_of_birth = parse_date(plan["date_of_birth"])
                    user_fields.append("date_of_birth")
                if user_fields:
                    student_user.save(update_fields=user_fields)
                profile.current_class = Class.objects.get(id=plan["class_id"])
                profile.save(update_fields=["current_class"])
        except ValueError as exc:
            failed.append({"line": plan["line"], "name": label, "message": str(exc)})
            continue
        except Exception as exc:  # one bad row must not stop the batch
            failed.append({"line": plan["line"], "name": label, "message": f"Could not create this student ({exc})."})
            continue

        try:
            ensure_student_wallet(profile.user)
        except Exception:
            pass
        try:
            app_views._sync_student_guardians_to_parent_directory(profile)
        except Exception:
            warnings.append(f"{label}: the guardian could not be added to the parent directory.")
        if assign_tokens:
            try:
                assign_monthly_activation_credits(
                    user.tenant, scope="student", months=1, actor=user, student_id=str(profile.id)
                )
                tokens_assigned += 1
            except ValueError as exc:
                token_message = token_message or str(exc)

        new_profiles.append(profile)
        created.append({
            "line": plan["line"],
            "name": label,
            "student_id": profile.student_id,
            "email": plan["email"],
            "password": password,
            "class_label": plan["class_label"],
            "guardian_name": plan["guardian_name"],
            "guardian_phone": plan["guardian_phone"],
            "warnings": plan["warnings"],
        })

    # Fees: each student's own class fees, then each affected class's published
    # bills once (not once per student).
    try:
        for profile in new_profiles:
            sync_student_class_fees(profile, actor=user)
        class_ids = {profile.current_class_id for profile in new_profiles if profile.current_class_id}
        if class_ids:
            for bill in Bill.objects.filter(classes__in=class_ids, status=Bill.STATUS_PUBLISHED).distinct():
                sync_bill_invoices(bill, actor=user)
    except Exception:
        warnings.append("The students were created but their fees could not be synced. Open Finance to check.")

    return {
        "created": created,
        "skipped": skipped,
        "failed": failed,
        "warnings": warnings,
        "tokens_assigned": tokens_assigned,
        "token_message": token_message,
    }
