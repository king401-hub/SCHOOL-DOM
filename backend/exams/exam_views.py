import hashlib
import json

from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from django.conf import settings
from django.core.mail import send_mail
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from django.db import transaction
from django.db.models import Q
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken
from datetime import datetime, timedelta
import random

from notifications.models import Notification
from notifications.push import push_for_notifications
from users.models import StudentEnrollment, User, resolve_legacy_tenant_for_school
from users.app_views import _profile_picture_url
from .models import Exam, ExamAttempt, ExamPin, ExamPinUsage, Question, StudentAnswer
from .serializers import (
    ExamSerializer,
    ExamAttemptSerializer,
    ExamAttemptDetailSerializer,
    QuestionSerializer,
    StudentAnswerSerializer,
    ExamResultSerializer,
)


def _tokens_for_cbt_student(user):
    refresh = RefreshToken.for_user(user)
    refresh["role"] = user.role
    refresh["tenant"] = str(user.tenant.id) if user.tenant else None
    return {
        "refresh": str(refresh),
        "access": str(refresh.access_token),
    }


def _student_session_payload(user):
    profile = getattr(user, "student_profile", None)
    profile_picture = ""
    if getattr(user, "profile_picture", None):
        try:
            profile_picture = user.profile_picture.url
        except Exception:
            profile_picture = ""
    return {
        "id": str(user.id),
        "email": user.email,
        "first_name": user.first_name,
        "last_name": user.last_name,
        "full_name": user.get_full_name() or user.email,
        "role": user.role,
        "student_id": getattr(profile, "student_id", "") or "",
        "admission_number": getattr(profile, "admission_number", "") or "",
        "class_name": str(getattr(profile, "current_class", "") or ""),
        "profile_picture": profile_picture,
        "is_active": user.is_active,
    }


def _find_students_by_identifier(identifier):
    """
    Return every student matching this identifier, across all tenants.
    student_id/admission_number are school-assigned, not globally unique, so a bare
    `.first()` here would let an identifier collision (e.g. two schools both using
    "1", "2", "3"...) resolve to the wrong tenant's student. Callers must pick the
    correct candidate by cross-checking against a tenant-scoped context (a PIN valid
    for that candidate's own school, or an already tenant-scoped exam) - never treat
    the first match as authoritative.
    """
    value = str(identifier or "").strip()
    if not value:
        return User.objects.none()
    return (
        User.objects.filter(role="student", is_active=True)
        .filter(
            Q(student_profile__student_id__iexact=value)
            | Q(student_profile__admission_number__iexact=value)
            | Q(email__iexact=value)
        )
        .select_related("tenant", "student_profile", "student_profile__current_class")
    )


def _exams_for_student(student, *, pin):
    now = timezone.now()
    normalized_pin = ExamPin.normalize_pin(pin)
    pin_digest = ExamPin.digest_pin(normalized_pin)
    exams = Exam.objects.filter(
        pins__pin_digest=pin_digest,
        pins__is_active=True,
        is_published=True,
        start_date__lte=now,
        end_date__gte=now,
    ).distinct()

    profile = getattr(student, "student_profile", None)
    enrolled_exam_ids = []
    if profile:
        enrolled_exam_ids = list(
            StudentEnrollment.objects.filter(student=profile)
            .values_list("exams__id", flat=True)
        )
        enrolled_exam_ids = [exam_id for exam_id in enrolled_exam_ids if exam_id]

    if profile and profile.current_class_id:
        exams = exams.filter(
            Q(class_group_id=profile.current_class_id)
            | Q(class_group__isnull=True)
            | Q(id__in=enrolled_exam_ids)
        )
    elif enrolled_exam_ids:
        exams = exams.filter(Q(class_group__isnull=True) | Q(id__in=enrolled_exam_ids))
    else:
        exams = exams.filter(class_group__isnull=True)

    legacy_tenant = resolve_legacy_tenant_for_school(getattr(student, "tenant", None))
    if not legacy_tenant:
        return exams.none()
    return exams.filter(Q(class_group__tenant=legacy_tenant) | Q(tenant=legacy_tenant)).order_by("start_date")


def _published_exam_queryset_for_user(user):
    queryset = Exam.objects.filter(is_published=True)
    legacy_tenant = resolve_legacy_tenant_for_school(getattr(user, "tenant", None))
    if not legacy_tenant:
        return queryset.none()
    return queryset.filter(Q(class_group__tenant=legacy_tenant) | Q(tenant=legacy_tenant)).distinct()


def _offline_pin_hash(pin):
    plain_pin = ExamPin.normalize_pin(getattr(pin, "plain_pin", "") if pin else "")
    if not plain_pin:
        return ""
    return hashlib.sha256(plain_pin.encode("utf-8")).hexdigest()


def _question_queryset_for_exam(exam):
    direct = exam.questions.all()
    if direct.exists():
        return direct.select_related("group").distinct()
    try:
        return Question.objects.filter(question_banks__exam=exam).select_related("group").distinct()
    except Exception:
        return Question.objects.none()


def _file_url(request, field):
    if not field:
        return ""
    try:
        url = field.url
    except Exception:
        return ""
    return request.build_absolute_uri(url) if request else url


def _question_payload(question, request=None):
    group = question.group
    return {
        "id": question.id,
        "text": question.text,
        "image": _file_url(request, question.image),
        "attachment": _file_url(request, question.attachment),
        "options": question.options or [],
        "question_type": question.question_type,
        "points": question.points,
        "group_order": question.group_order,
        "group": {
            "id": group.id,
            "title": group.title,
            "group_type": group.group_type,
            "passage_text": group.passage_text,
            "image": _file_url(request, group.image),
        } if group else None,
    }


def _offline_question_payload(question, request=None):
    payload = _question_payload(question, request)
    payload["type"] = payload.get("question_type")
    payload["marks"] = payload.get("points")
    # correct_answer is needed by the admin desktop app for local scoring in the
    # pre-upload broadsheet.  It is safe to include here because the package is
    # only ever decrypted on the admin's machine, not on student devices.
    payload["correct_answer"] = question.correct_answer
    return payload


def _offline_student_payload(user, request=None):
    profile = getattr(user, "student_profile", None)
    profile_picture = ""
    if getattr(user, "profile_picture", None):
        try:
            profile_picture = user.profile_picture.url
            if request is not None:
                profile_picture = request.build_absolute_uri(profile_picture)
        except Exception:
            profile_picture = ""
    return {
        "id": str(user.id),
        "student_id": getattr(profile, "student_id", "") or getattr(profile, "admission_number", "") or user.email,
        "admission_number": getattr(profile, "admission_number", "") or "",
        "full_name": user.get_full_name() or user.email,
        "email": user.email,
        "class_name": str(getattr(profile, "current_class", "") or ""),
        "profile_picture": profile_picture,
        "is_active": user.is_active,
    }


def _question_units(questions):
    units = []
    grouped = {}
    for question in questions:
        if question.group_id:
            grouped.setdefault(question.group_id, []).append(question)
        else:
            units.append([question])
    for rows in grouped.values():
        rows.sort(key=lambda item: (item.group_order or 0, item.id))
        units.append(rows)
    units.sort(key=lambda rows: min(item.id for item in rows))
    return units


def _build_attempt_question_order(exam):
    questions = list(_question_queryset_for_exam(exam).order_by("id"))
    units = _question_units(questions)
    if exam.shuffle_questions:
        random.SystemRandom().shuffle(units)
    return [question.id for unit in units for question in unit]


def _ordered_questions_for_attempt(attempt):
    questions_by_id = {question.id: question for question in _question_queryset_for_exam(attempt.exam)}
    order = [int(item) for item in (attempt.question_order or []) if str(item).isdigit()]
    ordered = [questions_by_id.pop(question_id) for question_id in order if question_id in questions_by_id]
    if questions_by_id:
        ordered.extend([question for unit in _question_units(questions_by_id.values()) for question in unit])
    return ordered


def _client_ip(request):
    forwarded = request.META.get("HTTP_X_FORWARDED_FOR", "")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR")


def _cbt_student_payload(request):
    user = request.user
    profile = getattr(user, "student_profile", None)
    return {
        "id": (profile.student_id if profile else "") or (profile.admission_number if profile else "") or user.username,
        "name": f"{user.first_name} {user.last_name}".strip() or user.email,
        "avatar": _profile_picture_url(request, user),
    }


def _record_pin_usage(request, *, exam, pin=None, entered_pin="", status_value=ExamPinUsage.STATUS_REJECTED, message="", attempt=None):
    digest = ExamPin.digest_pin(entered_pin) if entered_pin else ""
    return ExamPinUsage.objects.create(
        tenant=exam.tenant,
        pin=pin,
        exam=exam,
        student=request.user if getattr(request, "user", None) and request.user.is_authenticated else None,
        attempt=attempt,
        entered_pin_digest=digest,
        status=status_value,
        message=message[:255],
        ip_address=_client_ip(request),
        user_agent=str(request.META.get("HTTP_USER_AGENT", ""))[:255],
    )


def _validate_exam_pin_for_start(request, exam, active_attempt=None):
    active_pins = exam.pins.filter(is_active=True)
    if not active_pins.exists():
        return True, None, ""

    entered_pin = ExamPin.normalize_pin(request.data.get("pin") or request.data.get("exam_pin") or "")
    if not entered_pin:
        _record_pin_usage(request, exam=exam, entered_pin="", message="PIN was not provided.")
        return False, None, "Enter the exam PIN to access this CBT exam."

    pin_digest = ExamPin.digest_pin(entered_pin)
    pin = active_pins.filter(pin_digest=pin_digest).first()
    if not pin or not pin.check_pin(entered_pin):
        _record_pin_usage(request, exam=exam, entered_pin=entered_pin, message="Invalid PIN.")
        return False, None, "Invalid exam PIN."

    if active_attempt and pin.successful_usage_queryset().filter(attempt=active_attempt, student=request.user).exists():
        return True, pin, ""

    usable, reason = pin.can_be_used()
    if not usable:
        _record_pin_usage(request, exam=exam, pin=pin, entered_pin=entered_pin, message=reason)
        return False, pin, reason

    return True, pin, ""


AUTO_SUBMIT_REASON_LABELS = {
    "timer_expired": "Exam timer expired",
    "tab_switch_limit": "Exceeded tab-switching warnings",
    "malpractice": "Attempted malpractice",
    "connection_lost": "Lost connection for too long",
    "force_exit": "Forcefully exited exam environment",
    "fullscreen_exit": "Exited full-screen exam mode",
    "security_violation": "Security violation",
    "server_timer_expired": "Server timer expired",
    "offline_timeout_sync": "Offline timeout submission",
    "unknown": "Auto-submitted by exam monitor",
}


def _safe_json_list(value, limit=80):
    if not isinstance(value, list):
        return []
    cleaned = []
    for item in value[:limit]:
        if isinstance(item, dict):
            cleaned.append({str(key)[:80]: str(val)[:1000] for key, val in item.items()})
        else:
            cleaned.append({"message": str(item)[:1000]})
    return cleaned


def _auto_submit_payload(request, fallback_reason="unknown"):
    raw_reason = str(request.data.get("auto_submit_reason") or request.data.get("reason_code") or fallback_reason).strip()
    reason = raw_reason if raw_reason in AUTO_SUBMIT_REASON_LABELS else fallback_reason
    display = str(request.data.get("auto_submit_reason_display") or request.data.get("reason") or "").strip()
    details = str(request.data.get("auto_submit_details") or request.data.get("details") or "").strip()
    return {
        "reason": reason,
        "display": (display or AUTO_SUBMIT_REASON_LABELS.get(reason, AUTO_SUBMIT_REASON_LABELS["unknown"]))[:160],
        "details": details[:4000],
        "warnings": _safe_json_list(request.data.get("warning_history") or request.data.get("warnings") or []),
        "logs": _safe_json_list(request.data.get("activity_logs") or request.data.get("logs") or []),
    }


def _mark_attempt_submitted(attempt, *, auto_submitted=False, auto_payload=None, submitted_at=None):
    attempt.end_time = submitted_at or timezone.now()
    attempt.is_completed = True
    attempt.is_submitted = True
    update_fields = ["end_time", "is_completed", "is_submitted", "updated_at"]
    if auto_submitted:
        payload = auto_payload or {}
        attempt.auto_submitted = True
        attempt.auto_submit_reason = payload.get("reason") or "unknown"
        attempt.auto_submit_reason_display = payload.get("display") or AUTO_SUBMIT_REASON_LABELS["unknown"]
        attempt.auto_submit_details = payload.get("details") or ""
        attempt.auto_submit_warning_history = payload.get("warnings") or []
        attempt.auto_submit_activity_logs = payload.get("logs") or []
        update_fields.extend([
            "auto_submitted",
            "auto_submit_reason",
            "auto_submit_reason_display",
            "auto_submit_details",
            "auto_submit_warning_history",
            "auto_submit_activity_logs",
        ])
    attempt.save(update_fields=update_fields)


def _normalize_selected_answer(value):
    if isinstance(value, list):
        return value[0] if value else None
    return value


def _grade_attempt(attempt):
    """Auto-grades the objective (mcq/true_false) portion of an attempt only.
    Theory questions (short_answer/paragraph/essay) are left with a NULL
    StudentAnswer.score/is_correct - that NULL *is* the "pending manual
    grading" state, resolved later by publish_theory_grades. total_points
    still sums every question so a Mixed exam's percentage only becomes
    meaningful once the theory portion is published; score/percentage here
    reflect the objective-only partial total until then."""
    questions = list(_question_queryset_for_exam(attempt.exam))
    question_map = {question.id: question for question in questions}
    answers = {answer.question_id: answer for answer in StudentAnswer.objects.filter(attempt=attempt, question_id__in=question_map)}
    total_points = sum(question.points for question in questions)
    score = 0

    for question in questions:
        answer = answers.get(question.id)
        if question.question_type in Question.THEORY_TYPES:
            continue
        selected = _normalize_selected_answer(answer.selected_options if answer else None)
        correct_index = None
        options = question.options or []
        if question.correct_answer in options:
            correct_index = options.index(question.correct_answer)
        try:
            is_correct = int(selected) == int(correct_index)
        except (TypeError, ValueError):
            is_correct = False
        if answer:
            answer.is_correct = is_correct
            answer.score = question.points if is_correct else 0
            answer.save(update_fields=["is_correct", "score", "updated_at"])
        if is_correct:
            score += question.points

    attempt.score = score
    attempt.total_points = total_points
    attempt.percentage = (score / total_points * 100) if total_points else 0
    attempt.graded_at = timezone.now()
    attempt.save(update_fields=["score", "total_points", "percentage", "graded_at", "updated_at"])
    return score, total_points


def _attempt_needs_theory_grading(attempt):
    """True if this attempt has at least one theory-type answer still
    awaiting a teacher's score - the exact NULL-score signal _grade_attempt
    leaves behind for theory questions."""
    question_ids = _question_queryset_for_exam(attempt.exam).values_list("id", flat=True)
    return StudentAnswer.objects.filter(
        attempt=attempt, question_id__in=question_ids,
        question__question_type__in=Question.THEORY_TYPES, score__isnull=True,
    ).exists()


def _publish_theory_grades(attempt):
    """Recomputes attempt.score/percentage from ALL StudentAnswer.score
    values (objective + now-graded theory) and finalizes graded_at. Callers
    must have already verified _attempt_needs_theory_grading(attempt) is
    False before calling this."""
    question_ids = _question_queryset_for_exam(attempt.exam).values_list("id", flat=True)
    answers = StudentAnswer.objects.filter(attempt=attempt, question_id__in=question_ids)
    score = sum(answer.score or 0 for answer in answers)
    attempt.score = score
    attempt.percentage = (score / attempt.total_points * 100) if attempt.total_points else 0
    attempt.graded_at = timezone.now()
    attempt.save(update_fields=["score", "percentage", "graded_at", "updated_at"])
    return attempt


def _format_question_options(options):
    if not options:
        return "No options provided."
    labels = ["A", "B", "C", "D", "E"]
    lines = []
    for index, option in enumerate(options):
        label = labels[index] if index < len(labels) else str(index + 1)
        lines.append(f"{label}. {option}")
    return "\n".join(lines)


def _admin_users_for_school(school):
    queryset = User.objects.filter(
        role__in=["school_admin", "principal", "super_admin"],
        email__isnull=False,
    ).exclude(email="")
    if school:
        queryset = queryset.filter(tenant=school)
    return queryset


def _resolve_flag_report_recipients(school, teacher=None):
    configured_email = str(getattr(settings, "INAPPROPRIATE_QUESTION_REPORT_EMAIL", "") or "").strip()
    recipients = [configured_email] if configured_email else []
    recipients.extend(_admin_users_for_school(school).values_list("email", flat=True)[:10])
    teacher_email = str(getattr(teacher, "email", "") or "").strip()
    teacher_school = getattr(teacher, "tenant", None)
    if teacher_email and (not school or teacher_school == school):
        recipients.append(teacher_email)
    return list(dict.fromkeys(recipients))


def _create_flag_notifications(*, school, admin_users, teacher, title, message):
    if not school:
        return
    recipients = list(admin_users)
    if teacher:
        recipients.append(teacher)
    seen = set()
    notifications = []
    for user in recipients:
        if not user or user.id in seen:
            continue
        seen.add(user.id)
        notifications.append(
            Notification(
                tenant=school,
                user=user,
                title=title,
                message=message,
                notification_type="alert",
                priority=4,
                channel="in_app",
                event_type="inappropriate_question",
                reference_model="exams.Question",
                is_delivered=True,
                delivered_at=timezone.now(),
            )
        )
    if notifications:
        Notification.objects.bulk_create(notifications)
        push_for_notifications(notifications)


def _student_flag_count(*, school, student, exam_title):
    student_name = student.get_full_name() or student.email
    queryset = Notification.objects.filter(
        event_type="inappropriate_question",
        reference_model="exams.Question",
        title="Inappropriate question flagged",
        message__icontains=student_name,
    ).filter(message__icontains=exam_title)
    if school:
        queryset = queryset.filter(tenant=school)
    return queryset.count()


class ExamListView(APIView):
    """List available exams for students"""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        legacy_tenant = resolve_legacy_tenant_for_school(getattr(request.user, "tenant", None))
        if not legacy_tenant:
            return Response([])
        now = timezone.now()

        exams = Exam.objects.filter(
            is_published=True,
            end_date__gte=now,
        ).filter(Q(class_group__tenant=legacy_tenant) | Q(tenant=legacy_tenant))

        student_profile = getattr(request.user, "student_profile", None)
        enrolled_exam_ids = []
        if student_profile:
            enrolled_exam_ids = list(
                StudentEnrollment.objects.filter(student=student_profile)
                .values_list("exams__id", flat=True)
            )
            enrolled_exam_ids = [exam_id for exam_id in enrolled_exam_ids if exam_id]

        if student_profile and student_profile.current_class_id:
            exams = exams.filter(
                Q(class_group_id=student_profile.current_class_id)
                | Q(class_group__isnull=True)
                | Q(id__in=enrolled_exam_ids)
            )
        elif enrolled_exam_ids:
            exams = exams.filter(Q(class_group__isnull=True) | Q(id__in=enrolled_exam_ids))
        
        exam_list = list(exams.distinct().order_by("start_date"))
        attempts_by_exam = {}
        if exam_list:
            for attempt in ExamAttempt.objects.filter(
                exam_id__in=[exam.id for exam in exam_list],
                student=request.user,
            ).order_by("-created_at"):
                attempts_by_exam.setdefault(attempt.exam_id, []).append(attempt)

        serializer = ExamSerializer(exam_list, many=True)
        payload = []
        for exam_data in serializer.data:
            exam_attempts = attempts_by_exam.get(exam_data["id"], [])
            submitted_attempt = next((attempt for attempt in exam_attempts if attempt.is_submitted or attempt.is_completed), None)
            active_attempt = next((attempt for attempt in exam_attempts if not attempt.is_submitted), None)
            exam_data = dict(exam_data)
            exam_data.update(
                {
                    "is_submitted": bool(submitted_attempt),
                    "is_completed": bool(submitted_attempt and submitted_attempt.is_completed),
                    "submitted_attempt_id": submitted_attempt.id if submitted_attempt else None,
                    "submitted_at": submitted_attempt.end_time if submitted_attempt else None,
                    "active_attempt_id": active_attempt.id if active_attempt else None,
                }
            )
            payload.append(exam_data)
        return Response(payload)


class StudentCbtEntryView(APIView):
    """Start/resume CBT with only Student ID and Exam PIN for desktop exam stations."""
    permission_classes = [AllowAny]

    @transaction.atomic
    def post(self, request):
        student_identifier = request.data.get("student_id") or request.data.get("admission_number") or request.data.get("student")
        entered_pin = ExamPin.normalize_pin(request.data.get("pin") or request.data.get("exam_pin") or "")
        candidates = _find_students_by_identifier(student_identifier)
        if not candidates.exists():
            return Response({"success": False, "message": "Student ID was not found."}, status=status.HTTP_404_NOT_FOUND)
        if not entered_pin:
            return Response({"success": False, "message": "Enter the exam PIN."}, status=status.HTTP_400_BAD_REQUEST)

        # student_id/admission_number can collide across schools - only accept a candidate
        # whose OWN tenant has an exam this PIN actually unlocks, never the first match.
        student = None
        exam = None
        for candidate in candidates:
            candidate_exam = _exams_for_student(candidate, pin=entered_pin).first()
            if candidate_exam:
                student, exam = candidate, candidate_exam
                break
        if not student or not exam:
            return Response({"success": False, "message": "No open exam matches this Student ID and PIN."}, status=status.HTTP_404_NOT_FOUND)

        submitted_count = ExamAttempt.objects.filter(exam=exam, student=student, is_submitted=True).count()
        if submitted_count >= exam.max_attempts:
            return Response(
                {"success": False, "message": f"Maximum {exam.max_attempts} attempt(s) allowed."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        active_attempt = ExamAttempt.objects.select_for_update().filter(
            exam=exam,
            student=student,
            is_submitted=False,
        ).first()

        active_pins = exam.pins.filter(is_active=True)
        pin = active_pins.filter(pin_digest=ExamPin.digest_pin(entered_pin)).first()
        if not pin or not pin.check_pin(entered_pin):
            return Response({"success": False, "message": "Invalid exam PIN."}, status=status.HTTP_403_FORBIDDEN)

        if not (active_attempt and pin.successful_usage_queryset().filter(attempt=active_attempt, student=student).exists()):
            usable, reason = pin.can_be_used()
            if not usable:
                return Response({"success": False, "message": reason}, status=status.HTTP_403_FORBIDDEN)

        if active_attempt:
            attempt = active_attempt
            if not attempt.question_order:
                attempt.question_order = _build_attempt_question_order(exam)
                attempt.save(update_fields=["question_order", "updated_at"])
        else:
            attempt = ExamAttempt.objects.create(
                exam=exam,
                student=student,
                tenant=exam.tenant,
                is_offline=bool(request.data.get("is_offline", False)),
                device_id=request.data.get("device_id") or _client_ip(request),
                question_order=_build_attempt_question_order(exam),
            )

        if not pin.successful_usage_queryset().filter(attempt=attempt, student=student).exists():
            ExamPinUsage.objects.create(
                tenant=exam.tenant,
                pin=pin,
                exam=exam,
                student=student,
                attempt=attempt,
                entered_pin_digest=ExamPin.digest_pin(entered_pin),
                status=ExamPinUsage.STATUS_ACCEPTED,
                message="PIN accepted from Student CBT desktop entry.",
                ip_address=_client_ip(request),
                user_agent=str(request.META.get("HTTP_USER_AGENT", ""))[:255],
            )

        tokens = _tokens_for_cbt_student(student)
        return Response({
            "success": True,
            "attempt_id": attempt.id,
            "exam_id": exam.id,
            "exam": ExamSerializer(exam).data,
            "student": _student_session_payload(student),
            "session": {
                "user": _student_session_payload(student),
                "access": tokens["access"],
                "refresh": tokens["refresh"],
                "school_code": student.tenant.schema_name if student.tenant else "",
                "signedInAt": timezone.now().isoformat(),
                "auth_mode": "cbt_entry",
            },
        }, status=status.HTTP_200_OK)


class StartExamView(APIView):
    """Start a new exam attempt"""
    permission_classes = [IsAuthenticated]

    def post(self, request, exam_id):
        exam = get_object_or_404(_published_exam_queryset_for_user(request.user), id=exam_id)
        
        # Check if exam is available
        now = timezone.now()
        if exam.start_date > now or exam.end_date < now:
            return Response(
                {'error': 'Exam is not available at this time'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Check attempt limit
        existing_attempts = ExamAttempt.objects.filter(
            exam=exam,
            student=request.user,
            is_submitted=True
        ).count()
        
        if existing_attempts >= exam.max_attempts:
            return Response(
                {'error': f'Maximum {exam.max_attempts} attempt(s) allowed'},
                status=status.HTTP_400_BAD_REQUEST
            )

        active_attempt = ExamAttempt.objects.filter(
            exam=exam,
            student=request.user,
            is_submitted=False
        ).first()

        pin_valid, validated_pin, pin_error = _validate_exam_pin_for_start(request, exam, active_attempt=active_attempt)
        if not pin_valid:
            return Response(
                {'error': pin_error or 'Invalid exam PIN'},
                status=status.HTTP_403_FORBIDDEN
            )

        if active_attempt:
            if not active_attempt.question_order:
                active_attempt.question_order = _build_attempt_question_order(exam)
                active_attempt.save(update_fields=["question_order", "updated_at"])
            return Response({
                'attempt_id': active_attempt.id,
                'exam_id': exam.id,
                'start_time': active_attempt.start_time,
                'duration_minutes': exam.duration_minutes,
                'question_count': len(active_attempt.question_order or [])
            })
        
        # Create exam attempt
        attempt = ExamAttempt.objects.create(
            exam=exam,
            student=request.user,
            tenant=exam.tenant,
            is_offline=request.data.get('is_offline', False),
            device_id=request.data.get('device_id', None),
            question_order=_build_attempt_question_order(exam),
        )
        if validated_pin:
            _record_pin_usage(
                request,
                exam=exam,
                pin=validated_pin,
                entered_pin=request.data.get("pin") or request.data.get("exam_pin") or "",
                status_value=ExamPinUsage.STATUS_ACCEPTED,
                message="PIN accepted and exam attempt started.",
                attempt=attempt,
            )
        
        # Prepare response
        return Response({
            'attempt_id': attempt.id,
            'exam_id': exam.id,
            'start_time': attempt.start_time,
            'duration_minutes': exam.duration_minutes,
            'question_count': len(attempt.question_order or [])
        }, status=status.HTTP_201_CREATED)


class ExamAttemptDetailView(APIView):
    """Get exam attempt details with questions and answers"""
    permission_classes = [IsAuthenticated]

    def get(self, request, attempt_id):
        attempt = get_object_or_404(ExamAttempt, id=attempt_id, student=request.user)
        
        if attempt.is_submitted:
            return Response(
                {'error': 'Exam has already been submitted'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        exam = attempt.exam
        elapsed = (timezone.now() - attempt.start_time).total_seconds()
        if elapsed >= exam.duration_minutes * 60:
            _mark_attempt_submitted(
                attempt,
                auto_submitted=True,
                auto_payload={
                    "reason": "server_timer_expired",
                    "display": AUTO_SUBMIT_REASON_LABELS["server_timer_expired"],
                    "details": "Attempt detail was requested after the server-side exam duration had elapsed.",
                    "warnings": [],
                    "logs": [{"type": "server_timer_check", "message": "Server submitted expired attempt.", "time": timezone.now().isoformat()}],
                },
            )
            _grade_attempt(attempt)
            return Response({'error': 'Exam time has expired and the attempt was submitted.'}, status=status.HTTP_400_BAD_REQUEST)
        
        questions = _ordered_questions_for_attempt(attempt)
        
        # Fetch student answers
        student_answers = StudentAnswer.objects.filter(attempt=attempt)
        answers_dict = {
            str(ans.question_id): ans.selected_options
            for ans in student_answers
        }
        
        # Calculate time remaining
        total_seconds = exam.duration_minutes * 60
        time_remaining = max(0, int(total_seconds - elapsed))
        
        return Response({
            'attempt': {
                'id': attempt.id,
                'start_time': attempt.start_time,
                'is_completed': attempt.is_completed
            },
            'exam': {
                'id': exam.id,
                'title': exam.title,
                'duration_minutes': exam.duration_minutes,
                'instructions': getattr(exam, 'instructions', '')
            },
            'questions': [_question_payload(question, request) for question in questions],
            'student': _cbt_student_payload(request),
            'answers': answers_dict,
            'time_remaining_seconds': time_remaining
        })


class SaveExamAnswerView(APIView):
    """Save an exam answer"""
    permission_classes = [IsAuthenticated]

    def post(self, request, attempt_id):
        attempt = get_object_or_404(ExamAttempt, id=attempt_id, student=request.user)
        
        if attempt.is_submitted:
            return Response(
                {'error': 'Exam has already been submitted'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        question_id = request.data.get('question_id')
        selected_options = request.data.get('selected_options')
        answer_text = request.data.get('answer_text')
        
        question = get_object_or_404(_question_queryset_for_exam(attempt.exam), id=question_id)
        
        if (timezone.now() - attempt.start_time).total_seconds() > attempt.exam.duration_minutes * 60 + 10:
            return Response({'error': 'Exam time has expired'}, status=status.HTTP_400_BAD_REQUEST)

        options = question.options or []
        try:
            selected_index = int(selected_options)
        except (TypeError, ValueError):
            selected_index = None
        if selected_index is not None and (selected_index < 0 or selected_index >= len(options)):
            return Response({'error': 'Selected answer is not valid for this question'}, status=status.HTTP_400_BAD_REQUEST)

        answer, created = StudentAnswer.objects.update_or_create(
            attempt=attempt,
            question=question,
            defaults={
                'tenant': attempt.tenant or attempt.exam.tenant,
                'selected_options': selected_options,
                'answer_text': answer_text
            }
        )
        
        return Response({
            'success': True,
            'answer_id': answer.id
        })


class FlagExamQuestionView(APIView):
    """Email a teacher/admin report for an inappropriate question."""
    permission_classes = [IsAuthenticated]

    def post(self, request, attempt_id):
        attempt = get_object_or_404(
            ExamAttempt.objects.select_related("exam", "exam__teacher", "exam__tenant"),
            id=attempt_id,
            student=request.user,
        )

        if attempt.is_submitted:
            return Response(
                {"error": "Exam has already been submitted"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        question_id = request.data.get("question_id")
        reason = str(request.data.get("reason") or "").strip()
        if not reason:
            return Response(
                {"error": "Please describe why this question is inappropriate."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if len(reason) > 2000:
            return Response(
                {"error": "Report text must be 2000 characters or fewer."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        school = getattr(request.user, "tenant", None)
        if _student_flag_count(school=school, student=request.user, exam_title=attempt.exam.title) >= 2:
            return Response(
                {"error": "You can only flag 2 questions in this quiz."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        question = get_object_or_404(_question_queryset_for_exam(attempt.exam), id=question_id)
        admin_users = list(_admin_users_for_school(school)[:10])
        recipients = _resolve_flag_report_recipients(school, teacher=attempt.exam.teacher)
        if not recipients:
            return Response(
                {"error": "No report recipient email is configured."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        selected_answer = StudentAnswer.objects.filter(attempt=attempt, question=question).first()
        options = question.options or []
        subject_name = getattr(attempt.exam.subject, "name", "") or "No subject recorded"
        school_name = (
            getattr(getattr(request.user, "tenant", None), "name", "")
            or getattr(attempt.exam.tenant, "name", "")
            or "No school recorded"
        )
        selected_value = _normalize_selected_answer(selected_answer.selected_options if selected_answer else None)
        selected_text = "Not answered"
        try:
            selected_index = int(selected_value)
            if 0 <= selected_index < len(options):
                selected_text = f"{chr(65 + selected_index)}. {options[selected_index]}"
        except (TypeError, ValueError):
            if selected_answer and selected_answer.answer_text:
                selected_text = selected_answer.answer_text

        correct_answer = question.correct_answer or "No correct answer recorded"
        subject = f"Inappropriate question report: {attempt.exam.title}"
        student_name = request.user.get_full_name() or request.user.email
        message = "\n".join(
            [
                "A student flagged a quiz question as inappropriate.",
                "",
                f"Exam: {attempt.exam.title}",
                f"School: {school_name}",
                f"Subject: {subject_name}",
                f"Attempt ID: {attempt.id}",
                f"Student: {student_name} ({request.user.email})",
                f"Question ID: {question.id}",
                "",
                "Question:",
                question.text,
                "",
                "Options:",
                _format_question_options(options),
                "",
                f"Correct answer: {correct_answer}",
                f"Student selected answer: {selected_text}",
                "",
                "Student report:",
                reason,
            ]
        )

        send_mail(
            subject,
            message,
            settings.DEFAULT_FROM_EMAIL,
            recipients,
            fail_silently=False,
        )
        _create_flag_notifications(
            school=school,
            admin_users=admin_users,
            teacher=attempt.exam.teacher,
            title="Inappropriate question flagged",
            message=f"{student_name} flagged a question in {attempt.exam.title} ({subject_name}).",
        )

        return Response({"success": True, "message": "Question report sent."})


class SubmitExamView(APIView):
    """Submit exam and calculate results"""
    permission_classes = [IsAuthenticated]

    @transaction.atomic
    def post(self, request, attempt_id):
        attempt = get_object_or_404(ExamAttempt.objects.select_for_update(), id=attempt_id, student=request.user)
        
        if attempt.is_submitted:
            return Response(
                {'error': 'Exam has already been submitted'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        auto_submitted = bool(request.data.get("auto_submitted"))
        auto_payload = _auto_submit_payload(request) if auto_submitted else None
        _mark_attempt_submitted(attempt, auto_submitted=auto_submitted, auto_payload=auto_payload)
        
        score, total_points = _grade_attempt(attempt)
        
        return Response({
            'success': True,
            'attempt_id': attempt.id,
            'message': 'Exam Completed'
        })


class ExamResultView(APIView):
    """Get exam results"""
    permission_classes = [IsAuthenticated]

    def get(self, request, attempt_id):
        attempt_qs = ExamAttempt.objects.select_related("exam", "exam__teacher")
        role = getattr(request.user, "role", "")
        if role == "teacher":
            attempt = get_object_or_404(attempt_qs, id=attempt_id, exam__teacher=request.user)
        elif role in {"school_admin", "principal", "super_admin"}:
            legacy_tenant = resolve_legacy_tenant_for_school(getattr(request.user, "tenant", None))
            attempt = get_object_or_404(
                attempt_qs.filter(Q(exam__class_group__tenant=legacy_tenant) | Q(exam__tenant=legacy_tenant)),
                id=attempt_id,
            )
        else:
            # Students (and any other role) never see their own CBT score or
            # grade through this endpoint - only admins and teachers can view
            # a completed attempt's full result.
            attempt = get_object_or_404(attempt_qs, id=attempt_id, student=request.user)
            return Response({
                'success': True,
                'attempt_id': attempt.id,
                'exam_title': attempt.exam.title,
                'message': 'Exam Completed'
            })

        if not attempt.is_submitted:
            return Response(
                {'error': 'Exam has not been submitted yet'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        answers = StudentAnswer.objects.filter(attempt=attempt).select_related("question")
        total_points = attempt.total_points or sum(ans.question.points for ans in answers)
        earned_points = attempt.score
        needs_theory_grading = _attempt_needs_theory_grading(attempt)

        percentage = (earned_points / total_points * 100) if total_points > 0 else 0
        grade, is_passed = self._calculate_grade(request.user, percentage)

        return Response({
            'attempt_id': attempt.id,
            'exam_title': attempt.exam.title,
            'score': earned_points,
            'total_points': total_points,
            'percentage': round(percentage, 2),
            'grade': grade,
            'is_passed': is_passed,
            'submitted_at': attempt.end_time,
            # While True, score/percentage above only reflect the
            # objective portion - some theory answer(s) below are still
            # awaiting a teacher's score.
            'needs_theory_grading': needs_theory_grading,
            'answers_review': [{
                'question_number': i + 1,
                'question_text': ans.question.text,
                'question_type': ans.question.question_type,
                'user_answer': ans.answer_text if ans.question.question_type in Question.THEORY_TYPES else ans.selected_options,
                'correct_answer': ans.question.correct_answer,
                'is_correct': ans.is_correct,
                'pending_grading': ans.question.question_type in Question.THEORY_TYPES and ans.score is None,
                'points_earned': ans.score if ans.score is not None else 0,
                'total_points': ans.question.points,
                'teacher_feedback': ans.teacher_feedback or "",
                'explanation': ans.question.explanation
            } for i, ans in enumerate(answers)]
        })
    
    def _calculate_grade(self, user, percentage):
        """Resolve (letter grade, is_passed) from the school's admin-configured
        grading system, so a CBT result always agrees with the grade the same
        score would get anywhere else in the app (report cards, transcripts,
        manually-entered scores) - this used to be a hardcoded 90/80/70/60
        scale with a separate hardcoded 40% pass mark, independent of
        whatever grading scale the admin actually configured."""
        from academic.models import GradeScale
        from users.app_views import _grade_for_percentage, _tenant_for_model

        # _grade_for_percentage resolves `user`'s core.SchoolTenant into the
        # tenants.Tenant GradeScale actually stores its FK against - reuse
        # that same resolution here rather than using user.tenant directly,
        # which is the wrong tenant model for this lookup.
        letter, _remark = _grade_for_percentage(user, percentage)
        tenant = _tenant_for_model(GradeScale, user)
        lowest_scale = GradeScale.objects.filter(tenant=tenant, is_active=True).order_by("min_percentage").first()
        is_passed = bool(letter) and (not lowest_scale or letter != lowest_scale.letter)
        return letter, is_passed


# Theory answers (short_answer/paragraph/essay) can't be auto-marked - a
# teacher (their own exams) or admin (whole tenant) manually scores each one,
# then publishes to fold the theory portion into the attempt's final score.
THEORY_GRADING_ROLES = {"teacher", "school_admin", "principal", "super_admin"}


def _theory_gradable_attempts_qs(user):
    """Attempts the given user is allowed to grade theory answers for -
    teachers see only their own exams, admins see their whole tenant. Mirrors
    the exact role split ExamResultView.get already uses above."""
    attempt_qs = ExamAttempt.objects.select_related("exam", "exam__teacher", "student")
    role = getattr(user, "role", "")
    if role == "teacher":
        return attempt_qs.filter(exam__teacher=user)
    if role in {"school_admin", "principal", "super_admin"}:
        legacy_tenant = resolve_legacy_tenant_for_school(getattr(user, "tenant", None))
        return attempt_qs.filter(Q(exam__class_group__tenant=legacy_tenant) | Q(exam__tenant=legacy_tenant))
    return attempt_qs.none()


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def theory_grading_queue(request):
    """List submitted attempts that still have at least one ungraded theory
    answer - the admin/teacher "needs grading" queue. Uses one Exists(...)
    annotation across the whole queryset rather than a per-attempt query."""
    from django.db.models import Exists, OuterRef

    role = getattr(request.user, "role", "")
    if role not in THEORY_GRADING_ROLES:
        return Response({"success": False, "message": "Only teachers and administrators can grade theory answers."}, status=status.HTTP_403_FORBIDDEN)

    pending_answers = StudentAnswer.objects.filter(
        attempt=OuterRef("pk"), question__question_type__in=Question.THEORY_TYPES, score__isnull=True,
    )
    attempts = (
        _theory_gradable_attempts_qs(request.user)
        .filter(is_submitted=True)
        .annotate(needs_grading=Exists(pending_answers))
        .filter(needs_grading=True)
        .order_by("-end_time")
    )
    return Response({
        "success": True,
        "attempts": [
            {
                "attempt_id": attempt.id,
                "exam_id": attempt.exam_id,
                "exam_title": attempt.exam.title,
                "student_name": attempt.student.get_full_name() or attempt.student.email,
                "submitted_at": attempt.end_time,
            }
            for attempt in attempts
        ],
    })


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def attempt_theory_answers(request, attempt_id):
    """Every theory-type answer for one attempt, for the "review each
    student's answer" grading screen."""
    from users.app_views import _media_url, _question_group_payload

    role = getattr(request.user, "role", "")
    if role not in THEORY_GRADING_ROLES:
        return Response({"success": False, "message": "Only teachers and administrators can grade theory answers."}, status=status.HTTP_403_FORBIDDEN)
    attempt = get_object_or_404(_theory_gradable_attempts_qs(request.user), id=attempt_id)

    answers = (
        StudentAnswer.objects.filter(attempt=attempt, question__question_type__in=Question.THEORY_TYPES)
        .select_related("question", "question__group")
        .order_by("question__group_order", "id")
    )
    return Response({
        "success": True,
        "attempt_id": attempt.id,
        "exam_title": attempt.exam.title,
        "student_name": attempt.student.get_full_name() or attempt.student.email,
        "answers": [
            {
                "answer_id": answer.id,
                "question_id": answer.question_id,
                "question_text": answer.question.text,
                "passage": _question_group_payload(answer.question.group, request) if answer.question.group else None,
                "image": _media_url(request, answer.question.image),
                "attachment": _media_url(request, answer.question.attachment),
                "points": answer.question.points,
                "answer_text": answer.answer_text or "",
                "score": answer.score,
                "teacher_feedback": answer.teacher_feedback or "",
            }
            for answer in answers
        ],
    })


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def grade_theory_answer(request, attempt_id, answer_id):
    role = getattr(request.user, "role", "")
    if role not in THEORY_GRADING_ROLES:
        return Response({"success": False, "message": "Only teachers and administrators can grade theory answers."}, status=status.HTTP_403_FORBIDDEN)
    attempt = get_object_or_404(_theory_gradable_attempts_qs(request.user), id=attempt_id)
    answer = get_object_or_404(
        StudentAnswer.objects.filter(question__question_type__in=Question.THEORY_TYPES),
        id=answer_id, attempt=attempt,
    )

    try:
        score = float(request.data.get("score"))
    except (TypeError, ValueError):
        return Response({"success": False, "message": "A numeric score is required."}, status=status.HTTP_400_BAD_REQUEST)
    if score < 0 or score > answer.question.points:
        return Response(
            {"success": False, "message": f"Score must be between 0 and {answer.question.points}."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    answer.score = score
    answer.is_correct = score > 0
    answer.teacher_feedback = str(request.data.get("feedback", "")).strip()
    answer.save(update_fields=["score", "is_correct", "teacher_feedback", "updated_at"])

    return Response({
        "success": True,
        "answer_id": answer.id,
        "score": answer.score,
        "teacher_feedback": answer.teacher_feedback,
        "attempt_needs_grading": _attempt_needs_theory_grading(attempt),
    })


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def publish_theory_grades_view(request, attempt_id):
    role = getattr(request.user, "role", "")
    if role not in THEORY_GRADING_ROLES:
        return Response({"success": False, "message": "Only teachers and administrators can publish results."}, status=status.HTTP_403_FORBIDDEN)
    attempt = get_object_or_404(_theory_gradable_attempts_qs(request.user), id=attempt_id)

    if _attempt_needs_theory_grading(attempt):
        return Response(
            {"success": False, "message": "Every theory answer must be scored before publishing."},
            status=status.HTTP_400_BAD_REQUEST,
        )
    _publish_theory_grades(attempt)
    return Response({
        "success": True,
        "message": "Results published.",
        "score": attempt.score,
        "total_points": attempt.total_points,
        "percentage": round(attempt.percentage, 2),
    })


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def exam_timer_sync(request, attempt_id):
    """Sync exam timer with server"""
    attempt = get_object_or_404(ExamAttempt, id=attempt_id, student=request.user)
    
    if attempt.is_submitted:
        return Response({'expired': True})
    
    elapsed = (timezone.now() - attempt.start_time).total_seconds()
    total_seconds = attempt.exam.duration_minutes * 60
    time_remaining = max(0, int(total_seconds - elapsed))
    
    if time_remaining <= 0:
        # Auto-submit
        _mark_attempt_submitted(
            attempt,
            auto_submitted=True,
            auto_payload={
                "reason": "timer_expired",
                "display": AUTO_SUBMIT_REASON_LABELS["timer_expired"],
                "details": "Server timer sync reached zero remaining seconds.",
                "warnings": [],
                "logs": [{"type": "timer_sync", "message": "Timer sync submitted expired attempt.", "time": timezone.now().isoformat()}],
            },
        )
        _grade_attempt(attempt)
        return Response({'expired': True, 'auto_submitted': True})
    
    return Response({
        'expired': False,
        'time_remaining_seconds': time_remaining
    })


@api_view(['POST'])
@permission_classes([IsAuthenticated])
@transaction.atomic
def sync_offline_exam_attempt(request):
    """Sync and grade a CBT submission that was completed while offline."""
    exam_id = request.data.get("exam_id")
    attempt_id = request.data.get("attempt_id")
    answers = request.data.get("answers") or {}
    offline_attempt_id = str(request.data.get("offline_attempt_id") or "").strip()
    started_at = parse_datetime(str(request.data.get("started_at") or "")) or timezone.now()
    submitted_at = parse_datetime(str(request.data.get("submitted_at") or "")) or timezone.now()
    auto_submitted = bool(request.data.get("auto_submitted"))
    auto_payload = _auto_submit_payload(request, fallback_reason="offline_timeout_sync") if auto_submitted else None

    if not exam_id:
        return Response({"success": False, "message": "exam_id is required."}, status=status.HTTP_400_BAD_REQUEST)
    if not isinstance(answers, dict):
        return Response({"success": False, "message": "answers must be an object keyed by question id."}, status=status.HTTP_400_BAD_REQUEST)

    exam = get_object_or_404(_published_exam_queryset_for_user(request.user), id=exam_id)
    question_ids = set(_question_queryset_for_exam(exam).values_list("id", flat=True))
    if not question_ids:
        return Response({"success": False, "message": "This exam has no questions to sync."}, status=status.HTTP_400_BAD_REQUEST)

    if offline_attempt_id:
        existing = ExamAttempt.objects.filter(device_id=offline_attempt_id, student=request.user, exam=exam, is_submitted=True).first()
        if existing:
            return Response({"success": True, "attempt_id": existing.id, "message": "Offline submission already synced."})

    attempt = None
    if attempt_id:
        attempt = ExamAttempt.objects.select_for_update().filter(id=attempt_id, student=request.user, exam=exam).first()

    if attempt and attempt.is_submitted:
        return Response({"success": True, "attempt_id": attempt.id, "message": "Offline submission already synced."})

    if not attempt:
        attempt = ExamAttempt.objects.create(
            exam=exam,
            student=request.user,
            tenant=exam.tenant,
            start_time=started_at,
            is_offline=True,
            sync_status="pending",
            device_id=offline_attempt_id or None,
        )

    for raw_question_id, selected_options in answers.items():
        try:
            question_id = int(raw_question_id)
        except (TypeError, ValueError):
            continue
        if question_id not in question_ids:
            continue
        StudentAnswer.objects.update_or_create(
            attempt=attempt,
            question_id=question_id,
            defaults={
                "tenant": attempt.tenant or exam.tenant,
                "selected_options": selected_options,
            },
        )

    if auto_submitted:
        _mark_attempt_submitted(attempt, auto_submitted=True, auto_payload=auto_payload, submitted_at=submitted_at)
    else:
        _mark_attempt_submitted(attempt, submitted_at=submitted_at)
    attempt.is_offline = True
    attempt.sync_status = "synced"
    if offline_attempt_id and not attempt.device_id:
        attempt.device_id = offline_attempt_id
    attempt.save(
        update_fields=[
            "is_offline",
            "sync_status",
            "device_id",
            "updated_at",
        ]
    )

    # Grading happens here, but the score/percentage is deliberately not
    # included below - the student calling this endpoint should never see
    # their CBT result, same policy as SubmitExamView and ExamResultView.
    _grade_attempt(attempt)
    return Response(
        {
            "success": True,
            "attempt_id": attempt.id,
            "message": "Offline exam synced and graded.",
        },
        status=status.HTTP_201_CREATED,
    )


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def cbt_offline_sync_package(request):
    """Return the published CBT package used by the offline SchoolDom desktop client."""
    if request.user.role not in {"school_admin", "principal", "super_admin", "teacher", "accountant"}:
        return Response({"success": False, "message": "Admin or teacher access required."}, status=status.HTTP_403_FORBIDDEN)

    exams = _published_exam_queryset_for_user(request.user).prefetch_related("questions", "pins").select_related("subject", "class_group")
    student_queryset = User.objects.filter(role="student", is_active=True).select_related("tenant", "student_profile", "student_profile__current_class")
    if getattr(request.user, "tenant", None):
        student_queryset = student_queryset.filter(tenant=request.user.tenant)
    else:
        student_queryset = student_queryset.none()

    exam_rows = []
    for exam in exams.order_by("start_date"):
        active_pin = exam.pins.filter(is_active=True).order_by("-created_at").first()
        questions = [_offline_question_payload(question, request) for question in _question_queryset_for_exam(exam).order_by("id")]
        exam_rows.append(
            {
                "id": exam.id,
                "title": exam.title,
                "subject": getattr(exam.subject, "name", "") or "",
                "class_name": getattr(exam.class_group, "name", "") or "All classes",
                "duration_minutes": exam.duration_minutes,
                "duration_seconds": exam.duration_minutes * 60,
                "start_date": exam.start_date,
                "end_date": exam.end_date,
                "instructions": exam.instructions,
                "questions": questions,
                "pin_preview": active_pin.pin_preview if active_pin else "",
                "offline_pin_hash": _offline_pin_hash(active_pin),
            }
        )

    student_rows = [_offline_student_payload(student, request=request) for student in student_queryset.order_by("last_name", "first_name", "email")]
    generated_at = timezone.now()
    package_id = hashlib.sha256(
        json.dumps(
            {
                "tenant": str(getattr(getattr(request.user, "tenant", None), "id", "")),
                "generated_at": generated_at.isoformat(),
                "exams": [str(item["id"]) for item in exam_rows],
                "students": [str(item.get("student_id") or item.get("id") or "") for item in student_rows],
            },
            sort_keys=True,
        ).encode("utf-8")
    ).hexdigest()

    return Response(
        {
            "success": True,
            "package_type": "schooldom_cbt_exam_package",
            "package_version": 1,
            "package_id": package_id,
            "generated_at": generated_at,
            "school": {
                "id": str(getattr(getattr(request.user, "tenant", None), "id", "")),
                "name": getattr(getattr(request.user, "tenant", None), "name", "") or "",
                "school_code": getattr(getattr(request.user, "tenant", None), "schema_name", "") or "",
            },
            "lifecycle": {
                "stage": "pull",
                "lock_required": True,
                "push_endpoint": "/api/exams/cbt/offline-results/",
                "portable_import_endpoint": "/api/exams/cbt/package/results/import/",
            },
            "exams": exam_rows,
            "students": student_rows,
        }
    )


@api_view(["POST"])
@permission_classes([IsAuthenticated])
@transaction.atomic
def cbt_regenerate_exam_pin(request, exam_id):
    """Regenerate the active CBT PIN for one published exam and return the LAN-safe hash."""
    if request.user.role not in {"school_admin", "principal", "super_admin", "teacher", "accountant"}:
        return Response({"success": False, "message": "Admin or teacher access required."}, status=status.HTTP_403_FORBIDDEN)

    exam = get_object_or_404(_published_exam_queryset_for_user(request.user), id=exam_id)
    active_pins = exam.pins.select_for_update().filter(is_active=True)
    previous_pin = active_pins.order_by("-created_at").first()
    usage_policy = getattr(previous_pin, "usage_policy", ExamPin.USE_REUSABLE) if previous_pin else ExamPin.USE_REUSABLE
    expires_at = getattr(previous_pin, "expires_at", None) if previous_pin else None

    for pin in active_pins:
        pin.is_active = False
        pin.deactivated_at = timezone.now()
        pin.deactivated_by = request.user
        pin.last_regenerated_at = timezone.now()
        pin.last_regenerated_by = request.user
        pin.save(update_fields=["is_active", "deactivated_at", "deactivated_by", "last_regenerated_at", "last_regenerated_by", "updated_at"])

    for _ in range(10):
        plain_pin = ExamPin.generate_plain_pin()
        new_pin = ExamPin(
            exam=exam,
            tenant=getattr(exam, "tenant", None) or getattr(request.user, "tenant", None),
            usage_policy=usage_policy,
            expires_at=expires_at,
            is_active=True,
            created_by=request.user,
            last_regenerated_at=timezone.now(),
            last_regenerated_by=request.user,
        )
        new_pin.set_pin(plain_pin)
        if not ExamPin.objects.filter(pin_digest=new_pin.pin_digest).exists():
            new_pin.save()
            ExamPinUsage.objects.create(
                pin=new_pin,
                exam=exam,
                tenant=getattr(exam, "tenant", None) or getattr(request.user, "tenant", None),
                status=ExamPinUsage.STATUS_REGENERATED,
                message="PIN regenerated from offline admin CBT app.",
                ip_address=request.META.get("REMOTE_ADDR"),
                user_agent=(request.META.get("HTTP_USER_AGENT") or "")[:255],
            )
            return Response(
                {
                    "success": True,
                    "exam_id": exam.id,
                    "pin": new_pin.plain_pin,
                    "pin_preview": new_pin.pin_preview,
                    "offline_pin_hash": _offline_pin_hash(new_pin),
                    "message": "New CBT PIN generated.",
                }
            )

    return Response({"success": False, "message": "Could not generate a unique PIN. Try again."}, status=status.HTTP_409_CONFLICT)


@api_view(["POST", "DELETE"])
@permission_classes([IsAuthenticated])
@transaction.atomic
def cbt_delete_offline_result(request):
    """Delete a CBT result so the student can retake the exam from the LAN client."""
    if request.user.role not in {"school_admin", "principal", "super_admin", "teacher", "accountant"}:
        return Response({"success": False, "message": "Admin or teacher access required."}, status=status.HTTP_403_FORBIDDEN)

    exam_id = request.data.get("exam_id")
    student_identifier = request.data.get("student_id") or request.data.get("admission_number") or request.data.get("student")
    offline_session_id = str(request.data.get("session_id") or request.data.get("offline_attempt_id") or "").strip()
    if not exam_id or not student_identifier:
        return Response({"success": False, "message": "exam_id and student_id are required."}, status=status.HTTP_400_BAD_REQUEST)

    exam = get_object_or_404(_published_exam_queryset_for_user(request.user), id=exam_id)
    # student_id/admission_number can collide across schools - only accept a candidate
    # from the same tenant as the admin/teacher performing this action.
    legacy_tenant = resolve_legacy_tenant_for_school(getattr(request.user, "tenant", None))
    student = None
    if legacy_tenant:
        student = next(
            (c for c in _find_students_by_identifier(student_identifier)
             if resolve_legacy_tenant_for_school(getattr(c, "tenant", None)) == legacy_tenant),
            None,
        )
    if not student:
        return Response({"success": False, "message": "Student was not found."}, status=status.HTTP_404_NOT_FOUND)

    attempts = ExamAttempt.objects.filter(exam=exam, student=student)
    if offline_session_id:
        session_filter = Q(device_id=offline_session_id)
        if offline_session_id.isdigit():
            session_filter |= Q(id=int(offline_session_id))
        attempts = attempts.filter(session_filter)
    deleted_count = attempts.count()
    attempts.delete()
    return Response(
        {
            "success": True,
            "deleted": deleted_count,
            "exam_id": exam.id,
            "student_id": student_identifier,
            "message": "Result deleted. Student can retake the exam.",
        }
    )


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def cbt_exam_package_export(request):
    """Download a portable JSON package for fully offline CBT clients."""
    package_response = cbt_offline_sync_package(request)
    if package_response.status_code >= 400:
        return package_response
    payload = package_response.data
    stamp = timezone.now().strftime("%Y%m%d%H%M%S")
    response = HttpResponse(
        json.dumps(payload, default=str, indent=2),
        content_type="application/json",
    )
    response["Content-Disposition"] = f'attachment; filename="schooldom-cbt-package-{stamp}.json"'
    return response


def _unwrap_cbt_sync_payload(data):
    envelope = (data.get("sync_envelope") or data.get("envelope")) if isinstance(data, dict) else None
    if not isinstance(envelope, dict):
        return data, {}
    payload = envelope.get("payload") or {}
    if not isinstance(payload, dict):
        payload = {}
    payload.setdefault("sync_id", envelope.get("sync_id") or "")
    payload.setdefault("device_id", envelope.get("device_id") or "")
    payload.setdefault("package_id", envelope.get("package_id") or "")
    payload.setdefault("package_locked_at", envelope.get("package_locked_at") or "")
    return payload, envelope


def _ingest_cbt_offline_result(actor, payload):
    payload, envelope = _unwrap_cbt_sync_payload(payload or {})
    exam_id = payload.get("exam_id")
    student_identifier = payload.get("student_id") or payload.get("admission_number") or payload.get("student")
    answers = payload.get("answers") or {}
    offline_session_id = str(payload.get("session_id") or payload.get("offline_attempt_id") or "").strip()
    started_at = parse_datetime(str(payload.get("started_at") or "")) or timezone.now()
    submitted_at = parse_datetime(str(payload.get("submitted_at") or "")) or timezone.now()
    audit_logs = payload.get("audit_logs") or payload.get("activity_logs") or []
    if not isinstance(audit_logs, list):
        audit_logs = []

    if not exam_id:
        return {"success": False, "message": "exam_id is required."}, status.HTTP_400_BAD_REQUEST
    if not isinstance(answers, dict):
        return {"success": False, "message": "answers must be an object keyed by question id."}, status.HTTP_400_BAD_REQUEST

    exam = get_object_or_404(_published_exam_queryset_for_user(actor), id=exam_id)
    # student_id/admission_number can collide across schools - only accept a candidate
    # from the same tenant as the actor (admin/teacher) syncing this result.
    legacy_tenant = resolve_legacy_tenant_for_school(getattr(actor, "tenant", None))
    student = None
    if legacy_tenant:
        student = next(
            (c for c in _find_students_by_identifier(student_identifier)
             if resolve_legacy_tenant_for_school(getattr(c, "tenant", None)) == legacy_tenant),
            None,
        )
    if not student:
        return {"success": False, "message": "Student was not found."}, status.HTTP_404_NOT_FOUND
    sync_device_id = str(payload.get("device_id") or envelope.get("device_id") or "").strip()
    sync_package_id = str(payload.get("package_id") or envelope.get("package_id") or "").strip()
    if offline_session_id:
        # Primary dedup: exact session ID match
        existing = ExamAttempt.objects.filter(
            device_id=offline_session_id, student=student, exam=exam, is_submitted=True
        ).first()
        if existing:
            return {"success": True, "attempt_id": existing.id, "message": "Offline result already synced."}, status.HTTP_200_OK
    else:
        # Fallback dedup when session_id is missing: prevent re-upload of the
        # same offline result for a student who has already been synced via this
        # device/package combination.
        if sync_device_id and sync_package_id:
            existing = ExamAttempt.objects.filter(
                student=student, exam=exam, is_submitted=True, is_offline=True,
                sync_status="synced",
            ).filter(
                auto_submit_activity_logs__contains=[{"device_id": sync_device_id}]
            ).first()
            if existing:
                return {"success": True, "attempt_id": existing.id, "message": "Offline result already synced."}, status.HTTP_200_OK

    attempt = ExamAttempt.objects.create(
        exam=exam,
        student=student,
        tenant=exam.tenant,
        start_time=started_at,
        is_offline=True,
        sync_status="pending",
        device_id=offline_session_id or None,
        question_order=[question.id for question in _question_queryset_for_exam(exam).order_by("id")],
    )
    question_ids = set(_question_queryset_for_exam(exam).values_list("id", flat=True))
    for raw_question_id, answer_value in answers.items():
        try:
            question_id = int(raw_question_id)
        except (TypeError, ValueError):
            continue
        if question_id not in question_ids:
            continue
        StudentAnswer.objects.update_or_create(
            attempt=attempt,
            question_id=question_id,
            defaults={
                "tenant": attempt.tenant or exam.tenant,
                "selected_options": answer_value,
                "answer_text": answer_value if isinstance(answer_value, str) else "",
            },
        )

    _mark_attempt_submitted(
        attempt,
        auto_submitted=str(payload.get("cause") or "").lower() in {"timer_elapsed", "auto_submit"},
        auto_payload={
            "reason": "offline_timeout_sync" if str(payload.get("cause") or "").lower() == "timer_elapsed" else "unknown",
            "display": "Offline CBT submission",
            "details": "Submitted from SchoolDom CBT Client.",
            "warnings": payload.get("malpractice_log") or [],
            "logs": audit_logs or payload.get("malpractice_log") or [],
        },
        submitted_at=submitted_at,
    )
    attempt.is_offline = True
    attempt.sync_status = "synced"
    if audit_logs and not attempt.auto_submit_activity_logs:
        attempt.auto_submit_activity_logs = audit_logs
    attempt.save(update_fields=["is_offline", "sync_status", "auto_submit_activity_logs", "updated_at"])
    score, total_points = _grade_attempt(attempt)
    return {
        "success": True,
        "attempt_id": attempt.id,
        "score": score,
        "total_points": total_points,
        "percentage": attempt.percentage,
        "sync_id": payload.get("sync_id") or envelope.get("sync_id") or "",
        "device_id": sync_device_id,
        "package_id": sync_package_id,
        "message": "Offline CBT result synced.",
    }, status.HTTP_201_CREATED


@api_view(["POST"])
@permission_classes([IsAuthenticated])
@transaction.atomic
def cbt_offline_result_ingest(request):
    """Ingest a result submitted by the admin desktop client for a student who wrote offline."""
    if request.user.role not in {"school_admin", "principal", "super_admin", "teacher", "accountant"}:
        return Response({"success": False, "message": "Admin or teacher access required."}, status=status.HTTP_403_FORBIDDEN)
    payload, response_status = _ingest_cbt_offline_result(request.user, request.data)
    return Response(payload, status=response_status)


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def cbt_results_package_import(request):
    """Import a portable result package exported from the offline CBT desktop app."""
    if request.user.role not in {"school_admin", "principal", "super_admin", "teacher", "accountant"}:
        return Response({"success": False, "message": "Admin or teacher access required."}, status=status.HTTP_403_FORBIDDEN)
    package_payload = request.data or {}
    results = package_payload.get("results") or package_payload.get("items") or []
    if not isinstance(results, list):
        return Response({"success": False, "message": "results must be a list."}, status=status.HTTP_400_BAD_REQUEST)

    processed = []
    for item in results:
        if isinstance(item, dict) and isinstance(item.get("sync_envelope"), dict):
            payload = {"sync_envelope": item.get("sync_envelope")}
        else:
            payload = item.get("payload") if isinstance(item, dict) else None
        if not isinstance(payload, dict):
            processed.append({"success": False, "message": "Invalid result item."})
            continue
        try:
            response_payload, response_status = _ingest_cbt_offline_result(request.user, payload)
            processed.append({
                "success": response_status < 400,
                "status_code": response_status,
                "data": response_payload,
            })
        except Exception as exc:
            processed.append({"success": False, "message": str(exc)})

    imported = sum(1 for item in processed if item.get("success"))
    return Response({
        "success": True,
        "imported": imported,
        "failed": len(processed) - imported,
        "processed": processed,
    })


# ---------------------------------------------------------------------------
# CBT Admin App auto-update version endpoint
# ---------------------------------------------------------------------------
# Update CBT_ADMIN_APP_VERSION in your Django settings (or .env via a
# settings override) whenever you publish a new installer.  The desktop app
# checks this endpoint on every launch and prompts the admin to update when
# 'version' is newer than the installed version.
#
# Example settings.py entry:
#   CBT_ADMIN_APP_VERSION = {
#       "version": "0.2.0",
#       "release_notes": "- Fixed timer sync\n- HTML question rendering",
#       "release_date": "2026-08-01",
#       "download_url": "https://schooldom.academy/media/app/cbt/SchoolDom-Admin-Sync-Win7-0.2.0-Setup.exe",
#       "file_size_bytes": 4567890,
#       "is_mandatory": False,
#   }
_CBT_ADMIN_APP_VERSION_DEFAULT = {
    "version": "0.1.0",
    "release_notes": "Initial release of SchoolDom Admin Sync for Windows 7.",
    "release_date": "2026-07-27",
    "download_url": "",
    "file_size_bytes": None,
    "is_mandatory": False,
}

@api_view(['GET'])
@permission_classes([AllowAny])
def cbt_app_version(request):
    info = getattr(settings, 'CBT_ADMIN_APP_VERSION', _CBT_ADMIN_APP_VERSION_DEFAULT)
    return Response(info)


def _grade_letter_for(user, percentage):
    """Grade for a percentage, through the same admin-configured GradeScale as
    report cards, transcripts and the CBT result page.

    Deliberately delegates rather than querying GradeScale here: this screen
    inventing its own boundaries is the exact bug ExamResultGradingTests was
    written to prevent, and a submission popup disagreeing with the report card
    on the same percentage would be worse than showing no grade at all.
    """
    from users.app_views import _grade_for_percentage

    return _grade_for_percentage(user, percentage)


REVIEW_STATUS_CORRECT = "correct"
REVIEW_STATUS_INCORRECT = "incorrect"
REVIEW_STATUS_PARTIAL = "partial"
REVIEW_STATUS_UNANSWERED = "unanswered"
REVIEW_STATUS_PENDING = "pending"


def _answer_review_state(question, answer):
    """What actually happened on one question.

    The distinction that matters is a NULL score on a theory answer: that is
    _grade_attempt leaving the question for a human, not a zero awarded. Showing
    it as an incorrect answer worth nothing is exactly what this endpoint exists
    to avoid, so it reports as pending and stays out of the awarded total.
    """
    possible = float(question.points or 0)
    is_theory = question.question_type in Question.THEORY_TYPES

    if answer is None:
        return {"status": REVIEW_STATUS_UNANSWERED, "awarded": 0.0, "possible": possible, "graded": True}

    if is_theory:
        answered = bool((answer.answer_text or "").strip())
        if answer.score is None:
            # Ungraded. A blank theory answer is still ungraded until a teacher
            # confirms it earns nothing, so both wait rather than scoring zero.
            return {
                "status": REVIEW_STATUS_PENDING if answered else REVIEW_STATUS_UNANSWERED,
                "awarded": 0.0,
                "possible": possible,
                "graded": False,
            }
        awarded = float(answer.score)
        if possible > 0 and awarded >= possible:
            status_value = REVIEW_STATUS_CORRECT
        elif awarded <= 0:
            status_value = REVIEW_STATUS_INCORRECT
        else:
            status_value = REVIEW_STATUS_PARTIAL
        return {"status": status_value, "awarded": awarded, "possible": possible, "graded": True}

    selected = _normalize_selected_answer(answer.selected_options)
    if selected is None and not (answer.answer_text or "").strip():
        return {"status": REVIEW_STATUS_UNANSWERED, "awarded": 0.0, "possible": possible, "graded": True}

    return {
        "status": REVIEW_STATUS_CORRECT if answer.is_correct else REVIEW_STATUS_INCORRECT,
        "awarded": float(answer.score or 0),
        "possible": possible,
        "graded": True,
    }


def _student_answer_display(question, answer):
    """What the student put down, as text an admin can read."""
    if answer is None:
        return ""
    if question.question_type in Question.THEORY_TYPES:
        return answer.answer_text or ""
    options = question.options or []
    selected = _normalize_selected_answer(answer.selected_options)
    try:
        index = int(selected)
    except (TypeError, ValueError):
        return answer.answer_text or ""
    if 0 <= index < len(options):
        return "%s. %s" % (chr(65 + index), options[index])
    return answer.answer_text or ""


def _correct_answer_display(question):
    if question.question_type in Question.THEORY_TYPES:
        return question.correct_answer or ""
    options = question.options or []
    if question.correct_answer in options:
        index = options.index(question.correct_answer)
        return "%s. %s" % (chr(65 + index), question.correct_answer)
    return question.correct_answer or ""


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def attempt_review(request, attempt_id):
    """One student's whole submitted exam, question by question.

    Every figure is summed from the individual questions rather than read off
    ExamAttempt.score, so the summary always reconciles with the rows beneath
    it. ExamAttempt.score is objective-only until theory grades are published,
    which would otherwise make the two disagree on a mixed exam.
    """
    from users.app_views import _media_url, _question_group_payload

    role = getattr(request.user, "role", "")
    if role not in THEORY_GRADING_ROLES:
        return Response(
            {"success": False, "message": "Only teachers and administrators can review submissions."},
            status=status.HTTP_403_FORBIDDEN,
        )

    attempt = get_object_or_404(
        _theory_gradable_attempts_qs(request.user).select_related(
            "exam__subject", "exam__class_group", "exam__exam_type", "student"
        ),
        id=attempt_id,
    )

    questions = list(_question_queryset_for_exam(attempt.exam).order_by("group__id", "group_order", "id"))
    answers = {
        answer.question_id: answer
        for answer in StudentAnswer.objects.filter(attempt=attempt).select_related("question")
    }

    rows = []
    awarded_total = 0.0
    possible_total = 0.0
    graded_possible = 0.0
    tally = {
        REVIEW_STATUS_CORRECT: 0,
        REVIEW_STATUS_INCORRECT: 0,
        REVIEW_STATUS_PARTIAL: 0,
        REVIEW_STATUS_UNANSWERED: 0,
        REVIEW_STATUS_PENDING: 0,
    }

    for index, question in enumerate(questions, start=1):
        answer = answers.get(question.id)
        state = _answer_review_state(question, answer)
        tally[state["status"]] = tally.get(state["status"], 0) + 1
        awarded_total += state["awarded"]
        possible_total += state["possible"]
        if state["graded"]:
            graded_possible += state["possible"]

        rows.append({
            "number": index,
            "question_id": question.id,
            "question_text": question.text,
            "question_type": question.question_type,
            "is_theory": question.question_type in Question.THEORY_TYPES,
            "options": question.options or [],
            "passage": _question_group_payload(question.group, request) if question.group_id else None,
            "image": _media_url(request, question.image),
            "student_answer": _student_answer_display(question, answer),
            "correct_answer": _correct_answer_display(question),
            "marks_awarded": round(state["awarded"], 2),
            "marks_possible": round(state["possible"], 2),
            "status": state["status"],
            "teacher_feedback": (answer.teacher_feedback or "") if answer else "",
        })

    # Percentage is over the whole paper, so a mixed exam with theory still
    # outstanding reads low on purpose - the popup labels those questions
    # Pending Grading so the number is never mistaken for a final result.
    percentage = round((awarded_total / possible_total * 100), 2) if possible_total else 0.0
    letter, remark = _grade_letter_for(request.user, percentage)
    student_profile = getattr(attempt.student, "student_profile", None)

    return Response({
        "success": True,
        "attempt_id": attempt.id,
        "student_name": attempt.student.get_full_name() or attempt.student.email,
        "student_id": getattr(student_profile, "student_id", "") or getattr(student_profile, "admission_number", "") or "",
        "class_name": str(attempt.exam.class_group) if attempt.exam.class_group_id else "",
        "exam_title": attempt.exam.title,
        "subject": attempt.exam.subject.name if attempt.exam.subject_id else "",
        "exam_type": attempt.exam.exam_type.name if attempt.exam.exam_type_id else attempt.exam.get_exam_format_display(),
        "submitted_at": attempt.end_time or attempt.updated_at,
        "started_at": attempt.start_time,
        "auto_submitted": attempt.auto_submitted,
        "score": round(awarded_total, 2),
        "total_marks": round(possible_total, 2),
        "graded_marks": round(graded_possible, 2),
        "percentage": percentage,
        "grade": letter,
        "grade_remark": remark,
        "total_questions": len(questions),
        "answered_questions": len(questions) - tally[REVIEW_STATUS_UNANSWERED],
        "unanswered_questions": tally[REVIEW_STATUS_UNANSWERED],
        "correct_questions": tally[REVIEW_STATUS_CORRECT],
        "incorrect_questions": tally[REVIEW_STATUS_INCORRECT],
        "partial_questions": tally[REVIEW_STATUS_PARTIAL],
        "pending_questions": tally[REVIEW_STATUS_PENDING],
        "questions": rows,
    })
