from django.conf import settings
from django.core.mail import send_mail
from django.db import transaction
import json
import random
from datetime import timedelta
from collections import defaultdict

from django.db.models import Q
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from academic.models import AcademicYear, GradeScale, Subject, Term
from exams.models import Question as ExamQuestion
from notifications.models import Notification
from notifications.push import push_for_notifications
from users.models import User, resolve_legacy_tenant_for_school
from .models import (
    Question as QuizQuestion,
    PersonalQuizAnswer,
    PersonalQuizAttempt,
    PersonalQuizFolder,
    PersonalQuizFolderQuestion,
    PersonalQuizQuestion,
    Quiz,
    Submission,
)
from .serializers import (
    QuizListSerializer,
    QuizSerializer,
    StudentQuizSerializer,
    SubmissionDetailSerializer,
    SubmissionSerializer,
)


MAX_PERSONAL_QUESTIONS = 20
DAILY_PERSONAL_TIME_LIMIT_MINUTES = 15
INBUILT_PERSONAL_QUIZ_TENANT_SLUGS = {"icon_tutor", "icon_tutor_8"}
INBUILT_PERSONAL_QUIZ_FOLDER_SUFFIX = " Personal Quiz Pool"
PLACEHOLDER_PERSONAL_QUESTION_PREFIXES = (
    "Which subject is this personal quiz focused on?",
    "This quiz was generated for ",
    "Fill in the blank: The selected subject is ____.",
    "Which class is attached to this quiz attempt?",
    "Students can create the questions in a personal quiz.",
    "The code for ",
    "What is the maximum number of questions allowed in a personal quiz?",
    "Your quiz score is calculated instantly after submission.",
)
PLACEHOLDER_PERSONAL_QUESTION_SNIPPETS = (
    "set a topic",
    "select a topic",
    "choose a topic",
    "pick a topic",
    "topic in math",
    "topic in mathematics",
)
SUBJECT_PERSONAL_QUIZ_ALIASES = {
    "acc": {"Accounting", "Financial Accounting"},
    "accounting": {"Accounting", "Financial Accounting"},
    "agric": {"Agricultural Science", "Agriculture"},
    "agricultural science": {"Agricultural Science", "Agriculture"},
    "agriculture": {"Agricultural Science", "Agriculture"},
    "anh": {"Animal Husbandry"},
    "animal husbandry": {"Animal Husbandry"},
    "art": {"Fine Arts", "Visual Arts", "Art"},
    "arts": {"Fine Arts", "Visual Arts", "Art"},
    "bio": {"Biology"},
    "biology": {"Biology"},
    "chem": {"Chemistry"},
    "chemistry": {"Chemistry"},
    "civ": {"Civic Education", "Civics"},
    "civic": {"Civic Education", "Civics"},
    "civics": {"Civic Education", "Civics"},
    "civic education": {"Civic Education", "Civics"},
    "com": {"Commerce"},
    "commerce": {"Commerce"},
    "comp": {"Computer Studies", "Computer Science", "ICT", "Information and Communication Technology"},
    "computer": {"Computer Studies", "Computer Science", "ICT", "Information and Communication Technology"},
    "computer studies": {"Computer Studies", "Computer Science", "ICT", "Information and Communication Technology"},
    "computer science": {"Computer Studies", "Computer Science", "ICT", "Information and Communication Technology"},
    "crk": {"Christian Religious Studies", "Christian Religious Knowledge", "CRS"},
    "crs": {"Christian Religious Studies", "Christian Religious Knowledge", "CRS"},
    "christian religious knowledge": {"Christian Religious Studies", "Christian Religious Knowledge", "CRS"},
    "christian religious studies": {"Christian Religious Studies", "Christian Religious Knowledge", "CRS"},
    "eco": {"Economics"},
    "economics": {"Economics"},
    "eng": {"English", "English Language"},
    "english": {"English", "English Language"},
    "english language": {"English", "English Language"},
    "fine arts": {"Fine Arts", "Visual Arts", "Art"},
    "financial accounting": {"Accounting", "Financial Accounting"},
    "fmath": {"Further Mathematics", "Further Maths"},
    "further math": {"Further Mathematics", "Further Maths"},
    "further maths": {"Further Mathematics", "Further Maths"},
    "further mathematics": {"Further Mathematics", "Further Maths"},
    "geo": {"Geography"},
    "geography": {"Geography"},
    "government": {"Government"},
    "gov": {"Government"},
    "hist": {"History"},
    "history": {"History"},
    "irs": {"Islamic Religious Studies", "Islamic Religious Knowledge", "IRS"},
    "islamic religious knowledge": {"Islamic Religious Studies", "Islamic Religious Knowledge", "IRS"},
    "islamic religious studies": {"Islamic Religious Studies", "Islamic Religious Knowledge", "IRS"},
    "lit": {"Literature", "Literature in English"},
    "literature": {"Literature", "Literature in English"},
    "literature in english": {"Literature", "Literature in English"},
    "mth": {"Mathematics", "General Mathematics"},
    "mat": {"Mathematics", "General Mathematics"},
    "math": {"Mathematics", "General Mathematics"},
    "maths": {"Mathematics", "General Mathematics"},
    "mathematics": {"Mathematics", "General Mathematics"},
    "general mathematics": {"Mathematics", "General Mathematics"},
    "music": {"Music"},
    "mus": {"Music"},
    "bus": {"Business Studies", "Business"},
    "business": {"Business Studies", "Business"},
    "business studies": {"Business Studies", "Business"},
    "off": {"Office Practice"},
    "office": {"Office Practice"},
    "office practice": {"Office Practice"},
    "phy": {"Physics"},
    "physics": {"Physics"},
    "visual arts": {"Fine Arts", "Visual Arts", "Art"},
}


def _student_profile(user):
    return getattr(user, "student_profile", None)


def _class_label(class_group):
    if not class_group:
        return "your class"
    return class_group.name if not class_group.section else f"{class_group.name} {class_group.section}"


def _normalize_answer(value):
    return str(value or "").strip().casefold()


def _today():
    return timezone.localdate()


def _week_start(value):
    return value - timedelta(days=value.weekday())


def _month_start(value):
    return value.replace(day=1)


def _percentage(score, total):
    return round((float(score or 0) / max(float(total or 0), 1.0)) * 100, 1) if total else 0


def _active_academic_year(user):
    legacy_tenant = resolve_legacy_tenant_for_school(getattr(user, "tenant", None))
    if not legacy_tenant:
        return None
    return AcademicYear.objects.filter(is_active=True, tenant=legacy_tenant).order_by("-start_date").first()


def _active_term(user):
    legacy_tenant = resolve_legacy_tenant_for_school(getattr(user, "tenant", None))
    if not legacy_tenant:
        return None
    return Term.objects.select_related("academic_year").filter(is_active=True, tenant=legacy_tenant).order_by("-start_date").first()


def _term_for_date(user, value):
    legacy_tenant = resolve_legacy_tenant_for_school(getattr(user, "tenant", None))
    if not legacy_tenant:
        return None
    term = Term.objects.select_related("academic_year").filter(
        start_date__lte=value, end_date__gte=value, tenant=legacy_tenant
    ).order_by("-start_date").first()
    return term or _active_term(user)


def _year_for_date(user, value, term=None):
    if term and term.academic_year_id:
        return term.academic_year
    legacy_tenant = resolve_legacy_tenant_for_school(getattr(user, "tenant", None))
    if not legacy_tenant:
        return None
    year = AcademicYear.objects.filter(start_date__lte=value, end_date__gte=value, tenant=legacy_tenant).order_by("-start_date").first()
    return year or _active_academic_year(user)


def _attempt_due_at(attempt):
    return attempt.started_at + timedelta(minutes=attempt.time_limit_minutes or DAILY_PERSONAL_TIME_LIMIT_MINUTES)


def _shuffle_options(options, correct_answer):
    normalized_correct = str(correct_answer or "").strip()
    if isinstance(options, str):
        try:
            decoded = json.loads(options)
            options = decoded if isinstance(decoded, list) else []
        except (TypeError, ValueError):
            options = []
    cleaned = [str(option).strip() for option in (options or []) if str(option).strip()]
    if normalized_correct and normalized_correct not in cleaned:
        cleaned.append(normalized_correct)
    random.shuffle(cleaned)
    return cleaned


def _format_report_options(options):
    if not options:
        return "No options provided."
    return "\n".join(f"{chr(65 + index)}. {option}" for index, option in enumerate(options))


def _admin_users_for_school(school):
    queryset = User.objects.filter(
        role__in=["school_admin", "principal", "super_admin"],
        email__isnull=False,
    ).exclude(email="")
    if school:
        queryset = queryset.filter(tenant=school)
    return queryset


def _question_report_recipients(school=None):
    configured_email = str(getattr(settings, "INAPPROPRIATE_QUESTION_REPORT_EMAIL", "") or "").strip()
    recipients = [configured_email] if configured_email else []
    recipients.extend(_admin_users_for_school(school).values_list("email", flat=True)[:10])
    return list(dict.fromkeys(recipients))


def _create_flag_notifications(*, school, admin_users, teacher, title, message, reference_model):
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
                reference_model=reference_model,
                is_delivered=True,
                delivered_at=timezone.now(),
            )
        )
    if notifications:
        Notification.objects.bulk_create(notifications)
        push_for_notifications(notifications)


def _recent_student_flag_count(*, student, reference_model, title):
    school = getattr(student, "tenant", None)
    queryset = Notification.objects.filter(
        event_type="inappropriate_question",
        reference_model=reference_model,
        message__icontains=student.get_full_name() or student.email,
        title="Inappropriate question flagged",
    )
    if school:
        queryset = queryset.filter(tenant=school)
    if title:
        queryset = queryset.filter(message__icontains=title)
    return queryset.count()


def _send_inappropriate_question_report(*, title, school, school_name, subject_name, student, question_id, question_text, options, correct_answer, selected_answer, reason):
    recipients = _question_report_recipients(school)
    if not recipients:
        return False
    student_name = student.get_full_name() or student.email
    message = "\n".join(
        [
            "A student flagged a quiz question as inappropriate.",
            "",
            f"Quiz: {title}",
            f"School: {school_name or 'No school recorded'}",
            f"Subject: {subject_name or 'No subject recorded'}",
            f"Student: {student_name} ({student.email})",
            f"Question ID: {question_id}",
            "",
            "Question:",
            question_text,
            "",
            "Options:",
            _format_report_options(options),
            "",
            f"Correct answer: {correct_answer or 'No correct answer recorded'}",
            f"Student selected answer: {selected_answer or 'Not answered'}",
            "",
            "Student report:",
            reason,
        ]
    )
    send_mail(
        f"Inappropriate question report: {title}",
        message,
        settings.DEFAULT_FROM_EMAIL,
        recipients,
        fail_silently=False,
    )
    return True


def _resolve_student_legacy_tenant(user, profile=None):
    """Resolve the legacy tenants.Tenant for a student user.

    Falls back to the tenant of the student's current class when the school→legacy
    slug mapping fails, which can happen if core.SchoolTenant.schema_name doesn't
    exactly match tenants.Tenant.slug for the school.
    """
    tenant = resolve_legacy_tenant_for_school(getattr(user, "tenant", None))
    if not tenant:
        if profile is None:
            profile = _student_profile(user)
        if profile and profile.current_class_id:
            tenant = getattr(profile.current_class, "tenant", None)
    return tenant


def _subject_queryset_for_student(user, profile=None):
    profile = profile or _student_profile(user)
    legacy_tenant = _resolve_student_legacy_tenant(user, profile)
    subjects = Subject.objects.all().order_by("name")
    subjects = subjects.filter(tenant=legacy_tenant) if legacy_tenant else subjects.none()
    if profile and profile.current_class_id and profile.current_class.subjects.exists():
        subjects = subjects.filter(classes=profile.current_class)
    return subjects.distinct()


def _daily_streak(attempts):
    dates = sorted({attempt.daily_date or timezone.localtime(attempt.submitted_at).date() for attempt in attempts if attempt.is_submitted and attempt.submitted_at}, reverse=True)
    if not dates:
        return 0
    current = _today()
    if dates[0] < current:
        current = dates[0]
    streak = 0
    date_set = set(dates)
    while current in date_set:
        streak += 1
        current = current - timedelta(days=1)
    return streak


def _weekly_streak(attempts, today=None):
    today = today or _today()
    current_week_start = _week_start(today)
    dates = {
        attempt.daily_date or timezone.localtime(attempt.submitted_at).date()
        for attempt in attempts
        if attempt.is_submitted and attempt.submitted_at
    }
    cursor = today
    streak = 0
    while cursor >= current_week_start and cursor in dates:
        streak += 1
        cursor = cursor - timedelta(days=1)
    return streak


def _personal_quiz_metrics(student, attempts=None):
    today = _today()
    current_week = _week_start(today)
    current_month = _month_start(today)
    active_term = _active_term(student)
    attempts = list(
        attempts
        if attempts is not None
        else PersonalQuizAttempt.objects.filter(student=student, is_submitted=True)
        .select_related("subject", "class_group", "term", "academic_year")
        .order_by("-submitted_at")
    )

    def attempt_date(attempt):
        if attempt.daily_date:
            return attempt.daily_date
        if attempt.submitted_at:
            return timezone.localtime(attempt.submitted_at).date()
        return timezone.localdate(attempt.started_at)

    def attempt_percentage(attempt):
        return round(float(attempt.percentage), 1) if getattr(attempt, "percentage", 0) else _percentage(attempt.score, attempt.total_points)

    current_term_attempts = [
        attempt for attempt in attempts
        if (active_term and attempt.term_id == active_term.id)
        or (not active_term and (not attempt.term_id or attempt_date(attempt).year == today.year))
    ]
    current_month_attempts = [attempt for attempt in current_term_attempts if _month_start(attempt.month_start or attempt_date(attempt)) == current_month]
    current_week_attempts = [attempt for attempt in current_term_attempts if (attempt.week_start or _week_start(attempt_date(attempt))) == current_week]

    subject_map = {}
    for attempt in current_month_attempts:
        key = attempt.subject_id or f"subject-{attempt.subject.name if attempt.subject else 'general'}"
        row = subject_map.setdefault(
            key,
            {
                "subject_id": attempt.subject_id,
                "subject": attempt.subject.name if attempt.subject else "General",
                "completed": 0,
                "total_percentage": 0,
                "best_percentage": 0,
            },
        )
        pct = attempt_percentage(attempt)
        row["completed"] += 1
        row["total_percentage"] += pct
        row["best_percentage"] = max(row["best_percentage"], pct)
    subject_rows = []
    for row in subject_map.values():
        average = round(row["total_percentage"] / max(row["completed"], 1), 1)
        subject_rows.append({**row, "average_percentage": average})
    subject_rows.sort(key=lambda item: (-item["average_percentage"], item["subject"]))

    monthly_trends = []
    month_map = defaultdict(list)
    for attempt in current_term_attempts:
        month_map[attempt.month_start or _month_start(attempt_date(attempt))].append(attempt_percentage(attempt))
    for month, percentages in sorted(month_map.items()):
        monthly_trends.append(
            {
                "month": month,
                "label": month.strftime("%b %Y"),
                "completed": len(percentages),
                "average_percentage": round(sum(percentages) / max(len(percentages), 1), 1),
            }
        )

    week_map = defaultdict(set)
    for attempt in current_term_attempts:
        date_value = attempt_date(attempt)
        week_map[attempt.week_start or _week_start(date_value)].add(date_value)
    weekly_history = [
        {
            "week_start": week,
            "week_end": week + timedelta(days=6),
            "completed_days": len(days),
            "completed_quizzes": sum(1 for attempt in current_term_attempts if (attempt.week_start or _week_start(attempt_date(attempt))) == week),
        }
        for week, days in sorted(week_map.items(), reverse=True)
    ]

    term_map = defaultdict(list)
    for attempt in attempts:
        key = attempt.term_id or "unassigned"
        term_map[key].append(attempt)
    term_history = []
    for key, records in term_map.items():
        term = records[0].term if key != "unassigned" else None
        percentages = [attempt_percentage(item) for item in records]
        term_history.append(
            {
                "term_id": term.id if term else None,
                "term": term.name if term else "Unassigned term",
                "academic_year": term.academic_year.name if term and term.academic_year_id else (records[0].academic_year.name if records[0].academic_year_id else ""),
                "is_active": bool(active_term and term and term.id == active_term.id),
                "completed": len(records),
                "average_percentage": round(sum(percentages) / max(len(percentages), 1), 1),
                "best_percentage": max(percentages, default=0),
                "archived": bool(active_term and (not term or term.id != active_term.id)),
            }
        )
    term_history.sort(key=lambda item: (not item["is_active"], item["term"]))

    month_percentages = [attempt_percentage(attempt) for attempt in current_month_attempts]
    term_percentages = [attempt_percentage(attempt) for attempt in current_term_attempts]
    return {
        "active_term": {
            "id": active_term.id if active_term else None,
            "name": active_term.name if active_term else "Current term",
            "start_date": active_term.start_date if active_term else None,
            "end_date": active_term.end_date if active_term else None,
        },
        "weekly_streak": {
            "week_start": current_week,
            "week_end": current_week + timedelta(days=6),
            "current": _weekly_streak(current_term_attempts, today),
            "completed_this_week": len(current_week_attempts),
            "completed_days_this_week": len({attempt_date(attempt) for attempt in current_week_attempts}),
            "history": weekly_history[:12],
        },
        "monthly": {
            "month_start": current_month,
            "total_completed": len(current_month_attempts),
            "overall_average_percentage": round(sum(month_percentages) / max(len(month_percentages), 1), 1) if month_percentages else 0,
            "highest_subjects": subject_rows[:3],
            "weakest_subjects": sorted(subject_rows, key=lambda item: (item["average_percentage"], item["subject"]))[:3],
            "subjects": subject_rows,
            "progress_trends": monthly_trends[-6:],
        },
        "term": {
            "total_completed": len(current_term_attempts),
            "overall_average_percentage": round(sum(term_percentages) / max(len(term_percentages), 1), 1) if term_percentages else 0,
            "history": term_history,
        },
        "history": [_personal_attempt_payload(attempt) for attempt in attempts[:50]],
    }


def _personal_question_payload(question, include_answer=False, answer=None):
    payload = {
        "id": question.id,
        "order": question.order,
        "question_type": question.question_type,
        "prompt": question.prompt,
        "options": question.options or [],
        "points": question.points,
        "explanation": question.explanation,
    }
    if include_answer:
        payload.update(
            {
                "correct_answer": question.correct_answer,
                "answer_text": answer.answer_text if answer else "",
                "is_correct": answer.is_correct if answer else False,
                "earned_points": answer.earned_points if answer else 0,
            }
        )
    return payload


def _grade_for_attempt(attempt, percentage):
    scale = None
    if getattr(attempt, "tenant_id", None):
        scale = (
            GradeScale.objects.filter(
                tenant=attempt.tenant,
                is_active=True,
                min_percentage__lte=percentage,
                max_percentage__gte=percentage,
            )
            .order_by("-min_percentage")
            .first()
        )
    if scale:
        return {"letter": scale.letter, "remark": scale.remark}
    if percentage >= 70:
        return {"letter": "A", "remark": "Excellent"}
    if percentage >= 60:
        return {"letter": "B", "remark": "Very good"}
    if percentage >= 50:
        return {"letter": "C", "remark": "Good"}
    if percentage >= 45:
        return {"letter": "D", "remark": "Fair"}
    if percentage >= 40:
        return {"letter": "E", "remark": "Pass"}
    return {"letter": "F", "remark": "Needs improvement"}


def _personal_attempt_payload(attempt, include_questions=False, include_answers=False):
    total = attempt.total_points or attempt.questions.count()
    percentage = round(float(attempt.percentage), 1) if getattr(attempt, "percentage", 0) else _percentage(attempt.score, total)
    payload = {
        "id": attempt.id,
        "title": attempt.title,
        "subject": attempt.subject.name if attempt.subject else "",
        "subject_id": attempt.subject_id,
        "class_group": _class_label(attempt.class_group),
        "academic_year": attempt.academic_year.name if getattr(attempt, "academic_year_id", None) else "",
        "term": attempt.term.name if getattr(attempt, "term_id", None) else "",
        "week_start": attempt.week_start,
        "month_start": attempt.month_start,
        "time_limit_minutes": attempt.time_limit_minutes,
        "score": attempt.score,
        "total_points": total,
        "percentage": percentage,
        "grade": _grade_for_attempt(attempt, percentage),
        "started_at": attempt.started_at,
        "submitted_at": attempt.submitted_at,
        "is_submitted": attempt.is_submitted,
        "auto_submitted": attempt.auto_submitted,
        "daily_date": attempt.daily_date,
        "due_at": _attempt_due_at(attempt),
        "question_count": attempt.questions.count(),
    }
    if include_questions:
        answer_map = {}
        if include_answers:
            answer_map = {answer.question_id: answer for answer in attempt.answers.all()}
        payload["questions"] = [
            _personal_question_payload(question, include_answers, answer_map.get(question.id))
            for question in attempt.questions.all()
        ]
    return payload


def _finalize_personal_attempt(attempt, answer_map=None, auto_submitted=False):
    if attempt.is_submitted:
        return attempt

    answer_map = answer_map or {}
    score = 0
    answer_records = []
    questions = list(attempt.questions.all())
    for question in questions:
        answer_text = str(answer_map.get(str(question.id), "")).strip()
        is_correct = _normalize_answer(answer_text) == _normalize_answer(question.correct_answer)
        earned = question.points if is_correct else 0
        score += earned
        answer_records.append(
            PersonalQuizAnswer(
                attempt=attempt,
                question=question,
                answer_text=answer_text,
                is_correct=is_correct,
                earned_points=earned,
            )
        )

    PersonalQuizAnswer.objects.bulk_create(answer_records)
    attempt.score = score
    attempt.total_points = sum(question.points for question in questions)
    attempt.percentage = _percentage(score, attempt.total_points)
    attempt.submitted_at = timezone.now()
    basis_date = attempt.daily_date or timezone.localdate(attempt.submitted_at)
    attempt.week_start = _week_start(basis_date)
    attempt.month_start = _month_start(basis_date)
    if not attempt.term_id:
        attempt.term = _term_for_date(attempt.student, basis_date)
    if not attempt.academic_year_id:
        attempt.academic_year = _year_for_date(attempt.student, basis_date, attempt.term)
    attempt.is_submitted = True
    attempt.auto_submitted = auto_submitted
    attempt.save(update_fields=["score", "total_points", "percentage", "submitted_at", "week_start", "month_start", "term", "academic_year", "is_submitted", "auto_submitted", "updated_at"])
    return attempt


def _auto_submit_if_expired(attempt):
    if not attempt or attempt.is_submitted:
        return attempt
    if timezone.now() >= _attempt_due_at(attempt):
        return _finalize_personal_attempt(attempt, {}, auto_submitted=True)
    return attempt


def _is_placeholder_personal_question(question):
    prompt = str(getattr(question, "prompt", "") or "").strip()
    normalized = prompt.casefold()
    return any(prompt.startswith(prefix) for prefix in PLACEHOLDER_PERSONAL_QUESTION_PREFIXES) or any(snippet in normalized for snippet in PLACEHOLDER_PERSONAL_QUESTION_SNIPPETS)


def _is_placeholder_prompt(prompt):
    normalized = str(prompt or "").strip().casefold()
    return any(str(prompt or "").strip().startswith(prefix) for prefix in PLACEHOLDER_PERSONAL_QUESTION_PREFIXES) or any(snippet in normalized for snippet in PLACEHOLDER_PERSONAL_QUESTION_SNIPPETS)


def _attempt_has_placeholder_questions(attempt):
    questions = list(attempt.questions.all())
    return bool(questions) and any(_is_placeholder_personal_question(question) for question in questions)


def _coerce_options(value):
    if isinstance(value, str):
        try:
            decoded = json.loads(value)
            value = decoded
        except (TypeError, ValueError):
            value = []
    if isinstance(value, dict):
        value = list(value.values())
    return [str(option).strip() for option in (value or []) if str(option).strip()]


def _resolve_exam_correct_answer(options, correct_answer):
    answer = str(correct_answer or "").strip()
    if not answer:
        return ""
    if len(answer) == 1 and answer.upper() in "ABCDEFGH":
        index = ord(answer.upper()) - ord("A")
        if 0 <= index < len(options):
            return options[index]
    for option in options:
        if _normalize_answer(option) == _normalize_answer(answer):
            return option
    return answer


def _personal_question_from_exam_question(item, order):
    prompt = str(item.text or "").strip()
    question_type = PersonalQuizQuestion.FILL_BLANK
    options = []
    if item.question_type == "mcq":
        question_type = PersonalQuizQuestion.OBJECTIVE
        options = _coerce_options(item.options)
    elif item.question_type == "true_false":
        question_type = PersonalQuizQuestion.TRUE_FALSE
        options = ["True", "False"]

    correct_answer = _resolve_exam_correct_answer(options, item.correct_answer)
    if not prompt or not correct_answer:
        return None
    if question_type == PersonalQuizQuestion.OBJECTIVE and len(options) < 2:
        return None

    return PersonalQuizQuestion(
        question_type=question_type,
        prompt=prompt,
        options=_shuffle_options(options, correct_answer),
        correct_answer=correct_answer,
        explanation=str(item.explanation or "").strip(),
        order=order,
        points=item.points or 1,
    )


def _subject_personal_quiz_terms(subject):
    values = {
        str(getattr(subject, "name", "") or "").strip(),
        str(getattr(subject, "code", "") or "").strip(),
    }
    for value in list(values):
        values.update(SUBJECT_PERSONAL_QUIZ_ALIASES.get(value.casefold(), set()))
    return {value for value in values if value}


def _inbuilt_personal_folder_filter():
    return Q(folder__tenant__slug__in=INBUILT_PERSONAL_QUIZ_TENANT_SLUGS) | Q(
        folder__tenant__slug__istartswith="icon_tutor",
        folder__name__iendswith=INBUILT_PERSONAL_QUIZ_FOLDER_SUFFIX,
    )


def _question_bank_subject_filter(subject):
    subject_terms = _subject_personal_quiz_terms(subject)
    filters = Q(question_banks__subject=subject)
    for term in subject_terms:
        filters |= Q(question_banks__subject__name__iexact=term)
        filters |= Q(question_banks__subject__code__iexact=term)
    return filters


def _build_personal_questions(subject, class_group, count, tenant=None):
    subject_terms = _subject_personal_quiz_terms(subject)
    subject_filters = Q(folder__subject=subject)
    for term in subject_terms:
        subject_filters |= Q(folder__subject__name__iexact=term)
        subject_filters |= Q(folder__subject__code__iexact=term)
        subject_filters |= Q(folder__subject__isnull=True, folder__subject_code__iexact=term)
        subject_filters |= Q(folder__subject__isnull=True, folder__subject_name__iexact=term)
        subject_filters |= Q(folder__subject__isnull=True, folder__name__iexact=f"{term}{INBUILT_PERSONAL_QUIZ_FOLDER_SUFFIX}")
        subject_filters |= Q(folder__subject__isnull=True, folder__name__icontains=term)

    available_folder_filter = Q(folder__tenant__isnull=True)
    if tenant:
        available_folder_filter |= Q(folder__tenant=tenant)
    available_folder_filter |= _inbuilt_personal_folder_filter()

    base_pool = PersonalQuizFolderQuestion.objects.filter(
        folder__is_active=True,
        is_active=True,
    ).filter(available_folder_filter)

    def class_scoped(queryset):
        if class_group:
            return queryset.filter(Q(folder__class_group=class_group) | Q(folder__class_group__isnull=True))
        return queryset.filter(folder__class_group__isnull=True)

    def add_questions(queryset, selected):
        remaining = count - len(selected)
        if remaining <= 0:
            return selected
        selected_ids = [item.id for item in selected]
        if selected_ids:
            queryset = queryset.exclude(id__in=selected_ids)
        candidates = list(class_scoped(queryset).order_by("?")[: max(remaining * 5, remaining)])
        real_questions = [item for item in candidates if not _is_placeholder_prompt(item.prompt)]
        return selected + real_questions[:remaining]

    folder_questions = []
    folder_questions = add_questions(base_pool.filter(subject_filters), folder_questions)
    folder_questions = add_questions(
        base_pool.filter(
            folder__subject__isnull=True,
            folder__subject_code="",
            folder__subject_name="",
        ),
        folder_questions,
    )

    if len(folder_questions) < count:
        folder_questions = add_questions(
            PersonalQuizFolderQuestion.objects.filter(
                folder__is_active=True,
                is_active=True,
                folder__tenant__isnull=True,
                folder__subject__isnull=True,
                folder__class_group__isnull=True,
            ),
            folder_questions,
        )

    if not folder_questions:
        folder_questions = add_questions(
            PersonalQuizFolderQuestion.objects.filter(
                folder__is_active=True,
                is_active=True,
                folder__class_group__isnull=True,
            ).filter(subject_filters),
            folder_questions,
        )

    if not folder_questions:
        remaining = count - len(folder_questions)
        selected_ids = [item.id for item in folder_questions]
        shared_pool = PersonalQuizFolderQuestion.objects.filter(
            folder__is_active=True,
            is_active=True,
        ).filter(subject_filters)
        if selected_ids:
            shared_pool = shared_pool.exclude(id__in=selected_ids)
        shared_candidates = list(shared_pool.order_by("?")[: max(remaining * 5, remaining)])
        folder_questions += [item for item in shared_candidates if not _is_placeholder_prompt(item.prompt)][:remaining]

    questions = []
    if folder_questions:
        questions = [
            PersonalQuizQuestion(
                question_type=item.question_type,
                prompt=item.prompt,
                options=_shuffle_options(item.options or [], item.correct_answer),
                correct_answer=item.correct_answer,
                explanation=item.explanation,
                order=index + 1,
                points=item.points,
            )
            for index, item in enumerate(random.sample(folder_questions, len(folder_questions)))
        ]
        if len(questions) >= count:
            return questions

    if len(questions) < count:
        # Path A: via QuestionBank — bank has both tenant and subject set
        bank_filter = _question_bank_subject_filter(subject)
        if tenant:
            bank_filter &= Q(question_banks__tenant=tenant)
        else:
            bank_filter &= Q(question_banks__tenant__isnull=True)

        # Path B: via Exam.questions M2M — question belongs to the tenant and
        # the exam it was assigned to has a matching subject.  This catches
        # questions that exist in the CBT system but aren't inside any bank.
        _eq_subject_terms = _subject_personal_quiz_terms(subject)
        exam_subject_q = Q(exams__subject=subject)
        for _term in _eq_subject_terms:
            exam_subject_q |= Q(exams__subject__name__iexact=_term)
            exam_subject_q |= Q(exams__subject__code__iexact=_term)
        if tenant:
            exam_path_filter = exam_subject_q & Q(tenant=tenant)
        else:
            exam_path_filter = exam_subject_q & Q(tenant__isnull=True)

        exam_questions = list(
            ExamQuestion.objects.filter(bank_filter | exam_path_filter)
            .exclude(text="")
            .distinct()
            .order_by("?")[: max((count - len(questions)) * 5, count - len(questions))]
        )
        for item in exam_questions:
            if _is_placeholder_prompt(item.text):
                continue
            question = _personal_question_from_exam_question(item, len(questions) + 1)
            if question:
                questions.append(question)

    return questions


def _personal_question_availability_count(subject, class_group, tenant=None):
    return len(_build_personal_questions(subject, class_group, MAX_PERSONAL_QUESTIONS, tenant))


class TeacherQuizListCreate(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        legacy_tenant = resolve_legacy_tenant_for_school(getattr(request.user, "tenant", None))
        quizzes = (
            Quiz.objects.filter(teacher=request.user)
            .prefetch_related("questions__choices", "submissions")
            .order_by("-created_at")
        )
        quizzes = quizzes.filter(tenant=legacy_tenant) if legacy_tenant else quizzes.none()
        return Response(QuizListSerializer(quizzes, many=True).data)

    def post(self, request):
        serializer = QuizSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        quiz = serializer.save()
        return Response(QuizSerializer(quiz).data, status=status.HTTP_201_CREATED)


class TeacherQuizDetail(APIView):
    permission_classes = [IsAuthenticated]

    def get_object(self, request, quiz_id):
        return get_object_or_404(Quiz, id=quiz_id, teacher=request.user)

    def get(self, request, quiz_id):
        quiz = self.get_object(request, quiz_id)
        return Response(QuizSerializer(quiz).data)

    def patch(self, request, quiz_id):
        quiz = self.get_object(request, quiz_id)
        serializer = QuizSerializer(quiz, data=request.data, partial=True, context={"request": request})
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(QuizSerializer(quiz).data)

    def delete(self, request, quiz_id):
        quiz = self.get_object(request, quiz_id)
        quiz.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class TeacherQuizSubmissions(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, quiz_id):
        quiz = get_object_or_404(Quiz, id=quiz_id, teacher=request.user)
        submissions = quiz.submissions.select_related("student").order_by("-submitted_at")
        payload = [
            {
                "id": submission.id,
                "student_id": submission.student_id,
                "student_email": getattr(submission.student, "email", ""),
                "score": submission.score,
                "total_points": submission.total_points,
                "submitted_at": submission.submitted_at,
            }
            for submission in submissions
        ]
        return Response(payload)


def _personal_quiz_folder_payload(folder):
    return {
        "id": folder.id,
        "name": folder.name,
        "description": folder.description,
        "subject_id": folder.subject_id,
        "subject": folder.subject.name if folder.subject else folder.subject_name or "",
        "subject_code": folder.subject_code or (folder.subject.code if folder.subject else ""),
        "class_group": _class_label(folder.class_group) if folder.class_group else "All classes",
        "is_global": folder.tenant_id is None,
        "question_count": folder.folder_questions.filter(is_active=True).count(),
        "questions": [
            {
                "id": q.id,
                "question_type": q.question_type,
                "prompt": q.prompt,
                "options": q.options or [],
                "correct_answer": q.correct_answer,
                "points": q.points,
            }
            for q in folder.folder_questions.filter(is_active=True).order_by("order", "id")[:100]
        ],
    }


class PersonalQuizResourceFolder(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if getattr(request.user, "role", "") not in {"school_admin", "principal", "super_admin"}:
            return Response({"detail": "Personal quiz question pools are not available to this account."}, status=status.HTTP_403_FORBIDDEN)
        legacy_tenant = resolve_legacy_tenant_for_school(getattr(request.user, "tenant", None))
        folders = PersonalQuizFolder.objects.filter(is_active=True).select_related("subject", "class_group").prefetch_related("folder_questions")
        folders = folders.filter(Q(tenant=legacy_tenant) | Q(tenant__isnull=True)) if legacy_tenant else folders.filter(tenant__isnull=True)

        subjects = []
        if legacy_tenant:
            subjects = list(
                Subject.objects.filter(tenant=legacy_tenant).order_by("name").values("id", "name", "code")
            )

        return Response({"folders": [_personal_quiz_folder_payload(f) for f in folders[:50]], "subjects": subjects})

    def post(self, request):
        if request.user.role not in {"school_admin", "principal", "super_admin"}:
            return Response({"detail": "Only school administrators can manage personal quiz folders."}, status=status.HTTP_403_FORBIDDEN)
        is_global = bool(request.data.get("is_global")) and request.user.role == "super_admin"
        if is_global:
            legacy_tenant = None
        else:
            legacy_tenant = resolve_legacy_tenant_for_school(getattr(request.user, "tenant", None))
            if not legacy_tenant:
                return Response({"detail": "Your school is not fully set up yet. Contact support."}, status=status.HTTP_400_BAD_REQUEST)

        subject = None
        subject_id = request.data.get("subject_id")
        if subject_id:
            subject = Subject.objects.filter(id=subject_id).first()

        subject_name = str(request.data.get("subject_name") or (subject.name if subject else "") or "").strip()
        subject_code = str(request.data.get("subject_code") or (subject.code if subject else "") or "").strip().upper()
        default_name = f"{subject_name or subject_code or 'General'} Personal Quiz Pool"
        name = str(request.data.get("name") or default_name).strip() or default_name

        folder = PersonalQuizFolder.objects.create(
            tenant=legacy_tenant,
            name=name,
            description=str(request.data.get("description") or "").strip(),
            subject=subject,
            subject_name=subject_name,
            subject_code=subject_code,
        )
        return Response(_personal_quiz_folder_payload(folder), status=status.HTTP_201_CREATED)


class PersonalQuizResourceFolderDetail(APIView):
    permission_classes = [IsAuthenticated]

    def _get_folder(self, request, folder_id):
        if request.user.role not in {"school_admin", "principal", "super_admin"}:
            return None, Response({"detail": "Only school administrators can manage personal quiz folders."}, status=status.HTTP_403_FORBIDDEN)
        legacy_tenant = resolve_legacy_tenant_for_school(getattr(request.user, "tenant", None))
        folder_query = PersonalQuizFolder.objects.filter(id=folder_id, is_active=True).select_related("subject", "class_group").prefetch_related("folder_questions")
        if request.user.role == "super_admin":
            folder_query = folder_query.filter(Q(tenant=legacy_tenant) | Q(tenant__isnull=True))
        elif legacy_tenant:
            folder_query = folder_query.filter(tenant=legacy_tenant)
        else:
            folder_query = folder_query.none()
        folder = folder_query.first()
        if not folder:
            return None, Response({"detail": "Folder not found."}, status=status.HTTP_404_NOT_FOUND)
        return folder, None

    def patch(self, request, folder_id):
        folder, err = self._get_folder(request, folder_id)
        if err:
            return err
        subject = folder.subject
        subject_id = request.data.get("subject_id")
        if subject_id is not None:
            subject = Subject.objects.filter(id=subject_id).first() if subject_id else None
        subject_name = str(request.data.get("subject_name") or (subject.name if subject else "") or "").strip()
        subject_code = str(request.data.get("subject_code") or (subject.code if subject else "") or "").strip().upper()
        update_fields = []
        if "name" in request.data:
            folder.name = str(request.data["name"]).strip() or folder.name
            update_fields.append("name")
        if subject_id is not None:
            folder.subject = subject
            folder.subject_name = subject_name
            folder.subject_code = subject_code
            update_fields += ["subject", "subject_name", "subject_code"]
        if update_fields:
            folder.save(update_fields=update_fields)
        return Response(_personal_quiz_folder_payload(folder))

    def delete(self, request, folder_id):
        folder, err = self._get_folder(request, folder_id)
        if err:
            return err
        folder.is_active = False
        folder.save(update_fields=["is_active"])
        return Response({"detail": "Folder deleted."}, status=status.HTTP_200_OK)


class PersonalQuizResourceQuestion(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, folder_id):
        if request.user.role not in {"school_admin", "principal", "super_admin"}:
            return Response({"detail": "Only school administrators can add personal quiz questions."}, status=status.HTTP_403_FORBIDDEN)
        legacy_tenant = resolve_legacy_tenant_for_school(getattr(request.user, "tenant", None))
        folder_query = PersonalQuizFolder.objects.filter(id=folder_id, is_active=True)
        if request.user.role == "super_admin":
            folder_query = folder_query.filter(Q(tenant=legacy_tenant) | Q(tenant__isnull=True))
        elif legacy_tenant:
            folder_query = folder_query.filter(tenant=legacy_tenant)
        else:
            folder_query = folder_query.none()
        folder = get_object_or_404(folder_query)
        prompt = str(request.data.get("prompt") or "").strip()
        correct_answer = str(request.data.get("correct_answer") or "").strip()
        if len(prompt) < 3 or not correct_answer:
            return Response({"detail": "Prompt and correct answer are required."}, status=status.HTTP_400_BAD_REQUEST)
        question = PersonalQuizFolderQuestion.objects.create(
            folder=folder,
            question_type=request.data.get("question_type") or PersonalQuizQuestion.OBJECTIVE,
            prompt=prompt,
            options=request.data.get("options") or [],
            correct_answer=correct_answer,
            explanation=str(request.data.get("explanation") or "").strip(),
            order=folder.folder_questions.count() + 1,
            points=int(request.data.get("points") or 1),
        )
        return Response({"id": question.id, "prompt": question.prompt, "question_type": question.question_type, "options": question.options or [], "correct_answer": question.correct_answer, "points": question.points}, status=status.HTTP_201_CREATED)

    def delete(self, request, folder_id, question_id):
        if request.user.role not in {"school_admin", "principal", "super_admin"}:
            return Response({"detail": "Only school administrators can delete personal quiz questions."}, status=status.HTTP_403_FORBIDDEN)
        legacy_tenant = resolve_legacy_tenant_for_school(getattr(request.user, "tenant", None))
        folder_query = PersonalQuizFolder.objects.filter(id=folder_id, is_active=True)
        if request.user.role == "super_admin":
            folder_query = folder_query.filter(Q(tenant=legacy_tenant) | Q(tenant__isnull=True))
        elif legacy_tenant:
            folder_query = folder_query.filter(tenant=legacy_tenant)
        else:
            folder_query = folder_query.none()
        folder = get_object_or_404(folder_query)
        question = get_object_or_404(PersonalQuizFolderQuestion, id=question_id, folder=folder)
        question.is_active = False
        question.save(update_fields=["is_active"])
        return Response({"detail": "Question removed."}, status=status.HTTP_200_OK)


class StudentQuizList(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        legacy_tenant = resolve_legacy_tenant_for_school(getattr(request.user, "tenant", None))
        if not legacy_tenant:
            return Response([])
        quizzes = Quiz.objects.filter(is_published=True, tenant=legacy_tenant).prefetch_related("questions__choices")
        return Response(StudentQuizSerializer(quizzes, many=True).data)


class StudentQuizDetail(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, quiz_id):
        legacy_tenant = resolve_legacy_tenant_for_school(getattr(request.user, "tenant", None))
        queryset = Quiz.objects.prefetch_related("questions__choices").filter(is_published=True)
        queryset = queryset.filter(tenant=legacy_tenant) if legacy_tenant else queryset.none()
        quiz = get_object_or_404(queryset, id=quiz_id)
        return Response(StudentQuizSerializer(quiz).data)


class StudentQuizSubmit(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, quiz_id):
        legacy_tenant = resolve_legacy_tenant_for_school(getattr(request.user, "tenant", None))
        queryset = Quiz.objects.prefetch_related("questions__choices").filter(is_published=True)
        queryset = queryset.filter(tenant=legacy_tenant) if legacy_tenant else queryset.none()
        quiz = get_object_or_404(queryset, id=quiz_id)
        serializer = SubmissionSerializer(data=request.data, context={"request": request, "quiz": quiz})
        serializer.is_valid(raise_exception=True)
        submission = serializer.save()
        return Response(SubmissionDetailSerializer(submission).data, status=status.HTTP_201_CREATED)


class StudentQuizFlagQuestion(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, quiz_id):
        legacy_tenant = resolve_legacy_tenant_for_school(getattr(request.user, "tenant", None))
        quiz_query = Quiz.objects.select_related("teacher").prefetch_related("questions__choices").filter(is_published=True)
        quiz_query = quiz_query.filter(tenant=legacy_tenant) if legacy_tenant else quiz_query.none()
        quiz = get_object_or_404(quiz_query, id=quiz_id)
        question = get_object_or_404(QuizQuestion.objects.prefetch_related("choices"), quiz=quiz, id=request.data.get("question_id"))
        reason = str(request.data.get("reason") or "").strip()
        if not reason:
            return Response({"detail": "Please describe why this question is inappropriate."}, status=status.HTTP_400_BAD_REQUEST)
        if len(reason) > 2000:
            return Response({"detail": "Report text must be 2000 characters or fewer."}, status=status.HTTP_400_BAD_REQUEST)
        if _recent_student_flag_count(student=request.user, reference_model="quizzes.Question", title=quiz.title) >= 2:
            return Response({"detail": "You can only flag 2 questions in this quiz."}, status=status.HTTP_400_BAD_REQUEST)

        choices = list(question.choices.all())
        selected_choice_id = request.data.get("answer")
        selected_answer = "Not answered"
        for choice in choices:
            if str(choice.id) == str(selected_choice_id):
                selected_answer = choice.text
                break
        correct_answer = ", ".join(choice.text for choice in choices if choice.is_correct)
        sent = _send_inappropriate_question_report(
            title=quiz.title,
            school=getattr(request.user, "tenant", None),
            school_name=getattr(getattr(request.user, "tenant", None), "name", "") or getattr(quiz.tenant, "name", ""),
            subject_name=getattr(getattr(quiz, "subject", None), "name", "") or getattr(quiz, "description", "") or "Teacher quiz",
            student=request.user,
            question_id=question.id,
            question_text=question.text,
            options=[choice.text for choice in choices],
            correct_answer=correct_answer,
            selected_answer=selected_answer,
            reason=reason,
        )
        if not sent:
            return Response({"detail": "No report recipient email is configured."}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        school = getattr(request.user, "tenant", None)
        _create_flag_notifications(
            school=school,
            admin_users=list(_admin_users_for_school(school)[:10]),
            teacher=quiz.teacher,
            title="Inappropriate question flagged",
            message=f"{request.user.get_full_name() or request.user.email} flagged a question in {quiz.title}.",
            reference_model="quizzes.Question",
        )
        return Response({"success": True, "message": "Question report sent."})


class StudentQuizResult(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, quiz_id):
        legacy_tenant = resolve_legacy_tenant_for_school(getattr(request.user, "tenant", None))
        quiz_query = Quiz.objects.all()
        quiz_query = quiz_query.filter(tenant=legacy_tenant) if legacy_tenant else quiz_query.none()
        quiz = get_object_or_404(quiz_query, id=quiz_id)
        submission = get_object_or_404(
            Submission.objects.prefetch_related("answers__question__choices", "answers__choice"),
            quiz=quiz,
            student=request.user,
        )
        return Response(SubmissionDetailSerializer(submission).data)


class PersonalQuizOptions(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if getattr(request.user, "role", "") != "student":
            return Response({"detail": "Only students can use personal quizzes."}, status=status.HTTP_403_FORBIDDEN)

        profile = _student_profile(request.user)
        subjects = list(_subject_queryset_for_student(request.user, profile))
        today = _today()
        today_attempts = {
            attempt.subject_id: _auto_submit_if_expired(attempt)
            for attempt in PersonalQuizAttempt.objects.filter(student=request.user, daily_date=today).select_related("subject", "class_group").prefetch_related("questions")
        }

        history = (
            PersonalQuizAttempt.objects.filter(student=request.user)
            .select_related("subject", "class_group")
            .prefetch_related("questions")
            .order_by("-started_at")[:8]
        )
        submitted = list(
            PersonalQuizAttempt.objects.filter(student=request.user, is_submitted=True)
            .select_related("subject", "class_group", "term", "academic_year")
            .order_by("-submitted_at")
        )
        average = 0
        if submitted:
            average = round(sum(_percentage(attempt.score, attempt.total_points) for attempt in submitted) / len(submitted), 1)
        best = max((_percentage(attempt.score, attempt.total_points) for attempt in submitted), default=0)
        completed_today = sum(1 for attempt in today_attempts.values() if attempt.is_submitted)
        metrics = _personal_quiz_metrics(request.user, submitted)
        subject_payload = []
        for subject in subjects:
            attempt = today_attempts.get(subject.id)
            available_question_count = _personal_question_availability_count(subject, profile.current_class if profile else None, _resolve_student_legacy_tenant(request.user, profile))
            status_label = "available"
            if attempt and attempt.is_submitted:
                status_label = "completed"
            elif attempt:
                status_label = "in_progress"
            elif available_question_count <= 0:
                status_label = "unavailable"
            subject_payload.append(
                {
                    "id": subject.id,
                    "name": subject.name,
                    "code": subject.code,
                    "available_question_count": available_question_count,
                    "today_status": status_label,
                    "today_attempt": _personal_attempt_payload(attempt) if attempt else None,
                }
            )

        return Response(
            {
                "class_group": {
                    "id": profile.current_class_id if profile else None,
                    "name": _class_label(profile.current_class if profile else None),
                },
                "daily_date": today,
                "daily_reset": "midnight",
                "time_limit_minutes": DAILY_PERSONAL_TIME_LIMIT_MINUTES,
                "subjects": subject_payload,
                "max_questions": MAX_PERSONAL_QUESTIONS,
                "stats": {
                    "attempts": PersonalQuizAttempt.objects.filter(student=request.user).count(),
                    "submitted": PersonalQuizAttempt.objects.filter(student=request.user, is_submitted=True).count(),
                    "average_percentage": average,
                    "best_percentage": best,
                    "streak_days": _daily_streak(submitted),
                    "weekly_streak": metrics["weekly_streak"]["current"],
                    "completed_today": completed_today,
                    "available_today": max(len(subjects) - completed_today, 0),
                    "total_subjects": len(subjects),
                },
                "metrics": metrics,
                "history": [_personal_attempt_payload(attempt) for attempt in history],
            }
        )


class PersonalQuizGenerate(APIView):
    permission_classes = [IsAuthenticated]

    @transaction.atomic
    def post(self, request):
        if getattr(request.user, "role", "") != "student":
            return Response({"detail": "Only students can generate personal quizzes."}, status=status.HTTP_403_FORBIDDEN)

        profile = _student_profile(request.user)
        if not profile or not profile.current_class_id:
            return Response({"detail": "Your student profile must have a class before a quiz can be generated."}, status=status.HTTP_400_BAD_REQUEST)

        legacy_tenant = _resolve_student_legacy_tenant(request.user, profile)
        subject_query = _subject_queryset_for_student(request.user, profile)
        subject = get_object_or_404(subject_query, id=request.data.get("subject_id"))
        today = _today()
        existing_attempt = (
            PersonalQuizAttempt.objects.filter(student=request.user, subject=subject, daily_date=today)
            .select_related("subject", "class_group")
            .prefetch_related("questions", "answers")
            .first()
        )
        if existing_attempt:
            existing_attempt = _auto_submit_if_expired(existing_attempt)
            if existing_attempt.is_submitted:
                return Response(
                    {
                        "detail": "You have already completed this subject quiz today. It will reset tomorrow.",
                        "attempt": _personal_attempt_payload(existing_attempt, include_questions=True, include_answers=True),
                    },
                    status=status.HTTP_409_CONFLICT,
                )
            if existing_attempt.questions.exists():
                if _attempt_has_placeholder_questions(existing_attempt):
                    existing_attempt.delete()
                else:
                    return Response(_personal_attempt_payload(existing_attempt, include_questions=True), status=status.HTTP_200_OK)
            else:
                existing_attempt.delete()

        try:
            question_count = int(request.data.get("question_count", MAX_PERSONAL_QUESTIONS))
        except (TypeError, ValueError):
            question_count = MAX_PERSONAL_QUESTIONS
        question_count = max(1, min(question_count, MAX_PERSONAL_QUESTIONS))

        questions = _build_personal_questions(subject, profile.current_class, question_count, legacy_tenant)
        if not questions:
            return Response(
                {
                    "detail": (
                        f"No real personal quiz questions are available for {subject.name}. "
                        "Please add questions to the Personal Quiz Folder or CBT question bank for this subject."
                    )
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        today = _today()
        attempt = PersonalQuizAttempt.objects.create(
            tenant=legacy_tenant,
            student=request.user,
            subject=subject,
            class_group=profile.current_class,
            academic_year=_year_for_date(request.user, today, _term_for_date(request.user, today)),
            term=_term_for_date(request.user, today),
            title=f"{subject.name} Daily Personal Quiz",
            time_limit_minutes=DAILY_PERSONAL_TIME_LIMIT_MINUTES,
            total_points=sum(question.points for question in questions),
            daily_date=today,
            week_start=_week_start(today),
            month_start=_month_start(today),
        )
        for question in questions:
            question.attempt = attempt
        PersonalQuizQuestion.objects.bulk_create(questions)

        attempt = PersonalQuizAttempt.objects.prefetch_related("questions").select_related("subject", "class_group").get(id=attempt.id)
        return Response(_personal_attempt_payload(attempt, include_questions=True), status=status.HTTP_201_CREATED)


class PersonalQuizSubmit(APIView):
    permission_classes = [IsAuthenticated]

    @transaction.atomic
    def post(self, request, attempt_id):
        if getattr(request.user, "role", "") != "student":
            return Response({"detail": "Only students can submit personal quizzes."}, status=status.HTTP_403_FORBIDDEN)
        attempt = get_object_or_404(
            PersonalQuizAttempt.objects.select_related("subject", "class_group").prefetch_related("questions", "answers"),
            id=attempt_id,
            student=request.user,
        )
        if attempt.is_submitted:
            return Response(_personal_attempt_payload(attempt, include_questions=True, include_answers=True))

        answers_payload = request.data.get("answers", [])
        answer_map = {str(item.get("question")): item.get("answer", "") for item in answers_payload if item.get("question")}
        _finalize_personal_attempt(attempt, answer_map, auto_submitted=bool(request.data.get("auto_submitted")))
        attempt = PersonalQuizAttempt.objects.select_related("subject", "class_group").prefetch_related("questions", "answers").get(id=attempt.id)
        return Response(_personal_attempt_payload(attempt, include_questions=True, include_answers=True), status=status.HTTP_201_CREATED)


class PersonalQuizFlagQuestion(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, attempt_id):
        if getattr(request.user, "role", "") != "student":
            return Response({"detail": "Only students can report personal quiz questions."}, status=status.HTTP_403_FORBIDDEN)
        attempt = get_object_or_404(
            PersonalQuizAttempt.objects.select_related("subject", "class_group").prefetch_related("questions"),
            id=attempt_id,
            student=request.user,
        )
        if attempt.is_submitted:
            return Response({"detail": "This quiz has already been submitted."}, status=status.HTTP_400_BAD_REQUEST)

        question_id = request.data.get("question_id")
        if not question_id:
            return Response({"detail": "Question id is required."}, status=status.HTTP_400_BAD_REQUEST)
        question = get_object_or_404(attempt.questions.all(), id=question_id)
        reason = str(request.data.get("reason") or "").strip()
        if not reason:
            return Response({"detail": "Please describe why this question is inappropriate."}, status=status.HTTP_400_BAD_REQUEST)
        if len(reason) > 2000:
            return Response({"detail": "Report text must be 2000 characters or fewer."}, status=status.HTTP_400_BAD_REQUEST)
        if _recent_student_flag_count(student=request.user, reference_model="quizzes.PersonalQuizQuestion", title=attempt.title) >= 2:
            return Response({"detail": "You can only flag 2 questions in this quiz."}, status=status.HTTP_400_BAD_REQUEST)

        return Response({"success": True, "message": "Question report sent."})


class PersonalQuizHistory(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if getattr(request.user, "role", "") != "student":
            return Response({"detail": "Only students can view personal quiz history."}, status=status.HTTP_403_FORBIDDEN)
        attempts = (
            PersonalQuizAttempt.objects.filter(student=request.user)
            .select_related("subject", "class_group", "term", "academic_year")
            .prefetch_related("questions")
            .order_by("-started_at")
        )
        submitted = attempts.filter(is_submitted=True)
        submitted_list = list(submitted)
        total_submitted = len(submitted_list)
        average = 0
        if total_submitted:
            average = round(sum(_percentage(attempt.score, attempt.total_points) for attempt in submitted_list) / total_submitted, 1)
        best = max((_percentage(attempt.score, attempt.total_points) for attempt in submitted_list), default=0)
        metrics = _personal_quiz_metrics(request.user, submitted_list)
        return Response(
            {
                "stats": {
                    "attempts": attempts.count(),
                    "submitted": total_submitted,
                    "average_percentage": average,
                    "best_percentage": best,
                    "streak_days": _daily_streak(submitted_list),
                    "weekly_streak": metrics["weekly_streak"]["current"],
                },
                "metrics": metrics,
                "history": [_personal_attempt_payload(attempt) for attempt in attempts[:20]],
            }
        )
