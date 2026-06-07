import csv
import io
import json
import os
import re
import uuid
import zipfile
from datetime import date, timedelta
from decimal import Decimal, InvalidOperation
from urllib.parse import quote

import qrcode
import requests
from django.conf import settings
from django.core.files.base import ContentFile
from django.core.mail import send_mail
from django.core import signing
from django.core.files.storage import default_storage
from django.core.signing import BadSignature, SignatureExpired
from django.db import transaction as db_transaction
from django.db.models import Avg, Count, Q, Sum, Prefetch
from django.http import FileResponse
from django.shortcuts import get_object_or_404
from django.urls import reverse
from django.utils import timezone
from django.utils.dateparse import parse_date, parse_datetime
from django.utils.text import slugify
from rest_framework.decorators import api_view, authentication_classes, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
from finance.models import Wallet, SchoolFee, Transaction, AdminWallet, StudentPaymentReference, ActivationCreditPool
from finance.services import process_due_fees, ensure_student_wallet, get_or_create_student_payment_reference, fee_paid_amount
from attendance.utils import get_frontend_base_url
from apps.app.views import admin_app_installer_path, offline_cbt_installer_path

from academic.models import (
    AcademicYear,
    Class,
    Subject,
    Term,
    AttendanceRecord,
    LessonPlan,
    QuestionPrompt,
    QuestionResponse,
    GradeScale,
    ResultBatch,
    StudentSubjectScore,
    StudentClassPromotion,
    TeacherNote,
)
from core.models import SchoolTenant, Domain
from exams.models import Exam, ExamAttempt, ExamPin, ExamPinUsage, ExamType, Question, QuestionBank, QuestionGroup, StudentAnswer
from tenants.models import Tenant
from users.models import DatabaseImportJob, StudentEnrollment, StudentProfile, StudentTestimonial, SupportTicket, TeacherProfile, User, generate_short_student_id, generate_short_teacher_id, random_code_digits, school_code_letters
from apps.app.views import ADMIN_APP_FILENAME, admin_app_installer_path

try:
    from hr.models import StaffProfile
except Exception:  # pragma: no cover - HR app is optional in older installs
    StaffProfile = None

try:
    from notifications.models import Announcement, InAppMessage, Notification, NotificationPreference, SMSConfiguration
except Exception:  # pragma: no cover - optional app fallback
    Announcement = None
    InAppMessage = None
    Notification = None
    NotificationPreference = None
    SMSConfiguration = None

ADMIN_ROLES = {"school_admin", "principal", "super_admin"}
ID_CARD_SIGNING_SALT = "schooldom.id-card.verify"
ADMIN_EXAM_HIDDEN_SUBJECT_CODES = {"PHY", "CHEM"}
ADMIN_EXAM_HIDDEN_SUBJECT_NAMES = {"physics", "chemistry"}


def _resolve_school_tenant_for_user(user, school_code=""):
    linked_school = getattr(user, "tenant", None)
    if linked_school:
        return linked_school

    requested_code = str(school_code or "").strip().lower()
    if requested_code:
        school = SchoolTenant.objects.filter(schema_name__iexact=requested_code, is_active=True).first()
        if school and getattr(user, "role", None) != "super_admin":
            user.tenant = school
            user.save(update_fields=["tenant"])
        return school

    if getattr(user, "role", None) == "super_admin":
        return None

    schools = SchoolTenant.objects.filter(is_active=True).order_by("id")
    if schools.count() == 1:
        school = schools.first()
        user.tenant = school
        user.save(update_fields=["tenant"])
        return school

    return None


def _scope_to_user_tenant(queryset, user, school_code=""):
    """
    Scope queryset to current user tenant where model supports it.
    Handles both core.SchoolTenant and legacy tenants.Tenant relations.
    """
    try:
        field = queryset.model._meta.get_field("tenant")
    except Exception:
        return queryset

    user_tenant = _resolve_school_tenant_for_user(user, school_code=school_code)
    if not user_tenant:
        return queryset.none()

    related_model = field.remote_field.model
    if related_model == user_tenant.__class__:
        return queryset.filter(tenant=user_tenant)

    # Legacy mapping for models using tenants.Tenant
    if related_model._meta.label_lower == "tenants.tenant":
        mapped = related_model.objects.filter(slug__iexact=user_tenant.schema_name).first()
        if not mapped:
            mapped = related_model.objects.create(
                slug=user_tenant.schema_name,
                name=user_tenant.name,
            )
        return queryset.filter(tenant=mapped)

    return queryset.none()


def _tenant_for_model(model_class, user, school_code=""):
    """
    Resolve the correct tenant object for a model's tenant foreign key.
    """
    user_tenant = _resolve_school_tenant_for_user(user, school_code=school_code)
    if not user_tenant:
        return None

    try:
        field = model_class._meta.get_field("tenant")
    except Exception:
        return None

    related_model = field.remote_field.model
    if related_model == user_tenant.__class__:
        return user_tenant

    if related_model._meta.label_lower == "tenants.tenant":
        mapped = related_model.objects.filter(slug__iexact=user_tenant.schema_name).first()
        if not mapped:
            mapped = related_model.objects.create(
                slug=user_tenant.schema_name,
                name=user_tenant.name,
            )
        return mapped

    return None


def _hide_from_admin_exam_subjects(subject):
    code = str(getattr(subject, "code", "") or "").strip().upper()
    name = str(getattr(subject, "name", "") or "").strip().casefold()
    return code in ADMIN_EXAM_HIDDEN_SUBJECT_CODES or name in ADMIN_EXAM_HIDDEN_SUBJECT_NAMES


def _admin_exam_subject_options(queryset, user):
    if getattr(user, "role", None) not in ADMIN_ROLES:
        return queryset
    return queryset.exclude(
        Q(code__iexact="PHY")
        | Q(code__iexact="CHEM")
        | Q(name__iexact="Physics")
        | Q(name__iexact="Chemistry")
    )


DATABASE_IMPORT_EXTENSIONS = {
    ".csv",
    ".tsv",
    ".xlsx",
    ".xls",
    ".json",
    ".sql",
    ".zip",
    ".jpg",
    ".jpeg",
    ".png",
    ".gif",
    ".webp",
    ".pdf",
    ".doc",
    ".docx",
}
DATABASE_IMPORT_MAX_BYTES = 100 * 1024 * 1024


def _database_import_job_payload(job, request=None):
    upload_url = ""
    try:
        upload_url = job.upload.url if job.upload else ""
        if upload_url and request:
            upload_url = request.build_absolute_uri(upload_url)
    except Exception:
        upload_url = ""
    return {
        "id": str(job.id),
        "import_type": job.import_type,
        "import_type_label": job.get_import_type_display(),
        "source_platform": job.source_platform,
        "link_key": job.link_key,
        "notes": job.notes,
        "original_filename": job.original_filename,
        "file_size": job.file_size,
        "status": job.status,
        "summary": job.summary or {},
        "errors": job.errors or [],
        "uploaded_by": job.uploaded_by.get_full_name() if job.uploaded_by else "",
        "created_at": job.created_at,
        "updated_at": job.updated_at,
        "upload_url": upload_url,
    }


def _decode_upload_sample(uploaded_file, max_bytes=2 * 1024 * 1024):
    uploaded_file.seek(0)
    raw = uploaded_file.read(max_bytes)
    uploaded_file.seek(0)
    return raw.decode("utf-8-sig", errors="replace")


def _summarize_delimited_upload(uploaded_file, delimiter=","):
    text = _decode_upload_sample(uploaded_file)
    rows = list(csv.reader(io.StringIO(text), delimiter=delimiter))
    headers = rows[0] if rows else []
    data_rows = rows[1:] if len(rows) > 1 else []
    return {
        "format": "tsv" if delimiter == "\t" else "csv",
        "headers": headers[:80],
        "sample_rows": data_rows[:5],
        "estimated_rows_in_sample": len(data_rows),
    }


def _summarize_json_upload(uploaded_file):
    text = _decode_upload_sample(uploaded_file)
    parsed = json.loads(text)
    if isinstance(parsed, list):
        sample = parsed[:3]
        keys = sorted({key for item in sample if isinstance(item, dict) for key in item.keys()})
        count = len(parsed)
    elif isinstance(parsed, dict):
        sample = parsed
        keys = sorted(parsed.keys())
        count = len(parsed)
    else:
        sample = parsed
        keys = []
        count = 1
    return {"format": "json", "top_level_count": count, "keys": keys[:80], "sample": sample}


def _safe_zip_members(uploaded_file):
    uploaded_file.seek(0)
    with zipfile.ZipFile(uploaded_file) as archive:
        members = []
        unsafe = []
        for item in archive.infolist()[:500]:
            normalized = os.path.normpath(item.filename).replace("\\", "/")
            if normalized.startswith("../") or normalized.startswith("/") or item.file_size > DATABASE_IMPORT_MAX_BYTES:
                unsafe.append(item.filename)
                continue
            members.append(
                {
                    "name": item.filename,
                    "size": item.file_size,
                    "extension": os.path.splitext(item.filename)[1].lower(),
                }
            )
    uploaded_file.seek(0)
    return members, unsafe


def _summarize_zip_upload(uploaded_file):
    members, unsafe = _safe_zip_members(uploaded_file)
    media_extensions = {".jpg", ".jpeg", ".png", ".gif", ".webp", ".pdf", ".doc", ".docx"}
    data_extensions = {".csv", ".tsv", ".xlsx", ".xls", ".json", ".sql"}
    return {
        "format": "zip",
        "file_count": len(members),
        "data_files": [item for item in members if item["extension"] in data_extensions][:80],
        "media_files": [item for item in members if item["extension"] in media_extensions][:80],
        "unsafe_entries": unsafe,
    }


def _summarize_sql_upload(uploaded_file):
    text = _decode_upload_sample(uploaded_file)
    statements = [item.strip() for item in text.split(";") if item.strip()]
    return {
        "format": "sql",
        "statement_count_in_sample": len(statements),
        "tables_referenced": sorted(set(re.findall(r"(?:into|table|from)\s+[`\"]?([A-Za-z0-9_\.]+)", text, flags=re.IGNORECASE)))[:80],
        "execution_policy": "SQL backups are validated and stored for admin review; they are never executed directly from upload.",
    }


def _summarize_database_import_upload(uploaded_file):
    filename = uploaded_file.name or ""
    extension = os.path.splitext(filename)[1].lower()
    if extension not in DATABASE_IMPORT_EXTENSIONS:
        return {}, [f"{extension or 'This file type'} is not supported for school database import."]
    if uploaded_file.size > DATABASE_IMPORT_MAX_BYTES:
        return {}, ["Upload is larger than the 100 MB safety limit."]
    try:
        if extension == ".csv":
            summary = _summarize_delimited_upload(uploaded_file, ",")
        elif extension == ".tsv":
            summary = _summarize_delimited_upload(uploaded_file, "\t")
        elif extension == ".json":
            summary = _summarize_json_upload(uploaded_file)
        elif extension == ".zip":
            summary = _summarize_zip_upload(uploaded_file)
        elif extension == ".sql":
            summary = _summarize_sql_upload(uploaded_file)
        elif extension in {".xlsx", ".xls"}:
            summary = {
                "format": extension.lstrip("."),
                "review_note": "Spreadsheet accepted. Column mapping is completed during migration review.",
            }
        else:
            summary = {
                "format": extension.lstrip("."),
                "asset_import": True,
                "review_note": "Asset accepted. It can be linked to matching student, teacher, school, or document records by the selected key.",
            }
    except Exception as exc:
        return {}, [f"Could not inspect file safely: {exc}"]
    summary.update(
        {
            "filename": filename,
            "extension": extension,
            "size": uploaded_file.size,
            "supported_records": [
                "students",
                "teachers",
                "classes",
                "subjects",
                "cbt_results",
                "attendance",
                "payments",
                "timetables",
                "assignments",
                "documents",
                "academic_records",
            ],
            "asset_linking": "Images and documents can be matched by admission number, student ID, employee ID, email, class code, or filename convention.",
        }
    )
    return summary, list(summary.get("unsafe_entries") or [])


STUDENT_IMAGE_IMPORT_EXTENSIONS = {".jpg", ".jpeg", ".png", ".gif", ".webp"}


def _student_name_from_image_filename(filename):
    base = os.path.splitext(os.path.basename(filename or ""))[0]
    cleaned = re.sub(r"[_\-]+", " ", base)
    cleaned = re.sub(r"\b(copy|passport|photo|image|student)\b", " ", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\s+", " ", cleaned).strip(" .")
    if not cleaned:
        return "", ""
    parts = [part.capitalize() for part in cleaned.split(" ") if part]
    if len(parts) == 1:
        return parts[0], "Student"
    return " ".join(parts[:-1]), parts[-1]


def _student_import_email(first_name, last_name, school, index=0):
    school_slug = (slugify(getattr(school, "schema_name", "") or getattr(school, "name", "") or "school") or "school").replace("_", "-")
    name_slug = slugify(f"{first_name} {last_name}") or f"student-{index + 1}"
    email = f"{name_slug}@{school_slug}.imported.local"
    suffix = 2
    while User.objects.filter(email__iexact=email).exclude(role="student", tenant=school).exists():
        email = f"{name_slug}-{suffix}@{school_slug}.imported.local"
        suffix += 1
    return email


def _create_or_update_student_from_image(user, school, image_file, filename, index=0):
    first_name, last_name = _student_name_from_image_filename(filename)
    if not first_name:
        raise ValueError(f"{filename or 'Image'} does not contain a readable student name.")
    image_file.seek(0)
    return _ensure_student_profile_for_tenant(
        user=user,
        email=_student_import_email(first_name, last_name, school, index),
        first_name=first_name,
        last_name=last_name,
        guardian_name="Guardian",
        guardian_phone="",
        guardian_relation="Guardian",
        profile_picture=image_file,
        student_password="StudentPass123",
        confirm_student_password="StudentPass123",
    )


def _apply_student_image_database_import(user, school, uploaded_file, summary):
    filename = uploaded_file.name or ""
    extension = os.path.splitext(filename)[1].lower()
    imported = []
    errors = []

    if extension in STUDENT_IMAGE_IMPORT_EXTENSIONS:
        try:
            uploaded_file.seek(0)
            content = ContentFile(uploaded_file.read(), name=os.path.basename(filename))
            imported.append(_create_or_update_student_from_image(user, school, content, filename))
        except Exception as exc:
            errors.append(str(exc))
        finally:
            uploaded_file.seek(0)
    elif extension == ".zip":
        uploaded_file.seek(0)
        with zipfile.ZipFile(uploaded_file) as archive:
            image_members = [
                item
                for item in archive.infolist()
                if not item.is_dir()
                and os.path.splitext(item.filename)[1].lower() in STUDENT_IMAGE_IMPORT_EXTENSIONS
                and not os.path.normpath(item.filename).replace("\\", "/").startswith("../")
            ]
            for index, item in enumerate(image_members):
                try:
                    content = ContentFile(archive.read(item), name=os.path.basename(item.filename))
                    imported.append(_create_or_update_student_from_image(user, school, content, item.filename, index))
                except Exception as exc:
                    errors.append(f"{item.filename}: {exc}")
        uploaded_file.seek(0)

    if imported or errors:
        summary["student_image_import"] = {
            "created_or_updated": len(imported),
            "students": [
                {
                    "student_id": profile.student_id,
                    "name": profile.user.get_full_name(),
                    "email": profile.user.email,
                }
                for profile in imported[:50]
            ],
        }
    return imported, errors


def _class_label(class_obj):
    section = (class_obj.section or "").strip()
    return f"{class_obj.name} - {section}" if section else class_obj.name

def _current_student_class(user):
    profile = StudentProfile.objects.select_related("current_class").filter(user=user).first()
    if profile:
        return profile.current_class
    return None


def _active_academic_year(user):
    return _scope_to_user_tenant(AcademicYear.objects.all(), user).filter(is_active=True).order_by("-start_date").first()


def _active_term(user):
    return _scope_to_user_tenant(Term.objects.select_related("academic_year"), user).filter(is_active=True).order_by("-start_date").first()


def _academic_year_payload(item):
    if not item:
        return None
    return {
        "id": item.id,
        "name": item.name,
        "start_date": item.start_date,
        "end_date": item.end_date,
        "is_active": item.is_active,
    }


def _term_payload(item):
    if not item:
        return None
    return {
        "id": item.id,
        "name": item.name,
        "start_date": item.start_date,
        "end_date": item.end_date,
        "is_active": item.is_active,
        "academic_year_id": item.academic_year_id,
    }


def _lesson_plan_payload(plan):
    return {
        "id": plan.id,
        "week_number": plan.week_number,
        "title": plan.title,
        "subject_id": plan.subject_id,
        "subject": plan.subject.name if plan.subject_id else "",
        "class_id": plan.class_group_id,
        "class_name": _class_label(plan.class_group) if plan.class_group_id else "",
        "teacher": plan.teacher.get_full_name() if plan.teacher_id else "",
        "objectives": plan.objectives,
        "activities": plan.activities,
        "resources": plan.resources,
        "assessment": plan.assessment,
        "notes": plan.notes,
        "status": plan.status,
        "term": plan.term.name if plan.term_id else "",
        "academic_year": plan.academic_year.name if plan.academic_year_id else "",
        "updated_at": plan.updated_at,
    }


def _school_fee_payload(fee):
    paid_amount = fee_paid_amount(fee)
    remaining_balance = max(fee.amount - paid_amount, Decimal("0.00"))
    if remaining_balance <= 0:
        payment_status = "paid"
    elif paid_amount > 0:
        payment_status = "partial"
    else:
        payment_status = fee.status
    return {
        "id": str(fee.id),
        "title": fee.title,
        "amount": fee.amount,
        "currency": fee.currency,
        "due_date": fee.due_date,
        "status": fee.status,
        "amount_paid": paid_amount,
        "remaining_balance": remaining_balance,
        "payment_status": payment_status,
    }


def _teacher_note_payload(note):
    return {
        "id": note.id,
        "title": note.title,
        "body": note.body,
        "pinned": note.pinned,
        "term": note.term.name if note.term_id else "",
        "academic_year": note.academic_year.name if note.academic_year_id else "",
        "updated_at": note.updated_at,
    }


def _exam_auto_submission_payload(attempt):
    warning_history = attempt.auto_submit_warning_history if isinstance(attempt.auto_submit_warning_history, list) else []
    activity_logs = attempt.auto_submit_activity_logs if isinstance(attempt.auto_submit_activity_logs, list) else []
    return {
        "id": attempt.id,
        "attempt_id": attempt.id,
        "exam_id": attempt.exam_id,
        "exam_title": attempt.exam.title,
        "student_name": attempt.student.get_full_name() or attempt.student.email,
        "student_email": attempt.student.email,
        "student_id": getattr(getattr(attempt.student, "student_profile", None), "student_id", ""),
        "class_name": _class_label(attempt.exam.class_group) if attempt.exam.class_group else "All classes",
        "subject": attempt.exam.subject.name if attempt.exam.subject else "General",
        "submitted_at": attempt.end_time,
        "reason_code": attempt.auto_submit_reason or "unknown",
        "reason": attempt.auto_submit_reason_display or attempt.auto_submit_reason or "Auto-submitted",
        "details": attempt.auto_submit_details,
        "warning_history": warning_history,
        "activity_logs": activity_logs,
        "warning_count": len(warning_history),
        "activity_count": len(activity_logs),
    }


def _notify_admins_exam_ready(exam, teacher):
    if not Notification or not getattr(teacher, "tenant_id", None):
        return

    admin_users = User.objects.filter(
        tenant=teacher.tenant,
        role__in=ADMIN_ROLES,
        is_active=True,
    ).exclude(id=teacher.id)[:20]
    teacher_name = teacher.get_full_name() or teacher.email
    notifications = [
        Notification(
            tenant=teacher.tenant,
            user=admin,
            title="Exam ready for publishing",
            message=f"{teacher_name} submitted {exam.title} for admin review and publishing.",
            notification_type="info",
            priority=3,
            channel="in_app",
            event_type="exam_ready_for_publishing",
            reference_id=exam.id,
            reference_model="exams.Exam",
            deep_link="/exams",
            is_delivered=True,
            delivered_at=timezone.now(),
        )
        for admin in admin_users
    ]
    if notifications:
        Notification.objects.bulk_create(notifications)


def _exam_pin_payload(pin, include_usage=False):
    exam = pin.exam
    usage_qs = pin.usages.select_related("student", "attempt").order_by("-created_at")
    successful_qs = usage_qs.filter(status=ExamPinUsage.STATUS_ACCEPTED)
    payload = {
        "id": pin.id,
        "exam_id": pin.exam_id,
        "exam_title": exam.title,
        "subject": exam.subject.name if exam.subject else "General",
        "subject_id": exam.subject_id,
        "class_name": _class_label(exam.class_group) if exam.class_group else "All classes",
        "class_id": exam.class_group_id,
        "exam_type": exam.exam_type.name if exam.exam_type else "Exam",
        "start_date": exam.start_date,
        "end_date": exam.end_date,
        "usage_policy": pin.usage_policy,
        "is_active": pin.is_active,
        "is_expired": pin.is_expired,
        "expires_at": pin.expires_at,
        "pin_preview": pin.pin_preview,
        "plain_pin": getattr(pin, "plain_pin", "") or "",
        "created_by": pin.created_by.get_full_name() or pin.created_by.email if pin.created_by else "",
        "created_at": pin.created_at,
        "last_regenerated_at": pin.last_regenerated_at,
        "reset_at": pin.reset_at,
        "usage_count": successful_qs.count(),
        "rejected_count": usage_qs.filter(status=ExamPinUsage.STATUS_REJECTED).count(),
    }
    if include_usage:
        payload["usage_history"] = [
            {
                "id": usage.id,
                "status": usage.status,
                "message": usage.message,
                "student": usage.student.get_full_name() or usage.student.email if usage.student else "",
                "student_email": usage.student.email if usage.student else "",
                "attempt_id": usage.attempt_id,
                "ip_address": usage.ip_address,
                "created_at": usage.created_at,
            }
            for usage in usage_qs[:80]
        ]
    return payload


def _to_bool(value, default=False):
    if value is None:
        return default
    if isinstance(value, bool):
        return value

    normalized = str(value).strip().lower()
    if normalized in {"1", "true", "yes", "y", "submitted", "complete", "completed"}:
        return True
    if normalized in {"0", "false", "no", "n", "pending", "incomplete"}:
        return False
    return default


def _profile_picture_url(request, user_obj):
    if not user_obj or not getattr(user_obj, "profile_picture", None):
        return ""

    try:
        url = user_obj.profile_picture.url
    except Exception:
        return ""

    if not url:
        return ""

    try:
        return request.build_absolute_uri(url) if request else url
    except Exception:
        return url


def _media_url(request, file_field):
    if not file_field:
        return ""
    try:
        url = file_field.url
    except Exception:
        return ""
    if not url:
        return ""
    try:
        return request.build_absolute_uri(url) if request else url
    except Exception:
        return url


def _school_payload(school, request=None):
    if not school:
        return {}
    return {
        "id": school.id,
        "name": school.name,
        "school_code": school.schema_name,
        "email": school.email or "",
        "phone": school.phone or "",
        "address": school.address or "",
        "logo": _media_url(request, school.logo),
        "favicon": _media_url(request, school.favicon),
        "currency": school.currency,
        "timezone": school.timezone,
    }


def _build_id_card_verify_url(request, token):
    ngrok_url = str(getattr(settings, "NGROK_PUBLIC_URL", "") or "").strip().rstrip("/")
    base_url = ngrok_url or get_frontend_base_url(request)
    verify_path = f"/id-cards/verify/?token={quote(token)}"
    if base_url:
        return f"{base_url}{verify_path}"
    return request.build_absolute_uri(verify_path)


def _enrollment_payload(enrollment, request=None):
    exams = list(enrollment.exams.all())
    return {
        "id": str(enrollment.id),
        "student_id": str(enrollment.student.id),
        "student_name": enrollment.student.user.get_full_name(),
        "student_email": enrollment.student.user.email,
        "student_profile_picture": _profile_picture_url(request, enrollment.student.user),
        "school": enrollment.school.name,
        "class_id": enrollment.assigned_class_id,
        "class_name": _class_label(enrollment.assigned_class) if enrollment.assigned_class else "Unassigned",
        "exam_count": len(exams),
        "exam_titles": [exam.title for exam in exams[:5]],
        "message_sent": bool(enrollment.enrollment_message_id),
        "created_by": enrollment.created_by.get_full_name() if enrollment.created_by else "System",
        "created_at": enrollment.created_at,
    }


def _student_payload(student_profile, request=None):
    student_user = student_profile.user
    return {
        "id": str(student_profile.id),
        "user_id": str(student_user.id),
        "name": student_user.get_full_name(),
        "first_name": student_user.first_name,
        "last_name": student_user.last_name,
        "email": student_user.email,
        "phone": student_user.phone,
        "gender": student_user.gender or "",
        "date_of_birth": student_user.date_of_birth,
        "is_active": student_user.is_active,
        "profile_picture": _profile_picture_url(request, student_user),
        "student_id": student_profile.student_id,
        "state_of_origin": student_profile.state_of_origin,
        "local_government": student_profile.local_government,
        "disability": student_profile.disability,
        "medical_records": student_profile.medical_conditions,
        "blood_group": student_profile.blood_group,
        "student_type": student_profile.student_type,
        "home_address": student_profile.home_address,
        "guardian_name": student_profile.guardian_name,
        "guardian_phone": student_profile.guardian_phone,
        "guardian_email": student_profile.guardian_email,
        "guardian_relation": student_profile.guardian_relation,
        "second_guardian_name": student_profile.second_guardian_name,
        "second_guardian_phone": student_profile.second_guardian_phone,
        "second_guardian_email": student_profile.second_guardian_email,
        "second_guardian_relation": student_profile.second_guardian_relation,
        "class_id": student_profile.current_class_id,
        "class_name": _class_label(student_profile.current_class) if student_profile.current_class else "Unassigned",
        "admission_date": student_profile.admission_date,
        "created_at": student_profile.created_at,
    }


def _is_terminal_testimonial_class(class_name):
    normalized = re.sub(r"[^A-Z0-9]", "", str(class_name or "").upper())
    return "JSS3" in normalized or "SSS3" in normalized


def _student_document_payload(student_profile, request=None):
    payload = _student_payload(student_profile, request=request)
    payload["admission_number"] = student_profile.admission_number
    payload["is_testimonial_eligible"] = _is_terminal_testimonial_class(payload.get("class_name"))
    return payload


def _testimonial_defaults_for_student(student_profile, request=None):
    current_class = _class_label(student_profile.current_class) if student_profile.current_class else ""
    subjects = (
        Subject.objects.filter(classes=student_profile.current_class)
        .order_by("name")
        .values_list("name", flat=True)
        if student_profile.current_class_id
        else []
    )
    return {
        "admission_number": student_profile.admission_number,
        "student_name": student_profile.user.get_full_name(),
        "date_of_birth": student_profile.user.date_of_birth,
        "gender": student_profile.user.gender or "",
        "state_of_origin": student_profile.state_of_origin,
        "local_government": student_profile.local_government,
        "admission_date": student_profile.admission_date,
        "class_of_admission": "",
        "date_of_leaving": date.today(),
        "class_of_leaving": current_class,
        "reason_for_leaving": "Completion of course",
        "educational_attainment": "Basic Education Certificate" if _is_terminal_testimonial_class(current_class) and "JSS" in current_class.upper() else "SSCE",
        "subjects_offered": ", ".join(subjects),
        "co_curricular_activities": "NIL",
        "prizes_and_honors": "NIL",
        "office_held": "NIL",
        "administrator_remarks": "He/she is well behaved.",
        "issue_date": date.today(),
        "principal_name": "",
    }


def _testimonial_payload(record, student_profile, request=None):
    defaults = _testimonial_defaults_for_student(student_profile, request=request)
    if record:
        defaults.update(
            {
                "class_of_admission": record.class_of_admission,
                "date_of_leaving": record.date_of_leaving,
                "class_of_leaving": record.class_of_leaving,
                "reason_for_leaving": record.reason_for_leaving,
                "educational_attainment": record.educational_attainment,
                "subjects_offered": record.subjects_offered,
                "co_curricular_activities": record.co_curricular_activities,
                "prizes_and_honors": record.prizes_and_honors,
                "office_held": record.office_held,
                "administrator_remarks": record.administrator_remarks,
                "issue_date": record.issue_date,
                "principal_name": record.principal_name,
            }
        )
    return defaults


def _transcript_payload(student_profile, request=None):
    scores_qs = (
        StudentSubjectScore.objects.select_related("subject", "class_group", "term__academic_year")
        .filter(student=student_profile)
        .exclude(approval_status=ResultBatch.REJECTED)
        .order_by("term__academic_year__start_date", "term__start_date", "subject__name")
    )

    history_map = {}
    total_score = 0.0
    total_max = 0.0
    for item in scores_qs:
        score = float(item.score or 0)
        max_score = float(item.max_score or 0)
        total_score += score
        total_max += max_score
        percentage = item.percentage
        grade = item.grade
        remark = item.performance_remark or item.remarks
        if percentage is not None and not grade:
            grade, remark = _grade_for_percentage(student_profile.user, percentage)

        year_name = item.term.academic_year.name if item.term_id and item.term.academic_year_id else "Unassigned Session"
        term_name = item.term.name if item.term_id else "Unassigned Term"
        class_name = _class_label(item.class_group) if item.class_group_id else _class_label(student_profile.current_class) if student_profile.current_class_id else ""
        group_key = (year_name, term_name, class_name)
        group = history_map.setdefault(
            group_key,
            {
                "session": year_name,
                "term": term_name,
                "class_name": class_name,
                "subjects": [],
                "total_score": 0.0,
                "total_max": 0.0,
            },
        )
        group["subjects"].append(
            {
                "id": str(item.id),
                "subject_id": item.subject_id,
                "subject": item.subject.name if item.subject_id else "",
                "score": score,
                "max_score": max_score,
                "percentage": percentage,
                "grade": grade,
                "remark": remark,
                "status": item.approval_status,
            }
        )
        group["total_score"] += score
        group["total_max"] += max_score

    history = []
    for group in history_map.values():
        average = round((group["total_score"] / group["total_max"]) * 100, 2) if group["total_max"] else 0
        grade, remark = _grade_for_percentage(student_profile.user, average) if average else ("", "")
        group["average"] = average
        group["grade"] = grade
        group["remark"] = remark
        history.append(group)

    cumulative = round((total_score / total_max) * 100, 2) if total_max else 0
    cumulative_grade, cumulative_remark = _grade_for_percentage(student_profile.user, cumulative) if cumulative else ("", "")
    class_history = []
    seen_classes = set()
    for item in scores_qs:
        if item.class_group_id:
            label = _class_label(item.class_group)
            if label not in seen_classes:
                seen_classes.add(label)
                class_history.append(label)
    if student_profile.current_class_id and _class_label(student_profile.current_class) not in seen_classes:
        class_history.append(_class_label(student_profile.current_class))

    return {
        "school": _school_payload(student_profile.user.tenant, request),
        "student": _student_document_payload(student_profile, request=request),
        "admission_date": student_profile.admission_date,
        "class_history": class_history,
        "session_history": sorted({group["session"] for group in history if group["session"]}),
        "term_records": history,
        "cumulative": {
            "total_score": round(total_score, 2),
            "total_max": round(total_max, 2),
            "average": cumulative,
            "grade": cumulative_grade,
            "remark": cumulative_remark,
            "subject_records": sum(len(group["subjects"]) for group in history),
        },
    }


def _teacher_payload(teacher_profile, request=None):
    user = teacher_profile.user
    return {
        "id": str(teacher_profile.id),
        "user_id": str(user.id),
        "name": user.get_full_name(),
        "first_name": user.first_name,
        "last_name": user.last_name,
        "email": user.email,
        "phone": user.phone,
        "gender": user.gender or "",
        "date_of_birth": user.date_of_birth,
        "profile_picture": _profile_picture_url(request, user),
        "employee_id": teacher_profile.employee_id,
        "specialization": teacher_profile.specialization,
        "qualification": teacher_profile.qualification,
        "subjects_text": teacher_profile.subjects_text,
        "employment_type": teacher_profile.employment_type,
        "years_of_experience": teacher_profile.years_of_experience,
        "hire_date": teacher_profile.hire_date,
        "monthly_salary": teacher_profile.monthly_salary,
        "emergency_contact_name": teacher_profile.emergency_contact_name,
        "emergency_contact_phone": teacher_profile.emergency_contact_phone,
        "emergency_contact_relation": teacher_profile.emergency_contact_relation,
        "cv": _media_url(request, teacher_profile.resume),
        "resume": _media_url(request, teacher_profile.resume),
        "certificates": _media_url(request, teacher_profile.certificates),
        "is_active": user.is_active,
        "created_at": teacher_profile.created_at,
        "subjects": [
            {
                "id": subject.id,
                "name": subject.name,
                "code": subject.code,
            }
            for subject in teacher_profile.subjects.all()[:50]
        ],
        "assigned_classes": [
            {
                "id": class_obj.id,
                "name": class_obj.name,
                "section": class_obj.section,
                "label": _class_label(class_obj),
            }
            for class_obj in teacher_profile.assigned_classes.all()[:50]
        ],
    }


def _school_identity_payload(tenant, request=None):
    if not tenant:
        return {"name": "SchoolDom", "code": "", "logo": ""}
    logo_url = ""
    logo = getattr(tenant, "logo", None)
    if logo:
        try:
            logo_url = logo.url
            if request:
                logo_url = request.build_absolute_uri(logo_url)
        except Exception:
            logo_url = ""
    return {
        "name": getattr(tenant, "name", "") or "SchoolDom",
        "code": getattr(tenant, "school_code", "") or getattr(tenant, "schema_name", "") or "",
        "logo": logo_url,
    }


def _id_card_student_payload(student_profile, request=None):
    payload = _student_payload(student_profile, request=request)
    return {
        "id": payload["id"],
        "person_type": "student",
        "display_type": "Student",
        "name": payload["name"],
        "first_name": payload["first_name"],
        "last_name": payload["last_name"],
        "unique_id": payload["student_id"],
        "profile_picture": payload["profile_picture"],
        "date_of_birth": payload["date_of_birth"],
        "gender": payload["gender"],
        "primary_label": payload["class_name"],
        "secondary_label": payload["student_type"] or "Learner",
        "admission_or_employment_date": payload["admission_date"],
        "email": payload["email"],
        "phone": payload["phone"],
        "guardian_name": payload["guardian_name"],
        "guardian_phone": payload["guardian_phone"],
        "blood_group": payload["blood_group"],
        "address": payload["home_address"],
        "is_active": payload["is_active"],
    }


def _id_card_teacher_payload(teacher_profile, request=None):
    payload = _teacher_payload(teacher_profile, request=request)
    class_labels = [item.get("label") for item in payload.get("assigned_classes", []) if item.get("label")]
    subject_labels = [item.get("name") for item in payload.get("subjects", []) if item.get("name")]
    return {
        "id": payload["id"],
        "person_type": "teacher",
        "display_type": "Teaching Staff",
        "name": payload["name"],
        "first_name": payload["first_name"],
        "last_name": payload["last_name"],
        "unique_id": payload["employee_id"],
        "profile_picture": payload["profile_picture"],
        "date_of_birth": getattr(teacher_profile.user, "date_of_birth", None),
        "gender": getattr(teacher_profile.user, "gender", "") or "",
        "primary_label": payload["specialization"] or "Teacher",
        "secondary_label": ", ".join(subject_labels[:3]) or payload["subjects_text"] or "Academic staff",
        "admission_or_employment_date": payload["hire_date"],
        "email": payload["email"],
        "phone": payload["phone"],
        "department": "Teaching",
        "assigned_classes": ", ".join(class_labels[:4]),
        "qualification": payload["qualification"],
        "employment_type": payload["employment_type"],
        "is_active": payload["is_active"],
    }


def _id_card_staff_payload(staff, request=None):
    linked_user = getattr(staff, "user", None)
    profile_picture = _profile_picture_url(request, linked_user) if linked_user else ""
    return {
        "id": str(staff.id),
        "person_type": "staff",
        "display_type": staff.get_staff_type_display() if hasattr(staff, "get_staff_type_display") else "Staff",
        "name": staff.full_name,
        "first_name": staff.first_name,
        "last_name": staff.last_name,
        "unique_id": staff.staff_code,
        "profile_picture": profile_picture,
        "date_of_birth": getattr(linked_user, "date_of_birth", None) if linked_user else None,
        "gender": staff.gender or (getattr(linked_user, "gender", "") if linked_user else ""),
        "primary_label": staff.role,
        "secondary_label": staff.department or staff.employment_type,
        "admission_or_employment_date": staff.hire_date,
        "email": staff.email,
        "phone": staff.phone,
        "department": staff.department,
        "employment_type": staff.employment_type,
        "employment_status": staff.employment_status,
        "address": staff.address,
        "is_active": staff.employment_status == "active",
    }


def _public_id_card_verification_person(person):
    return {
        "person_type": person.get("person_type"),
        "display_type": person.get("display_type") or "ID Card",
        "name": person.get("name") or "",
        "unique_id": person.get("unique_id") or "",
        "email": person.get("email") or "",
        "is_active": bool(person.get("is_active")),
    }


def _id_card_challenge_payload(person):
    return {
        "person_type": person.get("person_type"),
        "display_type": person.get("display_type") or "ID Card",
        "id_label": "Student ID" if person.get("person_type") == "student" else "Staff ID",
    }


def _id_card_credentials_match(person, email, unique_id):
    expected_email = str(person.get("email") or "").strip().lower()
    expected_id = str(person.get("unique_id") or "").strip().lower()
    return bool(expected_email and expected_id and email.strip().lower() == expected_email and unique_id.strip().lower() == expected_id)


def _resolve_id_card_person(user, person_type, person_id, request=None):
    tenant = getattr(user, "tenant", None)
    normalized_type = str(person_type or "").strip().lower()
    normalized_id = str(person_id or "").strip()
    if not tenant or not normalized_id:
        return None
    if normalized_type == "student":
        student = get_object_or_404(
            StudentProfile.objects.select_related("user", "current_class").filter(user__tenant=tenant),
            id=normalized_id,
        )
        return _id_card_student_payload(student, request=request)
    if normalized_type == "teacher":
        teacher = get_object_or_404(
            TeacherProfile.objects.select_related("user").prefetch_related("subjects", "assigned_classes").filter(user__tenant=tenant),
            id=normalized_id,
        )
        return _id_card_teacher_payload(teacher, request=request)
    if normalized_type == "staff" and StaffProfile is not None:
        staff = get_object_or_404(StaffProfile.objects.select_related("user").filter(tenant=tenant), id=normalized_id)
        return _id_card_staff_payload(staff, request=request)
    return None


def _resolve_id_card_person_for_tenant(tenant, person_type, person_id, request=None):
    normalized_type = str(person_type or "").strip().lower()
    normalized_id = str(person_id or "").strip()
    if not tenant or not normalized_id:
        return None
    if normalized_type == "student":
        student = get_object_or_404(
            StudentProfile.objects.select_related("user", "current_class").filter(user__tenant=tenant),
            id=normalized_id,
        )
        return _id_card_student_payload(student, request=request)
    if normalized_type == "teacher":
        teacher = get_object_or_404(
            TeacherProfile.objects.select_related("user").prefetch_related("subjects", "assigned_classes").filter(user__tenant=tenant),
            id=normalized_id,
        )
        return _id_card_teacher_payload(teacher, request=request)
    if normalized_type == "staff" and StaffProfile is not None:
        staff = get_object_or_404(StaffProfile.objects.select_related("user").filter(tenant=tenant), id=normalized_id)
        return _id_card_staff_payload(staff, request=request)
    return None


def _assessment_type_for_exam(exam):
    exam_type_name = str(getattr(getattr(exam, "exam_type", None), "name", "") or "").strip().lower()
    if exam_type_name == "test":
        return "test"
    return "exam"


def _subjects_taught_for_teacher(user, limit=12):
    if not user:
        return []

    names = set()
    profile = TeacherProfile.objects.filter(user=user).prefetch_related("subjects").first()
    if profile:
        names.update(subject.name for subject in profile.subjects.all())

    subject_names = (
        _scope_to_user_tenant(Exam.objects.select_related("subject"), user)
        .filter(teacher=user, subject__isnull=False)
        .values_list("subject__name", flat=True)
        .distinct()
    )
    names.update(name for name in subject_names[:limit] if str(name or "").strip())
    return list(names)[:limit]


def _validate_teacher_password(teacher_password, confirm_teacher_password):
    password = str(teacher_password or "")
    confirm = str(confirm_teacher_password or "")

    if not password:
        raise ValueError("teacher_password is required for new teacher accounts.")

    if password != confirm:
        raise ValueError("teacher_password and confirm_teacher_password do not match.")

    if len(password) < 8:
        raise ValueError("teacher_password must be at least 8 characters.")

    if not re.search(r"[A-Z]", password):
        raise ValueError("teacher_password must include at least one uppercase letter.")

    if not re.search(r"[a-z]", password):
        raise ValueError("teacher_password must include at least one lowercase letter.")

    if not re.search(r"[0-9]", password):
        raise ValueError("teacher_password must include at least one number.")

    return password


def _validate_student_password(student_password, confirm_student_password):
    password = str(student_password or "")
    confirm = str(confirm_student_password or "")

    if not password:
        raise ValueError("student_password is required for new student accounts.")

    if password != confirm:
        raise ValueError("student_password and confirm_student_password do not match.")

    if len(password) < 8:
        raise ValueError("student_password must be at least 8 characters.")

    if not re.search(r"[A-Z]", password):
        raise ValueError("student_password must include at least one uppercase letter.")

    if not re.search(r"[a-z]", password):
        raise ValueError("student_password must include at least one lowercase letter.")

    if not re.search(r"[0-9]", password):
        raise ValueError("student_password must include at least one number.")

    return password


def _positive_duration_minutes(value):
    try:
        duration = int(value)
    except (TypeError, ValueError):
        return 0
    return duration if duration > 0 else 0


def _ensure_student_profile_for_tenant(
    user,
    email,
    first_name,
    last_name,
    guardian_name,
    guardian_phone,
    guardian_email="",
    guardian_relation="Guardian",
    second_guardian_name="",
    second_guardian_phone="",
    second_guardian_email="",
    second_guardian_relation="",
    state_of_origin="",
    local_government="",
    disability="no",
    medical_records="",
    blood_group="",
    student_type="",
    home_address="",
    profile_picture=None,
    student_password=None,
    confirm_student_password=None,
):
    student_user = User.objects.filter(email__iexact=email).first()
    if student_user and student_user.role != "student":
        raise ValueError("This email already exists for a non-student account.")

    if student_user and student_user.tenant_id != user.tenant_id:
        raise ValueError("Student email belongs to another school.")

    if not student_user:
        if not first_name or not last_name:
            raise ValueError("first_name and last_name are required when creating a new student.")

        student_user = User(
            email=email,
            first_name=first_name,
            last_name=last_name,
            role="student",
            tenant=user.tenant,
            is_active=True,
            is_verified=True,
            admin_otp_purpose='',  # Default value for admin OTP purpose
        )
        if profile_picture:
            student_user.profile_picture = profile_picture
        validated_password = _validate_student_password(student_password, confirm_student_password)
        student_user.set_password(validated_password)
        student_user.save()
    else:
        update_fields = []
        if profile_picture:
            student_user.profile_picture = profile_picture
            update_fields.append("profile_picture")

        if student_password or confirm_student_password:
            validated_password = _validate_student_password(student_password, confirm_student_password)
            student_user.set_password(validated_password)
            update_fields.append("password")

        if update_fields:
            student_user.save(update_fields=update_fields)

    profile = StudentProfile.objects.filter(user=student_user).first()
    if profile:
        return profile

    if not guardian_name:
        raise ValueError("guardian_name is required when creating a new student profile.")

    stamp = timezone.now().strftime("%Y%m%d%H%M%S")
    base = slugify(student_user.email.split("@")[0]).replace("-", "").upper() or student_user.id.hex
    student_code = generate_short_student_id(f"{base}{student_user.id.hex}", user.tenant)
    admission = f"ADM{stamp}{student_user.id.hex[:4].upper()}"

    return StudentProfile.objects.create(
        user=student_user,
        student_id=student_code,
        admission_number=admission,
        admission_date=timezone.now().date(),
        guardian_name=guardian_name,
        guardian_phone=guardian_phone or "",
        guardian_email=guardian_email or "",
        guardian_relation=guardian_relation or "Guardian",
        second_guardian_name=second_guardian_name or "",
        second_guardian_phone=second_guardian_phone or "",
        second_guardian_email=second_guardian_email or "",
        second_guardian_relation=second_guardian_relation or "",
        state_of_origin=state_of_origin or "",
        local_government=local_government or "",
        disability=disability or "no",
        medical_conditions=medical_records or "",
        blood_group=blood_group or "",
        student_type=student_type or "",
        home_address=home_address or "",
    )


def _ensure_teacher_user_for_tenant(
    user,
    email,
    first_name,
    last_name,
    phone,
    profile_picture=None,
    teacher_password=None,
    confirm_teacher_password=None,
):
    teacher_user = User.objects.filter(email__iexact=email).first()
    if teacher_user and teacher_user.role != "teacher":
        raise ValueError("This email already exists for a non-teacher account.")

    if teacher_user and teacher_user.tenant_id != user.tenant_id:
        raise ValueError("Teacher email belongs to another school.")

    if not teacher_user:
        if not first_name or not last_name:
            raise ValueError("first_name and last_name are required when creating a new teacher.")

        teacher_user = User(
            email=email,
            first_name=first_name,
            last_name=last_name,
            role="teacher",
            tenant=user.tenant,
            is_active=True,
            is_verified=True,
            phone=phone or "",
            admin_otp_purpose='',  # Default value for admin OTP purpose
        )
        if profile_picture:
            teacher_user.profile_picture = profile_picture
        if teacher_password is None or confirm_teacher_password is None:
            teacher_user.set_password(User.objects.make_random_password())
        else:
            validated_password = _validate_teacher_password(teacher_password, confirm_teacher_password)
            teacher_user.set_password(validated_password)
        teacher_user.save()
        return teacher_user

    update_fields = []
    if teacher_password or confirm_teacher_password:
        validated_password = _validate_teacher_password(teacher_password, confirm_teacher_password)
        teacher_user.set_password(validated_password)
        update_fields.append("password")
    if first_name and teacher_user.first_name != first_name:
        teacher_user.first_name = first_name
        update_fields.append("first_name")
    if last_name and teacher_user.last_name != last_name:
        teacher_user.last_name = last_name
        update_fields.append("last_name")
    if phone and teacher_user.phone != phone:
        teacher_user.phone = phone
        update_fields.append("phone")
    if profile_picture:
        teacher_user.profile_picture = profile_picture
        update_fields.append("profile_picture")

    if update_fields:
        teacher_user.save(update_fields=update_fields)

    return teacher_user


def _parse_id_list(raw_value):
    """
    Accepts lists, tuples, QueryDict lists, or comma-separated strings and returns a list of IDs.
    """
    if raw_value is None:
        return []
    if isinstance(raw_value, (list, tuple)):
        return [str(item).strip() for item in raw_value if str(item).strip()]
    if isinstance(raw_value, str):
        return [item.strip() for item in raw_value.split(",") if item.strip()]
    try:
        return [str(raw_value).strip()]
    except Exception:
        return []


def _parse_money_amount(raw_value, field_name="amount"):
    try:
        amount = Decimal(str(raw_value if raw_value not in (None, "") else "0"))
        if amount < 0:
            raise ValueError
        return amount.quantize(Decimal("0.01"))
    except (InvalidOperation, ValueError, TypeError):
        raise ValueError(f"{field_name} must be a valid amount.")


def _decimal_from_request(value, field_name):
    try:
        return Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        raise ValueError(f"{field_name} must be a valid number.")


def _attendance_location_payload(request):
    payload = request.data.get("location") or {}
    latitude = payload.get("latitude", request.data.get("latitude"))
    longitude = payload.get("longitude", request.data.get("longitude"))
    accuracy = payload.get("accuracy", request.data.get("accuracy"))

    if latitude in (None, "") or longitude in (None, ""):
        raise ValueError("Enable device location services and allow GPS access before marking attendance.")

    latitude = _decimal_from_request(latitude, "Latitude")
    longitude = _decimal_from_request(longitude, "Longitude")
    if latitude < Decimal("-90") or latitude > Decimal("90"):
        raise ValueError("Latitude is outside the valid GPS range.")
    if longitude < Decimal("-180") or longitude > Decimal("180"):
        raise ValueError("Longitude is outside the valid GPS range.")

    accuracy_value = None
    if accuracy not in (None, ""):
        accuracy_value = _decimal_from_request(accuracy, "Accuracy")
        if accuracy_value < 0:
            raise ValueError("GPS accuracy cannot be negative.")

    address = str(payload.get("address") or request.data.get("address") or "").strip()
    if not address:
        address = f"{latitude}, {longitude}"

    device_info = str(
        payload.get("device_info")
        or request.data.get("device_info")
        or request.data.get("client_device_info")
        or request.META.get("HTTP_USER_AGENT", "")
        or ""
    ).strip()

    return {
        "latitude": latitude,
        "longitude": longitude,
        "accuracy": accuracy_value,
        "address": address[:2000],
        "device_info": device_info[:2000],
    }


def _subject_payload(subject):
    return {"id": subject.id, "name": subject.name, "code": subject.code}


def _class_payload(class_obj, student_count=None):
    payload = {
        "id": class_obj.id,
        "name": class_obj.name,
        "section": class_obj.section or "",
        "label": _class_label(class_obj),
        "subjects": [_subject_payload(subject) for subject in class_obj.subjects.all()],
        "subject_ids": [subject.id for subject in class_obj.subjects.all()],
    }
    if student_count is not None:
        payload["student_count"] = student_count
    return payload


def _promotion_payload(promotion):
    return {
        "id": promotion.id,
        "student_id": str(promotion.student_id),
        "student_name": promotion.student.user.get_full_name() if promotion.student_id else "",
        "student_code": promotion.student.student_id if promotion.student_id else "",
        "from_class_id": promotion.from_class_id,
        "from_class_name": _class_label(promotion.from_class) if promotion.from_class else "Unassigned",
        "to_class_id": promotion.to_class_id,
        "to_class_name": _class_label(promotion.to_class) if promotion.to_class else "Unassigned",
        "from_term_id": promotion.from_term_id,
        "from_term_name": promotion.from_term.name if promotion.from_term else "",
        "to_term_id": promotion.to_term_id,
        "to_term_name": promotion.to_term.name if promotion.to_term else "",
        "from_academic_year_id": promotion.from_academic_year_id,
        "from_academic_year_name": promotion.from_academic_year.name if promotion.from_academic_year else "",
        "to_academic_year_id": promotion.to_academic_year_id,
        "to_academic_year_name": promotion.to_academic_year.name if promotion.to_academic_year else "",
        "scope": promotion.scope,
        "scope_value": promotion.scope_value,
        "batch_reference": promotion.batch_reference,
        "promoted_by": promotion.promoted_by.get_full_name() if promotion.promoted_by else "System",
        "created_at": promotion.created_at,
    }


def _promotion_scope_students(user, payload):
    scope = str(payload.get("scope") or StudentClassPromotion.SCOPE_CLASS).strip().lower()
    if scope not in {choice[0] for choice in StudentClassPromotion.SCOPE_CHOICES}:
        raise ValueError("Choose a valid promotion scope.")

    students = StudentProfile.objects.select_related("user", "current_class", "current_term").filter(
        user__tenant=user.tenant,
        user__is_active=True,
    )
    scope_value = ""
    source_class = None
    source_term = None

    source_class_id = payload.get("source_class_id")
    if source_class_id not in (None, ""):
        source_class = get_object_or_404(_scope_to_user_tenant(Class.objects.all(), user), id=source_class_id)
        students = students.filter(current_class=source_class)
        scope_value = _class_label(source_class)

    source_term_id = payload.get("source_term_id")
    if source_term_id not in (None, ""):
        source_term = get_object_or_404(_scope_to_user_tenant(Term.objects.select_related("academic_year"), user), id=source_term_id)
        students = students.filter(current_term=source_term)

    if scope == StudentClassPromotion.SCOPE_CLASS and not source_class:
        raise ValueError("Select the class you want to promote from.")

    if scope == StudentClassPromotion.SCOPE_DEPARTMENT:
        department = str(payload.get("source_department") or payload.get("scope_value") or "").strip()
        if not department:
            raise ValueError("Enter or select a department/section.")
        students = students.filter(current_class__section__iexact=department)
        scope_value = department

    if scope == StudentClassPromotion.SCOPE_LEVEL:
        level = str(payload.get("source_level") or payload.get("scope_value") or "").strip()
        if not level:
            raise ValueError("Enter an academic level to match.")
        students = students.filter(current_class__name__icontains=level)
        scope_value = level

    if scope == StudentClassPromotion.SCOPE_SESSION:
        if not source_term:
            raise ValueError("Select a current term/session for session-wide promotion.")
        scope_value = source_term.name

    return scope, scope_value, source_class, source_term, students.order_by("user__first_name", "user__last_name")


def _build_promotion_preview(user, payload):
    scope, scope_value, source_class, source_term, students_qs = _promotion_scope_students(user, payload)
    target_class_id = payload.get("target_class_id")
    if target_class_id in (None, ""):
        raise ValueError("Select the destination class.")
    target_class = get_object_or_404(_scope_to_user_tenant(Class.objects.all(), user), id=target_class_id)

    target_term = None
    target_term_id = payload.get("target_term_id")
    if target_term_id not in (None, ""):
        target_term = get_object_or_404(_scope_to_user_tenant(Term.objects.select_related("academic_year"), user), id=target_term_id)
    else:
        target_term = _active_term(user)

    source_term = source_term or _active_term(user)
    source_year = source_term.academic_year if source_term and source_term.academic_year_id else _active_academic_year(user)
    target_year = target_term.academic_year if target_term and target_term.academic_year_id else source_year

    if source_class and source_class.id == target_class.id:
        raise ValueError("Source and destination class cannot be the same.")

    existing_qs = StudentClassPromotion.objects.filter(
        tenant=_tenant_for_model(StudentClassPromotion, user),
        student_id__in=students_qs.values_list("id", flat=True),
        to_class=target_class,
        from_term=source_term,
        to_term=target_term,
        from_academic_year=source_year,
        to_academic_year=target_year,
    )
    if source_class:
        existing_qs = existing_qs.filter(from_class=source_class)
    existing = set(existing_qs.values_list("student_id", flat=True))

    eligible = []
    blocked = []
    for student in students_qs[:1000]:
        reason = ""
        if student.current_class_id == target_class.id:
            reason = "Already in destination class"
        elif student.id in existing:
            reason = "Already promoted for this class/session"

        item = {
            "id": str(student.id),
            "name": student.user.get_full_name(),
            "student_id": student.student_id,
            "email": student.user.email,
            "from_class_id": student.current_class_id,
            "from_class_name": _class_label(student.current_class) if student.current_class else "Unassigned",
            "to_class_id": target_class.id,
            "to_class_name": _class_label(target_class),
            "current_term_id": student.current_term_id,
            "current_term_name": student.current_term.name if student.current_term else "",
        }
        if reason:
            blocked.append({**item, "reason": reason})
        else:
            eligible.append(item)

    return {
        "scope": scope,
        "scope_value": scope_value,
        "source_class": _class_payload(source_class) if source_class else None,
        "target_class": _class_payload(target_class),
        "source_term": _term_payload(source_term),
        "target_term": _term_payload(target_term),
        "source_academic_year": _academic_year_payload(source_year),
        "target_academic_year": _academic_year_payload(target_year),
        "summary": {
            "matched_students": students_qs.count(),
            "eligible_students": len(eligible),
            "blocked_students": len(blocked),
            "already_in_target": len([item for item in blocked if item["reason"] == "Already in destination class"]),
            "duplicate_promotions": len([item for item in blocked if item["reason"] == "Already promoted for this class/session"]),
        },
        "students": eligible[:100],
        "blocked_students": blocked[:100],
    }


def _teacher_assigned_classes(user):
    teacher_profile = TeacherProfile.objects.filter(user=user).prefetch_related("assigned_classes").first()
    if not teacher_profile:
        return Class.objects.none()
    return _scope_to_user_tenant(teacher_profile.assigned_classes.all(), user)


def _sync_teacher_hr_salary(teacher_profile):
    if StaffProfile is None:
        return
    staff = StaffProfile.objects.filter(tenant=teacher_profile.user.tenant, user=teacher_profile.user).first()
    if not staff:
        return
    update_fields = []
    if staff.base_salary != teacher_profile.monthly_salary:
        staff.base_salary = teacher_profile.monthly_salary
        update_fields.append("base_salary")
    if staff.staff_type != StaffProfile.TEACHING:
        staff.staff_type = StaffProfile.TEACHING
        update_fields.append("staff_type")
    if update_fields:
        staff.save(update_fields=sorted(set(update_fields + ["updated_at"])))


def _message_recipient_queryset_for_user(user):
    base = User.objects.filter(tenant=user.tenant, is_active=True).exclude(id=user.id)
    role = getattr(user, "role", "")
    if role == "student":
        return base.filter(role__in=["teacher", "school_admin", "principal", "super_admin"])
    if role == "teacher":
        student_user_ids = StudentProfile.objects.filter(
            user__tenant=user.tenant,
            user__is_active=True,
        ).values_list("user_id", flat=True)
        return base.filter(Q(role__in=["school_admin", "principal", "super_admin"]) | Q(id__in=student_user_ids))
    return base


def _is_allowed_message_recipient(sender, recipient):
    if _can_manage_school_settings(sender):
        return True
    return _message_recipient_queryset_for_user(sender).filter(id=recipient.id).exists()


def _normalize_sms_phone(value):
    digits = re.sub(r"\D+", "", str(value or ""))
    if not digits:
        return ""
    if digits.startswith("00"):
        digits = digits[2:]
    if len(digits) == 11 and digits.startswith("0"):
        return f"234{digits[1:]}"
    if len(digits) == 10:
        return f"234{digits}"
    return digits


def _guardian_sms_contacts_for_school(school):
    if not school:
        return []

    contacts = []
    seen = set()
    profiles = (
        StudentProfile.objects.select_related("user", "current_class")
        .filter(user__tenant=school, user__is_active=True)
        .order_by("user__first_name", "user__last_name", "student_id")
    )
    for profile in profiles:
        student_name = profile.user.get_full_name() or profile.student_id
        for slot, name_attr, phone_attr, relation_attr in (
            ("primary", "guardian_name", "guardian_phone", "guardian_relation"),
            ("secondary", "second_guardian_name", "second_guardian_phone", "second_guardian_relation"),
        ):
            phone = _normalize_sms_phone(getattr(profile, phone_attr, ""))
            if not phone or phone in seen:
                continue
            seen.add(phone)
            guardian_name = str(getattr(profile, name_attr, "") or "").strip()
            relation = str(getattr(profile, relation_attr, "") or "").strip()
            contacts.append(
                {
                    "id": f"{profile.id}:{slot}",
                    "name": guardian_name or relation or "Guardian",
                    "phone": phone,
                    "raw_phone": getattr(profile, phone_attr, "") or "",
                    "relation": relation,
                    "student_id": str(profile.id),
                    "student_code": profile.student_id,
                    "student_name": student_name,
                    "class_name": _class_label(profile.current_class) if profile.current_class else "Unassigned",
                    "source": slot,
                }
            )
    return contacts


def _kudisms_config_for_school(school):
    config = None
    if SMSConfiguration and school:
        try:
            config = getattr(school, "sms_config", None)
        except Exception:
            config = None

    token = (
        str(getattr(config, "api_key", "") or "").strip()
        or str(getattr(settings, "KUDISMS_TOKEN", "") or os.environ.get("KUDISMS_TOKEN", "")).strip()
    )
    sender_id = (
        str(getattr(config, "sender_id", "") or "").strip()
        or str(getattr(settings, "KUDISMS_SENDER_ID", "") or os.environ.get("KUDISMS_SENDER_ID", "")).strip()
        or "neo"
    )
    gateway = str(getattr(settings, "KUDISMS_GATEWAY", "") or os.environ.get("KUDISMS_GATEWAY", "") or "2").strip()
    is_active = bool(getattr(config, "is_active", False)) if config else bool(token)
    if config and getattr(config, "provider", "") and getattr(config, "provider", "") != "custom":
        is_active = False

    return {
        "token": token,
        "sender_id": sender_id,
        "gateway": gateway,
        "is_active": is_active,
    }


def _send_kudisms_bulk_sms(school, phone_numbers, message):
    config = _kudisms_config_for_school(school)
    if not config["token"] or not config["is_active"]:
        raise ValueError("Bulk SMS is not configured. Add a Custom SMS configuration with your KudiSMS token.")

    recipients = []
    seen = set()
    for phone in phone_numbers:
        normalized = _normalize_sms_phone(phone)
        if normalized and normalized not in seen:
            seen.add(normalized)
            recipients.append(normalized)

    if not recipients:
        raise ValueError("Add at least one valid guardian phone number.")

    response = requests.get(
        "https://my.kudisms.net/api/sms",
        params={
            "token": config["token"],
            "senderID": config["sender_id"],
            "recipients": ",".join(recipients),
            "message": message,
            "gateway": config["gateway"],
        },
        timeout=20,
    )
    if response.status_code >= 400:
        raise ValueError(f"KudiSMS rejected the request with status {response.status_code}.")

    return {
        "recipient_count": len(recipients),
        "recipients": recipients,
        "provider_response": response.text[:500],
        "sender_id": config["sender_id"],
    }


MESSAGE_ATTACHMENT_MAX_FILES = 5
MESSAGE_ATTACHMENT_MAX_BYTES = 10 * 1024 * 1024


def _message_attachment_url(path, request=None):
    if not path:
        return ""
    try:
        url = default_storage.url(path)
    except Exception:
        media_url = getattr(settings, "MEDIA_URL", "/media/")
        url = f"{media_url.rstrip('/')}/{path.lstrip('/')}"
    return request.build_absolute_uri(url) if request else url


def _message_attachment_payload(item, request=None):
    if not isinstance(item, dict):
        return None
    payload = {
        "name": item.get("name") or item.get("filename") or "Attachment",
        "content_type": item.get("content_type") or "",
        "size": item.get("size") or 0,
        "url": item.get("url") or _message_attachment_url(item.get("path"), request=request),
    }
    return payload if payload["url"] else None


def _message_payload(message, request=None, viewer=None):
    viewer_id = getattr(viewer, "id", None)
    outgoing = viewer_id and message.sender_id == viewer_id
    attachments = [
        payload
        for payload in (_message_attachment_payload(item, request=request) for item in (message.attachments or []))
        if payload
    ]
    return {
        "id": str(message.id),
        "from": message.sender.get_full_name(),
        "from_name": message.sender.get_full_name(),
        "from_email": message.sender.email,
        "from_role": message.sender.role,
        "to": message.recipient.get_full_name(),
        "to_name": message.recipient.get_full_name(),
        "to_email": message.recipient.email,
        "to_role": message.recipient.role,
        "direction": "outgoing" if outgoing else "incoming",
        "subject": message.subject or "",
        "body": message.body,
        "attachments": attachments,
        "is_read": message.is_read,
        "created_at": message.created_at,
    }


def _tenant_notifications_for_user(user):
    if not Notification or not getattr(user, "tenant_id", None):
        return Notification.objects.none() if Notification else []
    return Notification.objects.filter(user=user, tenant=user.tenant)


def _tenant_inbox_for_user(user):
    if not InAppMessage or not getattr(user, "tenant_id", None):
        return InAppMessage.objects.none() if InAppMessage else []
    return InAppMessage.objects.filter(recipient=user, tenant=user.tenant, deleted_by_recipient=False)


def _collect_message_attachments(request):
    uploaded_files = []
    for field_name in ("attachments", "attachment", "files"):
        uploaded_files.extend(request.FILES.getlist(field_name))
    if len(uploaded_files) > MESSAGE_ATTACHMENT_MAX_FILES:
        raise ValueError(f"You can attach up to {MESSAGE_ATTACHMENT_MAX_FILES} files per message.")

    attachments = []
    for uploaded_file in uploaded_files:
        if uploaded_file.size > MESSAGE_ATTACHMENT_MAX_BYTES:
            raise ValueError(f"{uploaded_file.name} is larger than 10 MB.")
        original_name = os.path.basename(uploaded_file.name or "attachment")
        saved_path = default_storage.save(
            f"message_attachments/{timezone.now():%Y/%m}/{uuid.uuid4().hex}_{original_name}",
            uploaded_file,
        )
        attachments.append(
            {
                "name": original_name,
                "path": saved_path,
                "url": _message_attachment_url(saved_path, request=request),
                "size": uploaded_file.size,
                "content_type": getattr(uploaded_file, "content_type", "") or "",
            }
        )
    return attachments


def _ensure_default_grade_scales(user):
    tenant_obj = _tenant_for_model(GradeScale, user)
    if not tenant_obj:
        return GradeScale.objects.none()
    defaults = [
        ("A", 70, 100, "Excellent"),
        ("B", 60, 69.99, "Very good"),
        ("C", 50, 59.99, "Good"),
        ("D", 45, 49.99, "Fair"),
        ("E", 40, 44.99, "Pass"),
        ("F", 0, 39.99, "Needs improvement"),
    ]
    for letter, min_value, max_value, remark in defaults:
        GradeScale.objects.get_or_create(
            tenant=tenant_obj,
            letter=letter,
            defaults={"min_percentage": min_value, "max_percentage": max_value, "remark": remark},
        )
    return GradeScale.objects.filter(tenant=tenant_obj, is_active=True)


def _grade_for_percentage(user, percentage):
    grade = _ensure_default_grade_scales(user).filter(
        min_percentage__lte=percentage,
        max_percentage__gte=percentage,
        is_active=True,
    ).order_by("-min_percentage").first()
    if not grade:
        return "", ""
    return grade.letter, grade.remark


def _can_manage_school_settings(user):
    return user.role in {"school_admin", "principal", "super_admin"}


def _normalize_school_code(raw_value):
    normalized = slugify(str(raw_value or "")).replace("-", "_")
    normalized = re.sub(r"[^a-z0-9_]", "_", normalized)
    normalized = re.sub(r"_+", "_", normalized).strip("_")
    if not normalized:
        normalized = "school"
    if normalized[0].isdigit():
        normalized = f"sch_{normalized}"
    return normalized[:63]


def _unique_school_code_for_name(school, name):
    base = _normalize_school_code(name)
    candidate = base
    suffix = 1
    while (
        SchoolTenant.objects.filter(schema_name__iexact=candidate).exclude(id=school.id).exists()
        or Tenant.objects.filter(slug__iexact=candidate).exclude(slug__iexact=school.schema_name).exists()
    ):
        suffix += 1
        suffix_text = f"_{suffix}"
        candidate = f"{base[:63 - len(suffix_text)]}{suffix_text}"
    return candidate


def _unique_school_domain(schema_name, school):
    base = f"{schema_name}.school.local"
    candidate = base
    suffix = 1
    while Domain.objects.filter(domain__iexact=candidate).exclude(tenant=school).exists():
        suffix += 1
        candidate = f"{schema_name}-{suffix}.school.local"
    return candidate


def _random_school_identifier(prefix, school, exists):
    letters = school_code_letters(school)
    candidate = f"{prefix}{letters}{random_code_digits()}"
    while exists(candidate):
        candidate = f"{prefix}{letters}{random_code_digits()}"
    return candidate


def _regenerate_school_linked_codes(school):
    students = list(StudentProfile.objects.select_related("user").filter(user__tenant=school).order_by("created_at", "id"))
    teachers = list(TeacherProfile.objects.select_related("user").filter(user__tenant=school).order_by("created_at", "id"))
    staff_records = list(StaffProfile.objects.select_related("user", "tenant").filter(tenant=school).order_by("created_at", "id")) if StaffProfile is not None else []

    for index, student in enumerate(students, start=1):
        student.student_id = f"TMPST{index:06d}"
        student.save(update_fields=["student_id"])

    for index, teacher in enumerate(teachers, start=1):
        teacher.employee_id = f"TMPTC{index:06d}"
        teacher.save(update_fields=["employee_id"])

    for index, staff in enumerate(staff_records, start=1):
        staff.staff_code = f"TMPSF{index:06d}"
        staff.save(update_fields=["staff_code"])

    references = list(StudentPaymentReference.objects.select_related("student").filter(student__user__tenant=school).order_by("created_at", "id"))
    for index, reference in enumerate(references, start=1):
        reference.code = f"TMPRF{index:06d}"
        reference.save(update_fields=["code"])

    used_student_codes = set()
    student_codes_by_id = {}
    for student in students:
        student.student_id = _random_school_identifier(
            "ST",
            school,
            lambda value: value in used_student_codes or StudentProfile.objects.filter(student_id__iexact=value).exclude(id=student.id).exists(),
        )
        used_student_codes.add(student.student_id)
        student_codes_by_id[str(student.id)] = student.student_id
        student.save(update_fields=["student_id", "updated_at"])

    teacher_codes_by_user = {}
    used_teacher_codes = set()
    for teacher in teachers:
        teacher.employee_id = _random_school_identifier(
            "TC",
            school,
            lambda value: value in used_teacher_codes or TeacherProfile.objects.filter(employee_id__iexact=value).exclude(id=teacher.id).exists(),
        )
        used_teacher_codes.add(teacher.employee_id)
        teacher_codes_by_user[str(teacher.user_id)] = teacher.employee_id
        teacher.save(update_fields=["employee_id", "updated_at"])

    used_staff_codes = set()
    for staff in staff_records:
        linked_teacher_code = teacher_codes_by_user.get(str(staff.user_id))
        if staff.staff_type == StaffProfile.TEACHING and linked_teacher_code and linked_teacher_code not in used_staff_codes:
            next_code = linked_teacher_code
        else:
            prefix = "NS" if staff.staff_type == StaffProfile.NON_TEACHING else "TC"
            next_code = _random_school_identifier(
                prefix,
                school,
                lambda value: value in used_staff_codes or StaffProfile.objects.filter(tenant=school, staff_code__iexact=value).exclude(id=staff.id).exists(),
            )
        used_staff_codes.add(next_code)
        staff.staff_code = next_code
        staff.save(update_fields=["staff_code", "updated_at"])

    for reference in references:
        reference.code = student_codes_by_id.get(str(reference.student_id)) or StudentProfile.objects.get(id=reference.student_id).student_id
        reference.save(update_fields=["code", "updated_at"])

    return {
        "students": len(students),
        "teachers": len(teachers),
        "staff": len(staff_records),
        "payment_references": len(references),
    }


def _announcement_visible_to_user(announcement, user):
    role = getattr(user, "role", "")
    audience_type = str(getattr(announcement, "audience_type", "") or "all").strip().lower()

    if audience_type == "all":
        return True
    if audience_type == "students":
        return role == "student"
    if audience_type == "teachers":
        return role == "teacher"
    if audience_type == "parents":
        return role == "parent"
    if audience_type == "staff":
        return role in {"school_admin", "principal", "super_admin", "teacher"}
    if audience_type == "role":
        target_roles = announcement.target_roles if isinstance(announcement.target_roles, list) else []
        return role in target_roles

    return role in {"school_admin", "principal", "super_admin"}


def _visible_announcements_for_user(user, now=None):
    if not Announcement or not getattr(user, "tenant_id", None):
        return []

    current_time = now or timezone.now()
    base_queryset = (
        Announcement.objects.filter(
            tenant=user.tenant,
            is_published=True,
            publish_from__lte=current_time,
        )
        .filter(Q(publish_until__isnull=True) | Q(publish_until__gte=current_time))
        .order_by("-is_pinned", "-priority", "-publish_from")
    )
    return [item for item in base_queryset if _announcement_visible_to_user(item, user)]


def _build_unique_announcement_slug(title):
    base_slug = slugify(title) or "announcement"
    base_slug = base_slug[:220]
    timestamp = timezone.now().strftime("%Y%m%d%H%M%S%f")
    candidate = f"{base_slug}-{timestamp}"
    if len(candidate) > 250:
        candidate = candidate[:250]

    suffix = 1
    while Announcement and Announcement.objects.filter(slug=candidate).exists():
        numbered_suffix = f"{timestamp}-{suffix}"
        allowed_base = max(1, 250 - len(numbered_suffix) - 1)
        candidate = f"{base_slug[:allowed_base]}-{numbered_suffix}"
        suffix += 1

    return candidate


def _performance_status(value, low=50, mid=70, inverse=False):
    numeric = float(value or 0)
    if inverse:
        if numeric <= low:
            return "strong"
        if numeric <= mid:
            return "watch"
        return "weak"
    if numeric >= mid:
        return "strong"
    if numeric >= low:
        return "watch"
    return "weak"


def _department_bucket(subject_name="", subject_code=""):
    label = f"{subject_name} {subject_code}".lower()
    if any(item in label for item in ["math", "physics", "chem", "biology", "basic science", "agric", "computer", "ict"]):
        return "Sciences"
    if any(item in label for item in ["english", "literature", "language", "french", "yoruba", "igbo", "hausa"]):
        return "Languages"
    if any(item in label for item in ["account", "commerce", "economics", "business"]):
        return "Commercial"
    if any(item in label for item in ["government", "history", "civic", "social", "religion", "crs", "irs"]):
        return "Humanities"
    return "General Studies"


def _score_percentage(score):
    max_score = float(score.max_score or 0)
    if max_score <= 0:
        return 0
    return round((float(score.score or 0) / max_score) * 100, 1)


def _average(values):
    values = [float(item or 0) for item in values]
    if not values:
        return 0
    return round(sum(values) / len(values), 1)


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def performance_heatmap_snapshot(request):
    user = request.user
    if user.role not in ADMIN_ROLES:
        return Response(
            {"success": False, "message": "Only school administrators can view the performance heatmap."},
            status=status.HTTP_403_FORBIDDEN,
        )

    school = _resolve_school_tenant_for_user(user, school_code=request.query_params.get("school_code"))
    if not school:
        return Response({"success": False, "message": "Could not resolve school tenant."}, status=status.HTTP_400_BAD_REQUEST)

    today = timezone.localdate()
    current_start = today - timedelta(days=13)
    previous_start = today - timedelta(days=27)
    month_start = today.replace(day=1)

    students_qs = User.objects.filter(role="student", tenant=school)
    scores_qs = (
        _scope_to_user_tenant(StudentSubjectScore.objects.select_related("subject", "class_group", "student"), user)
        .filter(student__user__tenant=school)
        .order_by("-updated_at")
    )
    scores = list(scores_qs[:2000])

    subjects = {}
    classes = {}
    departments = {}
    for item in scores:
        percentage = _score_percentage(item)
        subject_name = item.subject.name if item.subject else "General"
        subject_code = item.subject.code if item.subject else ""
        class_name = _class_label(item.class_group) if item.class_group else "Unassigned"
        subject_key = item.subject_id or subject_name
        class_key = item.class_group_id or class_name

        subjects.setdefault(subject_key, {"name": subject_name, "code": subject_code, "scores": [], "classes": set()})
        subjects[subject_key]["scores"].append(percentage)
        subjects[subject_key]["classes"].add(class_name)

        classes.setdefault(class_key, {"name": class_name, "scores": [], "subjects": set()})
        classes[class_key]["scores"].append(percentage)
        classes[class_key]["subjects"].add(subject_name)

        department = _department_bucket(subject_name, subject_code)
        departments.setdefault(department, {"name": department, "scores": [], "subjects": set()})
        departments[department]["scores"].append(percentage)
        departments[department]["subjects"].add(subject_name)

    weak_subjects = sorted(
        [
            {
                "name": item["name"],
                "code": item["code"],
                "average": _average(item["scores"]),
                "entries": len(item["scores"]),
                "class_count": len(item["classes"]),
                "status": _performance_status(_average(item["scores"])),
            }
            for item in subjects.values()
        ],
        key=lambda row: row["average"],
    )[:12]

    low_classes = sorted(
        [
            {
                "name": item["name"],
                "average": _average(item["scores"]),
                "entries": len(item["scores"]),
                "subject_count": len(item["subjects"]),
                "status": _performance_status(_average(item["scores"])),
            }
            for item in classes.values()
        ],
        key=lambda row: row["average"],
    )[:12]

    attendance_qs = (
        _scope_to_user_tenant(AttendanceRecord.objects.select_related("class_group", "student"), user)
        .filter(student__tenant=school, date__gte=previous_start)
    )
    attendance_by_class = {}
    present_statuses = {"present", "late"}
    for item in attendance_qs[:5000]:
        class_name = _class_label(item.class_group) if item.class_group else "Unassigned"
        bucket = attendance_by_class.setdefault(class_name, {"current_total": 0, "current_present": 0, "previous_total": 0, "previous_present": 0})
        is_present = str(item.status or "").lower() in present_statuses
        if item.date >= current_start:
            bucket["current_total"] += 1
            bucket["current_present"] += 1 if is_present else 0
        else:
            bucket["previous_total"] += 1
            bucket["previous_present"] += 1 if is_present else 0

    attendance_decline = []
    for class_name, item in attendance_by_class.items():
        current_rate = round((item["current_present"] / item["current_total"]) * 100, 1) if item["current_total"] else 0
        previous_rate = round((item["previous_present"] / item["previous_total"]) * 100, 1) if item["previous_total"] else current_rate
        decline = round(previous_rate - current_rate, 1)
        attendance_decline.append(
            {
                "class_name": class_name,
                "current_rate": current_rate,
                "previous_rate": previous_rate,
                "decline": decline,
                "status": _performance_status(current_rate),
            }
        )
    attendance_decline = sorted(attendance_decline, key=lambda row: (row["decline"], -row["current_rate"]), reverse=True)[:10]

    fees_qs = (
        SchoolFee.objects.select_related("student", "student__user", "student__current_class")
        .filter(student__user__tenant=school)
        .order_by("-created_at")[:1500]
    )
    fee_expected = Decimal("0")
    fee_paid = Decimal("0")
    fee_by_class = {}
    for fee in fees_qs:
        amount = Decimal(fee.amount or 0)
        paid = Decimal(fee_paid_amount(fee) or 0)
        fee_expected += amount
        fee_paid += paid
        class_name = _class_label(fee.student.current_class) if getattr(fee.student, "current_class", None) else "Unassigned"
        bucket = fee_by_class.setdefault(class_name, {"expected": Decimal("0"), "paid": Decimal("0")})
        bucket["expected"] += amount
        bucket["paid"] += paid
    collection_rate = round((float(fee_paid) / float(fee_expected)) * 100, 1) if fee_expected else 0
    fee_class_trends = []
    for class_name, item in fee_by_class.items():
        rate = round((float(item["paid"]) / float(item["expected"])) * 100, 1) if item["expected"] else 0
        fee_class_trends.append(
            {
                "class_name": class_name,
                "expected": float(item["expected"]),
                "paid": float(item["paid"]),
                "collection_rate": rate,
                "status": _performance_status(rate),
            }
        )
    fee_class_trends = sorted(fee_class_trends, key=lambda row: row["collection_rate"])[:10]

    monthly_transactions = [
        {
            "date": tx.created_at.date(),
            "amount": float(tx.amount or 0),
            "status": tx.status,
            "type": tx.tx_type,
        }
        for tx in Transaction.objects.filter(admin_wallet__tenant=school, created_at__date__gte=month_start).order_by("created_at")[:500]
    ]

    attempts_qs = (
        _scope_to_user_tenant(ExamAttempt.objects.select_related("exam", "exam__subject", "exam__class_group"), user)
        .filter(created_at__date__gte=month_start)
        .order_by("-created_at")
    )
    attempts = list(attempts_qs[:2000])
    exam_completion = _average([100 if item.is_submitted or item.is_completed else 0 for item in attempts])
    exam_average = _average([float(item.percentage or 0) for item in attempts if item.is_submitted or item.is_completed])
    exam_auto_rate = _average([100 if item.auto_submitted else 0 for item in attempts])
    exams_by_subject = {}
    for item in attempts:
        subject_name = item.exam.subject.name if item.exam and item.exam.subject else "General"
        bucket = exams_by_subject.setdefault(subject_name, {"scores": [], "attempts": 0, "auto": 0})
        bucket["attempts"] += 1
        bucket["auto"] += 1 if item.auto_submitted else 0
        if item.is_submitted or item.is_completed:
            bucket["scores"].append(float(item.percentage or 0))
    exam_subjects = sorted(
        [
            {
                "name": name,
                "average": _average(item["scores"]),
                "attempts": item["attempts"],
                "auto_submitted": item["auto"],
                "status": _performance_status(_average(item["scores"])),
            }
            for name, item in exams_by_subject.items()
        ],
        key=lambda row: row["average"],
    )[:10]

    department_rows = sorted(
        [
            {
                "name": item["name"],
                "average": _average(item["scores"]),
                "subject_count": len(item["subjects"]),
                "entries": len(item["scores"]),
                "status": _performance_status(_average(item["scores"])),
            }
            for item in departments.values()
        ],
        key=lambda row: row["average"],
    )

    risk_score = _average(
        [
            100 - _average([row["average"] for row in weak_subjects]) if weak_subjects else 0,
            100 - _average([row["average"] for row in low_classes]) if low_classes else 0,
            100 - _average([row["current_rate"] for row in attendance_decline]) if attendance_decline else 0,
            100 - collection_rate,
            100 - exam_average,
        ]
    )

    return Response(
        {
            "success": True,
            "generated_at": timezone.now(),
            "school": _school_payload(school, request),
            "summary": {
                "students": students_qs.count(),
                "score_entries": len(scores),
                "weak_subjects": sum(1 for item in weak_subjects if item["status"] == "weak"),
                "low_classes": sum(1 for item in low_classes if item["status"] == "weak"),
                "attendance_current": _average([row["current_rate"] for row in attendance_decline]),
                "fee_collection_rate": collection_rate,
                "exam_average": exam_average,
                "exam_completion": exam_completion,
                "exam_auto_submit_rate": exam_auto_rate,
                "risk_score": round(risk_score, 1),
                "risk_status": _performance_status(100 - risk_score),
            },
            "weak_subjects": weak_subjects,
            "low_classes": low_classes,
            "attendance_decline": attendance_decline,
            "fee_trends": {
                "expected": float(fee_expected),
                "paid": float(fee_paid),
                "collection_rate": collection_rate,
                "class_trends": fee_class_trends,
                "monthly_transactions": monthly_transactions,
            },
            "examination_statistics": {
                "attempts": len(attempts),
                "completion_rate": exam_completion,
                "average": exam_average,
                "auto_submit_rate": exam_auto_rate,
                "subjects": exam_subjects,
            },
            "departmental_performance": department_rows,
        }
    )


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def dashboard_snapshot(request):
    user = request.user
    now = timezone.now()
    seven_days_ago = now - timedelta(days=7)

    students_qs = User.objects.filter(role="student", tenant=user.tenant)
    active_students = students_qs.filter(is_active=True).count()
    new_students_7d = students_qs.filter(created_at__gte=seven_days_ago).count()

    classes_qs = _scope_to_user_tenant(Class.objects.all(), user)
    exams_qs = _scope_to_user_tenant(Exam.objects.all(), user)
    attempts_qs = _scope_to_user_tenant(ExamAttempt.objects.all(), user)
    announcements = _visible_announcements_for_user(user, now=now)

    upcoming_exams = exams_qs.filter(start_date__gte=now).count()
    pending_submissions = attempts_qs.filter(is_submitted=False).count()
    auto_submitted_exams = attempts_qs.filter(auto_submitted=True, is_submitted=True).count()
    unread_notifications = _tenant_notifications_for_user(user).filter(is_read=False).count() if Notification else 0

    recent_announcements = announcements[:3]
    recent_students = (
        StudentProfile.objects.select_related("user", "current_class")
        .filter(user__tenant=user.tenant)
        .order_by("-created_at")[:8]
    )

    finance_summary = None
    if user.role in ADMIN_ROLES:
        admin_wallet, _ = AdminWallet.objects.get_or_create(tenant=user.tenant)
        finance_summary = {
            "balance": admin_wallet.balance,
            "currency": admin_wallet.currency,
            "pending_fees": SchoolFee.objects.filter(
                student__user__tenant=user.tenant, status=SchoolFee.STATUS_PENDING
            ).count(),
            "overdue_fees": SchoolFee.objects.filter(
                student__user__tenant=user.tenant, status=SchoolFee.STATUS_OVERDUE
            ).count(),
        }

    prompt_qs = _scope_to_user_tenant(QuestionPrompt.objects.filter(is_active=True), user).order_by("-created_at")
    if user.role == "teacher":
        prompt_qs = prompt_qs.filter(created_by=user)
    prompt_qs = prompt_qs.select_related("class_group").prefetch_related(
        Prefetch(
            "responses",
            queryset=QuestionResponse.objects.select_related("student").order_by("-updated_at"),
            to_attr="ordered_responses",
        )
    )
    question_prompts_list = list(prompt_qs[:8])

    return Response(
        {
            "success": True,
            "school": _school_payload(user.tenant, request),
            "metrics": {
                "active_students": active_students,
                "new_students_7d": new_students_7d,
                "classes": classes_qs.count(),
                "upcoming_exams": upcoming_exams,
                "pending_submissions": pending_submissions,
                "auto_submitted_exams": auto_submitted_exams,
                "unread_notifications": unread_notifications,
            },
            "announcements": [
                {
                    "id": str(item.id),
                    "title": item.title,
                    "priority": item.priority,
                    "published_at": item.publish_from,
                }
                for item in recent_announcements
            ],
            "finance": finance_summary,
            "recent_students": [
                {
                    "id": str(student.id),
                    "name": student.user.get_full_name(),
                    "email": student.user.email,
                    "student_id": student.student_id,
                    "class_name": _class_label(student.current_class) if student.current_class else "Unassigned",
                    "admission_date": student.admission_date,
                    "created_at": student.created_at,
                    "profile_picture": _profile_picture_url(request, student.user),
                }
                for student in recent_students
            ],
        }
    )


def _public_admin_app_school(request):
    requested_code = str(request.GET.get("school_code") or "").strip()
    if requested_code:
        school = SchoolTenant.objects.filter(schema_name__iexact=requested_code, is_active=True).first()
        if school:
            return school
        return None

    host = request.get_host().split(":", 1)[0].lower()
    domain = Domain.objects.select_related("tenant").filter(domain__iexact=host).first()
    if domain and domain.tenant and domain.tenant.is_active:
        return domain.tenant

    return None


@api_view(["GET"])
@permission_classes([AllowAny])
def admin_desktop_bootstrap(request):
    school = _public_admin_app_school(request)
    now = timezone.now()
    legacy_tenant = None
    if school:
        legacy_tenant = (
            Tenant.objects.filter(slug__iexact=school.schema_name).first()
            or Tenant.objects.filter(slug__iexact=slugify(school.schema_name)).first()
            or Tenant.objects.filter(slug__iexact=slugify(school.name)).first()
            or Tenant.objects.filter(name__iexact=school.name).first()
        )
    tenant_filter = {"tenant": legacy_tenant} if legacy_tenant else None
    students_qs = User.objects.filter(role="student", tenant=school) if school else User.objects.none()
    student_profiles_qs = (
        StudentProfile.objects.select_related("user", "current_class", "current_term", "activation_credit")
        .filter(user__tenant=school if school else None)
        if school
        else StudentProfile.objects.none()
    )
    student_class_ids = student_profiles_qs.exclude(current_class__isnull=True).values_list("current_class_id", flat=True)
    classes_qs = (
        Class.objects.filter(Q(**tenant_filter) | Q(id__in=student_class_ids))
        if tenant_filter
        else Class.objects.filter(id__in=student_class_ids)
    ).distinct()
    exams_qs = Exam.objects.filter(**tenant_filter).select_related("subject", "class_group", "exam_type").prefetch_related("questions") if tenant_filter else Exam.objects.none()
    attempts_qs = ExamAttempt.objects.filter(**tenant_filter) if tenant_filter else ExamAttempt.objects.none()
    banks_qs = QuestionBank.objects.filter(**tenant_filter) if tenant_filter else QuestionBank.objects.none()
    token_pool = ActivationCreditPool.objects.filter(tenant=school).first() if school else None
    active_year = AcademicYear.objects.filter(tenant=legacy_tenant, is_active=True).order_by("-start_date").first() if legacy_tenant else None
    active_term = Term.objects.select_related("academic_year").filter(tenant=legacy_tenant, is_active=True).order_by("-start_date").first() if legacy_tenant else None
    active_credit_count = 0
    inactive_credit_count = 0
    desktop_students = []
    for profile in student_profiles_qs.order_by("user__first_name", "user__last_name", "student_id"):
        credit = getattr(profile, "activation_credit", None)
        has_login_credit = bool(getattr(credit, "has_login_credit", False))
        is_active = bool(profile.user.is_active and has_login_credit)
        if is_active:
            active_credit_count += 1
        else:
            inactive_credit_count += 1
        desktop_students.append(
            {
                "id": str(profile.id),
                "user_id": str(profile.user_id),
                "student_id": profile.student_id,
                "admission_number": profile.admission_number or "",
                "full_name": profile.user.get_full_name() or profile.user.email,
                "email": profile.user.email,
                "phone": profile.user.phone or "",
                "class_id": profile.current_class_id,
                "class_name": _class_label(profile.current_class) if profile.current_class else "Unassigned",
                "current_term_id": profile.current_term_id,
                "current_term_name": profile.current_term.name if profile.current_term else "",
                "admission_date": profile.admission_date,
                "profile_picture": _profile_picture_url(request, profile.user),
                "gender": profile.user.gender or "",
                "date_of_birth": profile.user.date_of_birth,
                "state_of_origin": profile.state_of_origin or "",
                "local_government": profile.local_government or "",
                "guardian_name": profile.guardian_name or "",
                "guardian_phone": profile.guardian_phone or "",
                "guardian_email": profile.guardian_email or "",
                "guardian_relation": profile.guardian_relation or "",
                "second_guardian_name": profile.second_guardian_name or "",
                "second_guardian_phone": profile.second_guardian_phone or "",
                "second_guardian_email": profile.second_guardian_email or "",
                "second_guardian_relation": profile.second_guardian_relation or "",
                "home_address": profile.home_address or "",
                "blood_group": profile.blood_group or "",
                "disability": profile.disability or "",
                "student_type": profile.student_type or "",
                "allergies": profile.allergies or "",
                "medical_conditions": profile.medical_conditions or "",
                "is_active": is_active,
                "user_is_active": profile.user.is_active,
                "activation": {
                    "has_login_credit": has_login_credit,
                    "active_until": getattr(credit, "active_until", None),
                    "credits_assigned": getattr(credit, "credits_assigned", 0) if credit else 0,
                    "inactive_since": getattr(credit, "inactive_since", None),
                    "excluded_from_auto_deductions": bool(getattr(credit, "is_excluded_from_auto_deductions", False)) if credit else False,
                },
            }
        )

    desktop_classes = [
        {
            "id": item.id,
            "name": _class_label(item),
            "raw_name": item.name,
            "section": getattr(item, "section", "") or "",
        }
        for item in classes_qs.order_by("name")
    ]

    desktop_exams = []
    for exam in exams_qs.order_by("-created_at")[:100]:
        desktop_exams.append(
            {
                "id": exam.id,
                "title": exam.title,
                "subject": exam.subject.name if exam.subject else "",
                "subject_id": exam.subject_id,
                "class_id": exam.class_group_id,
                "class_name": _class_label(exam.class_group) if exam.class_group else "All classes",
                "duration_minutes": exam.duration_minutes,
                "instructions": exam.instructions,
                "start_date": exam.start_date,
                "end_date": exam.end_date,
                "is_published": exam.is_published,
                "active_pin_count": exam.pins.filter(is_active=True).count(),
                "questions": [
                    {
                        "id": question.id,
                        "text": question.text,
                        "type": "multiple_choice" if question.question_type == "mcq" else question.question_type,
                        "options": question.options or [],
                        "marks": question.points,
                    }
                    for question in exam.questions.all()[:200]
                ],
            }
        )

    school_payload = _school_payload(school, request) if school else {
        "name": "SchoolDom",
        "school_code": "",
        "email": "",
        "phone": "",
        "address": "",
        "logo": "",
    }

    return Response(
        {
            "success": True,
            "school": school_payload,
            "server": {
                "online": True,
                "host": request.get_host(),
                "checked_at": now,
            },
            "downloads": {
                "student_cbt": request.build_absolute_uri("/app/download/student-cbt/"),
            },
            "academic_year": _academic_year_payload(active_year),
            "term": _term_payload(active_term),
            "dashboard": {
                "settings": {
                    "name": school_payload.get("name") or "SchoolDom",
                    "ip_address": request.get_host(),
                    "refresh_interval": "30 sec",
                },
                "content": {
                    "total": banks_qs.count() + Question.objects.filter(question_banks__in=banks_qs).distinct().count(),
                },
                "candidate": {
                    "total": students_qs.count(),
                    "class": classes_qs.count(),
                },
                "client": {
                    "total": 1,
                },
                "test": {
                    "total": exams_qs.count(),
                    "licensed": exams_qs.filter(is_published=True).count(),
                    "pending": attempts_qs.filter(is_submitted=False).count(),
                    "ongoing": attempts_qs.filter(is_submitted=False, end_time__gte=now).count(),
                    "submitted": attempts_qs.filter(is_submitted=True).count(),
                    "batch_count": ResultBatch.objects.filter(**tenant_filter).count() if tenant_filter else 0,
                },
            },
            "local_data": {
                "school": school_payload,
                "classes": desktop_classes,
                "students": desktop_students,
                "exams": desktop_exams,
                "activation_tokens": {
                    "balance": token_pool.balance if token_pool else 0,
                    "price_per_credit": str(token_pool.price_per_credit) if token_pool else "200.00",
                    "currency": token_pool.currency if token_pool else school_payload.get("currency", "NGN"),
                    "auto_assign_enabled": bool(token_pool.auto_assign_enabled) if token_pool else False,
                    "active_students": active_credit_count,
                    "inactive_students": inactive_credit_count,
                },
            },
        }
    )


@api_view(["GET"])
@authentication_classes([])
@permission_classes([AllowAny])
def admin_desktop_download(request):
    app_path = admin_app_installer_path()
    if not app_path:
        return Response(
            {
                "success": False,
                "message": "SchoolDom Admin installer is not available on this server yet.",
            },
            status=status.HTTP_404_NOT_FOUND,
        )
    response = FileResponse(
        app_path.open("rb"),
        as_attachment=True,
        filename=ADMIN_APP_FILENAME,
        content_type="application/vnd.microsoft.portable-executable",
    )
    response["Cache-Control"] = "no-store"
    response["X-Content-Type-Options"] = "nosniff"
    return response


@api_view(["POST"])
@authentication_classes([])
@permission_classes([AllowAny])
def admin_desktop_support_tickets(request):
    school_code = str(request.data.get("school_code") or request.data.get("schoolCode") or "").strip()
    school = SchoolTenant.objects.filter(schema_name__iexact=school_code, is_active=True).first() if school_code else None
    if not school:
        return Response({"success": False, "message": "Select a valid school before sending support."}, status=status.HTTP_400_BAD_REQUEST)

    category = str(request.data.get("category") or "technical_issue").strip()
    allowed_categories = {value for value, _label in SupportTicket.CATEGORY_CHOICES}
    if category not in allowed_categories:
        category = "technical_issue"

    subject = str(request.data.get("subject") or "").strip()
    description = str(request.data.get("description") or request.data.get("message") or "").strip()
    requester_email = str(request.data.get("requester_email") or request.data.get("email") or school.email or "").strip()
    if len(subject) < 3:
        return Response({"success": False, "message": "Enter a support ticket subject."}, status=status.HTTP_400_BAD_REQUEST)
    if len(description) < 10:
        return Response({"success": False, "message": "Enter a brief description of the issue."}, status=status.HTTP_400_BAD_REQUEST)

    ticket = SupportTicket.objects.create(
        school=school,
        submitted_by=None,
        category=category,
        subject=subject[:180],
        description=description,
        requester_email=requester_email,
    )
    notified = _send_support_ticket_email(ticket, kind="created")
    if notified:
        now = timezone.now()
        ticket.support_notified_at = now
        ticket.requester_notified_at = now
        ticket.save(update_fields=["support_notified_at", "requester_notified_at"])

    return Response(
        {
            "success": True,
            "message": "Support ticket submitted.",
            "notified": notified,
            "ticket": _support_ticket_payload(ticket, request),
        },
        status=status.HTTP_201_CREATED,
    )


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def student_dashboard(request):
    user = request.user
    if user.role != "student":
        return Response(
            {"success": False, "message": "Only student accounts can access this dashboard."},
            status=status.HTTP_403_FORBIDDEN,
        )

    school = _resolve_school_tenant_for_user(user)
    if not school:
        return Response(
            {"success": False, "message": "Your account is not linked to a school."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    now = timezone.now()
    student_profile = StudentProfile.objects.select_related("current_class").filter(user=user).first()
    active_term = _active_term(user)

    upcoming_exams_qs = _scope_to_user_tenant(
        Exam.objects.select_related("subject", "class_group"),
        user,
    ).filter(is_published=True, end_date__gte=now)
    enrolled_exam_ids = []
    if student_profile:
        enrolled_exam_ids = list(
            StudentEnrollment.objects.filter(school=school, student=student_profile)
            .values_list("exams__id", flat=True)
        )
        enrolled_exam_ids = [exam_id for exam_id in enrolled_exam_ids if exam_id]
    if student_profile and student_profile.current_class_id:
        upcoming_exams_qs = upcoming_exams_qs.filter(
            Q(class_group_id=student_profile.current_class_id)
            | Q(class_group__isnull=True)
            | Q(id__in=enrolled_exam_ids)
        )
    elif enrolled_exam_ids:
        upcoming_exams_qs = upcoming_exams_qs.filter(Q(class_group__isnull=True) | Q(id__in=enrolled_exam_ids))
    upcoming_exams_qs = upcoming_exams_qs.distinct()

    attempts_qs = _scope_to_user_tenant(
        ExamAttempt.objects.select_related("exam", "exam__subject", "exam__class_group"),
        user,
    ).filter(student=user)
    attempts_by_exam = {attempt.exam_id: attempt for attempt in attempts_qs}
    results_qs = attempts_qs.filter(Q(is_submitted=True) | Q(is_completed=True)).order_by("-updated_at", "-created_at")
    recent_result_attempts = list(results_qs[:10])
    recent_result_scores = {}
    if recent_result_attempts:
        recent_result_scores = {
            row["attempt_id"]: row["total_score"]
            for row in (
                StudentAnswer.objects.filter(attempt_id__in=[item.id for item in recent_result_attempts])
                .values("attempt_id")
                .annotate(total_score=Sum("score"))
            )
        }

    inbox_qs = _tenant_inbox_for_user(user).order_by("-created_at") if InAppMessage else []
    unread_inbox = inbox_qs.filter(is_read=False).count() if InAppMessage else 0

    announcements = _visible_announcements_for_user(user, now=now)
    admin_contacts_qs = User.objects.filter(
        tenant=school,
        is_active=True,
        role__in=["school_admin", "principal", "super_admin"],
    ).order_by("first_name", "last_name", "email")
    teacher_contacts_qs = User.objects.filter(
        tenant=school,
        is_active=True,
        role="teacher",
    ).order_by("first_name", "last_name", "email")
    message_recipients_qs = (admin_contacts_qs | teacher_contacts_qs).distinct().order_by("first_name", "last_name", "email")

    student_class = student_profile.current_class if student_profile else None
    today_date = timezone.localdate()
    attendance_today = AttendanceRecord.objects.filter(student=user, date=today_date).first()
    attendance_history = list(
        AttendanceRecord.objects.filter(student=user).order_by("-date")[:5]
    )

    question_prompt_qs = _scope_to_user_tenant(
        QuestionPrompt.objects.filter(is_active=True),
        user,
    )
    if student_class:
        question_prompt_qs = question_prompt_qs.filter(
            Q(class_group=student_class) | Q(class_group__isnull=True)
        )
    else:
        question_prompt_qs = question_prompt_qs.filter(class_group__isnull=True)
    question_prompt_list = list(question_prompt_qs.order_by("-created_at")[:8])
    prompt_ids = [prompt.id for prompt in question_prompt_list]
    response_map = {
        response.prompt_id: response
        for response in QuestionResponse.objects.filter(student=user, prompt_id__in=prompt_ids)
    }

    wallet = Wallet.objects.filter(user=user).first()
    wallet_data = None
    wallet_transactions = []
    wallet_fees = []
    payment_reference_data = None
    payment_instructions = {}
    if student_profile:
        if not wallet:
            wallet = ensure_student_wallet(user)
        process_due_fees(student_profile, actor=user)
        payment_reference = get_or_create_student_payment_reference(student_profile)
        admin_wallet = AdminWallet.objects.filter(tenant=user.tenant).first()
        payment_reference_data = {"code": payment_reference.code}
        payment_instructions = {
            "bank_account_name": admin_wallet.bank_account_name if admin_wallet else "",
            "bank_account_number": admin_wallet.bank_account_number if admin_wallet else "",
            "bank_code": admin_wallet.bank_code if admin_wallet else "",
            "reference_code": payment_reference.code,
            "narration": f"School fees {payment_reference.code}",
        }
        wallet = Wallet.objects.prefetch_related("transactions").get(pk=wallet.pk)
        wallet_data = {
            "balance": wallet.balance,
            "currency": wallet.currency,
            "is_locked": wallet.is_locked,
            "id": str(wallet.id),
        }
        wallet_transactions = [
            {
                "id": str(tx.id),
                "amount": tx.amount,
                "currency": tx.currency,
                "status": tx.status,
                "type": tx.tx_type,
                "reference": tx.reference,
                "narration": tx.narration,
                "created_at": tx.created_at,
            }
            for tx in wallet.transactions.order_by("-created_at")[:12]
        ]
        wallet_fees = [
            _school_fee_payload(fee)
            for fee in SchoolFee.objects.filter(student=student_profile).order_by("due_date")[:12]
        ]

    upcoming_exams = []
    for exam in upcoming_exams_qs.order_by("start_date")[:8]:
        attempt = attempts_by_exam.get(exam.id)
        upcoming_exams.append(
            {
                "id": exam.id,
                "title": exam.title,
                "subject": exam.subject.name if exam.subject else "General",
                "class_name": _class_label(exam.class_group) if exam.class_group else "All classes",
                "start_date": exam.start_date,
                "end_date": exam.end_date,
                "duration_minutes": exam.duration_minutes,
                "can_start": exam.start_date <= now <= exam.end_date,
                "is_published": exam.is_published,
                "is_submitted": bool(attempt.is_submitted) if attempt else False,
                "is_completed": bool(attempt.is_completed) if attempt else False,
            }
        )

    subject_ids = set()
    if student_profile:
        subject_ids.update(
            StudentSubjectScore.objects.filter(student=student_profile, subject__isnull=False).values_list(
                "subject_id", flat=True
            )
        )
        enrollments = (
            StudentEnrollment.objects.filter(school=school, student=student_profile)
            .prefetch_related("exams__subject")
            .order_by("-created_at")
        )
        for enrollment in enrollments[:10]:
            subject_ids.update(exam.subject_id for exam in enrollment.exams.all() if exam.subject_id)

    subject_ids.update(upcoming_exams_qs.filter(subject__isnull=False).values_list("subject_id", flat=True))
    subject_ids.update(
        attempts_qs.filter(exam__subject__isnull=False).values_list("exam__subject_id", flat=True)
    )
    if student_class:
        subject_ids.update(student_class.subjects.values_list("id", flat=True))
    if not subject_ids and student_class:
        subject_ids.update(
            _scope_to_user_tenant(Exam.objects.filter(subject__isnull=False), user)
            .filter(Q(class_group=student_class) | Q(class_group__isnull=True))
            .values_list("subject_id", flat=True)
        )

    subjects = [
        {"id": subject.id, "name": subject.name, "code": subject.code}
        for subject in _scope_to_user_tenant(Subject.objects.filter(id__in=subject_ids), user).order_by("name", "code")
    ]

    daily_quiz = {
        "daily_date": today_date,
        "completed_today": 0,
        "total_subjects": len(subjects),
        "available_today": len(subjects),
        "average_percentage": 0,
        "best_percentage": 0,
        "streak_days": 0,
        "recent": [],
    }
    try:
        from quizzes.models import PersonalQuizAttempt

        personal_attempts = list(
            PersonalQuizAttempt.objects.filter(student=user, is_submitted=True)
            .select_related("subject", "class_group")
            .order_by("-submitted_at")[:100]
        )
        today_attempts = [attempt for attempt in personal_attempts if attempt.daily_date == today_date]
        percentages = [
            round((attempt.score / max(attempt.total_points, 1)) * 100, 1)
            for attempt in personal_attempts
            if attempt.total_points
        ]
        date_set = {attempt.daily_date for attempt in personal_attempts if attempt.daily_date}
        streak = 0
        cursor_date = today_date
        while cursor_date in date_set:
            streak += 1
            cursor_date = cursor_date - timedelta(days=1)
        daily_quiz = {
            "daily_date": today_date,
            "completed_today": len(today_attempts),
            "total_subjects": len(subjects),
            "available_today": max(len(subjects) - len(today_attempts), 0),
            "average_percentage": round(sum(percentages) / len(percentages), 1) if percentages else 0,
            "best_percentage": max(percentages, default=0),
            "streak_days": streak,
            "recent": [
                {
                    "id": attempt.id,
                    "subject": attempt.subject.name if attempt.subject else "Personal Quiz",
                    "score": attempt.score,
                    "total_points": attempt.total_points,
                    "percentage": round((attempt.score / max(attempt.total_points, 1)) * 100, 1) if attempt.total_points else 0,
                    "submitted_at": attempt.submitted_at,
                    "auto_submitted": attempt.auto_submitted,
                }
                for attempt in personal_attempts[:5]
            ],
        }
    except Exception:
        pass

    recent_results = []
    for attempt in recent_result_attempts:
        exam = attempt.exam
        if not exam:
            continue

        score = recent_result_scores.get(attempt.id)
        recent_results.append(
            {
                "id": str(attempt.id),
                "exam_id": exam.id,
                "exam_title": exam.title,
                "subject": exam.subject.name if exam.subject else "General",
                "class_name": _class_label(exam.class_group) if exam.class_group else "All classes",
                "status": "Completed" if attempt.is_completed else "Submitted",
                "is_submitted": attempt.is_submitted,
                "is_completed": attempt.is_completed,
                "score": round(score, 2) if score is not None else None,
                "exam_start_date": exam.start_date,
                "updated_at": attempt.updated_at,
            }
        )

    return Response(
        {
            "success": True,
            "school": _school_payload(school, request),
            "student": {
                "name": user.get_full_name(),
                "email": user.email,
                "phone": user.phone,
                "gender": user.gender or "",
                "date_of_birth": user.date_of_birth,
                "student_id": student_profile.student_id if student_profile else "",
                "admission_number": student_profile.student_id if student_profile else "",
                "admission_date": student_profile.admission_date if student_profile else None,
                "class_name": _class_label(student_profile.current_class) if student_profile and student_profile.current_class else "Unassigned",
                "term": active_term.name if active_term else "",
                "profile_picture": _profile_picture_url(request, user),
                "state_of_origin": student_profile.state_of_origin if student_profile else "",
                "local_government": student_profile.local_government if student_profile else "",
                "guardian_name": student_profile.guardian_name if student_profile else "",
                "guardian_phone": student_profile.guardian_phone if student_profile else "",
                "guardian_email": student_profile.guardian_email if student_profile else "",
                "guardian_relation": student_profile.guardian_relation if student_profile else "",
                "second_guardian_name": student_profile.second_guardian_name if student_profile else "",
                "second_guardian_phone": student_profile.second_guardian_phone if student_profile else "",
                "second_guardian_email": student_profile.second_guardian_email if student_profile else "",
                "second_guardian_relation": student_profile.second_guardian_relation if student_profile else "",
                "student_type": student_profile.student_type if student_profile else "",
                "blood_group": student_profile.blood_group if student_profile else "",
                "disability": student_profile.disability if student_profile else "",
                "home_address": student_profile.home_address if student_profile else "",
            },
            "active_term": _term_payload(active_term),
            "metrics": {
                "upcoming_exams": upcoming_exams_qs.count(),
                "completed_exams": attempts_qs.filter(is_completed=True).count(),
                "pending_submissions": attempts_qs.filter(is_submitted=False).count(),
                "unread_inbox": unread_inbox,
                "available_results": results_qs.count(),
                "attendance_marked_today": bool(attendance_today),
                "subjects_offered": len(subjects),
            },
            "upcoming_exams": upcoming_exams,
            "subjects": subjects,
            "daily_personal_quiz": daily_quiz,
            "announcements": [
                {
                    "id": str(item.id),
                    "title": item.title,
                    "priority": item.priority,
                    "published_at": item.publish_from,
                }
                for item in announcements[:4]
            ],
            "wallet": wallet_data,
            "payment_reference": payment_reference_data,
            "payment_instructions": payment_instructions,
            "transactions": wallet_transactions,
            "fees": wallet_fees,
            "attendance": {
                "class_name": _class_label(student_class) if student_class else "Unassigned",
                "today": {
                    "status": attendance_today.status,
                    "date": attendance_today.date,
                    "noted_by": attendance_today.noted_by.get_full_name() if attendance_today.noted_by else None,
                }
                if attendance_today
                else None,
                "history": [
                    {
                        "date": record.date,
                        "status": record.status,
                        "class_name": _class_label(record.class_group) if record.class_group else "Unassigned",
                        "noted_by": record.noted_by.get_full_name() if record.noted_by else None,
                    }
                    for record in attendance_history
                ],
            },
            "question_prompts": [
                {
                    "id": str(prompt.id),
                    "title": prompt.title,
                    "body": prompt.body,
                    "class_name": _class_label(prompt.class_group) if prompt.class_group else "General",
                    "due_date": prompt.due_date,
                    "created_at": prompt.created_at,
                    "is_active": prompt.is_active,
                    "response_text": response_map.get(prompt.id).response_text if response_map.get(prompt.id) else "",
                    "response_updated_at": response_map.get(prompt.id).updated_at if response_map.get(prompt.id) else None,
                    "is_answered": prompt.id in response_map,
                }
                for prompt in question_prompt_list
            ],
            "inbox": [
                _message_payload(item, request=request, viewer=user)
                for item in inbox_qs[:12]
            ],
            "recent_results": recent_results,
            "admin_contacts": [
                {
                    "id": str(item.id),
                    "name": item.get_full_name(),
                    "email": item.email,
                    "role": item.role,
                    "profile_picture": _profile_picture_url(request, item),
                }
                for item in admin_contacts_qs[:10]
            ],
            "recipients": [
                {
                    "id": str(item.id),
                    "name": item.get_full_name(),
                    "email": item.email,
                    "role": item.role,
                    "profile_picture": _profile_picture_url(request, item),
                }
                for item in message_recipients_qs[:100]
            ],
        }
    )


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def mark_attendance(request):
    return Response(
        {"success": False, "message": "Students cannot mark their own attendance. A teacher must mark attendance."},
        status=status.HTTP_403_FORBIDDEN,
    )


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def create_question_prompt(request):
    user = request.user
    if user.role != "teacher":
        return Response(
            {"success": False, "message": "Only teachers can create question prompts."},
            status=status.HTTP_403_FORBIDDEN,
        )

    title = str(request.data.get("title", "")).strip()
    body = str(request.data.get("body", "")).strip()
    if not title or not body:
        return Response(
            {"success": False, "message": "Title and body are required for a prompt."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    class_id = request.data.get("class_id")
    class_group = None
    if class_id:
        class_group = get_object_or_404(
            _scope_to_user_tenant(Class.objects.all(), user),
            id=class_id,
        )

    due_date_raw = request.data.get("due_date")
    due_date = parse_date(str(due_date_raw)) if due_date_raw else None

    tenant_obj = _tenant_for_model(QuestionPrompt, user)
    if not tenant_obj:
        return Response(
            {"success": False, "message": "Unable to resolve tenant for question prompts."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    prompt = QuestionPrompt.objects.create(
        title=title,
        body=body,
        class_group=class_group,
        due_date=due_date,
        created_by=user,
        tenant=tenant_obj,
    )

    return Response(
        {
            "success": True,
            "message": "Question prompt created.",
            "prompt": {
                "id": str(prompt.id),
                "title": prompt.title,
                "body": prompt.body,
                "class_name": _class_label(prompt.class_group) if prompt.class_group else "General",
                "due_date": prompt.due_date,
                "created_at": prompt.created_at,
            },
        },
        status=status.HTTP_201_CREATED,
    )


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def answer_question_prompt(request):
    user = request.user
    if user.role != "student":
        return Response(
            {"success": False, "message": "Only students can answer prompts."},
            status=status.HTTP_403_FORBIDDEN,
        )

    prompt_id = request.data.get("prompt_id")
    response_text = str(request.data.get("response_text", "")).strip()
    if not prompt_id:
        return Response(
            {"success": False, "message": "prompt_id is required."},
            status=status.HTTP_400_BAD_REQUEST,
        )
    if not response_text:
        return Response(
            {"success": False, "message": "response_text is required."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    prompt = get_object_or_404(
        _scope_to_user_tenant(QuestionPrompt.objects.filter(is_active=True), user),
        id=prompt_id,
    )

    response, created = QuestionResponse.objects.update_or_create(
        prompt=prompt,
        student=user,
        defaults={"response_text": response_text},
    )

    return Response(
        {
            "success": True,
            "message": "Response saved.",
            "response": {
                "id": str(response.id),
                "prompt_id": str(prompt.id),
                "response_text": response.response_text,
                "updated_at": response.updated_at,
            },
        }
    )


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def notify_exam_update(request, exam_id):
    user = request.user
    if user.role not in {"teacher", "school_admin"}:
        return Response(
            {"success": False, "message": "Only teachers or administrators can notify students."},
            status=status.HTTP_403_FORBIDDEN,
        )
    if not InAppMessage:
        return Response(
            {"success": False, "message": "Messaging module is not available."},
            status=status.HTTP_503_SERVICE_UNAVAILABLE,
        )

    exams_qs = _scope_to_user_tenant(Exam.objects.select_related("class_group"), user)
    if user.role == "teacher":
        exams_qs = exams_qs.filter(teacher=user)
    exam = get_object_or_404(exams_qs, id=exam_id)

    message = str(request.data.get("message", "")).strip()
    subject = str(request.data.get("subject", "")).strip() or f"Upcoming exam: {exam.title}"
    if not message:
        message = f"Reminder: {subject} is scheduled on {exam.start_date.strftime('%b %d, %Y %I:%M %p')}."

    student_profiles = StudentProfile.objects.filter(
        user__tenant=user.tenant,
        user__is_active=True,
        current_class=exam.class_group,
    ).select_related("user")
    if exam.class_group is None:
        student_profiles = StudentProfile.objects.filter(
            user__tenant=user.tenant,
            user__is_active=True,
        ).select_related("user")

    recipients = [profile.user for profile in student_profiles]
    messages = [
        InAppMessage(
            tenant=user.tenant,
            sender=user,
            recipient=student,
            subject=subject,
            body=message,
        )
        for student in recipients
    ]
    InAppMessage.objects.bulk_create(messages)

    return Response(
        {
            "success": True,
            "message": "Students notified.",
            "sent": len(messages),
        }
    )


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def teacher_dashboard(request):
    user = request.user
    if user.role != "teacher":
        return Response(
            {"success": False, "message": "Only teacher accounts can access this dashboard."},
            status=status.HTTP_403_FORBIDDEN,
        )

    school = _resolve_school_tenant_for_user(user)
    if not school:
        return Response(
            {"success": False, "message": "Your account is not linked to a school."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    now = timezone.now()
    teacher_profile = TeacherProfile.objects.select_related("user").filter(user=user).first()

    exams_qs = _scope_to_user_tenant(
        Exam.objects.select_related("subject", "class_group", "exam_type"),
        user,
    ).filter(teacher=user)
    attempts_qs = _scope_to_user_tenant(
        ExamAttempt.objects.select_related("exam", "exam__subject", "exam__class_group", "student"),
        user,
    ).filter(exam__teacher=user)
    submitted_attempts_qs = attempts_qs.filter(is_submitted=True).prefetch_related("answers__question").order_by("-end_time")
    submitted_attempts = list(submitted_attempts_qs[:20])
    average_percentage = submitted_attempts_qs.aggregate(value=Avg("percentage")).get("value") or 0
    announcements = _visible_announcements_for_user(user, now=now)
    inbox_qs = _tenant_inbox_for_user(user).order_by("-created_at") if InAppMessage else []
    if teacher_profile:
        classes_qs = _teacher_assigned_classes(user).order_by("name", "section")
        subjects_qs = _scope_to_user_tenant(teacher_profile.subjects.all(), user).order_by("name")
    else:
        classes_qs = Class.objects.none()
        subjects_qs = Subject.objects.none()

    question_prompt_qs = _scope_to_user_tenant(
        QuestionPrompt.objects.filter(is_active=True),
        user,
    ).select_related("class_group").prefetch_related(
        Prefetch(
            "responses",
            queryset=QuestionResponse.objects.select_related("student").order_by("-updated_at"),
            to_attr="ordered_responses",
        )
    )
    question_prompts_list = list(question_prompt_qs[:8])

    upcoming_assessments = exams_qs.filter(start_date__gte=now).order_by("start_date")
    subject_names = _subjects_taught_for_teacher(user)
    subjects_payload = (
        [
            {"id": subject.id, "name": subject.name, "code": subject.code}
            for subject in (teacher_profile.subjects.all() if teacher_profile else [])
        ]
        if teacher_profile
        else []
    )
    recipient_contacts = _message_recipient_queryset_for_user(user).order_by("role", "first_name", "last_name", "email")

    return Response(
        {
            "success": True,
            "profile": {
                "id": str(user.id),
                "name": user.get_full_name(),
                "email": user.email,
                "phone": user.phone,
                "profile_picture": _profile_picture_url(request, user),
                "employee_id": teacher_profile.employee_id if teacher_profile else "",
                "specialization": teacher_profile.specialization if teacher_profile else "",
                "qualification": teacher_profile.qualification if teacher_profile else "",
                "subjects_text": teacher_profile.subjects_text if teacher_profile else "",
                "employment_type": teacher_profile.employment_type if teacher_profile else "",
                "years_of_experience": teacher_profile.years_of_experience if teacher_profile else 0,
                "subjects_taught": subject_names,
                "subjects": subjects_payload,
            },
            "school": _school_payload(school, request),
            "metrics": {
                "total_assessments": exams_qs.count(),
                "published_assessments": exams_qs.filter(is_published=True).count(),
                "upcoming_assessments": upcoming_assessments.count(),
                "pending_submissions": attempts_qs.filter(is_submitted=False).count(),
                "unread_inbox": inbox_qs.filter(is_read=False).count() if InAppMessage else 0,
                "tests_created": exams_qs.filter(exam_type__name__iexact="Test").count(),
                "exams_created": exams_qs.exclude(exam_type__name__iexact="Test").count(),
                "submitted_results": submitted_attempts_qs.count(),
                "average_cbt_score": round(float(average_percentage), 1),
            },
            "cbt_results": [
                {
                    "id": attempt.id,
                    "attempt_id": attempt.id,
                    "exam_id": attempt.exam_id,
                    "exam_title": attempt.exam.title,
                    "student_name": attempt.student.get_full_name() or attempt.student.email,
                    "student_email": attempt.student.email,
                    "student_id": getattr(getattr(attempt.student, "student_profile", None), "student_id", ""),
                    "subject": attempt.exam.subject.name if attempt.exam.subject else "General",
                    "subject_id": attempt.exam.subject_id,
                    "class_name": _class_label(attempt.exam.class_group) if attempt.exam.class_group else "All classes",
                    "class_id": attempt.exam.class_group_id,
                    "score": attempt.score,
                    "total_points": attempt.total_points,
                    "percentage": round(float(attempt.percentage or 0), 1),
                    "submitted_at": attempt.end_time,
                    "answer_summary": [
                        {
                            "question": answer.question.text,
                            "selected_answer": answer.selected_options,
                            "correct_answer": answer.question.correct_answer,
                            "is_correct": answer.is_correct,
                            "score": answer.score,
                        }
                        for answer in attempt.answers.all()
                    ],
                }
                for attempt in submitted_attempts
            ],
            "upcoming_assessments": [
                {
                    "id": exam.id,
                    "title": exam.title,
                    "assessment_type": _assessment_type_for_exam(exam),
                    "subject": exam.subject.name if exam.subject else "General",
                    "class_name": _class_label(exam.class_group) if exam.class_group else "All classes",
                    "start_date": exam.start_date,
                    "end_date": exam.end_date,
                    "is_published": exam.is_published,
                }
                for exam in upcoming_assessments[:10]
            ],
            "announcements": [
                {
                    "id": str(item.id),
                    "title": item.title,
                    "priority": item.priority,
                    "published_at": item.publish_from,
                }
                for item in announcements[:4]
            ],
            "inbox": [
                _message_payload(item, request=request, viewer=user)
                for item in inbox_qs[:6]
            ],
            "options": {
                "classes": [
                    {
                        "id": item.id,
                        "name": item.name,
                        "section": item.section or "",
                        "label": _class_label(item),
                    }
                    for item in classes_qs[:100]
                ],
                "subjects": [
                    {
                        "id": item.id,
                        "name": item.name,
                        "code": item.code,
                    }
                    for item in subjects_qs[:100]
                ],
            },
            "recipients": [
                {
                    "id": str(item.id),
                    "name": item.get_full_name(),
                    "email": item.email,
                    "role": item.role,
                    "profile_picture": _profile_picture_url(request, item),
                }
                for item in recipient_contacts[:100]
            ],
            "question_prompts": [
                {
                    "id": str(prompt.id),
                    "title": prompt.title,
                    "class_name": _class_label(prompt.class_group) if prompt.class_group else "General",
                    "class_id": prompt.class_group_id,
                    "due_date": prompt.due_date,
                    "created_at": prompt.created_at,
                    "response_count": len(getattr(prompt, "ordered_responses", [])),
                    "latest_responses": [
                        {
                            "student": response.student.get_full_name(),
                            "updated_at": response.updated_at,
                        }
                        for response in getattr(prompt, "ordered_responses", [])[:3]
                    ],
                }
                for prompt in question_prompts_list
            ],
        }
    )


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def students_snapshot(request):
    user = request.user
    students = (
        StudentProfile.objects.select_related("user", "current_class")
        .filter(user__tenant=user.tenant)
        .order_by("-created_at")
    )
    classes_qs = _scope_to_user_tenant(Class.objects.all(), user).order_by("name", "section")

    total = students.count()
    with_guardian_phone = students.exclude(guardian_phone="").count()
    without_class = students.filter(current_class__isnull=True).count()

    return Response(
        {
            "success": True,
            "summary": {
                "total_students": total,
                "with_guardian_phone": with_guardian_phone,
                "without_class": without_class,
            },
            "students": [_student_payload(student, request=request) for student in students[:12]],
            "options": {
                "classes": [
                    {
                        "id": class_obj.id,
                        "label": _class_label(class_obj),
                    }
                    for class_obj in classes_qs[:100]
                ],
            },
        }
    )


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def documents_snapshot(request):
    from finance.services import get_or_create_activation_credit_pool
    
    user = request.user
    if user.role not in ADMIN_ROLES:
        return Response(
            {"success": False, "message": "Only administrators can manage transcripts and testimonials."},
            status=status.HTTP_403_FORBIDDEN,
        )
    if not user.tenant:
        return Response(
            {"success": False, "message": "Your account is not linked to a school."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    students = (
        StudentProfile.objects.select_related("user", "current_class")
        .filter(user__tenant=user.tenant)
        .order_by("user__last_name", "user__first_name")
    )
    eligible_count = 0
    student_payloads = []
    for student in students[:200]:
        payload = _student_document_payload(student, request=request)
        if payload["is_testimonial_eligible"]:
            eligible_count += 1
        student_payloads.append(payload)

    # Get credit balance for document generation
    credit_pool = get_or_create_activation_credit_pool(user.tenant)
    credit_balance = credit_pool.balance if credit_pool else 0

    return Response(
        {
            "success": True,
            "school": _school_payload(user.tenant, request),
            "summary": {
                "total_students": students.count(),
                "testimonial_eligible": eligible_count,
                "transcripts_ready": students.count(),
            },
            "credit_balance": credit_balance,
            "students": student_payloads,
        }
    )


@api_view(["GET", "PATCH"])
@permission_classes([IsAuthenticated])
def transcript_detail(request, student_id):
    from finance.services import deduct_document_generation_credit
    
    user = request.user
    if user.role not in ADMIN_ROLES:
        return Response(
            {"success": False, "message": "Only administrators can generate transcripts."},
            status=status.HTTP_403_FORBIDDEN,
        )
    student_profile = get_object_or_404(
        StudentProfile.objects.select_related("user", "current_class"),
        id=student_id,
        user__tenant=user.tenant,
    )
    
    should_generate = request.method == "GET" and request.query_params.get("generate") == "true"

    token_charged = False
    if should_generate:
        try:
            credit_pool = deduct_document_generation_credit(
                tenant=user.tenant,
                document_type="transcript",
                student_profile=student_profile,
                action="generate",
                actor=user,
                credits=1,
            )
            token_charged = bool(getattr(credit_pool, "document_credit_charged", True))
        except ValueError as exc:
            return Response(
                {"success": False, "message": str(exc)},
                status=status.HTTP_402_PAYMENT_REQUIRED,
            )
    
    if request.method == "PATCH":
        records = request.data.get("scores")
        if not isinstance(records, list):
            return Response(
                {"success": False, "message": "scores must be a list of transcript rows."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        for record in records:
            if not isinstance(record, dict) or not record.get("id"):
                continue
            score_obj = StudentSubjectScore.objects.filter(
                id=record.get("id"),
                student=student_profile,
                student__user__tenant=user.tenant,
            ).first()
            if not score_obj:
                continue
            update_fields = []
            if "score" in record:
                try:
                    score_obj.score = Decimal(str(record.get("score") or 0))
                except (InvalidOperation, TypeError, ValueError):
                    return Response({"success": False, "message": "score must be a valid number."}, status=status.HTTP_400_BAD_REQUEST)
                update_fields.append("score")
            if "max_score" in record:
                try:
                    max_score = Decimal(str(record.get("max_score") or 0))
                except (InvalidOperation, TypeError, ValueError):
                    return Response({"success": False, "message": "max_score must be a valid number."}, status=status.HTTP_400_BAD_REQUEST)
                if max_score <= 0:
                    return Response({"success": False, "message": "max_score must be greater than zero."}, status=status.HTTP_400_BAD_REQUEST)
                score_obj.max_score = max_score
                update_fields.append("max_score")
            if "grade" in record:
                score_obj.grade = str(record.get("grade") or "").strip()[:5]
                update_fields.append("grade")
            if "remark" in record or "remarks" in record:
                remark = str(record.get("remark", record.get("remarks", "")) or "").strip()
                score_obj.performance_remark = remark[:120]
                score_obj.remarks = remark
                update_fields.extend(["performance_remark", "remarks"])
            if "score" in record or "max_score" in record:
                percentage = score_obj.percentage
                if percentage is not None and "grade" not in record and "remark" not in record and "remarks" not in record:
                    grade_letter, grade_remark = _grade_for_percentage(user, percentage)
                    score_obj.grade = grade_letter
                    score_obj.performance_remark = grade_remark
                    update_fields.extend(["grade", "performance_remark"])
            if update_fields:
                score_obj.save(update_fields=sorted(set([*update_fields, "updated_at"])))
        return Response(
            {
                "success": True,
                "message": "Transcript details saved.",
                "transcript": _transcript_payload(student_profile, request=request),
            }
        )
    return Response({
        "success": True,
        "message": ("1 token used to generate transcript." if token_charged else "Transcript generated. No token used because this student's transcript was already generated.") if should_generate else "Transcript preview loaded.",
        "token_used": token_charged,
        "tokens_used": 1 if token_charged else 0,
        "document_type": "transcript",
        "transcript": _transcript_payload(student_profile, request=request),
    })


@api_view(["GET", "PATCH"])
@permission_classes([IsAuthenticated])
def testimonial_detail(request, student_id):
    from finance.services import deduct_document_generation_credit
    
    user = request.user
    if user.role not in ADMIN_ROLES:
        return Response(
            {"success": False, "message": "Only administrators can manage testimonials."},
            status=status.HTTP_403_FORBIDDEN,
        )
    student_profile = get_object_or_404(
        StudentProfile.objects.select_related("user", "current_class"),
        id=student_id,
        user__tenant=user.tenant,
    )
    if not _is_terminal_testimonial_class(_class_label(student_profile.current_class) if student_profile.current_class else ""):
        return Response(
            {"success": False, "message": "Testimonials are strictly available only for JSS3 and SSS3 students."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    should_generate = request.method == "GET" and request.query_params.get("generate") == "true"

    token_charged = False
    if should_generate:
        try:
            credit_pool = deduct_document_generation_credit(
                tenant=user.tenant,
                document_type="testimonial",
                student_profile=student_profile,
                action="generate",
                actor=user,
                credits=1,
            )
            token_charged = bool(getattr(credit_pool, "document_credit_charged", True))
        except ValueError as exc:
            return Response(
                {"success": False, "message": str(exc)},
                status=status.HTTP_402_PAYMENT_REQUIRED,
            )

    record = StudentTestimonial.objects.filter(student=student_profile, school=user.tenant).first()
    if request.method == "PATCH":
        record, created = StudentTestimonial.objects.get_or_create(
            student=student_profile,
            defaults={"school": user.tenant, "created_by": user},
        )
        field_names = [
            "class_of_admission",
            "class_of_leaving",
            "reason_for_leaving",
            "educational_attainment",
            "subjects_offered",
            "co_curricular_activities",
            "prizes_and_honors",
            "office_held",
            "administrator_remarks",
            "principal_name",
        ]
        for field_name in field_names:
            if field_name in request.data:
                setattr(record, field_name, str(request.data.get(field_name) or "").strip())
        for field_name in ["date_of_leaving", "issue_date"]:
            if field_name in request.data:
                raw_value = str(request.data.get(field_name) or "").strip()
                setattr(record, field_name, parse_date(raw_value) if raw_value else None)
        record.school = user.tenant
        record.updated_by = user
        record.save()

    payload = {
        "school": _school_payload(user.tenant, request),
        "student": _student_document_payload(student_profile, request=request),
        "testimonial": _testimonial_payload(record, student_profile, request=request),
    }
    return Response({
        "success": True,
        "message": ("1 token used to generate testimonial." if token_charged else "Testimonial generated. No token used because this student's testimonial was already generated.") if should_generate else ("Testimonial preview loaded." if request.method == "GET" else "Testimonial details saved."),
        "token_used": token_charged,
        "tokens_used": 1 if token_charged else 0,
        "document_type": "testimonial",
        **payload,
    })


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def create_student(request):
    user = request.user
    if not user.tenant:
        return Response(
            {"success": False, "message": "Your account is not linked to a school."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    student_email = str(request.data.get("student_email") or request.data.get("email") or "").strip().lower()
    if not student_email:
        return Response(
            {"success": False, "message": "student_email is required."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    first_name = str(request.data.get("first_name", "")).strip()
    last_name = str(request.data.get("last_name", "")).strip()
    guardian_name = str(request.data.get("guardian_name", "")).strip()
    guardian_phone = str(request.data.get("guardian_phone", "")).strip()
    guardian_email = str(request.data.get("guardian_email", "")).strip()
    guardian_relation = str(request.data.get("guardian_relation", "")).strip() or "Guardian"
    second_guardian_name = str(request.data.get("second_guardian_name", "")).strip()
    second_guardian_phone = str(request.data.get("second_guardian_phone", "")).strip()
    second_guardian_email = str(request.data.get("second_guardian_email", "")).strip()
    second_guardian_relation = str(request.data.get("second_guardian_relation", "")).strip()
    state_of_origin = str(request.data.get("state_of_origin", "")).strip()
    local_government = str(request.data.get("local_government", "")).strip()
    gender = str(request.data.get("gender", "")).strip()
    disability = str(request.data.get("disability", "no")).strip() or "no"
    medical_records = str(request.data.get("medical_records", "")).strip()
    blood_group = str(request.data.get("blood_group", "")).strip()
    student_type = str(request.data.get("student_type", "")).strip()
    home_address = str(request.data.get("home_address", "")).strip()
    date_of_birth_raw = str(request.data.get("date_of_birth", "")).strip()
    if gender and gender not in {"M", "F", "O", "N"}:
        return Response(
            {"success": False, "message": "gender must be one of M, F, O, or N."},
            status=status.HTTP_400_BAD_REQUEST,
        )
    student_password = str(request.data.get("student_password", "")).strip()
    confirm_student_password = str(request.data.get("confirm_student_password", "")).strip()
    profile_picture = request.FILES.get("profile_picture")
    class_id = request.data.get("class_id")
    admission_date_raw = str(request.data.get("admission_date", "")).strip()
    try:
        student_profile = _ensure_student_profile_for_tenant(
            user=user,
            email=student_email,
            first_name=first_name,
            last_name=last_name,
            guardian_name=guardian_name,
            guardian_phone=guardian_phone,
            guardian_email=guardian_email,
            guardian_relation=guardian_relation,
            second_guardian_name=second_guardian_name,
            second_guardian_phone=second_guardian_phone,
            second_guardian_email=second_guardian_email,
            second_guardian_relation=second_guardian_relation,
            state_of_origin=state_of_origin,
            local_government=local_government,
            disability=disability,
            medical_records=medical_records,
            blood_group=blood_group,
            student_type=student_type,
            home_address=home_address,
            profile_picture=profile_picture,
            student_password=student_password,
            confirm_student_password=confirm_student_password,
        )
        try:
            ensure_student_wallet(student_profile.user)
        except Exception:
            pass
    except ValueError as exc:
        return Response(
            {"success": False, "message": str(exc)},
            status=status.HTTP_400_BAD_REQUEST,
        )

    student_user = student_profile.user
    user_update_fields = []
    if first_name and student_user.first_name != first_name:
        student_user.first_name = first_name
        user_update_fields.append("first_name")
    if last_name and student_user.last_name != last_name:
        student_user.last_name = last_name
        user_update_fields.append("last_name")
    if gender in {"M", "F", "O", "N"} and student_user.gender != gender:
        student_user.gender = gender
        user_update_fields.append("gender")
    if date_of_birth_raw:
        date_of_birth = parse_date(date_of_birth_raw)
        if not date_of_birth:
            return Response(
                {"success": False, "message": "date_of_birth must be in YYYY-MM-DD format."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if student_user.date_of_birth != date_of_birth:
            student_user.date_of_birth = date_of_birth
            user_update_fields.append("date_of_birth")
    if user_update_fields:
        student_user.save(update_fields=user_update_fields)

    profile_update_fields = []
    if guardian_name and student_profile.guardian_name != guardian_name:
        student_profile.guardian_name = guardian_name
        profile_update_fields.append("guardian_name")
    if guardian_phone and student_profile.guardian_phone != guardian_phone:
        student_profile.guardian_phone = guardian_phone
        profile_update_fields.append("guardian_phone")
    if guardian_email and student_profile.guardian_email != guardian_email:
        student_profile.guardian_email = guardian_email
        profile_update_fields.append("guardian_email")
    if guardian_relation and student_profile.guardian_relation != guardian_relation:
        student_profile.guardian_relation = guardian_relation
        profile_update_fields.append("guardian_relation")
    secondary_guardian_values = {
        "second_guardian_name": second_guardian_name,
        "second_guardian_phone": second_guardian_phone,
        "second_guardian_email": second_guardian_email,
        "second_guardian_relation": second_guardian_relation,
    }
    for field_name, next_value in secondary_guardian_values.items():
        if next_value and getattr(student_profile, field_name) != next_value:
            setattr(student_profile, field_name, next_value)
            profile_update_fields.append(field_name)
    if state_of_origin and student_profile.state_of_origin != state_of_origin:
        student_profile.state_of_origin = state_of_origin
        profile_update_fields.append("state_of_origin")
    if local_government and student_profile.local_government != local_government:
        student_profile.local_government = local_government
        profile_update_fields.append("local_government")
    for field, value in {
        "disability": disability,
        "medical_conditions": medical_records,
        "blood_group": blood_group,
        "student_type": student_type,
        "home_address": home_address,
    }.items():
        if value and getattr(student_profile, field) != value:
            setattr(student_profile, field, value)
            profile_update_fields.append(field)

    if class_id not in (None, ""):
        assigned_class = get_object_or_404(_scope_to_user_tenant(Class.objects.all(), user), id=class_id)
        if student_profile.current_class_id != assigned_class.id:
            student_profile.current_class = assigned_class
            profile_update_fields.append("current_class")

    if admission_date_raw:
        admission_date = parse_date(admission_date_raw)
        if not admission_date:
            return Response(
                {"success": False, "message": "admission_date must be in YYYY-MM-DD format."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if student_profile.admission_date != admission_date:
            student_profile.admission_date = admission_date
            profile_update_fields.append("admission_date")

    if profile_update_fields:
        student_profile.save(update_fields=profile_update_fields)

    student_profile.refresh_from_db()
    return Response(
        {
            "success": True,
            "message": "Student saved.",
            "student": _student_payload(student_profile, request=request),
        },
        status=status.HTTP_201_CREATED,
    )


@api_view(["PATCH", "DELETE"])
@permission_classes([IsAuthenticated])
def student_detail(request, student_id):
    user = request.user
    student_profile = get_object_or_404(
        StudentProfile.objects.select_related("user", "current_class").filter(user__tenant=user.tenant),
        id=student_id,
    )
    student_user = student_profile.user

    if request.method == "DELETE":
        student_user.delete()
        return Response({"success": True, "message": "Student deleted."})

    user_update_fields = []
    profile_update_fields = []

    if "email" in request.data:
        new_email = str(request.data.get("email", "")).strip().lower()
        if not new_email:
            return Response(
                {"success": False, "message": "email cannot be blank."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        email_taken = User.objects.filter(email__iexact=new_email).exclude(id=student_user.id).exists()
        if email_taken:
            return Response(
                {"success": False, "message": "A user with this email already exists."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if student_user.email != new_email:
            student_user.email = new_email
            user_update_fields.append("email")

    if "gender" in request.data:
        gender = str(request.data.get("gender") or "").strip()
        if gender and gender not in {"M", "F", "O", "N"}:
            return Response(
                {"success": False, "message": "gender must be one of M, F, O, or N."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        normalized_gender = gender or None
        if student_user.gender != normalized_gender:
            student_user.gender = normalized_gender
            user_update_fields.append("gender")

    for field in ("first_name", "last_name", "phone"):
        if field in request.data:
            new_value = str(request.data.get(field) or "").strip()
            if getattr(student_user, field) != new_value:
                setattr(student_user, field, new_value)
                user_update_fields.append(field)

    if "is_active" in request.data:
        new_active = _to_bool(request.data.get("is_active"), default=student_user.is_active)
        if student_user.is_active != new_active:
            student_user.is_active = new_active
            user_update_fields.append("is_active")

    if "student_password" in request.data or "confirm_student_password" in request.data:
        new_password = str(request.data.get("student_password") or "").strip()
        confirm_password = str(request.data.get("confirm_student_password") or "").strip()
        if not new_password and not confirm_password:
            return Response(
                {"success": False, "message": "student_password is required when updating a password."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            validated_password = _validate_student_password(new_password, confirm_password)
        except ValueError as exc:
            return Response(
                {"success": False, "message": str(exc)},
                status=status.HTTP_400_BAD_REQUEST,
            )
        student_user.set_password(validated_password)
        user_update_fields.append("password")

    profile_picture = request.FILES.get("profile_picture")
    if profile_picture:
        student_user.profile_picture = profile_picture
        user_update_fields.append("profile_picture")

    if "guardian_name" in request.data:
        new_guardian_name = str(request.data.get("guardian_name") or "").strip()
        if not new_guardian_name:
            return Response(
                {"success": False, "message": "guardian_name cannot be blank."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if student_profile.guardian_name != new_guardian_name:
            student_profile.guardian_name = new_guardian_name
            profile_update_fields.append("guardian_name")

    if "guardian_phone" in request.data:
        new_guardian_phone = str(request.data.get("guardian_phone") or "").strip()
        if student_profile.guardian_phone != new_guardian_phone:
            student_profile.guardian_phone = new_guardian_phone
            profile_update_fields.append("guardian_phone")

    guardian_optional_fields = [
        "guardian_email",
        "guardian_relation",
        "second_guardian_name",
        "second_guardian_phone",
        "second_guardian_email",
        "second_guardian_relation",
    ]
    for field_name in guardian_optional_fields:
        if field_name in request.data:
            new_value = str(request.data.get(field_name) or "").strip()
            if field_name == "guardian_relation" and not new_value:
                new_value = "Guardian"
            if getattr(student_profile, field_name) != new_value:
                setattr(student_profile, field_name, new_value)
                profile_update_fields.append(field_name)

    if "state_of_origin" in request.data:
        new_state_of_origin = str(request.data.get("state_of_origin") or "").strip()
        if student_profile.state_of_origin != new_state_of_origin:
            student_profile.state_of_origin = new_state_of_origin
            profile_update_fields.append("state_of_origin")

    if "local_government" in request.data:
        new_local_government = str(request.data.get("local_government") or "").strip()
        if student_profile.local_government != new_local_government:
            student_profile.local_government = new_local_government
            profile_update_fields.append("local_government")

    if "date_of_birth" in request.data:
        raw_date_of_birth = str(request.data.get("date_of_birth") or "").strip()
        date_of_birth = parse_date(raw_date_of_birth) if raw_date_of_birth else None
        if raw_date_of_birth and not date_of_birth:
            return Response(
                {"success": False, "message": "date_of_birth must be in YYYY-MM-DD format."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if student_user.date_of_birth != date_of_birth:
            student_user.date_of_birth = date_of_birth
            user_update_fields.append("date_of_birth")

    profile_field_map = {
        "disability": "disability",
        "medical_records": "medical_conditions",
        "blood_group": "blood_group",
        "student_type": "student_type",
        "home_address": "home_address",
    }
    for payload_field, model_field in profile_field_map.items():
        if payload_field in request.data:
            next_value = str(request.data.get(payload_field) or "").strip()
            if getattr(student_profile, model_field) != next_value:
                setattr(student_profile, model_field, next_value)
                profile_update_fields.append(model_field)

    if "class_id" in request.data:
        raw_class_id = request.data.get("class_id")
        if raw_class_id in (None, ""):
            if student_profile.current_class_id is not None:
                student_profile.current_class = None
                profile_update_fields.append("current_class")
        else:
            assigned_class = get_object_or_404(_scope_to_user_tenant(Class.objects.all(), user), id=raw_class_id)
            if student_profile.current_class_id != assigned_class.id:
                student_profile.current_class = assigned_class
                profile_update_fields.append("current_class")

    if "admission_date" in request.data:
        raw_admission_date = str(request.data.get("admission_date") or "").strip()
        if not raw_admission_date:
            return Response(
                {"success": False, "message": "admission_date cannot be blank."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        admission_date = parse_date(raw_admission_date)
        if not admission_date:
            return Response(
                {"success": False, "message": "admission_date must be in YYYY-MM-DD format."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if student_profile.admission_date != admission_date:
            student_profile.admission_date = admission_date
            profile_update_fields.append("admission_date")

    if user_update_fields:
        student_user.save(update_fields=sorted(set(user_update_fields)))
    if profile_update_fields:
        student_profile.save(update_fields=sorted(set(profile_update_fields)))

    student_profile.refresh_from_db()
    return Response(
        {
            "success": True,
            "message": "Student updated.",
            "student": _student_payload(student_profile, request=request),
        }
    )


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def enrollments_snapshot(request):
    user = request.user
    if not user.tenant:
        return Response(
            {"success": False, "message": "Your account is not linked to a school."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    enrollments = (
        StudentEnrollment.objects.filter(school=user.tenant)
        .select_related("student__user", "assigned_class", "created_by", "school", "enrollment_message")
        .prefetch_related("exams")
        .order_by("-created_at")
    )
    classes_qs = _scope_to_user_tenant(Class.objects.all(), user)
    exams_qs = _scope_to_user_tenant(Exam.objects.all(), user)
    students_qs = StudentProfile.objects.filter(user__tenant=user.tenant).select_related("user").order_by("user__email")

    return Response(
        {
            "success": True,
            "summary": {
                "total_enrollments": enrollments.count(),
                "students_with_enrollment": enrollments.values("student_id").distinct().count(),
                "enrollments_with_class": enrollments.exclude(assigned_class__isnull=True).count(),
                "enrollments_with_exam": enrollments.filter(exams__isnull=False).distinct().count(),
            },
            "enrollments": [_enrollment_payload(item, request=request) for item in enrollments[:25]],
            "options": {
                "students": [
                    {
                        "id": str(student.id),
                        "name": student.user.get_full_name(),
                        "email": student.user.email,
                        "profile_picture": _profile_picture_url(request, student.user),
                        "student_id": student.student_id,
                    }
                    for student in students_qs[:100]
                ],
                "classes": [
                    {
                        "id": class_obj.id,
                        "label": _class_label(class_obj),
                    }
                    for class_obj in classes_qs.order_by("name", "section")[:100]
                ],
                "exams": [
                    {
                        "id": exam.id,
                        "title": exam.title,
                    }
                    for exam in exams_qs.order_by("-start_date", "title")[:100]
                ],
            },
        }
    )


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def create_enrollment(request):
    user = request.user
    if not user.tenant:
        return Response(
            {"success": False, "message": "Your account is not linked to a school."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    student_profile = None
    profile_picture = request.FILES.get("profile_picture")
    student_id = request.data.get("student_id")
    if student_id:
        student_profile = get_object_or_404(
            StudentProfile.objects.select_related("user").filter(user__tenant=user.tenant),
            id=student_id,
        )
        if profile_picture:
            student_profile.user.profile_picture = profile_picture
            student_profile.user.save(update_fields=["profile_picture"])
    else:
        email = str(request.data.get("student_email", "")).strip().lower()
        if not email:
            return Response(
                {"success": False, "message": "student_id or student_email is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        student_password = str(request.data.get("student_password", "")).strip()
        confirm_student_password = str(request.data.get("confirm_student_password", "")).strip()

        try:
            student_profile = _ensure_student_profile_for_tenant(
                user=user,
                email=email,
                first_name=str(request.data.get("first_name", "")).strip(),
                last_name=str(request.data.get("last_name", "")).strip(),
                guardian_name=str(request.data.get("guardian_name", "")).strip(),
                guardian_phone=str(request.data.get("guardian_phone", "")).strip(),
                guardian_email=str(request.data.get("guardian_email", "")).strip(),
                guardian_relation=str(request.data.get("guardian_relation", "")).strip() or "Guardian",
                second_guardian_name=str(request.data.get("second_guardian_name", "")).strip(),
                second_guardian_phone=str(request.data.get("second_guardian_phone", "")).strip(),
                second_guardian_email=str(request.data.get("second_guardian_email", "")).strip(),
                second_guardian_relation=str(request.data.get("second_guardian_relation", "")).strip(),
                profile_picture=profile_picture,
                student_password=student_password,
                confirm_student_password=confirm_student_password,
            )
        except ValueError as exc:
            return Response(
                {"success": False, "message": str(exc)},
                status=status.HTTP_400_BAD_REQUEST,
            )

    assigned_class = None
    class_id = request.data.get("class_id")
    if class_id not in (None, ""):
        assigned_class = get_object_or_404(_scope_to_user_tenant(Class.objects.all(), user), id=class_id)

    exam_ids = request.data.get("exam_ids")
    if hasattr(request.data, "getlist"):
        listed = [item for item in request.data.getlist("exam_ids") if str(item).strip()]
        if listed:
            exam_ids = listed
    if exam_ids in (None, ""):
        exam_ids = []
    if isinstance(exam_ids, str):
        exam_ids = [item.strip() for item in exam_ids.split(",") if item.strip()]
    if not isinstance(exam_ids, list):
        return Response(
            {"success": False, "message": "exam_ids must be an array or comma-separated string."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    normalized_exam_ids = []
    for raw_exam_id in exam_ids:
        try:
            normalized_exam_ids.append(int(str(raw_exam_id).strip()))
        except Exception:
            return Response(
                {"success": False, "message": "exam_ids must contain numeric exam IDs."},
                status=status.HTTP_400_BAD_REQUEST,
            )
    normalized_exam_ids = sorted(set(normalized_exam_ids))

    valid_exam_qs = _scope_to_user_tenant(Exam.objects.all(), user).filter(id__in=normalized_exam_ids)
    valid_exam_ids = list(valid_exam_qs.values_list("id", flat=True))
    if normalized_exam_ids and len(valid_exam_ids) != len(normalized_exam_ids):
        return Response(
            {"success": False, "message": "One or more exam_ids are invalid for this school."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    enrollment = StudentEnrollment.objects.create(
        school=user.tenant,
        student=student_profile,
        assigned_class=assigned_class,
        created_by=user,
        welcome_subject=str(request.data.get("welcome_subject", "")).strip() or "Enrollment update",
        welcome_message=str(request.data.get("welcome_message", "")).strip(),
    )
    if valid_exam_ids:
        enrollment.exams.set(valid_exam_ids)

    enrollment.apply_links()
    enrollment.refresh_from_db()
    enrollment = (
        StudentEnrollment.objects.filter(pk=enrollment.pk)
        .select_related("student__user", "assigned_class", "created_by", "school", "enrollment_message")
        .prefetch_related("exams")
        .first()
    )

    return Response(
        {
            "success": True,
            "message": "Enrollment created and linked successfully.",
            "enrollment": _enrollment_payload(enrollment, request=request),
        },
        status=status.HTTP_201_CREATED,
    )


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def teachers_snapshot(request):
    user = request.user
    if not user.tenant:
        return Response(
            {"success": False, "message": "Your account is not linked to a school."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    teachers = (
        TeacherProfile.objects.select_related("user")
        .prefetch_related("subjects", "assigned_classes")
        .filter(user__tenant=user.tenant)
        .order_by("-created_at")
    )

    return Response(
        {
            "success": True,
            "summary": {
                "total_teachers": teachers.count(),
                "active_teachers": teachers.filter(user__is_active=True).count(),
                "full_time_teachers": teachers.filter(employment_type="full_time").count(),
                "with_specialization": teachers.exclude(specialization="").exclude(
                    specialization__iexact="Not specified"
                ).count(),
            },
            "teachers": [_teacher_payload(item, request=request) for item in teachers[:25]],
            "options": {
                "employment_types": [
                    {"value": value, "label": label}
                    for value, label in TeacherProfile.EMPLOYMENT_TYPES
                ],
                "subjects": [
                    {"id": item.id, "name": item.name, "code": item.code}
                    for item in _scope_to_user_tenant(Subject.objects.all(), user)[:200]
                ],
                "classes": [
                    {"id": item.id, "name": item.name, "section": item.section, "label": _class_label(item)}
                    for item in _scope_to_user_tenant(Class.objects.all(), user).order_by("name", "section")[:200]
                ],
            },
        }
    )


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def id_cards_snapshot(request):
    user = request.user
    if user.role not in ADMIN_ROLES:
        return Response(
            {"success": False, "message": "Only administrators can generate ID cards."},
            status=status.HTTP_403_FORBIDDEN,
        )
    if not user.tenant:
        return Response(
            {"success": False, "message": "Your account is not linked to a school."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    students = (
        StudentProfile.objects.select_related("user", "current_class")
        .filter(user__tenant=user.tenant)
        .order_by("user__first_name", "user__last_name")[:500]
    )
    teachers = (
        TeacherProfile.objects.select_related("user")
        .prefetch_related("subjects", "assigned_classes")
        .filter(user__tenant=user.tenant)
        .order_by("user__first_name", "user__last_name")[:500]
    )
    teacher_user_ids = {item.user_id for item in teachers}
    staff_people = []
    if StaffProfile is not None:
        staff_people = [
            _id_card_staff_payload(item, request=request)
            for item in StaffProfile.objects.select_related("user")
            .filter(tenant=user.tenant)
            .exclude(user_id__in=teacher_user_ids)
            .order_by("first_name", "last_name")[:500]
        ]

    people = [
        *[_id_card_student_payload(item, request=request) for item in students],
        *[_id_card_teacher_payload(item, request=request) for item in teachers],
        *staff_people,
    ]

    return Response(
        {
            "success": True,
            "school": _school_identity_payload(user.tenant, request=request),
            "summary": {
                "students": len([item for item in people if item["person_type"] == "student"]),
                "teaching_staff": len([item for item in people if item["person_type"] == "teacher"]),
                "other_staff": len([item for item in people if item["person_type"] == "staff"]),
                "total": len(people),
            },
            "people": people,
        }
    )


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def id_card_qr_code(request):
    from finance.services import deduct_document_generation_credit
    
    user = request.user
    if user.role not in ADMIN_ROLES:
        return Response(
            {"success": False, "message": "Only administrators can generate ID card QR codes."},
            status=status.HTTP_403_FORBIDDEN,
        )
    person = _resolve_id_card_person(
        user,
        request.query_params.get("person_type"),
        request.query_params.get("person_id"),
        request=request,
    )
    if not person:
        return Response({"success": False, "message": "ID card profile not found."}, status=status.HTTP_404_NOT_FOUND)

    # Only deduct credit if this is for download, not preview
    is_download = request.query_params.get("download") == "true"
    token_charged = False
    if is_download:
        try:
            # Find the student/teacher profile if available
            student_profile = None
            if person["person_type"] == "student":
                student_profile = StudentProfile.objects.filter(id=person["id"], user__tenant=user.tenant).first()
            
            credit_pool = deduct_document_generation_credit(
                tenant=user.tenant,
                document_type="id_card",
                student_profile=student_profile,
                action="generate_qr",
                actor=user,
                credits=1,
            )
            token_charged = bool(getattr(credit_pool, "document_credit_charged", True))
        except ValueError as exc:
            return Response(
                {"success": False, "message": str(exc)},
                status=status.HTTP_402_PAYMENT_REQUIRED,
            )

    payload = {
        "tenant_id": str(user.tenant_id),
        "person_type": person["person_type"],
        "person_id": person["id"],
        "unique_id": person["unique_id"],
    }
    token = signing.dumps(payload, salt=ID_CARD_SIGNING_SALT, compress=True)
    verify_url = _build_id_card_verify_url(request, token)

    qr = qrcode.QRCode(error_correction=qrcode.constants.ERROR_CORRECT_M, box_size=10, border=3)
    qr.add_data(verify_url)
    qr.make(fit=True)
    image = qr.make_image(fill_color="#08111f", back_color="white")
    image_io = io.BytesIO()
    image.save(image_io, "PNG")
    image_io.seek(0)
    response = FileResponse(image_io, content_type="image/png")
    response["Content-Disposition"] = f'inline; filename="{person["unique_id"]}_id_card_qr.png"'
    if is_download:
        response["X-Token-Used"] = "1" if token_charged else "0"
        response["X-Token-Message"] = "1 token used to generate ID card." if token_charged else "ID card generated. No token used because this student's ID card was already generated."
    return response


@api_view(["GET", "POST"])
@permission_classes([AllowAny])
def id_card_verify(request):
    token = str(request.query_params.get("token") or request.data.get("token") or "").strip()
    if not token:
        return Response({"success": False, "message": "Verification token is required."}, status=status.HTTP_400_BAD_REQUEST)
    try:
        payload = signing.loads(token, salt=ID_CARD_SIGNING_SALT, max_age=60 * 60 * 24 * 365 * 10)
    except SignatureExpired:
        return Response({"success": False, "message": "This ID card verification token has expired."}, status=status.HTTP_400_BAD_REQUEST)
    except BadSignature:
        return Response({"success": False, "message": "Invalid ID card verification token."}, status=status.HTTP_400_BAD_REQUEST)
    tenant = SchoolTenant.objects.filter(id=payload.get("tenant_id"), is_active=True).first()
    if not tenant:
        return Response({"success": False, "message": "School could not be verified."}, status=status.HTTP_404_NOT_FOUND)
    person = _resolve_id_card_person_for_tenant(
        tenant,
        payload.get("person_type"),
        payload.get("person_id"),
        request=request,
    )
    if not person or str(person.get("unique_id") or "") != str(payload.get("unique_id") or ""):
        return Response({"success": False, "message": "ID card profile could not be verified."}, status=status.HTTP_404_NOT_FOUND)

    if request.method == "GET":
        return Response(
            {
                "success": True,
                "challenge_required": True,
                "verified": False,
                "message": "Enter the email and ID on the card to verify this profile.",
                "school": _school_identity_payload(tenant, request=request),
                "challenge": _id_card_challenge_payload(person),
            }
        )

    email = str(request.data.get("email") or "").strip()
    unique_id = str(request.data.get("unique_id") or request.data.get("student_id") or request.data.get("staff_id") or "").strip()
    if not email or not unique_id:
        return Response(
            {"success": False, "message": "Email and ID are required to verify this card."},
            status=status.HTTP_400_BAD_REQUEST,
        )
    if not _id_card_credentials_match(person, email, unique_id):
        return Response(
            {"success": False, "message": "Email and ID do not match this card."},
            status=status.HTTP_403_FORBIDDEN,
        )

    is_active = bool(person.get("is_active"))
    return Response(
        {
            "success": True,
            "verified": True,
            "active": is_active,
            "valid": is_active,
            "status": "active" if is_active else "inactive",
            "message": "ID card verified." if is_active else "ID card belongs to this school, but the profile is inactive.",
            "school": _school_identity_payload(tenant, request=request),
            "person": _public_id_card_verification_person(person),
        }
    )


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def create_teacher(request):
    user = request.user
    if not user.tenant:
        return Response(
            {"success": False, "message": "Your account is not linked to a school."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    teacher_email = str(request.data.get("teacher_email") or request.data.get("email") or "").strip().lower()
    if not teacher_email:
        return Response(
            {"success": False, "message": "teacher_email is required."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    first_name = str(request.data.get("first_name", "")).strip()
    last_name = str(request.data.get("last_name", "")).strip()
    phone = str(request.data.get("phone", "")).strip()
    gender = str(request.data.get("gender", "")).strip()
    if gender and gender not in {"M", "F", "O", "N"}:
        return Response(
            {"success": False, "message": "gender must be one of M, F, O, or N."},
            status=status.HTTP_400_BAD_REQUEST,
        )
    profile_picture = request.FILES.get("profile_picture")
    teacher_password = request.data.get("teacher_password", request.data.get("password"))
    confirm_teacher_password = request.data.get("confirm_teacher_password", request.data.get("confirm_password"))
    teacher_password = str(teacher_password or "").strip() or None
    confirm_teacher_password = str(confirm_teacher_password or "").strip() or None

    try:
        teacher_user = _ensure_teacher_user_for_tenant(
            user=user,
            email=teacher_email,
            first_name=first_name,
            last_name=last_name,
            phone=phone,
            profile_picture=profile_picture,
            teacher_password=teacher_password,
            confirm_teacher_password=confirm_teacher_password,
        )
    except ValueError as exc:
        return Response(
            {"success": False, "message": str(exc)},
            status=status.HTTP_400_BAD_REQUEST,
        )

    if gender and teacher_user.gender != gender:
        teacher_user.gender = gender
        teacher_user.save(update_fields=["gender"])

    if TeacherProfile.objects.filter(user=teacher_user).exists():
        return Response(
            {"success": False, "message": "Teacher profile already exists for this account."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    employment_type = str(request.data.get("employment_type", "full_time")).strip() or "full_time"
    valid_types = {value for value, _ in TeacherProfile.EMPLOYMENT_TYPES}
    if employment_type not in valid_types:
        return Response(
            {
                "success": False,
                "message": f"employment_type must be one of: {', '.join(sorted(valid_types))}.",
            },
            status=status.HTTP_400_BAD_REQUEST,
        )

    years_raw = request.data.get("years_of_experience", 0)
    try:
        years_of_experience = int(str(years_raw).strip() or 0)
    except Exception:
        return Response(
            {"success": False, "message": "years_of_experience must be a number."},
            status=status.HTTP_400_BAD_REQUEST,
        )
    if years_of_experience < 0:
        return Response(
            {"success": False, "message": "years_of_experience cannot be negative."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    try:
        monthly_salary = _parse_money_amount(request.data.get("monthly_salary"), "monthly_salary")
    except ValueError as exc:
        return Response({"success": False, "message": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

    hire_date_raw = request.data.get("hire_date")
    if hire_date_raw:
        hire_date = parse_date(str(hire_date_raw).strip())
        if not hire_date:
            return Response(
                {"success": False, "message": "hire_date must be in YYYY-MM-DD format."},
                status=status.HTTP_400_BAD_REQUEST,
            )
    else:
        hire_date = timezone.now().date()

    employee_id = str(request.data.get("employee_id", "")).strip() or generate_short_teacher_id(teacher_user.id.hex, user.tenant)
    if TeacherProfile.objects.filter(employee_id__iexact=employee_id).exists():
        return Response(
            {"success": False, "message": "employee_id already exists."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    teacher_profile = TeacherProfile.objects.create(
        user=teacher_user,
        employee_id=employee_id,
        qualification=str(request.data.get("qualification", "")).strip() or "Not specified",
        specialization=str(request.data.get("specialization", "")).strip() or "Not specified",
        subjects_text=str(request.data.get("subjects_text", "")).strip(),
        years_of_experience=years_of_experience,
        hire_date=hire_date,
        monthly_salary=monthly_salary,
        employment_type=employment_type,
        emergency_contact_name=str(request.data.get("emergency_contact_name", "")).strip() or "Not provided",
        emergency_contact_phone=str(request.data.get("emergency_contact_phone", "")).strip() or "Not provided",
        emergency_contact_relation=str(request.data.get("emergency_contact_relation", "")).strip() or "Not provided",
    )

    subject_ids = _parse_id_list(request.data.get("subject_ids"))
    if subject_ids:
        subjects = _scope_to_user_tenant(Subject.objects.all(), user).filter(id__in=subject_ids)
        teacher_profile.subjects.set(subjects)

    class_ids = _parse_id_list(request.data.get("class_ids"))
    if class_ids:
        classes = _scope_to_user_tenant(Class.objects.all(), user).filter(id__in=class_ids)
        teacher_profile.assigned_classes.set(classes)

    _sync_teacher_hr_salary(teacher_profile)

    return Response(
        {
            "success": True,
            "message": "Teacher created.",
            "teacher": _teacher_payload(teacher_profile, request=request),
        },
        status=status.HTTP_201_CREATED,
    )


@api_view(["PATCH", "DELETE"])
@permission_classes([IsAuthenticated])
def teacher_detail(request, teacher_id):
    user = request.user
    teacher_profile = get_object_or_404(
        TeacherProfile.objects.select_related("user").prefetch_related("subjects", "assigned_classes").filter(user__tenant=user.tenant),
        id=teacher_id,
    )
    teacher_user = teacher_profile.user

    if request.method == "DELETE":
        teacher_user.delete()
        return Response({"success": True, "message": "Teacher deleted."})

    user_update_fields = []
    profile_update_fields = []

    if "email" in request.data:
        new_email = str(request.data.get("email", "")).strip().lower()
        if not new_email:
            return Response(
                {"success": False, "message": "email cannot be blank."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        email_taken = User.objects.filter(email__iexact=new_email).exclude(id=teacher_user.id).exists()
        if email_taken:
            return Response(
                {"success": False, "message": "A user with this email already exists."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if teacher_user.email != new_email:
            teacher_user.email = new_email
            user_update_fields.append("email")

    for field in ("first_name", "last_name", "phone"):
        if field in request.data:
            new_value = str(request.data.get(field) or "").strip()
            if getattr(teacher_user, field) != new_value:
                setattr(teacher_user, field, new_value)
                user_update_fields.append(field)

    if "gender" in request.data:
        gender = str(request.data.get("gender") or "").strip()
        if gender and gender not in {"M", "F", "O", "N"}:
            return Response(
                {"success": False, "message": "gender must be one of M, F, O, or N."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if teacher_user.gender != gender:
            teacher_user.gender = gender
            user_update_fields.append("gender")

    teacher_password = str(request.data.get("teacher_password") or request.data.get("password") or "").strip()
    confirm_teacher_password = str(request.data.get("confirm_teacher_password") or request.data.get("confirm_password") or "").strip()
    if teacher_password or confirm_teacher_password:
        try:
            validated_password = _validate_teacher_password(teacher_password, confirm_teacher_password)
        except ValueError as exc:
            return Response({"success": False, "message": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        teacher_user.set_password(validated_password)
        user_update_fields.append("password")

    if "is_active" in request.data:
        new_active = _to_bool(request.data.get("is_active"), default=teacher_user.is_active)
        if teacher_user.is_active != new_active:
            teacher_user.is_active = new_active
            user_update_fields.append("is_active")

    profile_picture = request.FILES.get("profile_picture")
    if profile_picture:
        teacher_user.profile_picture = profile_picture
        user_update_fields.append("profile_picture")

    if "employee_id" in request.data:
        new_employee_id = str(request.data.get("employee_id") or "").strip()
        if not new_employee_id:
            return Response(
                {"success": False, "message": "employee_id cannot be blank."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        employee_id_taken = (
            TeacherProfile.objects.filter(employee_id__iexact=new_employee_id).exclude(id=teacher_profile.id).exists()
        )
        if employee_id_taken:
            return Response(
                {"success": False, "message": "employee_id already exists."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if teacher_profile.employee_id != new_employee_id:
            teacher_profile.employee_id = new_employee_id
            profile_update_fields.append("employee_id")

    if "employment_type" in request.data:
        employment_type = str(request.data.get("employment_type") or "").strip()
        valid_types = {value for value, _ in TeacherProfile.EMPLOYMENT_TYPES}
        if employment_type not in valid_types:
            return Response(
                {
                    "success": False,
                    "message": f"employment_type must be one of: {', '.join(sorted(valid_types))}.",
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
        if teacher_profile.employment_type != employment_type:
            teacher_profile.employment_type = employment_type
            profile_update_fields.append("employment_type")

    if "years_of_experience" in request.data:
        years_raw = request.data.get("years_of_experience")
        try:
            years_of_experience = int(str(years_raw).strip() or 0)
        except Exception:
            return Response(
                {"success": False, "message": "years_of_experience must be a number."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if years_of_experience < 0:
            return Response(
                {"success": False, "message": "years_of_experience cannot be negative."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if teacher_profile.years_of_experience != years_of_experience:
            teacher_profile.years_of_experience = years_of_experience
            profile_update_fields.append("years_of_experience")

    if "hire_date" in request.data:
        raw_hire_date = str(request.data.get("hire_date") or "").strip()
        if not raw_hire_date:
            return Response(
                {"success": False, "message": "hire_date cannot be blank."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        hire_date = parse_date(raw_hire_date)
        if not hire_date:
            return Response(
                {"success": False, "message": "hire_date must be in YYYY-MM-DD format."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if teacher_profile.hire_date != hire_date:
            teacher_profile.hire_date = hire_date
            profile_update_fields.append("hire_date")

    if "monthly_salary" in request.data:
        try:
            monthly_salary = _parse_money_amount(request.data.get("monthly_salary"), "monthly_salary")
        except ValueError as exc:
            return Response({"success": False, "message": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        if teacher_profile.monthly_salary != monthly_salary:
            teacher_profile.monthly_salary = monthly_salary
            profile_update_fields.append("monthly_salary")

    for field in ("qualification", "specialization", "emergency_contact_name", "emergency_contact_phone", "emergency_contact_relation"):
        if field in request.data:
            new_value = str(request.data.get(field) or "").strip()
            if getattr(teacher_profile, field) != new_value:
                setattr(teacher_profile, field, new_value)
                profile_update_fields.append(field)

    if "subjects_text" in request.data:
        new_subjects_text = str(request.data.get("subjects_text") or "").strip()
        if teacher_profile.subjects_text != new_subjects_text:
            teacher_profile.subjects_text = new_subjects_text
            profile_update_fields.append("subjects_text")

    if "subject_ids" in request.data:
        subject_ids = _parse_id_list(request.data.get("subject_ids"))
        subjects = _scope_to_user_tenant(Subject.objects.all(), user).filter(id__in=subject_ids)
        teacher_profile.subjects.set(subjects)

    if "class_ids" in request.data:
        class_ids = _parse_id_list(request.data.get("class_ids"))
        classes = _scope_to_user_tenant(Class.objects.all(), user).filter(id__in=class_ids)
        teacher_profile.assigned_classes.set(classes)

    if user_update_fields:
        teacher_user.save(update_fields=sorted(set(user_update_fields)))
    if profile_update_fields:
        teacher_profile.save(update_fields=sorted(set(profile_update_fields)))
    if "monthly_salary" in profile_update_fields:
        _sync_teacher_hr_salary(teacher_profile)

    teacher_profile.refresh_from_db()
    return Response(
        {
            "success": True,
            "message": "Teacher updated.",
            "teacher": _teacher_payload(teacher_profile, request=request),
        }
    )


@api_view(["GET", "PATCH"])
@permission_classes([IsAuthenticated])
def school_settings(request):
    user = request.user
    school = getattr(user, "tenant", None)
    if not school:
        return Response(
            {"success": False, "message": "Your account is not linked to a school."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    if request.method == "PATCH":
        if not _can_manage_school_settings(user):
            return Response(
                {"success": False, "message": "Only school administrators can update school settings."},
                status=status.HTTP_403_FORBIDDEN,
            )

        update_fields = []
        old_schema_name = school.schema_name
        name_changed = False
        linked_code_counts = None
        raw_name = request.data.get("name")
        if raw_name is not None:
            cleaned_name = str(raw_name).strip()
            if len(cleaned_name) < 3:
                return Response(
                    {"success": False, "message": "School name must be at least 3 characters."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            if cleaned_name != school.name:
                school.name = cleaned_name
                school.schema_name = _unique_school_code_for_name(school, cleaned_name)
                update_fields.append("name")
                update_fields.append("schema_name")
                name_changed = True

        for field in ("email", "phone", "address"):
            if field in request.data:
                new_value = str(request.data.get(field) or "").strip() or None
                if getattr(school, field) != new_value:
                    setattr(school, field, new_value)
                    update_fields.append(field)

        logo_file = request.FILES.get("logo")
        if logo_file:
            school.logo = logo_file
            update_fields.append("logo")

        favicon_file = request.FILES.get("favicon")
        if favicon_file:
            school.favicon = favicon_file
            update_fields.append("favicon")

        for field in ("currency", "timezone"):
            if field in request.data:
                new_value = str(request.data.get(field) or "").strip()
                if new_value and getattr(school, field) != new_value:
                    setattr(school, field, new_value)
                    update_fields.append(field)

        if update_fields:
            with db_transaction.atomic():
                school.save(update_fields=sorted(set(update_fields)))
                if name_changed:
                    legacy_tenant = Tenant.objects.filter(slug__iexact=old_schema_name).first()
                    if legacy_tenant:
                        legacy_tenant.slug = school.schema_name
                        legacy_tenant.name = school.name
                        legacy_tenant.save(update_fields=["slug", "name"])
                    else:
                        Tenant.objects.update_or_create(slug=school.schema_name, defaults={"name": school.name})

                    primary_domain = Domain.objects.filter(tenant=school, is_primary=True).order_by("id").first()
                    next_domain = _unique_school_domain(school.schema_name, school)
                    if primary_domain:
                        primary_domain.domain = next_domain
                        primary_domain.save(update_fields=["domain"])
                    else:
                        Domain.objects.create(tenant=school, domain=next_domain, is_primary=True)

                    linked_code_counts = _regenerate_school_linked_codes(school)

        active_year = _active_academic_year(user)
        year_name = str(request.data.get("academic_year_name") or "").strip()
        year_start = request.data.get("academic_year_start_date")
        year_end = request.data.get("academic_year_end_date")
        tenant_obj = _tenant_for_model(AcademicYear, user)
        if year_name and year_start and year_end and tenant_obj:
            parsed_start = parse_date(str(year_start))
            parsed_end = parse_date(str(year_end))
            if not parsed_start or not parsed_end or parsed_end <= parsed_start:
                return Response(
                    {"success": False, "message": "Academic year dates are invalid."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            AcademicYear.objects.filter(tenant=tenant_obj, is_active=True).update(is_active=False)
            active_year, _ = AcademicYear.objects.update_or_create(
                tenant=tenant_obj,
                name=year_name,
                defaults={"start_date": parsed_start, "end_date": parsed_end, "is_active": True},
            )

        active_term = _active_term(user)
        term_name = str(request.data.get("term_name") or "").strip()
        term_start = request.data.get("term_start_date")
        term_end = request.data.get("term_end_date")
        term_tenant = _tenant_for_model(Term, user)
        if term_name and term_start and term_end and term_tenant:
            parsed_start = parse_date(str(term_start))
            parsed_end = parse_date(str(term_end))
            if not parsed_start or not parsed_end or parsed_end <= parsed_start:
                return Response(
                    {"success": False, "message": "Term dates are invalid."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            if not active_year:
                active_year = _active_academic_year(user)
            Term.objects.filter(tenant=term_tenant, is_active=True).update(is_active=False)
            active_term, _ = Term.objects.update_or_create(
                tenant=term_tenant,
                name=term_name,
                academic_year=active_year,
                defaults={"start_date": parsed_start, "end_date": parsed_end, "is_active": True},
            )

        return Response(
            {
                "success": True,
                "message": "School settings updated.",
                "school": _school_payload(school, request),
                "academic_year": _academic_year_payload(active_year),
                "term": _term_payload(active_term),
                "support_tickets": [_support_ticket_payload(item, request) for item in SupportTicket.objects.filter(school=school)[:8]],
                "can_edit": True,
                "renamed": name_changed,
                "linked_code_counts": linked_code_counts or {},
            }
        )

    active_year = _active_academic_year(user)
    active_term = _active_term(user)
    return Response(
        {
            "success": True,
            "school": _school_payload(school, request),
            "academic_year": _academic_year_payload(active_year),
            "term": _term_payload(active_term),
            "academic_years": [_academic_year_payload(item) for item in _scope_to_user_tenant(AcademicYear.objects.all(), user)[:20]],
            "terms": [_term_payload(item) for item in _scope_to_user_tenant(Term.objects.select_related("academic_year"), user)[:20]],
            "support_tickets": [_support_ticket_payload(item, request) for item in SupportTicket.objects.filter(school=school)[:8]],
            "can_edit": _can_manage_school_settings(user),
        }
    )


def _support_email():
    return str(getattr(settings, "SCHOOLDOM_SUPPORT_EMAIL", "") or "support@schooldom.academy").strip()


def _support_ticket_payload(ticket, request=None):
    attachment_url = ""
    if ticket.attachment:
        try:
            attachment_url = ticket.attachment.url
            if request:
                attachment_url = request.build_absolute_uri(attachment_url)
        except Exception:
            attachment_url = ""
    return {
        "id": str(ticket.id),
        "category": ticket.category,
        "category_label": ticket.get_category_display(),
        "subject": ticket.subject,
        "description": ticket.description,
        "status": ticket.status,
        "status_label": ticket.get_status_display(),
        "requester_email": ticket.requester_email,
        "school": {
            "id": str(ticket.school_id),
            "name": getattr(ticket.school, "name", ""),
            "school_code": getattr(ticket.school, "schema_name", ""),
            "email": getattr(ticket.school, "email", ""),
            "phone": getattr(ticket.school, "phone", ""),
        },
        "submitted_by": ticket.submitted_by.get_full_name() if ticket.submitted_by_id else "",
        "submitted_by_email": ticket.submitted_by.email if ticket.submitted_by_id else "",
        "attachment": attachment_url,
        "created_at": ticket.created_at,
        "updated_at": ticket.updated_at,
    }


def _send_support_ticket_email(ticket, kind="created"):
    support_email = _support_email()
    requester_email = ticket.requester_email or (ticket.submitted_by.email if ticket.submitted_by_id else "")
    school = ticket.school
    subject_prefix = "SchoolDom support ticket"
    if kind == "status":
        subject = f"{subject_prefix} update: {ticket.get_status_display()} - {ticket.subject}"
        body = (
            f"Your SchoolDom support ticket status is now {ticket.get_status_display()}.\n\n"
            f"Ticket: {ticket.subject}\n"
            f"Category: {ticket.get_category_display()}\n"
            f"School: {school.name} ({school.schema_name})\n\n"
            "We will continue tracking this request in your School Settings support center."
        )
        recipients = [requester_email] if requester_email else []
    else:
        subject = f"{subject_prefix}: {ticket.subject}"
        body = (
            "A new SchoolDom support ticket was submitted.\n\n"
            f"School: {school.name}\n"
            f"School code: {school.schema_name}\n"
            f"School email: {school.email or '-'}\n"
            f"School phone: {school.phone or '-'}\n"
            f"Submitted by: {ticket.submitted_by.get_full_name() if ticket.submitted_by_id else '-'}\n"
            f"Requester email: {requester_email or '-'}\n"
            f"Category: {ticket.get_category_display()}\n"
            f"Status: {ticket.get_status_display()}\n\n"
            f"{ticket.description}"
        )
        recipients = [support_email]
        if requester_email and requester_email.lower() != support_email.lower():
            recipients.append(requester_email)

    if not recipients:
        return False

    try:
        send_mail(subject, body, settings.DEFAULT_FROM_EMAIL, recipients, fail_silently=False)
    except Exception:
        return False
    return True


@api_view(["GET", "POST", "PATCH"])
@permission_classes([IsAuthenticated])
def support_tickets(request):
    user = request.user
    school = getattr(user, "tenant", None)
    if not school:
        return Response({"success": False, "message": "Your account is not linked to a school."}, status=status.HTTP_400_BAD_REQUEST)
    if not _can_manage_school_settings(user):
        return Response({"success": False, "message": "Only school administrators can manage support tickets."}, status=status.HTTP_403_FORBIDDEN)

    if request.method == "GET":
        tickets = SupportTicket.objects.filter(school=school)[:20]
        return Response({"success": True, "tickets": [_support_ticket_payload(item, request) for item in tickets]})

    if request.method == "PATCH":
        ticket_id = request.data.get("id") or request.data.get("ticket_id")
        ticket = get_object_or_404(SupportTicket, id=ticket_id, school=school)
        next_status = str(request.data.get("status") or "").strip()
        allowed_statuses = {value for value, _label in SupportTicket.STATUS_CHOICES}
        if next_status not in allowed_statuses:
            return Response({"success": False, "message": "Select a valid ticket status."}, status=status.HTTP_400_BAD_REQUEST)
        status_changed = ticket.status != next_status
        if status_changed:
            ticket.status = next_status
            ticket.save(update_fields=["status", "updated_at"])
            if _send_support_ticket_email(ticket, kind="status"):
                ticket.last_status_email_at = timezone.now()
                ticket.save(update_fields=["last_status_email_at"])
        return Response({"success": True, "message": "Support ticket updated.", "ticket": _support_ticket_payload(ticket, request)})

    category = str(request.data.get("category") or "").strip()
    allowed_categories = {value for value, _label in SupportTicket.CATEGORY_CHOICES}
    if category not in allowed_categories:
        return Response({"success": False, "message": "Select a support category."}, status=status.HTTP_400_BAD_REQUEST)

    subject = str(request.data.get("subject") or "").strip()
    description = str(request.data.get("description") or "").strip()
    if len(subject) < 3:
        return Response({"success": False, "message": "Enter a support ticket subject."}, status=status.HTTP_400_BAD_REQUEST)
    if len(description) < 10:
        return Response({"success": False, "message": "Enter a brief description of the issue."}, status=status.HTTP_400_BAD_REQUEST)

    ticket = SupportTicket.objects.create(
        school=school,
        submitted_by=user,
        category=category,
        subject=subject[:180],
        description=description,
        attachment=request.FILES.get("attachment"),
        requester_email=str(request.data.get("requester_email") or user.email or school.email or "").strip(),
    )
    notified = _send_support_ticket_email(ticket, kind="created")
    now = timezone.now()
    if notified:
        ticket.support_notified_at = now
        ticket.requester_notified_at = now
        ticket.save(update_fields=["support_notified_at", "requester_notified_at"])

    return Response(
        {
            "success": True,
            "message": "Support ticket submitted. Email notifications will be sent as the ticket is updated.",
            "ticket": _support_ticket_payload(ticket, request),
        },
        status=status.HTTP_201_CREATED,
    )


def _database_imports_summary(school):
    jobs = DatabaseImportJob.objects.filter(tenant=school)
    return {
        "total_imports": jobs.count(),
        "validated": jobs.filter(status="validated").count(),
        "needs_review": jobs.filter(status="needs_review").count(),
        "failed": jobs.filter(status="failed").count(),
        "latest_import_at": jobs.order_by("-created_at").values_list("created_at", flat=True).first(),
    }


@api_view(["GET", "POST"])
@permission_classes([IsAuthenticated])
def database_imports(request):
    user = request.user
    if getattr(user, "role", None) not in ADMIN_ROLES:
        return Response({"success": False, "message": "Only school admins can access database imports."}, status=status.HTTP_403_FORBIDDEN)

    school = _resolve_school_tenant_for_user(user, school_code=request.data.get("school_code") if request.method == "POST" else "")
    if not school:
        return Response({"success": False, "message": "Could not resolve your school for this import."}, status=status.HTTP_400_BAD_REQUEST)

    if request.method == "POST":
        uploaded_files = request.FILES.getlist("file") or request.FILES.getlist("files")
        if not uploaded_files:
            return Response(
                {"success": False, "message": "Attach one or more CSV, Excel, JSON, SQL, ZIP, image, or document files."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        import_type = str(request.data.get("import_type") or "full_school").strip()
        allowed_types = {value for value, _label in DatabaseImportJob.IMPORT_TYPES}
        if import_type not in allowed_types:
            return Response({"success": False, "message": "Select a valid import category."}, status=status.HTTP_400_BAD_REQUEST)

        jobs = []
        all_errors = []
        applied_student_count = 0
        for uploaded_file in uploaded_files:
            summary, errors = _summarize_database_import_upload(uploaded_file)
            applied_students = []
            if not errors and import_type in {"full_school", "students"}:
                applied_students, apply_errors = _apply_student_image_database_import(user, school, uploaded_file, summary)
                errors = [*errors, *apply_errors]
                applied_student_count += len(applied_students)
            job = DatabaseImportJob.objects.create(
                tenant=school,
                uploaded_by=user,
                import_type=import_type,
                source_platform=str(request.data.get("source_platform") or "").strip(),
                link_key=str(request.data.get("link_key") or "admission_number").strip(),
                notes=str(request.data.get("notes") or "").strip(),
                upload=uploaded_file,
                original_filename=(uploaded_file.name or "migration-upload")[:255],
                file_size=uploaded_file.size,
                status="needs_review" if errors else "validated",
                summary=summary,
                errors=errors,
            )
            jobs.append(job)
            all_errors.extend(errors)
        history = DatabaseImportJob.objects.filter(tenant=school).select_related("uploaded_by")
        message = f"{len(jobs)} import file{'s' if len(jobs) != 1 else ''} uploaded and validated." if not all_errors else f"{len(jobs)} import file{'s' if len(jobs) != 1 else ''} uploaded; some need review."
        if applied_student_count and not all_errors:
            message = f"{applied_student_count} student image import{'s' if applied_student_count != 1 else ''} created or updated from {len(jobs)} file{'s' if len(jobs) != 1 else ''}."
        return Response(
            {
                "success": not all_errors,
                "message": message,
                "job": _database_import_job_payload(jobs[0], request) if jobs else None,
                "jobs": [_database_import_job_payload(item, request) for item in jobs],
                "summary": _database_imports_summary(school),
                "history": [_database_import_job_payload(item, request) for item in history[:20]],
            },
            status=status.HTTP_201_CREATED,
        )

    jobs = DatabaseImportJob.objects.filter(tenant=school).select_related("uploaded_by")
    return Response(
        {
            "success": True,
            "summary": _database_imports_summary(school),
            "history": [_database_import_job_payload(item, request) for item in jobs[:20]],
            "options": {
                "import_types": [{"value": value, "label": label} for value, label in DatabaseImportJob.IMPORT_TYPES],
                "link_keys": [
                    {"value": "admission_number", "label": "Admission number"},
                    {"value": "student_id", "label": "Student ID"},
                    {"value": "employee_id", "label": "Employee ID"},
                    {"value": "email", "label": "Email address"},
                    {"value": "filename", "label": "Filename convention"},
                ],
                "formats": ["CSV", "Excel", "JSON", "SQL backup", "ZIP", "Images", "Documents"],
            },
        }
    )


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def classes_snapshot(request):
    user = request.user
    classes = _scope_to_user_tenant(Class.objects.prefetch_related("subjects"), user)
    terms = _scope_to_user_tenant(Term.objects.select_related("academic_year"), user).order_by("-start_date", "name")
    academic_years = _scope_to_user_tenant(AcademicYear.objects.all(), user).order_by("-start_date", "name")

    student_counts = (
        StudentProfile.objects.filter(user__tenant=user.tenant)
        .values("current_class")
        .annotate(total=Count("id"))
    )
    by_class_id = {entry["current_class"]: entry["total"] for entry in student_counts if entry["current_class"]}

    classes_list = []
    for class_obj in classes.order_by("name", "section")[:20]:
        classes_list.append(_class_payload(class_obj, student_count=by_class_id.get(class_obj.id, 0)))

    return Response(
        {
            "success": True,
            "summary": {
                "total_classes": classes.count(),
                "unsectioned_classes": classes.filter(section__isnull=True).count()
                + classes.filter(section="").count(),
            },
            "classes": classes_list,
            "subjects": [
                _subject_payload(subject)
                for subject in _scope_to_user_tenant(Subject.objects.all(), user).order_by("name")[:500]
            ],
            "terms": [_term_payload(term) for term in terms[:100]],
            "academic_years": [_academic_year_payload(year) for year in academic_years[:50]],
            "promotion_history": [
                _promotion_payload(item)
                for item in StudentClassPromotion.objects.select_related(
                    "student__user",
                    "from_class",
                    "to_class",
                    "from_term",
                    "to_term",
                    "from_academic_year",
                    "to_academic_year",
                    "promoted_by",
                )
                .filter(tenant=_tenant_for_model(StudentClassPromotion, user))
                .order_by("-created_at")[:20]
            ],
        }
    )


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def class_promotions(request):
    user = request.user
    if getattr(user, "role", None) not in ADMIN_ROLES:
        return Response(
            {"success": False, "message": "Only school administrators can promote classes."},
            status=status.HTTP_403_FORBIDDEN,
        )

    action = str(request.data.get("action") or "preview").strip().lower()
    if action not in {"preview", "apply"}:
        return Response(
            {"success": False, "message": "action must be preview or apply."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    try:
        preview = _build_promotion_preview(user, request.data)
    except ValueError as exc:
        return Response({"success": False, "message": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

    if action == "preview":
        return Response({"success": True, "message": "Promotion preview ready.", "preview": preview})

    if not _to_bool(request.data.get("confirm"), default=False):
        return Response(
            {"success": False, "message": "Confirmation is required before applying a bulk promotion."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    tenant_obj = _tenant_for_model(StudentClassPromotion, user)
    if not tenant_obj:
        return Response(
            {"success": False, "message": "Could not resolve tenant for class promotion."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    eligible_ids = [item["id"] for item in preview["students"]]
    if not eligible_ids:
        return Response(
            {"success": False, "message": "No eligible students to promote."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    target_class = get_object_or_404(_scope_to_user_tenant(Class.objects.all(), user), id=preview["target_class"]["id"])
    target_term = None
    if preview.get("target_term"):
        target_term = get_object_or_404(_scope_to_user_tenant(Term.objects.all(), user), id=preview["target_term"]["id"])
    source_class = None
    if preview.get("source_class"):
        source_class = get_object_or_404(_scope_to_user_tenant(Class.objects.all(), user), id=preview["source_class"]["id"])
    source_term = None
    if preview.get("source_term"):
        source_term = get_object_or_404(_scope_to_user_tenant(Term.objects.all(), user), id=preview["source_term"]["id"])
    source_year = None
    if preview.get("source_academic_year"):
        source_year = get_object_or_404(_scope_to_user_tenant(AcademicYear.objects.all(), user), id=preview["source_academic_year"]["id"])
    target_year = None
    if preview.get("target_academic_year"):
        target_year = get_object_or_404(_scope_to_user_tenant(AcademicYear.objects.all(), user), id=preview["target_academic_year"]["id"])

    batch_reference = timezone.now().strftime("PROMO-%Y%m%d%H%M%S")
    note = str(request.data.get("note") or "").strip()

    with db_transaction.atomic():
        students = list(
            StudentProfile.objects.select_related("user", "current_class", "current_term")
            .filter(id__in=eligible_ids, user__tenant=user.tenant)
            .order_by("user__first_name", "user__last_name")
        )
        StudentClassPromotion.objects.bulk_create(
            [
                StudentClassPromotion(
                    tenant=tenant_obj,
                    student=student,
                    from_class=source_class or student.current_class,
                    to_class=target_class,
                    from_term=source_term or student.current_term,
                    to_term=target_term,
                    from_academic_year=source_year,
                    to_academic_year=target_year,
                    scope=preview["scope"],
                    scope_value=preview["scope_value"],
                    batch_reference=batch_reference,
                    promoted_by=user,
                    note=note,
                )
                for student in students
            ],
            ignore_conflicts=True,
        )
        for student in students:
            student.current_class = target_class
            if target_term:
                student.current_term = target_term
            student.save(update_fields=["current_class", "current_term"] if target_term else ["current_class"])

    applied_preview = _build_promotion_preview(user, request.data)
    return Response(
        {
            "success": True,
            "message": f"Promoted {len(students)} student(s) to {_class_label(target_class)}.",
            "batch_reference": batch_reference,
            "applied_count": len(students),
            "preview": applied_preview,
        }
    )


@api_view(["GET", "POST"])
@permission_classes([IsAuthenticated])
def lesson_planning(request):
    user = request.user
    active_year = _active_academic_year(user)
    active_term = _active_term(user)

    if request.method == "POST":
        if user.role != "teacher":
            return Response(
                {"success": False, "message": "Only teachers can create lesson plans."},
                status=status.HTTP_403_FORBIDDEN,
            )

        subject = get_object_or_404(_scope_to_user_tenant(Subject.objects.all(), user), id=request.data.get("subject_id"))
        class_group = get_object_or_404(_scope_to_user_tenant(Class.objects.all(), user), id=request.data.get("class_id"))
        try:
            week_number = int(request.data.get("week_number") or 1)
        except Exception:
            week_number = 1
        week_number = max(1, min(week_number, 20))

        if request.data.get("term_id"):
            active_term = get_object_or_404(_scope_to_user_tenant(Term.objects.all(), user), id=request.data.get("term_id"))
        if request.data.get("academic_year_id"):
            active_year = get_object_or_404(_scope_to_user_tenant(AcademicYear.objects.all(), user), id=request.data.get("academic_year_id"))

        tenant_obj = _tenant_for_model(LessonPlan, user)
        title = str(request.data.get("title") or "").strip()
        if not title:
            return Response({"success": False, "message": "Lesson title is required."}, status=status.HTTP_400_BAD_REQUEST)

        plan, _ = LessonPlan.objects.update_or_create(
            tenant=tenant_obj,
            teacher=user,
            academic_year=active_year,
            term=active_term,
            class_group=class_group,
            subject=subject,
            week_number=week_number,
            defaults={
                "title": title,
                "objectives": str(request.data.get("objectives") or "").strip(),
                "activities": str(request.data.get("activities") or "").strip(),
                "resources": str(request.data.get("resources") or "").strip(),
                "assessment": str(request.data.get("assessment") or "").strip(),
                "notes": str(request.data.get("notes") or "").strip(),
                "status": str(request.data.get("status") or LessonPlan.PLANNED).strip() or LessonPlan.PLANNED,
            },
        )
        return Response({"success": True, "message": "Lesson plan saved.", "lesson_plan": _lesson_plan_payload(plan)}, status=status.HTTP_201_CREATED)

    plans_qs = _scope_to_user_tenant(
        LessonPlan.objects.select_related("teacher", "subject", "class_group", "term", "academic_year"),
        user,
    )
    if active_year:
        plans_qs = plans_qs.filter(academic_year=active_year)
    if active_term:
        plans_qs = plans_qs.filter(term=active_term)

    if user.role == "teacher":
        plans_qs = plans_qs.filter(teacher=user)
        teacher_profile = TeacherProfile.objects.filter(user=user).prefetch_related("subjects", "assigned_classes").first()
        class_options = teacher_profile.assigned_classes.all() if teacher_profile and teacher_profile.assigned_classes.exists() else _scope_to_user_tenant(Class.objects.all(), user)
        subject_options = teacher_profile.subjects.all() if teacher_profile and teacher_profile.subjects.exists() else _scope_to_user_tenant(Subject.objects.all(), user)
    elif user.role == "student":
        student_class = _current_student_class(user)
        plans_qs = plans_qs.filter(class_group=student_class) if student_class else plans_qs.none()
        class_options = Class.objects.filter(id=student_class.id) if student_class else Class.objects.none()
        subject_options = student_class.subjects.all() if student_class else Subject.objects.none()
    else:
        class_options = _scope_to_user_tenant(Class.objects.all(), user)
        subject_options = _scope_to_user_tenant(Subject.objects.all(), user)

    total = plans_qs.count()
    completed = plans_qs.filter(status=LessonPlan.COMPLETED).count()
    latest_week = plans_qs.order_by("-week_number").values_list("week_number", flat=True).first() or 0
    return Response(
        {
            "success": True,
            "active_year": _academic_year_payload(active_year),
            "active_term": _term_payload(active_term),
            "progress": {
                "total_plans": total,
                "completed": completed,
                "latest_week": latest_week,
                "completion_percent": round((completed / total) * 100, 1) if total else 0,
            },
            "lesson_plans": [_lesson_plan_payload(plan) for plan in plans_qs[:100]],
            "options": {
                "classes": [{"id": item.id, "label": _class_label(item)} for item in class_options[:100]],
                "subjects": [{"id": item.id, "name": item.name, "code": item.code} for item in subject_options[:100]],
            },
        }
    )


@api_view(["GET", "POST"])
@permission_classes([IsAuthenticated])
def teacher_notes(request):
    user = request.user
    if user.role != "teacher":
        return Response({"success": False, "message": "Only teachers can use the academic notepad."}, status=status.HTTP_403_FORBIDDEN)

    active_year = _active_academic_year(user)
    active_term = _active_term(user)
    if request.method == "POST":
        title = str(request.data.get("title") or "Quick note").strip() or "Quick note"
        note = TeacherNote.objects.create(
            tenant=_tenant_for_model(TeacherNote, user),
            teacher=user,
            academic_year=active_year,
            term=active_term,
            title=title,
            body=str(request.data.get("body") or "").strip(),
            pinned=_to_bool(request.data.get("pinned"), default=False),
        )
        return Response({"success": True, "message": "Note saved.", "note": _teacher_note_payload(note)}, status=status.HTTP_201_CREATED)

    notes = _scope_to_user_tenant(TeacherNote.objects.select_related("term", "academic_year"), user).filter(teacher=user)
    return Response({"success": True, "notes": [_teacher_note_payload(note) for note in notes[:30]]})


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def exams_snapshot(request):
    user = request.user
    now = timezone.now()

    exams = _scope_to_user_tenant(
        Exam.objects.select_related("subject", "class_group", "exam_type").prefetch_related("questions"),
        user,
    ).order_by("-start_date")
    if user.role == "teacher":
        exams = exams.filter(teacher=user)

    attempts = _scope_to_user_tenant(
        ExamAttempt.objects.select_related("exam", "exam__subject", "exam__class_group", "student"),
        user,
    )
    monitor_attempts = attempts
    if user.role == "teacher":
        attempts = attempts.filter(exam__teacher=user)
        monitor_attempts = monitor_attempts.filter(exam__teacher=user)
    elif user.role in ADMIN_ROLES:
        attempts = attempts.distinct()
        monitor_attempts = monitor_attempts.distinct()
    submitted_attempts_qs = attempts.filter(is_submitted=True).prefetch_related("answers__question").order_by("-end_time")
    submitted_attempts = list(submitted_attempts_qs[:30])
    auto_submitted_attempts_qs = monitor_attempts.filter(auto_submitted=True, is_submitted=True).order_by("-end_time")
    auto_submitted_attempts = list(auto_submitted_attempts_qs[:50])
    average_percentage = submitted_attempts_qs.aggregate(value=Avg("percentage")).get("value") or 0

    class_options = _scope_to_user_tenant(Class.objects.all(), user).order_by("name", "section")
    subject_options = _admin_exam_subject_options(
        _scope_to_user_tenant(Subject.objects.all(), user),
        user,
    ).order_by("name")

    attempts_by_exam = {
        item["exam"]: item["total"]
        for item in attempts.values("exam").annotate(total=Count("id"))
        if item["exam"] is not None
    }
    submissions_by_exam = {
        item["exam"]: item["total"]
        for item in attempts.filter(is_submitted=True).values("exam").annotate(total=Count("id"))
        if item["exam"] is not None
    }

    exam_rows = []
    for exam in exams[:100]:
        exam_row = {
            "id": exam.id,
            "title": exam.title,
            "assessment_type": _assessment_type_for_exam(exam),
            "subject": exam.subject.name if exam.subject else "General",
            "class_name": _class_label(exam.class_group) if exam.class_group else "All classes",
            "class_id": exam.class_group_id,
            "subject_id": exam.subject_id,
            "start_date": exam.start_date,
            "end_date": exam.end_date,
            "is_published": exam.is_published,
            "question_count": exam.questions.count(),
            "attempts": attempts_by_exam.get(exam.id, 0),
            "submissions": submissions_by_exam.get(exam.id, 0),
        }
        exam_row.update(_exam_pin_summary_for_user(exam, user))
        exam_rows.append(exam_row)

    return Response(
        {
            "success": True,
            "school": _school_payload(getattr(user, "tenant", None), request),
            "summary": {
                "total_exams": exams.count(),
                "published_exams": exams.filter(is_published=True).count(),
                "upcoming_exams": exams.filter(start_date__gte=now).count(),
                "pending_attempts": attempts.filter(is_submitted=False).count(),
                "tests_count": exams.filter(exam_type__name__iexact="Test").count(),
                "exams_count": exams.exclude(exam_type__name__iexact="Test").count(),
                "submitted_results": submitted_attempts_qs.count(),
                "auto_submitted_exams": auto_submitted_attempts_qs.count(),
                "average_cbt_score": round(float(average_percentage), 1),
            },
            "exams": exam_rows,
            "downloads": {
                "admin_app": request.build_absolute_uri(reverse("admin_app_download")),
                "student_cbt": request.build_absolute_uri(reverse("student_cbt_app_download")),
                "admin_app_available": bool(admin_app_installer_path()),
                "student_cbt_available": bool(offline_cbt_installer_path()),
            },
            "submitted_results": [
                {
                    "id": attempt.id,
                    "attempt_id": attempt.id,
                    "exam_id": attempt.exam_id,
                    "exam_title": attempt.exam.title,
                    "student_name": attempt.student.get_full_name() or attempt.student.email,
                    "student_email": attempt.student.email,
                    "student_id": getattr(getattr(attempt.student, "student_profile", None), "student_id", ""),
                    "admission_number": getattr(getattr(attempt.student, "student_profile", None), "admission_number", ""),
                    "subject": attempt.exam.subject.name if attempt.exam.subject else "General",
                    "class_name": _class_label(attempt.exam.class_group) if attempt.exam.class_group else "All classes",
                    "class_id": attempt.exam.class_group_id,
                    "score": attempt.score,
                    "total_points": attempt.total_points,
                    "percentage": round(float(attempt.percentage or 0), 1),
                    "submitted_at": attempt.end_time,
                    "answer_summary": [
                        {
                            "question": answer.question.text,
                            "selected_answer": answer.selected_options,
                            "correct_answer": answer.question.correct_answer,
                            "is_correct": answer.is_correct,
                            "score": answer.score,
                        }
                        for answer in attempt.answers.all()
                    ],
                }
                for attempt in submitted_attempts
            ],
            "auto_submitted_exams": [
                _exam_auto_submission_payload(attempt)
                for attempt in auto_submitted_attempts
            ],
            "options": {
                "classes": [
                    {
                        "id": item.id,
                        "name": item.name,
                        "section": item.section or "",
                        "label": _class_label(item),
                    }
                    for item in class_options[:100]
                ],
                "subjects": [
                    {
                        "id": item.id,
                        "name": item.name,
                        "code": item.code,
                    }
                    for item in subject_options[:100]
                ],
                "assessment_types": [
                    {"value": "exam", "label": "Exam"},
                    {"value": "test", "label": "Test"},
                ],
            },
        },
    )


@api_view(["DELETE"])
@permission_classes([IsAuthenticated])
def delete_exam_attempt_result(request, attempt_id):
    user = request.user
    if getattr(user, "role", None) not in ADMIN_ROLES:
        return Response({"success": False, "message": "Only school admins can delete student exam results."}, status=status.HTTP_403_FORBIDDEN)

    attempt_qs = _scope_to_user_tenant(
        ExamAttempt.objects.select_related("exam", "student"),
        user,
    )
    attempt = get_object_or_404(attempt_qs, id=attempt_id)
    student_name = attempt.student.get_full_name() or attempt.student.email
    exam_title = attempt.exam.title
    with db_transaction.atomic():
        attempt.delete()
    return Response(
        {
            "success": True,
            "message": f"Deleted {student_name}'s result for {exam_title}. The student can retake the exam.",
            "attempt_id": attempt_id,
        }
    )


def _question_group_payload(group, request=None):
    if not group:
        return None
    return {
        "id": group.id,
        "title": group.title,
        "group_type": group.group_type,
        "passage_text": group.passage_text,
        "image": _media_url(request, group.image),
    }


def _can_manage_exam_pins(user):
    return getattr(user, "role", None) in ADMIN_ROLES


def _exam_pin_summary_for_user(exam, user):
    if not _can_manage_exam_pins(user):
        return {
            "pin_required": False,
            "active_pin_count": 0,
            "active_pin_preview": "",
        }
    active_pin = exam.pins.filter(is_active=True).order_by("-created_at").first()
    return {
        "pin_required": bool(active_pin),
        "active_pin_count": exam.pins.filter(is_active=True).count(),
        "active_pin_preview": active_pin.pin_preview if active_pin else "",
        "active_pin_plain": getattr(active_pin, "plain_pin", "") if active_pin else "",
    }


def _exam_editor_payload(exam, request=None):
    questions = list(exam.questions.all())
    user = getattr(request, "user", None)
    payload = {
        "id": exam.id,
        "title": exam.title,
        "assessment_type": _assessment_type_for_exam(exam),
        "subject": exam.subject.name if exam.subject else "General",
        "subject_id": exam.subject_id,
        "class_name": _class_label(exam.class_group) if exam.class_group else "All classes",
        "class_id": exam.class_group_id,
        "start_date": exam.start_date,
        "end_date": exam.end_date,
        "duration_minutes": exam.duration_minutes,
        "instructions": exam.instructions,
        "shuffle_questions": exam.shuffle_questions,
        "show_results_immediately": exam.show_results_immediately,
        "is_published": exam.is_published,
        "question_count": len(questions),
        "questions": [
            {
                "id": question.id,
                "question_type": question.question_type,
                "text": question.text,
                "points": question.points,
                "options": question.options or [],
                "correct_answer": question.correct_answer or "",
                "explanation": question.explanation or "",
                "image": _media_url(request, question.image),
                "group_order": question.group_order,
                "group": _question_group_payload(question.group, request),
                "source_question_id": question.id if question.question_banks.exists() else None,
            }
            for question in questions
        ],
    }
    payload.update(_exam_pin_summary_for_user(exam, user))
    return payload


def _clean_exam_questions_payload(raw_questions):
    if isinstance(raw_questions, str):
        try:
            raw_questions = json.loads(raw_questions)
        except Exception:
            return None, "Questions payload must be valid JSON."
    if not isinstance(raw_questions, list) or not raw_questions:
        return None, "Add at least one objective question before saving the exam."

    cleaned_questions = []
    for index, item in enumerate(raw_questions, start=1):
        text = str(item.get("text", "")).strip() if isinstance(item, dict) else ""
        raw_options = item.get("options", []) if isinstance(item, dict) else []
        options = [str(option).strip() for option in raw_options if str(option).strip()]
        correct_answer = str(item.get("correct_answer", "")).strip() if isinstance(item, dict) else ""
        try:
            points = int(item.get("points", 1))
        except Exception:
            points = 1
        try:
            source_question_id = int(item.get("source_question_id") or 0) or None
        except Exception:
            source_question_id = None
        group_payload = item.get("group") if isinstance(item.get("group"), dict) else {}
        group_key = str(item.get("group_key") or group_payload.get("key") or "").strip()
        group_type = str(group_payload.get("group_type") or item.get("group_type") or "").strip() or "passage"
        if group_type not in {choice[0] for choice in QuestionGroup.GROUP_TYPES}:
            group_type = "passage"

        if len(text) < 3:
            return None, f"Question {index} must include the question text."
        if len(options) < 2:
            return None, f"Question {index} must include at least two answer options."
        if correct_answer not in options:
            return None, f"Question {index} must have a correct answer selected from its options."
        if points <= 0:
            points = 1

        cleaned_questions.append(
            {
                "text": text,
                "options": options,
                "correct_answer": correct_answer,
                "points": points,
                "explanation": str(item.get("explanation", "")).strip() if isinstance(item, dict) else "",
                "source_question_id": source_question_id,
                "question_image_field": str(item.get("question_image_field") or "").strip(),
                "group_key": group_key,
                "group": {
                    "title": str(group_payload.get("title") or "").strip(),
                    "group_type": group_type,
                    "passage_text": str(group_payload.get("passage_text") or "").strip(),
                    "image_field": str(group_payload.get("image_field") or "").strip(),
                } if group_key else None,
            }
        )
    return cleaned_questions, ""


def _exam_question_from_payload(item, tenant_obj, user, request=None, groups_by_key=None, group_order=0):
    source_question_id = item.get("source_question_id")
    if source_question_id:
        source_qs = _scope_to_user_tenant(
            Question.objects.filter(question_banks__isnull=False).distinct(),
            user,
        )
        source_question = source_qs.filter(id=source_question_id).first()
        if (
            source_question
            and source_question.text == item["text"]
            and (source_question.options or []) == item["options"]
            and (source_question.correct_answer or "") == item["correct_answer"]
            and int(source_question.points or 1) == int(item["points"] or 1)
        ):
            return source_question
    return Question.objects.create(
        tenant=tenant_obj,
        question_type="mcq",
        text=item["text"],
        image=request.FILES.get(item.get("question_image_field")) if request and item.get("question_image_field") else None,
        options=item["options"],
        correct_answer=item["correct_answer"],
        points=item["points"],
        explanation=item["explanation"],
        group=(groups_by_key or {}).get(item.get("group_key")),
        group_order=group_order,
    )


def _question_groups_from_payload(cleaned_questions, tenant_obj, user, request=None):
    groups_by_key = {}
    for item in cleaned_questions:
        group_key = item.get("group_key")
        group_payload = item.get("group") or {}
        if not group_key or group_key in groups_by_key:
            continue
        group = QuestionGroup.objects.create(
            tenant=tenant_obj,
            title=group_payload.get("title") or "",
            group_type=group_payload.get("group_type") or "passage",
            passage_text=group_payload.get("passage_text") or "",
            image=request.FILES.get(group_payload.get("image_field")) if request and group_payload.get("image_field") else None,
            teacher=user,
        )
        groups_by_key[group_key] = group
    return groups_by_key


def _cbt_bank_question_payload(question, bank=None):
    return {
        "id": question.id,
        "bank_id": bank.id if bank else None,
        "bank_name": bank.name if bank else "",
        "question_type": question.question_type,
        "text": question.text,
        "points": question.points,
        "options": question.options or [],
        "correct_answer": question.correct_answer or "",
        "explanation": question.explanation or "",
        "image": _media_url(None, question.image),
        "group_order": question.group_order,
        "group": _question_group_payload(question.group),
        "subject_id": bank.subject_id if bank else None,
        "subject_name": bank.subject.name if bank and bank.subject else "",
    }


def _admin_exam_pin_queryset(user):
    pins = _scope_to_user_tenant(
        ExamPin.objects.select_related(
            "exam",
            "exam__subject",
            "exam__class_group",
            "exam__exam_type",
            "created_by",
        ).prefetch_related("usages"),
        user,
    )
    if getattr(user, "role", None) not in ADMIN_ROLES:
        return pins.none()
    return pins


def _generate_unique_exam_pin():
    for _ in range(20):
        plain_pin = ExamPin.generate_plain_pin()
        if not ExamPin.objects.filter(pin_digest=ExamPin.digest_pin(plain_pin)).exists():
            return plain_pin
    raise RuntimeError("Could not generate a unique exam PIN.")


@api_view(["GET", "POST"])
@permission_classes([IsAuthenticated])
def cbt_exam_pins(request):
    user = request.user
    if getattr(user, "role", None) not in ADMIN_ROLES:
        return Response({"success": False, "message": "Only authorized administrators can manage exam PINs."}, status=status.HTTP_403_FORBIDDEN)

    if request.method == "GET":
        pins = _admin_exam_pin_queryset(user)
        exam_id = request.query_params.get("exam_id")
        if exam_id:
            pins = pins.filter(exam_id=exam_id)
        return Response({"success": True, "pins": [_exam_pin_payload(pin, include_usage=True) for pin in pins[:100]]})

    exam = get_object_or_404(
        _scope_to_user_tenant(Exam.objects.select_related("subject", "class_group", "exam_type"), user),
        id=request.data.get("exam_id"),
    )
    usage_policy = str(request.data.get("usage_policy") or ExamPin.USE_ONE_TIME).strip()
    if usage_policy not in {ExamPin.USE_ONE_TIME, ExamPin.USE_REUSABLE}:
        return Response({"success": False, "message": "usage_policy must be one_time or reusable."}, status=status.HTTP_400_BAD_REQUEST)

    expires_at = None
    expires_raw = request.data.get("expires_at")
    if expires_raw:
        expires_at = parse_datetime(expires_raw)
        if not expires_at:
            return Response({"success": False, "message": "expires_at must be a valid date-time."}, status=status.HTTP_400_BAD_REQUEST)

    plain_pin = _generate_unique_exam_pin()
    pin = ExamPin(
        tenant=exam.tenant,
        exam=exam,
        usage_policy=usage_policy,
        expires_at=expires_at,
        created_by=user,
    )
    pin.set_pin(plain_pin)
    pin.save()
    return Response(
        {
            "success": True,
            "message": "Exam PIN generated.",
            "pin": _exam_pin_payload(pin, include_usage=True),
            "plain_pin": plain_pin,
        },
        status=status.HTTP_201_CREATED,
    )


@api_view(["GET", "PATCH", "POST"])
@permission_classes([IsAuthenticated])
def cbt_exam_pin_detail(request, pin_id):
    user = request.user
    if getattr(user, "role", None) not in ADMIN_ROLES:
        return Response({"success": False, "message": "Only authorized administrators can manage exam PINs."}, status=status.HTTP_403_FORBIDDEN)

    pin = get_object_or_404(_admin_exam_pin_queryset(user), id=pin_id)
    if request.method == "GET":
        return Response({"success": True, "pin": _exam_pin_payload(pin, include_usage=True)})

    action = str(request.data.get("action") or "").strip().lower()
    if request.method == "PATCH":
        action = action or "update"
    if action == "regenerate":
        plain_pin = _generate_unique_exam_pin()
        pin.set_pin(plain_pin)
        pin.is_active = True
        pin.deactivated_at = None
        pin.deactivated_by = None
        pin.last_regenerated_at = timezone.now()
        pin.last_regenerated_by = user
        pin.save(update_fields=["pin_digest", "pin_hash", "pin_preview", "plain_pin", "is_active", "deactivated_at", "deactivated_by", "last_regenerated_at", "last_regenerated_by", "updated_at"])
        ExamPinUsage.objects.create(tenant=pin.tenant, pin=pin, exam=pin.exam, student=user, status=ExamPinUsage.STATUS_REGENERATED, message="PIN regenerated by administrator.")
        return Response({"success": True, "message": "Exam PIN regenerated.", "pin": _exam_pin_payload(pin, include_usage=True), "plain_pin": plain_pin})

    if action == "deactivate":
        pin.is_active = False
        pin.deactivated_at = timezone.now()
        pin.deactivated_by = user
        pin.save(update_fields=["is_active", "deactivated_at", "deactivated_by", "updated_at"])
        ExamPinUsage.objects.create(tenant=pin.tenant, pin=pin, exam=pin.exam, student=user, status=ExamPinUsage.STATUS_DEACTIVATED, message="PIN deactivated by administrator.")
        return Response({"success": True, "message": "Exam PIN deactivated.", "pin": _exam_pin_payload(pin, include_usage=True)})

    if action == "reset":
        pin.reset_at = timezone.now()
        pin.reset_by = user
        pin.is_active = True
        pin.deactivated_at = None
        pin.deactivated_by = None
        pin.save(update_fields=["reset_at", "reset_by", "is_active", "deactivated_at", "deactivated_by", "updated_at"])
        ExamPinUsage.objects.create(tenant=pin.tenant, pin=pin, exam=pin.exam, student=user, status=ExamPinUsage.STATUS_RESET, message="PIN usage reset by administrator.")
        return Response({"success": True, "message": "Exam PIN reset.", "pin": _exam_pin_payload(pin, include_usage=True)})

    if action in {"update", ""}:
        update_fields = []
        if "usage_policy" in request.data:
            usage_policy = str(request.data.get("usage_policy") or "").strip()
            if usage_policy not in {ExamPin.USE_ONE_TIME, ExamPin.USE_REUSABLE}:
                return Response({"success": False, "message": "usage_policy must be one_time or reusable."}, status=status.HTTP_400_BAD_REQUEST)
            pin.usage_policy = usage_policy
            update_fields.append("usage_policy")
        if "expires_at" in request.data:
            raw_value = request.data.get("expires_at")
            pin.expires_at = parse_datetime(raw_value) if raw_value else None
            if raw_value and not pin.expires_at:
                return Response({"success": False, "message": "expires_at must be a valid date-time."}, status=status.HTTP_400_BAD_REQUEST)
            update_fields.append("expires_at")
        if "is_active" in request.data:
            pin.is_active = _to_bool(request.data.get("is_active"), default=pin.is_active)
            if pin.is_active:
                pin.deactivated_at = None
                pin.deactivated_by = None
                update_fields.extend(["deactivated_at", "deactivated_by"])
            update_fields.append("is_active")
        if update_fields:
            update_fields.append("updated_at")
            pin.save(update_fields=list(dict.fromkeys(update_fields)))
        return Response({"success": True, "message": "Exam PIN updated.", "pin": _exam_pin_payload(pin, include_usage=True)})

    return Response({"success": False, "message": "Unsupported PIN action."}, status=status.HTTP_400_BAD_REQUEST)


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def cbt_question_bank(request):
    user = request.user
    banks_qs = _scope_to_user_tenant(
        QuestionBank.objects.select_related("subject", "teacher").prefetch_related("questions"),
        user,
    )
    if getattr(user, "role", None) == "teacher":
        banks_qs = banks_qs.filter(Q(teacher=user) | Q(is_shared=True))
        teacher_profile = TeacherProfile.objects.filter(user=user).prefetch_related("subjects").first()
        assigned_subject_ids = []
        if teacher_profile:
            assigned_subject_ids = list(teacher_profile.subjects.values_list("id", flat=True))
        if assigned_subject_ids:
            banks_qs = banks_qs.filter(Q(teacher=user) | Q(subject_id__in=assigned_subject_ids))
        else:
            banks_qs = banks_qs.filter(teacher=user)
    elif getattr(user, "role", None) in ADMIN_ROLES:
        banks_qs = banks_qs.exclude(
            Q(subject__code__iexact="PHY")
            | Q(subject__code__iexact="CHEM")
            | Q(subject__name__iexact="Physics")
            | Q(subject__name__iexact="Chemistry")
        )

    subject_id = request.query_params.get("subject_id")
    if subject_id:
        banks_qs = banks_qs.filter(subject_id=subject_id)

    search = str(request.query_params.get("q") or "").strip()
    if search:
        banks_qs = banks_qs.filter(Q(name__icontains=search) | Q(questions__text__icontains=search)).distinct()

    try:
        limit = max(1, min(int(request.query_params.get("limit", 200)), 500))
    except Exception:
        limit = 200

    question_rows = []
    bank_rows = []
    seen_question_ids = set()
    for bank in banks_qs.order_by("subject__name", "name")[:100]:
        bank_questions = list(bank.questions.filter(question_type="mcq").order_by("id")[:limit])
        bank_rows.append(
            {
                "id": bank.id,
                "name": bank.name,
                "subject_id": bank.subject_id,
                "subject_name": bank.subject.name if bank.subject else "",
                "question_count": len(bank_questions),
                "is_shared": bank.is_shared,
            }
        )
        for question in bank_questions:
            if question.id in seen_question_ids:
                continue
            if search and search.lower() not in question.text.lower() and search.lower() not in bank.name.lower():
                continue
            seen_question_ids.add(question.id)
            question_rows.append(_cbt_bank_question_payload(question, bank))
            if len(question_rows) >= limit:
                break
        if len(question_rows) >= limit:
            break

    return Response(
        {
            "success": True,
            "banks": bank_rows,
            "questions": question_rows,
        }
    )


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def messages_snapshot(request):
    user = request.user
    now = timezone.now()

    notifications = _tenant_notifications_for_user(user).order_by("-created_at") if Notification else []
    inbox = _tenant_inbox_for_user(user).order_by("-created_at") if InAppMessage else []
    announcements = _visible_announcements_for_user(user, now=now)
    recipients = _message_recipient_queryset_for_user(user).order_by("role", "first_name", "last_name", "email")
    can_manage_messages = _can_manage_school_settings(user)
    guardian_sms_recipients = _guardian_sms_contacts_for_school(user.tenant) if can_manage_messages else []
    sms_config = _kudisms_config_for_school(user.tenant) if can_manage_messages else {}

    return Response(
        {
            "success": True,
            "summary": {
                "unread_notifications": notifications.filter(is_read=False).count() if Notification else 0,
                "unread_inbox": inbox.filter(is_read=False).count() if InAppMessage else 0,
                "active_announcements": len(announcements),
            },
            "notifications": [
                {
                    "id": str(item.id),
                    "title": item.title,
                    "message": item.message,
                    "type": item.notification_type,
                    "is_read": item.is_read,
                    "created_at": item.created_at,
                }
                for item in notifications[:8]
            ],
            "inbox": [
                _message_payload(item, request=request, viewer=user)
                for item in inbox[:20]
            ],
            "announcements": [
                {
                    "id": str(item.id),
                    "title": item.title,
                    "priority": item.priority,
                    "published_at": item.publish_from,
                }
                for item in announcements[:5]
            ],
            "recipients": [
                {
                    "id": str(item.id),
                    "name": item.get_full_name(),
                    "email": item.email,
                    "role": item.role,
                    "profile_picture": _profile_picture_url(request, item),
                }
                for item in recipients[:100]
            ],
            "guardian_sms_recipients": guardian_sms_recipients,
            "sms_configured": bool(sms_config.get("token") and sms_config.get("is_active")) if can_manage_messages else False,
        }
    )


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def create_class(request):
    name = str(request.data.get("name", "")).strip()
    section = str(request.data.get("section", "")).strip()
    subject_ids = _parse_id_list(request.data.get("subject_ids"))

    if len(name) < 2:
        return Response(
            {"success": False, "message": "Class name must be at least 2 characters."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    tenant_obj = _tenant_for_model(Class, request.user, school_code=request.data.get("school_code"))
    if not tenant_obj:
        return Response(
            {
                "success": False,
                "message": "Could not resolve tenant for class creation. Use a valid school code when signing in.",
            },
            status=status.HTTP_400_BAD_REQUEST,
        )

    class_obj = Class.objects.create(
        name=name,
        section=section or None,
        tenant=tenant_obj,
    )
    if subject_ids:
        subjects = _scope_to_user_tenant(Subject.objects.all(), request.user).filter(id__in=subject_ids)
        class_obj.subjects.set(subjects)
    class_obj = Class.objects.prefetch_related("subjects").get(id=class_obj.id)
    return Response(
        {
            "success": True,
            "message": "Class created.",
            "class": _class_payload(class_obj),
        },
        status=status.HTTP_201_CREATED,
    )


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def create_subject(request):
    user = request.user
    name = str(request.data.get("name", "")).strip()
    code = (str(request.data.get("code", "")).strip() or name[:5]).upper()

    if getattr(user, "role", None) not in ADMIN_ROLES:
        return Response(
            {"success": False, "message": "Only school administrators can create subjects."},
            status=status.HTTP_403_FORBIDDEN,
        )

    if len(name) < 2:
        return Response(
            {"success": False, "message": "Subject name must be at least 2 characters."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    tenant_obj = _tenant_for_model(Subject, user, school_code=request.data.get("school_code"))
    if not tenant_obj:
        return Response(
            {"success": False, "message": "Could not resolve tenant for subject creation."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    existing_subjects = _scope_to_user_tenant(Subject.objects.all(), user)
    if existing_subjects.filter(name__iexact=name).exists():
        return Response(
            {"success": False, "message": "Subject with this name already exists."},
            status=status.HTTP_400_BAD_REQUEST,
        )
    if existing_subjects.filter(code__iexact=code).exists():
        return Response(
            {"success": False, "message": "Subject with this code already exists."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    subject = Subject.objects.create(name=name, code=code, tenant=tenant_obj)
    return Response(
        {
            "success": True,
            "message": "Subject created.",
            "subject": {
                "id": subject.id,
                "name": subject.name,
                "code": subject.code,
                "tenant_id": subject.tenant_id,
            },
        },
        status=status.HTTP_201_CREATED,
    )


@api_view(["PATCH", "DELETE"])
@permission_classes([IsAuthenticated])
def subject_detail(request, subject_id):
    subject_qs = _scope_to_user_tenant(Subject.objects.all(), request.user)
    subject = get_object_or_404(subject_qs, id=subject_id)

    if request.method == "DELETE":
        subject.delete()
        return Response({"success": True, "message": "Subject deleted."})

    name = request.data.get("name")
    code = request.data.get("code")
    update_fields = []

    if name is not None:
        cleaned = str(name).strip()
        if len(cleaned) < 2:
            return Response(
                {"success": False, "message": "Subject name must be at least 2 characters."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        subject.name = cleaned
        update_fields.append("name")

    if code is not None:
        cleaned_code = str(code).strip()
        subject.code = cleaned_code or subject.code
        update_fields.append("code")

    if update_fields:
        subject.save(update_fields=update_fields)

    return Response(
        {
            "success": True,
            "message": "Subject updated.",
            "subject": {"id": subject.id, "name": subject.name, "code": subject.code},
        }
    )

@api_view(["PATCH", "DELETE"])
@permission_classes([IsAuthenticated])
def class_detail(request, class_id):
    classes_qs = _scope_to_user_tenant(Class.objects.prefetch_related("subjects"), request.user)
    class_obj = get_object_or_404(classes_qs, id=class_id)

    if request.method == "DELETE":
        class_obj.delete()
        return Response({"success": True, "message": "Class deleted."})

    name = request.data.get("name")
    section = request.data.get("section")

    update_fields = []
    if name is not None:
        cleaned = str(name).strip()
        if len(cleaned) < 2:
            return Response(
                {"success": False, "message": "Class name must be at least 2 characters."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        class_obj.name = cleaned
        update_fields.append("name")

    if section is not None:
        cleaned_section = str(section).strip()
        class_obj.section = cleaned_section or None
        update_fields.append("section")

    if update_fields:
        class_obj.save(update_fields=update_fields)

    if "subject_ids" in request.data:
        subject_ids = _parse_id_list(request.data.get("subject_ids"))
        subjects = _scope_to_user_tenant(Subject.objects.all(), request.user).filter(id__in=subject_ids)
        class_obj.subjects.set(subjects)

    class_obj = Class.objects.prefetch_related("subjects").get(id=class_obj.id)
    return Response(
        {
            "success": True,
            "message": "Class updated.",
            "class": _class_payload(class_obj),
        }
    )


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def create_exam(request):
    title = str(request.data.get("title", "")).strip()
    if len(title) < 3:
        return Response(
            {"success": False, "message": "Exam title must be at least 3 characters."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    start_raw = request.data.get("start_date")
    end_raw = request.data.get("end_date")
    start_date = parse_datetime(start_raw) if start_raw else None
    end_date = parse_datetime(end_raw) if end_raw else None
    if not start_date or not end_date:
        return Response(
            {"success": False, "message": "Valid start_date and end_date are required."},
            status=status.HTTP_400_BAD_REQUEST,
        )
    if end_date <= start_date:
        return Response(
            {"success": False, "message": "Exam end date must be after start date."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    duration_minutes = _positive_duration_minutes(request.data.get("duration_minutes"))
    if duration_minutes <= 0:
        return Response(
            {"success": False, "message": "Valid duration_minutes is required."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    tenant_obj = _tenant_for_model(Exam, request.user, school_code=request.data.get("school_code"))
    if not tenant_obj:
        return Response(
            {
                "success": False,
                "message": "Could not resolve tenant for exam creation. Use a valid school code when signing in.",
            },
            status=status.HTTP_400_BAD_REQUEST,
        )

    class_group = None
    class_id = request.data.get("class_id")
    if class_id not in (None, ""):
        class_group = get_object_or_404(_scope_to_user_tenant(Class.objects.all(), request.user), id=class_id)

    subject = None
    subject_id = request.data.get("subject_id")
    if subject_id not in (None, ""):
        subject = get_object_or_404(_scope_to_user_tenant(Subject.objects.all(), request.user), id=subject_id)
        if request.user.role in ADMIN_ROLES and _hide_from_admin_exam_subjects(subject):
            return Response(
                {"success": False, "message": "Physics and Chemistry are not available for admin exams."},
                status=status.HTTP_400_BAD_REQUEST,
            )

    assessment_type = str(request.data.get("assessment_type", "exam")).strip().lower() or "exam"
    if assessment_type not in {"exam", "test"}:
        return Response(
            {"success": False, "message": "assessment_type must be either 'exam' or 'test'."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    exam_type_name = "Test" if assessment_type == "test" else "Exam"
    exam_type = ExamType.objects.filter(tenant=tenant_obj, name__iexact=exam_type_name).first()
    if not exam_type:
        exam_type = ExamType.objects.create(tenant=tenant_obj, name=exam_type_name)

    can_publish_exam = request.user.role in ADMIN_ROLES
    is_published = _to_bool(request.data.get("is_published"), default=False) if can_publish_exam else False
    shuffle_questions = _to_bool(request.data.get("shuffle_questions"), default=False)
    cleaned_questions, questions_error = _clean_exam_questions_payload(request.data.get("questions") or [])
    if questions_error:
        return Response(
            {"success": False, "message": questions_error},
            status=status.HTTP_400_BAD_REQUEST,
        )

    exam = Exam.objects.create(
        title=title,
        subject=subject,
        class_group=class_group,
        teacher=request.user,
        exam_type=exam_type,
        start_date=start_date,
        end_date=end_date,
        duration_minutes=duration_minutes,
        instructions=str(request.data.get("instructions") or "").strip(),
        shuffle_questions=shuffle_questions,
        show_results_immediately=False,
        is_published=is_published,
        tenant=tenant_obj,
    )
    groups_by_key = _question_groups_from_payload(cleaned_questions, tenant_obj, request.user, request)
    created_questions = [
        _exam_question_from_payload(item, tenant_obj, request.user, request, groups_by_key, index)
        for index, item in enumerate(cleaned_questions, start=1)
    ]
    exam.questions.add(*created_questions)
    if request.user.role == "teacher":
        _notify_admins_exam_ready(exam, request.user)

    return Response(
        {
            "success": True,
            "message": "Exam created and published." if is_published else (
                "Exam sent to admin for publishing." if request.user.role == "teacher" else "Exam saved as draft."
            ),
            "exam": {
                "id": exam.id,
                "title": exam.title,
                "start_date": exam.start_date,
                "end_date": exam.end_date,
                "duration_minutes": exam.duration_minutes,
                "is_published": exam.is_published,
                "assessment_type": assessment_type,
                "question_count": len(created_questions),
                "class_name": _class_label(exam.class_group) if exam.class_group else "All classes",
            },
        },
        status=status.HTTP_201_CREATED,
    )


@api_view(["GET", "PATCH", "DELETE"])
@permission_classes([IsAuthenticated])
def exam_detail(request, exam_id):
    exams_qs = _scope_to_user_tenant(
        Exam.objects.select_related("subject", "class_group", "exam_type").prefetch_related("questions"),
        request.user,
    )
    if request.user.role == "teacher":
        exams_qs = exams_qs.filter(teacher=request.user)
    exam = get_object_or_404(exams_qs, id=exam_id)

    if request.method == "GET":
        return Response({"success": True, "exam": _exam_editor_payload(exam, request)})

    if request.method == "DELETE":
        if request.user.role == "teacher" and exam.is_published:
            return Response(
                {"success": False, "message": "Published exams can only be deleted by an administrator."},
                status=status.HTTP_403_FORBIDDEN,
            )
        exam.delete()
        return Response({"success": True, "message": "Exam deleted."})

    update_fields = []

    if "title" in request.data:
        title = str(request.data.get("title", "")).strip()
        if len(title) < 3:
            return Response(
                {"success": False, "message": "Exam title must be at least 3 characters."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        exam.title = title
        update_fields.append("title")

    if "start_date" in request.data:
        start_date = parse_datetime(request.data.get("start_date"))
        if not start_date:
            return Response(
                {"success": False, "message": "Invalid start_date."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        exam.start_date = start_date
        update_fields.append("start_date")

    if "end_date" in request.data:
        end_date = parse_datetime(request.data.get("end_date"))
        if not end_date:
            return Response(
                {"success": False, "message": "Invalid end_date."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        exam.end_date = end_date
        update_fields.append("end_date")

    if "duration_minutes" in request.data:
        duration_minutes = _positive_duration_minutes(request.data.get("duration_minutes"))
        if duration_minutes <= 0:
            return Response(
                {"success": False, "message": "Valid duration_minutes is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        exam.duration_minutes = duration_minutes
        update_fields.append("duration_minutes")

    if "class_id" in request.data:
        class_id = request.data.get("class_id")
        if class_id in (None, ""):
            exam.class_group = None
        else:
            exam.class_group = get_object_or_404(_scope_to_user_tenant(Class.objects.all(), request.user), id=class_id)
        update_fields.append("class_group")

    if "subject_id" in request.data:
        subject_id = request.data.get("subject_id")
        if subject_id in (None, ""):
            exam.subject = None
        else:
            subject = get_object_or_404(_scope_to_user_tenant(Subject.objects.all(), request.user), id=subject_id)
            if request.user.role in ADMIN_ROLES and _hide_from_admin_exam_subjects(subject):
                return Response(
                    {"success": False, "message": "Physics and Chemistry are not available for admin exams."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            exam.subject = subject
        update_fields.append("subject")

    if "assessment_type" in request.data:
        assessment_type = str(request.data.get("assessment_type", "exam")).strip().lower() or "exam"
        if assessment_type not in {"exam", "test"}:
            return Response(
                {"success": False, "message": "assessment_type must be either 'exam' or 'test'."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        exam_type_name = "Test" if assessment_type == "test" else "Exam"
        tenant_obj = exam.tenant or _tenant_for_model(ExamType, request.user, school_code=request.data.get("school_code"))
        exam_type = ExamType.objects.filter(tenant=tenant_obj, name__iexact=exam_type_name).first()
        if not exam_type:
            exam_type = ExamType.objects.create(tenant=tenant_obj, name=exam_type_name)
        exam.exam_type = exam_type
        update_fields.append("exam_type")

    if "instructions" in request.data:
        exam.instructions = str(request.data.get("instructions") or "").strip()
        update_fields.append("instructions")

    if "shuffle_questions" in request.data:
        exam.shuffle_questions = _to_bool(request.data.get("shuffle_questions"), default=exam.shuffle_questions)
        update_fields.append("shuffle_questions")

    if "show_results_immediately" in request.data:
        exam.show_results_immediately = _to_bool(
            request.data.get("show_results_immediately"),
            default=exam.show_results_immediately,
        )
        update_fields.append("show_results_immediately")

    if "is_published" in request.data:
        if request.user.role not in ADMIN_ROLES:
            if _to_bool(request.data.get("is_published"), default=False):
                return Response(
                    {"success": False, "message": "Only administrators can publish exams."},
                    status=status.HTTP_403_FORBIDDEN,
                )
        else:
            exam.is_published = _to_bool(request.data.get("is_published"), default=exam.is_published)
            update_fields.append("is_published")

    teacher_update_needs_admin_review = request.user.role == "teacher"
    if teacher_update_needs_admin_review and exam.is_published:
        exam.is_published = False
        update_fields.append("is_published")

    if update_fields:
        if "start_date" in update_fields or "end_date" in update_fields:
            if not exam.start_date or not exam.end_date or exam.end_date <= exam.start_date:
                return Response(
                    {"success": False, "message": "Exam end date must be after start date."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
        exam.save(update_fields=list(dict.fromkeys(update_fields)))

    if "questions" in request.data:
        cleaned_questions, questions_error = _clean_exam_questions_payload(request.data.get("questions") or [])
        if questions_error:
            return Response(
                {"success": False, "message": questions_error},
                status=status.HTTP_400_BAD_REQUEST,
            )
        tenant_obj = exam.tenant or _tenant_for_model(Question, request.user, school_code=request.data.get("school_code"))
        groups_by_key = _question_groups_from_payload(cleaned_questions, tenant_obj, request.user, request)
        replacement_questions = [
            _exam_question_from_payload(item, tenant_obj, request.user, request, groups_by_key, index)
            for index, item in enumerate(cleaned_questions, start=1)
        ]
        exam.questions.set(replacement_questions)
        if request.user.role == "teacher" and exam.is_published:
            exam.is_published = False
            exam.save(update_fields=["is_published", "updated_at"])

    exam = (
        Exam.objects.select_related("subject", "class_group", "exam_type")
        .prefetch_related("questions")
        .get(id=exam.id)
    )
    if request.user.role == "teacher":
        _notify_admins_exam_ready(exam, request.user)

    return Response(
        {
            "success": True,
            "message": "Exam sent to admin for publishing." if request.user.role == "teacher" else "Exam updated.",
            "exam": _exam_editor_payload(exam, request),
        }
    )


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def upload_exam_results(request, exam_id):
    exams_qs = _scope_to_user_tenant(Exam.objects.all(), request.user)
    exam = get_object_or_404(exams_qs, id=exam_id)

    uploaded_file = request.FILES.get("file")
    if not uploaded_file:
        return Response(
            {"success": False, "message": "CSV file is required (field name: file)."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    if not uploaded_file.name.lower().endswith(".csv"):
        return Response(
            {"success": False, "message": "Only CSV files are supported."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    tenant_obj = _tenant_for_model(ExamAttempt, request.user, school_code=request.data.get("school_code"))
    if not tenant_obj:
        return Response(
            {
                "success": False,
                "message": "Could not resolve tenant for result upload. Use a valid school code when signing in.",
            },
            status=status.HTTP_400_BAD_REQUEST,
        )

    try:
        decoded = uploaded_file.read().decode("utf-8-sig")
    except Exception:
        return Response(
            {"success": False, "message": "Could not decode CSV file. Use UTF-8."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    reader = csv.DictReader(io.StringIO(decoded))
    if not reader.fieldnames:
        return Response(
            {"success": False, "message": "CSV must include headers."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    lower_fields = {field.strip().lower() for field in reader.fieldnames if field}
    if "student_email" not in lower_fields and "email" not in lower_fields:
        return Response(
            {"success": False, "message": "CSV must contain 'student_email' (or 'email') column."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    processed = 0
    success_count = 0
    failed_count = 0
    errors = []

    for index, row in enumerate(reader, start=2):
        processed += 1
        normalized_row = {str(key).strip().lower(): value for key, value in row.items()}
        student_email = str(normalized_row.get("student_email") or normalized_row.get("email") or "").strip().lower()

        if not student_email:
            failed_count += 1
            errors.append({"row": index, "error": "Missing student email."})
            continue

        student = User.objects.filter(email__iexact=student_email, tenant=request.user.tenant, role="student").first()
        if not student:
            failed_count += 1
            errors.append({"row": index, "error": f"Student '{student_email}' not found in this school."})
            continue

        attempt = ExamAttempt.objects.filter(exam=exam, student=student).order_by("-created_at").first()
        if not attempt:
            attempt = ExamAttempt.objects.create(
                exam=exam,
                student=student,
                tenant=tenant_obj,
            )

        submitted = _to_bool(
            normalized_row.get("submitted") or normalized_row.get("is_submitted") or normalized_row.get("status"),
            default=True,
        )
        completed = _to_bool(
            normalized_row.get("completed") or normalized_row.get("is_completed") or normalized_row.get("status"),
            default=submitted,
        )

        attempt.is_submitted = submitted
        attempt.is_completed = completed
        if completed and not attempt.end_time:
            attempt.end_time = timezone.now()
        attempt.save(update_fields=["is_submitted", "is_completed", "end_time"])
        success_count += 1

    return Response(
        {
            "success": True,
            "message": "Result upload processed.",
            "summary": {
                "exam_id": exam.id,
                "exam_title": exam.title,
                "processed": processed,
                "success": success_count,
                "failed": failed_count,
            },
            "errors": errors[:20],
        }
    )


def _teacher_can_score_subject(teacher, subject):
    profile = TeacherProfile.objects.filter(user=teacher).prefetch_related("subjects").first()
    if profile and profile.subjects.filter(id=subject.id).exists():
        return True

    return _scope_to_user_tenant(
        Exam.objects.filter(teacher=teacher, subject=subject),
        teacher,
    ).exists()


def _student_result_report(student_profile, class_group=None, term=None, request=None, include_unpublished=False):
    class_group = class_group or student_profile.current_class
    scores_qs = (
        StudentSubjectScore.objects.select_related("subject", "teacher", "class_group", "term")
        .filter(student=student_profile)
        .filter(student__user__tenant=student_profile.user.tenant)
    )
    if class_group:
        scores_qs = scores_qs.filter(class_group=class_group)
    if term:
        scores_qs = scores_qs.filter(term=term)
    if not include_unpublished:
        scores_qs = scores_qs.filter(approval_status=ResultBatch.PUBLISHED)

    scores = []
    total_score = 0.0
    for item in scores_qs:
        numeric = float(item.score or 0)
        total_score += numeric
        scores.append(
            {
                "id": str(item.id),
                "subject_id": item.subject_id,
                "subject": item.subject.name if item.subject else "",
                "score": numeric,
                "max_score": float(item.max_score or 0),
                "percentage": item.percentage,
                "grade": item.grade,
                "performance_remark": item.performance_remark or item.remarks,
                "approval_status": item.approval_status,
                "components": {
                    "theory": float(item.theory_score or 0),
                    "cbt": float(item.cbt_score or 0),
                    "assessment": float(item.assessment_score or 0),
                    "assignment": float(item.assignment_score or 0),
                    "attendance": float(item.attendance_score or 0),
                    "other": float(item.other_score or 0),
                },
                "class_name": _class_label(item.class_group) if item.class_group else "",
                "term": item.term.name if item.term else "",
                "teacher": item.teacher.get_full_name() if item.teacher else "",
                "teacher_email": item.teacher.email if item.teacher else "",
                "recorded_at": item.updated_at,
            }
        )

    subject_count = len(scores)
    average_score = round(total_score / subject_count, 2) if subject_count else 0.0

    position = None
    class_size = 0
    if class_group:
        class_total_qs = StudentSubjectScore.objects.filter(class_group=class_group, student__user__tenant=student_profile.user.tenant)
        if not include_unpublished:
            class_total_qs = class_total_qs.filter(approval_status=ResultBatch.PUBLISHED)
        class_totals = class_total_qs.values("student").annotate(total=Sum("score")).order_by("-total", "student")
        class_size = class_totals.count()
        for idx, row in enumerate(class_totals, start=1):
            if row["student"] == student_profile.id:
                position = idx
                break

    return {
        "school": _school_payload(student_profile.user.tenant, request),
        "student": {
            "id": str(student_profile.id),
            "student_id": student_profile.student_id,
            "name": student_profile.user.get_full_name(),
            "gender": student_profile.user.gender,
            "email": student_profile.user.email,
            "class_name": _class_label(class_group) if class_group else "",
            "profile_picture": _profile_picture_url(request, student_profile.user),
        },
        "scores": scores,
        "total_score": round(total_score, 2),
        "average_score": average_score,
        "class_position": position,
        "class_size": class_size,
    }


def _result_leaderboard(user, class_group=None, term=None, teacher=None, limit=25):
    scores_qs = StudentSubjectScore.objects.select_related("student__user", "class_group").filter(
        student__user__tenant=user.tenant
    )
    if class_group:
        scores_qs = scores_qs.filter(class_group=class_group)
    if term:
        scores_qs = scores_qs.filter(term=term)
    if teacher:
        scores_qs = scores_qs.filter(teacher=teacher)

    totals = (
        scores_qs.values(
            "student",
            "student__student_id",
            "student__user__first_name",
            "student__user__last_name",
            "class_group__name",
            "class_group__section",
        )
        .annotate(total_score=Sum("score"), subject_count=Count("subject", distinct=True))
        .order_by("-total_score", "student__student_id")[:limit]
    )

    leaderboard = []
    for idx, row in enumerate(totals, start=1):
        leaderboard.append(
            {
                "rank": idx,
                "student_id": row["student__student_id"],
                "student_name": f"{row['student__user__first_name']} {row['student__user__last_name']}".strip(),
                "class_name": _class_label(class_group) if class_group else row["class_group__name"],
                "total_score": float(row["total_score"] or 0),
                "average_score": round(float(row["total_score"] or 0) / max(row["subject_count"] or 1, 1), 2),
            }
        )
    return leaderboard


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def teacher_class_students(request):
    user = request.user
    if user.role != "teacher":
        return Response({"success": False, "message": "Only teachers can view class students."}, status=status.HTTP_403_FORBIDDEN)
    class_id = request.query_params.get("class_id")
    subject_id = request.query_params.get("subject_id")
    context = str(request.query_params.get("context") or "").strip().lower()
    attendance_date = parse_date(str(request.query_params.get("date") or "")) or timezone.localdate()
    classes_qs = _teacher_assigned_classes(user)
    results_mode = False
    if context == "results" and subject_id:
        subject = get_object_or_404(_scope_to_user_tenant(Subject.objects.all(), user), id=subject_id)
        results_mode = _teacher_can_score_subject(user, subject)
        if not results_mode:
            return Response(
                {"success": False, "message": "You are not assigned to this subject."},
                status=status.HTTP_403_FORBIDDEN,
            )
    if class_id:
        if not results_mode and not classes_qs.filter(id=class_id).exists():
            return Response(
                {"success": False, "message": "You can only mark attendance for classes assigned to you."},
                status=status.HTTP_403_FORBIDDEN,
            )
        if not results_mode:
            classes_qs = classes_qs.filter(id=class_id)
    assigned_class_ids = list(classes_qs.values_list("id", flat=True))
    students_qs = StudentProfile.objects.select_related("user", "current_class").filter(user__tenant=user.tenant)
    if not results_mode:
        students_qs = students_qs.filter(current_class_id__in=assigned_class_ids) if assigned_class_ids else students_qs.none()
    if class_id:
        students_qs = students_qs.filter(current_class_id=class_id)
    attendance_qs = (
        AttendanceRecord.objects.select_related("student", "class_group", "noted_by")
        .filter(student__tenant=user.tenant, date=attendance_date, class_group_id__in=assigned_class_ids)
        .order_by("-updated_at")
    )
    if class_id:
        attendance_qs = attendance_qs.filter(class_group_id=class_id)
    return Response(
        {
            "success": True,
            "date": attendance_date,
            "classes": [{"id": item.id, "label": _class_label(item), "name": item.name} for item in classes_qs.order_by("name", "section")[:100]],
            "students": [
                {
                    "id": str(item.id),
                    "student_id": item.student_id,
                    "name": item.user.get_full_name(),
                    "email": item.user.email,
                    "class_id": item.current_class_id,
                    "class_name": _class_label(item.current_class) if item.current_class else "Unassigned",
                    "profile_picture": _profile_picture_url(request, item.user),
                }
                for item in students_qs.order_by("user__first_name", "user__last_name")[:200]
            ],
            "attendance_records": [
                {
                    "id": str(item.id),
                    "student_id": getattr(getattr(item.student, "student_profile", None), "student_id", ""),
                    "student_name": item.student.get_full_name() or item.student.email,
                    "class_id": item.class_group_id,
                    "class_name": _class_label(item.class_group) if item.class_group else "Unassigned",
                    "date": item.date,
                    "status": item.status,
                    "noted_by": item.noted_by.get_full_name() if item.noted_by else "",
                    "latitude": item.latitude,
                    "longitude": item.longitude,
                    "location_accuracy_meters": item.location_accuracy_meters,
                    "location_address": item.location_address,
                    "updated_at": item.updated_at,
                }
                for item in attendance_qs[:200]
            ],
        }
    )


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def teacher_mark_student_attendance(request):
    user = request.user
    if user.role != "teacher":
        return Response({"success": False, "message": "Only teachers can mark student attendance."}, status=status.HTTP_403_FORBIDDEN)
    student_code = str(
        request.data.get("student_id")
        or request.data.get("student_lookup")
        or request.data.get("student_email")
        or request.data.get("student_name")
        or ""
    ).strip()
    status_value = str(request.data.get("status") or "").strip().lower()
    if status_value not in {"present", "absent", "late"}:
        return Response({"success": False, "message": "status must be present, absent, or late."}, status=status.HTTP_400_BAD_REQUEST)
    assigned_classes = _teacher_assigned_classes(user)
    assigned_class_ids = set(assigned_classes.values_list("id", flat=True))
    student_profile = get_object_or_404(StudentProfile.objects.select_related("user", "current_class"), student_id__iexact=student_code, user__tenant=user.tenant)
    raw_class_id = request.data.get("class_id")
    if raw_class_id and str(student_profile.current_class_id) != str(raw_class_id):
        return Response(
            {"success": False, "message": "Selected student is not in that class."},
            status=status.HTTP_400_BAD_REQUEST,
        )
    if not student_profile.current_class_id or student_profile.current_class_id not in assigned_class_ids:
        return Response(
            {"success": False, "message": "You can only mark attendance for classes assigned to you."},
            status=status.HTTP_403_FORBIDDEN,
        )
    try:
        location = _attendance_location_payload(request)
    except ValueError as exc:
        return Response({"success": False, "message": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
    attendance_date = parse_date(str(request.data.get("date") or "")) or timezone.localdate()
    tenant_obj = _tenant_for_model(AttendanceRecord, user)
    attendance, _created = AttendanceRecord.objects.update_or_create(
        student=student_profile.user,
        date=attendance_date,
        defaults={
            "status": status_value,
            "class_group": student_profile.current_class,
            "noted_by": user,
            "tenant": tenant_obj,
            "latitude": location["latitude"],
            "longitude": location["longitude"],
            "location_accuracy_meters": location["accuracy"],
            "location_address": location["address"],
            "device_info": location["device_info"],
        },
    )
    return Response(
        {
            "success": True,
            "message": f"{student_profile.user.get_full_name()} marked {status_value}.",
            "attendance": {
                "id": str(attendance.id),
                "student_id": student_profile.student_id,
                "student_name": student_profile.user.get_full_name(),
                "class_name": _class_label(attendance.class_group) if attendance.class_group else "Unassigned",
                "date": attendance.date,
                "status": attendance.status,
                "latitude": attendance.latitude,
                "longitude": attendance.longitude,
                "location_accuracy_meters": attendance.location_accuracy_meters,
                "location_address": attendance.location_address,
            },
        }
    )


@api_view(["GET", "POST"])
@permission_classes([IsAuthenticated])
def grading_scales(request):
    user = request.user
    if user.role not in ADMIN_ROLES and user.role != "teacher":
        return Response({"success": False, "message": "Only admins and teachers can manage grading scales."}, status=status.HTTP_403_FORBIDDEN)
    scales = _ensure_default_grade_scales(user)
    if request.method == "POST":
        tenant_obj = _tenant_for_model(GradeScale, user)
        letter = str(request.data.get("letter") or "").strip().upper()
        if not letter:
            return Response({"success": False, "message": "letter is required."}, status=status.HTTP_400_BAD_REQUEST)
        try:
            min_percentage = Decimal(str(request.data.get("min_percentage", 0)))
            max_percentage = Decimal(str(request.data.get("max_percentage", 100)))
        except (InvalidOperation, TypeError, ValueError):
            return Response({"success": False, "message": "Grade percentages must be valid numbers."}, status=status.HTTP_400_BAD_REQUEST)
        if min_percentage < 0 or max_percentage > 100 or min_percentage > max_percentage:
            return Response({"success": False, "message": "Use a valid grade percentage range between 0 and 100."}, status=status.HTTP_400_BAD_REQUEST)
        scale, _created = GradeScale.objects.update_or_create(
            tenant=tenant_obj,
            letter=letter,
            defaults={
                "min_percentage": min_percentage,
                "max_percentage": max_percentage,
                "remark": str(request.data.get("remark") or "").strip(),
                "is_active": _to_bool(request.data.get("is_active"), True),
            },
        )
        scales = GradeScale.objects.filter(tenant=tenant_obj, is_active=True)
        message = f"Grade {scale.letter} saved."
    else:
        message = "Grade scales loaded."
    return Response(
        {
            "success": True,
            "message": message,
            "grades": [
                {
                    "id": item.id,
                    "letter": item.letter,
                    "min_percentage": float(item.min_percentage),
                    "max_percentage": float(item.max_percentage),
                    "remark": item.remark,
                    "is_active": item.is_active,
                }
                for item in scales
            ],
        }
    )


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def push_results_to_admin(request):
    user = request.user
    if user.role != "teacher":
        return Response({"success": False, "message": "Only teachers can push results."}, status=status.HTTP_403_FORBIDDEN)
    class_id = request.data.get("class_id")
    term_id = request.data.get("term_id")
    class_group = get_object_or_404(_scope_to_user_tenant(Class.objects.all(), user), id=class_id) if class_id else None
    term = get_object_or_404(_scope_to_user_tenant(Term.objects.all(), user), id=term_id) if term_id else None
    scores = StudentSubjectScore.objects.filter(teacher=user, approval_status__in=[ResultBatch.DRAFT, ResultBatch.REJECTED])
    if class_group:
        scores = scores.filter(class_group=class_group)
    if term:
        scores = scores.filter(term=term)
    if not scores.exists():
        return Response({"success": False, "message": "No draft results found to push."}, status=status.HTTP_400_BAD_REQUEST)
    for score in scores:
        percentage = score.percentage
        if percentage is None:
            continue
        grade_letter, grade_remark = _grade_for_percentage(user, percentage)
        if score.grade != grade_letter or score.performance_remark != grade_remark:
            score.grade = grade_letter
            score.performance_remark = grade_remark
            score.save(update_fields=["grade", "performance_remark", "updated_at"])
    tenant_obj = _tenant_for_model(ResultBatch, user)
    batch = ResultBatch.objects.create(
        tenant=tenant_obj,
        title=str(request.data.get("title") or f"{_class_label(class_group) if class_group else 'All classes'} results"),
        class_group=class_group,
        term=term,
        teacher=user,
        status=ResultBatch.PENDING,
        submitted_at=timezone.now(),
    )
    scores.update(result_batch=batch, approval_status=ResultBatch.PENDING, submitted_at=timezone.now())
    return Response({"success": True, "message": "Results pushed to admin for review.", "batch_id": batch.id, "count": scores.count()})


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def review_result_batch(request, batch_id):
    user = request.user
    if user.role not in ADMIN_ROLES:
        return Response({"success": False, "message": "Only admins can review results."}, status=status.HTTP_403_FORBIDDEN)
    batch = get_object_or_404(_scope_to_user_tenant(ResultBatch.objects.all(), user), id=batch_id)
    decision = str(request.data.get("status") or "").strip().lower()
    if decision not in {ResultBatch.APPROVED, ResultBatch.PUBLISHED, ResultBatch.REJECTED}:
        return Response({"success": False, "message": "status must be approved, published, or rejected."}, status=status.HTTP_400_BAD_REQUEST)
    now = timezone.now()
    batch.status = decision
    batch.reviewed_by = user
    batch.reviewed_at = now
    batch.admin_note = str(request.data.get("admin_note") or "").strip()
    if decision == ResultBatch.PUBLISHED:
        batch.published_at = now
    batch.save(update_fields=["status", "reviewed_by", "reviewed_at", "admin_note", "published_at", "updated_at"])
    update_fields = {"approval_status": decision, "approved_by": user if decision in {ResultBatch.APPROVED, ResultBatch.PUBLISHED} else None, "approved_at": now if decision in {ResultBatch.APPROVED, ResultBatch.PUBLISHED} else None}
    if decision == ResultBatch.PUBLISHED:
        update_fields["published_at"] = now
    batch.scores.update(**update_fields)
    return Response({"success": True, "message": f"Results {decision}.", "batch_id": batch.id})


@api_view(["DELETE"])
@permission_classes([IsAuthenticated])
def delete_result_batch(request, batch_id):
    user = request.user
    if user.role not in ADMIN_ROLES:
        return Response({"success": False, "message": "Only admins can delete results."}, status=status.HTTP_403_FORBIDDEN)
    batch = get_object_or_404(_scope_to_user_tenant(ResultBatch.objects.all(), user), id=batch_id)
    score_count = batch.scores.count()
    batch.scores.all().delete()
    batch.delete()
    return Response({"success": True, "message": f"Deleted result batch and {score_count} score record(s).", "batch_id": batch_id})


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def submit_subject_score(request):
    user = request.user
    if user.role != "teacher":
        return Response(
            {"success": False, "message": "Only teachers can submit subject scores."},
            status=status.HTTP_403_FORBIDDEN,
        )

    student_code = str(request.data.get("student_id") or "").strip()
    subject_id = request.data.get("subject_id") or request.data.get("subject")
    class_id = request.data.get("class_id")
    term_id = request.data.get("term_id")
    remarks = str(request.data.get("remarks", "")).strip()

    if not student_code:
        return Response(
            {"success": False, "message": "student_id is required."},
            status=status.HTTP_400_BAD_REQUEST,
        )
    if not subject_id:
        return Response(
            {"success": False, "message": "subject_id is required."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    component_fields = {
        "theory_score": "theory",
        "cbt_score": "cbt",
        "assessment_score": "assessment",
        "assignment_score": "assignment",
        "attendance_score": "attendance",
        "other_score": "other",
    }
    components = {}
    has_components = any(key in request.data or alias in request.data for key, alias in component_fields.items())
    for field, alias in component_fields.items():
        try:
            components[field] = float(request.data.get(field, request.data.get(alias, 0)) or 0)
        except Exception:
            return Response(
                {"success": False, "message": f"{field} must be a number."},
                status=status.HTTP_400_BAD_REQUEST,
            )
    if has_components:
        score_value = sum(components.values())
    else:
        try:
            score_value = float(request.data.get("score"))
        except Exception:
            return Response(
                {"success": False, "message": "score must be a number."},
                status=status.HTTP_400_BAD_REQUEST,
            )

    try:
        max_score = float(request.data.get("max_score", 100))
    except Exception:
        return Response(
            {"success": False, "message": "max_score must be a number."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    if score_value < 0:
        return Response(
            {"success": False, "message": "score cannot be negative."},
            status=status.HTTP_400_BAD_REQUEST,
        )
    if max_score <= 0:
        return Response(
            {"success": False, "message": "max_score must be greater than zero."},
            status=status.HTTP_400_BAD_REQUEST,
        )
    if score_value > max_score:
        return Response(
            {"success": False, "message": "score cannot exceed max_score."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    subject = get_object_or_404(_scope_to_user_tenant(Subject.objects.all(), user), id=subject_id)

    if not _teacher_can_score_subject(user, subject):
        return Response(
            {"success": False, "message": "You are not assigned to this subject."},
            status=status.HTTP_403_FORBIDDEN,
        )

    class_group = None
    if class_id not in (None, ""):
        class_group = get_object_or_404(_scope_to_user_tenant(Class.objects.all(), user), id=class_id)

    student_matches = StudentProfile.objects.select_related("user", "current_class").filter(
        user__tenant=user.tenant,
    )
    if class_id not in (None, ""):
        student_matches = student_matches.filter(current_class_id=class_id)
    name_terms = [term for term in re.split(r"\s+", student_code) if term]
    name_query = Q(user__first_name__icontains=student_code) | Q(user__last_name__icontains=student_code)
    if len(name_terms) >= 2:
        name_query |= Q(user__first_name__icontains=name_terms[0], user__last_name__icontains=name_terms[-1])
        name_query |= Q(user__first_name__icontains=name_terms[-1], user__last_name__icontains=name_terms[0])
    student_matches = student_matches.filter(
        Q(student_id__iexact=student_code)
        | Q(user__email__iexact=student_code)
        | name_query
    )
    student_profile = None
    normalized_lookup = re.sub(r"\s+", " ", student_code).strip().lower()
    for candidate in student_matches[:25]:
        candidate_name = re.sub(r"\s+", " ", candidate.user.get_full_name()).strip().lower()
        if (
            str(candidate.student_id or "").lower() == normalized_lookup
            or str(candidate.user.email or "").lower() == normalized_lookup
            or candidate_name == normalized_lookup
            or normalized_lookup in candidate_name
        ):
            student_profile = candidate
            break
    if not student_profile:
        return Response(
            {"success": False, "message": "Student not found in this school or selected class."},
            status=status.HTTP_404_NOT_FOUND,
        )

    if class_group and student_profile.current_class_id != class_group.id:
        return Response(
            {"success": False, "message": "Selected student is not in that class."},
            status=status.HTTP_400_BAD_REQUEST,
        )
    if not class_group and student_profile.current_class_id:
        class_group = student_profile.current_class

    if not class_group:
        return Response(
            {"success": False, "message": "Student does not have a class assigned."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    term = None
    if term_id not in (None, ""):
        term = get_object_or_404(_scope_to_user_tenant(Term.objects.all(), user), id=term_id)

    tenant_obj = _tenant_for_model(StudentSubjectScore, user, school_code=request.data.get("school_code"))
    if not tenant_obj:
        return Response(
            {"success": False, "message": "Could not resolve school for this score submission."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    percentage = round((score_value / max(max_score, 1)) * 100, 2)
    grade_letter, grade_remark = _grade_for_percentage(user, percentage)

    score_obj, _created = StudentSubjectScore.objects.update_or_create(
        student=student_profile,
        subject=subject,
        class_group=class_group,
        term=term,
        defaults={
            "score": score_value,
            "max_score": max_score,
            **components,
            "grade": grade_letter,
            "performance_remark": grade_remark,
            "approval_status": ResultBatch.DRAFT,
            "teacher": user,
            "remarks": remarks,
            "tenant": tenant_obj,
        },
    )

    report = _student_result_report(student_profile, class_group=class_group, term=term, request=request, include_unpublished=True)
    return Response(
        {
            "success": True,
            "message": "Score saved as draft. Push results to admin when ready.",
            "score": {
                "id": str(score_obj.id),
                "subject": subject.name,
                "score": score_value,
                "max_score": max_score,
                "grade": grade_letter,
                "remark": grade_remark,
                "approval_status": score_obj.approval_status,
            },
            "report": report,
        },
        status=status.HTTP_201_CREATED,
    )


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def results_snapshot(request):
    user = request.user
    allowed_roles = {"school_admin", "principal", "super_admin", "teacher"}
    if user.role not in allowed_roles:
        return Response(
            {"success": False, "message": "You are not allowed to view results."},
            status=status.HTTP_403_FORBIDDEN,
        )

    class_group = None
    term = None
    class_id = request.query_params.get("class_id")
    term_id = request.query_params.get("term_id")
    student_code = request.query_params.get("student_id")
    teacher_only = user.role == "teacher" and _to_bool(request.query_params.get("teacher_only"), default=False)

    if class_id:
        class_group = get_object_or_404(_scope_to_user_tenant(Class.objects.all(), user), id=class_id)
    if term_id:
        term = get_object_or_404(_scope_to_user_tenant(Term.objects.all(), user), id=term_id)

    scores_qs = StudentSubjectScore.objects.select_related("student__user", "subject", "class_group", "teacher").filter(student__user__tenant=user.tenant)
    if class_group:
        scores_qs = scores_qs.filter(class_group=class_group)
    if term:
        scores_qs = scores_qs.filter(term=term)
    if teacher_only:
        scores_qs = scores_qs.filter(teacher=user)

    response_payload = {
        "success": True,
        "summary": {
            "total_records": scores_qs.count(),
            "students_with_scores": scores_qs.values("student").distinct().count(),
            "pending_batches": ResultBatch.objects.filter(tenant=_tenant_for_model(ResultBatch, user), status=ResultBatch.PENDING).count() if user.role in ADMIN_ROLES else 0,
        },
        "results": [
            {
                "id": str(item.id),
                "student_id": item.student.student_id,
                "student_name": item.student.user.get_full_name(),
                "subject": item.subject.name if item.subject else "",
                "class_name": _class_label(item.class_group) if item.class_group else "",
                "score": float(item.score or 0),
                "max_score": float(item.max_score or 0),
                "percentage": item.percentage,
                "grade": item.grade,
                "remark": item.performance_remark or item.remarks,
                "approval_status": item.approval_status,
                "teacher": item.teacher.get_full_name() if item.teacher else "",
            }
            for item in scores_qs.order_by("-updated_at")[:200]
        ],
        "result_batches": [
            {
                "id": item.id,
                "title": item.title,
                "class_name": _class_label(item.class_group) if item.class_group else "All classes",
                "teacher": item.teacher.get_full_name() if item.teacher else "",
                "status": item.status,
                "submitted_at": item.submitted_at,
                "score_count": item.scores.count(),
            }
            for item in _scope_to_user_tenant(ResultBatch.objects.select_related("class_group", "teacher").prefetch_related("scores"), user).order_by("-updated_at")[:50]
        ] if user.role in ADMIN_ROLES else [],
        "grade_scales": [
            {"letter": item.letter, "min_percentage": float(item.min_percentage), "max_percentage": float(item.max_percentage), "remark": item.remark}
            for item in _ensure_default_grade_scales(user)
        ],
        "leaderboard": _result_leaderboard(
            user, class_group=class_group, term=term, teacher=user if teacher_only else None, limit=25
        ),
        "options": {
            "classes": [
                {"id": item.id, "label": _class_label(item)}
                for item in _scope_to_user_tenant(Class.objects.all(), user)[:100]
            ],
            "subjects": [
                {"id": item.id, "name": item.name, "code": item.code}
                for item in _scope_to_user_tenant(Subject.objects.all(), user)[:100]
            ],
            "terms": [
                {"id": item.id, "name": item.name}
                for item in _scope_to_user_tenant(Term.objects.all(), user)[:20]
            ],
        },
    }

    if student_code:
        student_profile = get_object_or_404(
            StudentProfile.objects.select_related("user", "current_class"),
            student_id__iexact=student_code,
            user__tenant=user.tenant,
        )
        response_payload["report_card"] = _student_result_report(
            student_profile, class_group=class_group or student_profile.current_class, term=term, request=request, include_unpublished=user.role in ADMIN_ROLES
        )

    if user.role == "teacher":
        response_payload["subjects_taught"] = _subjects_taught_for_teacher(user)

    return Response(response_payload)


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def student_my_results(request):
    user = request.user
    if user.role != "student":
        return Response(
            {"success": False, "message": "Only students can view this report card."},
            status=status.HTTP_403_FORBIDDEN,
        )

    student_profile = StudentProfile.objects.select_related("user", "current_class").filter(user=user).first()
    if not student_profile:
        return Response(
            {"success": False, "message": "Student profile is required to view results."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    class_group = None
    term = None
    class_id = request.query_params.get("class_id")
    term_id = request.query_params.get("term_id")

    if class_id not in (None, ""):
        class_group = get_object_or_404(_scope_to_user_tenant(Class.objects.all(), user), id=class_id)
    if term_id not in (None, ""):
        term = get_object_or_404(_scope_to_user_tenant(Term.objects.all(), user), id=term_id)

    report = _student_result_report(student_profile, class_group=class_group, term=term, request=request)
    return Response({"success": True, "report_card": report})


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def student_report_card(request, student_code):
    user = request.user
    if user.role not in {"school_admin", "principal", "super_admin"}:
        return Response(
            {"success": False, "message": "Only administrators can generate report cards."},
            status=status.HTTP_403_FORBIDDEN,
        )

    class_group = None
    term = None
    class_id = request.query_params.get("class_id")
    term_id = request.query_params.get("term_id")

    if class_id:
        class_group = get_object_or_404(_scope_to_user_tenant(Class.objects.all(), user), id=class_id)
    if term_id:
        term = get_object_or_404(_scope_to_user_tenant(Term.objects.all(), user), id=term_id)

    student_profile = get_object_or_404(
        StudentProfile.objects.select_related("user", "current_class"),
        student_id__iexact=student_code,
        user__tenant=user.tenant,
    )

    report = _student_result_report(student_profile, class_group=class_group, term=term, request=request)
    return Response({"success": True, "report_card": report})


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def messages_inbox(request):
    if not InAppMessage:
        return Response(
            {"success": True, "summary": {"total": 0, "unread": 0}, "messages": []},
        )

    messages = _tenant_inbox_for_user(request.user).order_by("-created_at")
    return Response(
        {
            "success": True,
            "summary": {
                "total": messages.count(),
                "unread": messages.filter(is_read=False).count(),
            },
            "messages": [
                _message_payload(msg, request=request, viewer=request.user)
                for msg in messages[:20]
            ],
        }
    )


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def send_message(request):
    target = str(request.data.get("target", "")).strip().lower()
    recipient_email = str(request.data.get("recipient_email", "")).strip().lower()
    body = str(request.data.get("body", "")).strip()
    subject = str(request.data.get("subject", "")).strip()
    try:
        attachments = _collect_message_attachments(request)
    except ValueError as exc:
        return Response(
            {"success": False, "message": str(exc)},
            status=status.HTTP_400_BAD_REQUEST,
        )

    if len(body) < 1 and not attachments:
        return Response(
            {"success": False, "message": "Message body or attachment is required."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    if target == "guardian_sms":
        if not _can_manage_school_settings(request.user):
            return Response(
                {"success": False, "message": "Only administrators can send guardian SMS."},
                status=status.HTTP_403_FORBIDDEN,
            )
        if not getattr(request.user, "tenant_id", None):
            return Response(
                {"success": False, "message": "Your account is not linked to a school."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        raw_recipients = request.data.get("recipients") or request.data.get("phone_numbers") or []
        if isinstance(raw_recipients, str):
            raw_recipients = re.split(r"[\s,;]+", raw_recipients)
        if not isinstance(raw_recipients, (list, tuple)):
            return Response(
                {"success": False, "message": "recipients must be a list of phone numbers."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            sms_result = _send_kudisms_bulk_sms(request.user.tenant, raw_recipients, body)
        except ValueError as exc:
            return Response(
                {"success": False, "message": str(exc)},
                status=status.HTTP_400_BAD_REQUEST,
            )
        except requests.RequestException:
            return Response(
                {"success": False, "message": "Could not reach KudiSMS. Please try again."},
                status=status.HTTP_502_BAD_GATEWAY,
            )

        return Response(
            {
                "success": True,
                "message": f"SMS sent to {sms_result['recipient_count']} guardian number(s).",
                "sms_data": sms_result,
            },
            status=status.HTTP_201_CREATED,
        )

    if target in {"students_teachers_announcement", "school_broadcast"}:
        if not Announcement:
            return Response(
                {"success": False, "message": "Announcements module is not available."},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )
        if not _can_manage_school_settings(request.user):
            return Response(
                {"success": False, "message": "Only administrators can publish announcements."},
                status=status.HTTP_403_FORBIDDEN,
            )
        if not getattr(request.user, "tenant_id", None):
            return Response(
                {"success": False, "message": "Your account is not linked to a school."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        title = (subject or body[:200] or "School announcement").strip()[:200]
        announcement = Announcement.objects.create(
            tenant=request.user.tenant,
            author=request.user,
            title=title,
            slug=_build_unique_announcement_slug(title),
            summary=body[:500],
            content=body,
            audience_type="role",
            target_roles=["student", "teacher", "staff"],
            attachments=attachments,
            publish_from=timezone.now(),
            is_published=True,
        )

        return Response(
            {
                "success": True,
                "message": "Announcement published to all staff, students, and teachers.",
                "announcement_data": {
                    "id": str(announcement.id),
                    "title": announcement.title,
                    "published_at": announcement.publish_from,
                },
            },
            status=status.HTTP_201_CREATED,
        )

    if not InAppMessage:
        return Response(
            {"success": False, "message": "Messaging module is not available."},
            status=status.HTTP_503_SERVICE_UNAVAILABLE,
        )

    if target == "class":
        class_id = request.data.get("class_id") or request.data.get("school_class")
        if not class_id:
            return Response(
                {"success": False, "message": "class_id is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if getattr(request.user, "role", "") == "teacher":
            class_qs = _teacher_assigned_classes(request.user)
        elif _can_manage_school_settings(request.user):
            class_qs = _scope_to_user_tenant(Class.objects.all(), request.user)
        else:
            return Response(
                {"success": False, "message": "Only teachers and administrators can message a class."},
                status=status.HTTP_403_FORBIDDEN,
            )

        class_obj = get_object_or_404(class_qs, id=class_id)
        student_profiles = (
            StudentProfile.objects.select_related("user")
            .filter(current_class=class_obj, user__tenant=request.user.tenant, user__is_active=True)
            .exclude(user=request.user)
        )
        recipients = [profile.user for profile in student_profiles if profile.user_id]
        if not recipients:
            return Response(
                {"success": False, "message": "No active students were found in this class."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        title = subject or f"Message for {_class_label(class_obj)}"
        messages = [
            InAppMessage(
                tenant=request.user.tenant,
                sender=request.user,
                recipient=recipient,
                subject=title,
                body=body,
                attachments=[dict(item) for item in attachments],
            )
            for recipient in recipients
        ]
        created_messages = InAppMessage.objects.bulk_create(messages)
        if Notification:
            Notification.objects.bulk_create(
                [
                    Notification(
                        tenant=request.user.tenant,
                        user=msg.recipient,
                        title=f"New message from {request.user.get_full_name() or request.user.email}",
                        message=body,
                        notification_type="info",
                        priority=2,
                        channel="in_app",
                        is_delivered=True,
                        delivered_at=timezone.now(),
                        event_type="message_received",
                        reference_id=msg.id,
                        reference_model="InAppMessage",
                        deep_link="/messages",
                    )
                    for msg in created_messages
                ]
            )

        return Response(
            {
                "success": True,
                "message": f"Message sent to {len(messages)} student(s) in {_class_label(class_obj)}.",
                "message_data": {
                    "class_id": class_obj.id,
                    "class_label": _class_label(class_obj),
                    "recipient_count": len(messages),
                    "subject": title,
                    "attachments": attachments,
                },
            },
            status=status.HTTP_201_CREATED,
        )

    if not recipient_email:
        return Response(
            {"success": False, "message": "recipient_email is required."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    recipient = get_object_or_404(User, email__iexact=recipient_email, tenant=request.user.tenant)
    if not _is_allowed_message_recipient(request.user, recipient):
        return Response(
            {"success": False, "message": "You can only message approved contacts for your role."},
            status=status.HTTP_403_FORBIDDEN,
        )

    message = InAppMessage.objects.create(
        tenant=request.user.tenant,
        sender=request.user,
        recipient=recipient,
        subject=subject or None,
        body=body,
        attachments=attachments,
    )
    if Notification:
        Notification.objects.create(
            tenant=request.user.tenant,
            user=recipient,
            title=f"New message from {request.user.get_full_name() or request.user.email}",
            message=body,
            notification_type="info",
            priority=2,
            channel="in_app",
            is_delivered=True,
            delivered_at=timezone.now(),
            event_type="message_received",
            reference_id=message.id,
            reference_model="InAppMessage",
            deep_link="/messages",
        )

    return Response(
        {
            "success": True,
            "message": "Message sent.",
            "message_data": {
                "id": str(message.id),
                "to": recipient.email,
                "subject": message.subject or "",
                "body": message.body,
                "attachments": _message_payload(message, request=request, viewer=request.user)["attachments"],
                "created_at": message.created_at,
            },
        },
        status=status.HTTP_201_CREATED,
    )


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def mark_message_read(request, message_id):
    if not InAppMessage:
        return Response(
            {"success": False, "message": "Messaging module is not available."},
            status=status.HTTP_503_SERVICE_UNAVAILABLE,
        )

    message = get_object_or_404(_tenant_inbox_for_user(request.user), id=message_id)
    message.mark_as_read()
    return Response({"success": True, "message": "Message marked as read."})


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def mark_notification_read(request, notification_id):
    if not Notification:
        return Response(
            {"success": False, "message": "Notification module is not available."},
            status=status.HTTP_503_SERVICE_UNAVAILABLE,
        )

    notification = get_object_or_404(_tenant_notifications_for_user(request.user), id=notification_id)
    notification.mark_as_read()
    return Response({"success": True, "message": "Notification marked as read."})


@api_view(["POST", "DELETE"])
@permission_classes([IsAuthenticated])
def register_mobile_device(request):
    token = str(request.data.get("token") or "").strip()
    platform = str(request.data.get("platform") or "").strip().lower()
    provider = str(request.data.get("provider") or "expo").strip().lower()
    device_name = str(request.data.get("device_name") or "").strip()

    if not token:
        return Response(
            {"success": False, "message": "Device token is required."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    user = request.user
    existing_tokens = list(user.device_tokens or [])
    normalized_tokens = []
    for item in existing_tokens:
        if isinstance(item, str):
            normalized_tokens.append({"token": item, "provider": "legacy"})
        elif isinstance(item, dict) and item.get("token"):
            normalized_tokens.append(item)

    if request.method == "DELETE":
        next_tokens = [item for item in normalized_tokens if item.get("token") != token]
        user.device_tokens = next_tokens
        user.save(update_fields=["device_tokens"])
        if NotificationPreference:
            preference = NotificationPreference.objects.filter(user=user).first()
            if preference:
                preference.device_tokens = [item for item in list(preference.device_tokens or []) if item.get("token", item) != token]
                preference.save(update_fields=["device_tokens"])
        return Response({"success": True, "message": "Device removed.", "device_count": len(next_tokens)})

    device_payload = {
        "token": token,
        "platform": platform,
        "provider": provider,
        "device_name": device_name,
        "registered_at": timezone.now().isoformat(),
    }
    next_tokens = [item for item in normalized_tokens if item.get("token") != token]
    next_tokens.append(device_payload)
    user.device_tokens = next_tokens[-12:]
    user.save(update_fields=["device_tokens"])

    if NotificationPreference and getattr(user, "tenant", None):
        preference, _ = NotificationPreference.objects.get_or_create(
            user=user,
            defaults={"tenant": user.tenant},
        )
        preference.device_tokens = user.device_tokens
        preference.allow_push = True
        preference.save(update_fields=["device_tokens", "allow_push", "updated_at"])

    return Response(
        {
            "success": True,
            "message": "Device registered.",
            "device_count": len(user.device_tokens),
        }
    )


@api_view(["DELETE"])
@permission_classes([IsAuthenticated])
def delete_message(request, message_id):
    if not InAppMessage:
        return Response(
            {"success": False, "message": "Messaging module is not available."},
            status=status.HTTP_503_SERVICE_UNAVAILABLE,
        )

    message = get_object_or_404(
        InAppMessage.objects.filter(tenant=request.user.tenant).filter(Q(sender=request.user) | Q(recipient=request.user)),
        id=message_id,
    )
    if message.sender_id == request.user.id:
        message.deleted_by_sender = True
        message.save(update_fields=["deleted_by_sender"])
    elif message.recipient_id == request.user.id:
        message.deleted_by_recipient = True
        message.save(update_fields=["deleted_by_recipient"])
    else:
        return Response(
            {"success": False, "message": "Not allowed."},
            status=status.HTTP_403_FORBIDDEN,
        )

    return Response({"success": True, "message": "Message deleted."})
