from django.conf import settings
from django.core.mail import send_mail
from django.db import transaction
import random
from datetime import timedelta

from django.db.models import Q
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from academic.models import GradeScale, Subject
from notifications.models import Notification
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
DAILY_PERSONAL_TIME_LIMIT_MINUTES = 12


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


def _attempt_due_at(attempt):
    return attempt.started_at + timedelta(minutes=attempt.time_limit_minutes or DAILY_PERSONAL_TIME_LIMIT_MINUTES)


def _shuffle_options(options, correct_answer):
    normalized_correct = str(correct_answer or "").strip()
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


def _subject_queryset_for_student(user, profile=None):
    profile = profile or _student_profile(user)
    legacy_tenant = resolve_legacy_tenant_for_school(getattr(user, "tenant", None))
    subjects = Subject.objects.all().order_by("name")
    if legacy_tenant:
        subjects = subjects.filter(tenant=legacy_tenant)
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
    percentage = round((attempt.score / total) * 100, 1) if total else 0
    payload = {
        "id": attempt.id,
        "title": attempt.title,
        "subject": attempt.subject.name if attempt.subject else "",
        "subject_id": attempt.subject_id,
        "class_group": _class_label(attempt.class_group),
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
    attempt.submitted_at = timezone.now()
    attempt.is_submitted = True
    attempt.auto_submitted = auto_submitted
    attempt.save(update_fields=["score", "total_points", "submitted_at", "is_submitted", "auto_submitted", "updated_at"])
    return attempt


def _auto_submit_if_expired(attempt):
    if not attempt or attempt.is_submitted:
        return attempt
    if timezone.now() >= _attempt_due_at(attempt):
        return _finalize_personal_attempt(attempt, {}, auto_submitted=True)
    return attempt


def _build_personal_questions(subject, class_group, count, tenant=None):
    subject_filters = Q(folder__subject=subject)
    if subject.code:
        subject_filters |= Q(folder__tenant__isnull=True, folder__subject__isnull=True, folder__subject_code__iexact=subject.code)
    subject_filters |= Q(folder__tenant__isnull=True, folder__subject__isnull=True, folder__subject_name__iexact=subject.name)
    subject_pool = PersonalQuizFolderQuestion.objects.filter(
        folder__is_active=True,
        is_active=True,
    ).filter(subject_filters)
    if tenant:
        subject_pool = subject_pool.filter(Q(folder__tenant=tenant) | Q(folder__tenant__isnull=True))
    if class_group:
        subject_pool = subject_pool.filter(Q(folder__class_group=class_group) | Q(folder__class_group__isnull=True))
    else:
        subject_pool = subject_pool.filter(folder__class_group__isnull=True)
    folder_questions = list(subject_pool.order_by("?")[:count])
    if not folder_questions:
        folder_questions = list(
            PersonalQuizFolderQuestion.objects.filter(
                folder__is_active=True,
                is_active=True,
                folder__subject__isnull=True,
            ).order_by("?")[:count]
        )
    if folder_questions:
        return [
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

    subject_name = subject.name
    subject_code = subject.code or subject.name[:3].upper()
    class_name = _class_label(class_group)
    distractors = [class_name, "General Studies", "SchoolDom", subject_code]

    templates = [
        (
            PersonalQuizQuestion.OBJECTIVE,
            f"Which subject is this personal quiz focused on?",
            [subject_name, *[item for item in distractors if item != subject_name]][:4],
            subject_name,
            f"This quiz was generated from your selected subject, {subject_name}.",
        ),
        (
            PersonalQuizQuestion.TRUE_FALSE,
            f"This quiz was generated for {class_name}.",
            ["True", "False"],
            "True",
            "Personal quizzes use the class on your student profile.",
        ),
        (
            PersonalQuizQuestion.FILL_BLANK,
            "Fill in the blank: The selected subject is ____.",
            [],
            subject_name,
            f"The selected subject is {subject_name}.",
        ),
        (
            PersonalQuizQuestion.OBJECTIVE,
            f"Which class is attached to this quiz attempt?",
            [class_name, subject_name, "Admin Office", "All Classes"],
            class_name,
            "The attempt is generated from the class assigned to your profile.",
        ),
        (
            PersonalQuizQuestion.TRUE_FALSE,
            "Students can create the questions in a personal quiz.",
            ["True", "False"],
            "False",
            "Personal quiz questions are generated automatically by the system.",
        ),
        (
            PersonalQuizQuestion.FILL_BLANK,
            f"The code for {subject_name} is ____.",
            [],
            subject_code,
            f"{subject_name} is stored with the code {subject_code}.",
        ),
        (
            PersonalQuizQuestion.OBJECTIVE,
            "What is the maximum number of questions allowed in a personal quiz?",
            ["10", "20", "30", "50"],
            "20",
            "SchoolDom limits generated personal quizzes to 20 questions.",
        ),
        (
            PersonalQuizQuestion.TRUE_FALSE,
            "Your quiz score is calculated instantly after submission.",
            ["True", "False"],
            "True",
            "The system scores objective, true or false, and fill-in-the-blank answers immediately.",
        ),
    ]

    questions = []
    for index in range(count):
        question_type, prompt, options, correct_answer, explanation = templates[index % len(templates)]
        cycle = (index // len(templates)) + 1
        suffix = f" ({cycle})" if cycle > 1 else ""
        questions.append(
            PersonalQuizQuestion(
                question_type=question_type,
                prompt=f"{prompt}{suffix}",
                options=_shuffle_options(options, correct_answer),
                correct_answer=correct_answer,
                explanation=explanation,
                order=index + 1,
                points=1,
            )
        )
    return questions


class TeacherQuizListCreate(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        legacy_tenant = resolve_legacy_tenant_for_school(getattr(request.user, "tenant", None))
        quizzes = (
            Quiz.objects.filter(teacher=request.user)
            .prefetch_related("questions__choices", "submissions")
            .order_by("-created_at")
        )
        if legacy_tenant:
            quizzes = quizzes.filter(tenant=legacy_tenant)
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


class PersonalQuizResourceFolder(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if getattr(request.user, "role", "") not in {"school_admin", "principal", "super_admin"}:
            return Response({"detail": "Personal quiz question pools are not available to this account."}, status=status.HTTP_403_FORBIDDEN)
        legacy_tenant = resolve_legacy_tenant_for_school(getattr(request.user, "tenant", None))
        folders = PersonalQuizFolder.objects.filter(is_active=True).prefetch_related("folder_questions")
        if legacy_tenant:
            folders = folders.filter(Q(tenant=legacy_tenant) | Q(tenant__isnull=True))
        payload = [
            {
                "id": folder.id,
                "name": folder.name,
                "description": folder.description,
                "subject": folder.subject.name if folder.subject else folder.subject_name or "All subjects",
                "class_group": _class_label(folder.class_group) if folder.class_group else "All classes",
                "question_count": folder.folder_questions.filter(is_active=True).count(),
                "questions": [
                    {
                        "id": question.id,
                        "question_type": question.question_type,
                        "prompt": question.prompt,
                        "options": question.options or [],
                        "points": question.points,
                    }
                    for question in folder.folder_questions.filter(is_active=True)[:50]
                ],
            }
            for folder in folders[:20]
        ]
        return Response({"folders": payload})

    def post(self, request):
        if request.user.role not in {"school_admin", "principal", "super_admin"}:
            return Response({"detail": "Only school administrators can manage personal quiz folders."}, status=status.HTTP_403_FORBIDDEN)
        legacy_tenant = resolve_legacy_tenant_for_school(getattr(request.user, "tenant", None))
        folder = PersonalQuizFolder.objects.create(
            tenant=legacy_tenant,
            name=str(request.data.get("name") or "Personal Quiz Questions").strip(),
            description=str(request.data.get("description") or "").strip(),
        )
        return Response({"id": folder.id, "name": folder.name, "description": folder.description, "question_count": 0}, status=status.HTTP_201_CREATED)


class PersonalQuizResourceQuestion(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, folder_id):
        if request.user.role not in {"school_admin", "principal", "super_admin"}:
            return Response({"detail": "Only school administrators can add personal quiz questions."}, status=status.HTTP_403_FORBIDDEN)
        folder = get_object_or_404(PersonalQuizFolder, id=folder_id, is_active=True)
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
        return Response({"id": question.id, "prompt": question.prompt, "question_type": question.question_type}, status=status.HTTP_201_CREATED)


class StudentQuizList(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        legacy_tenant = resolve_legacy_tenant_for_school(getattr(request.user, "tenant", None))
        quizzes = Quiz.objects.filter(is_published=True)
        if legacy_tenant:
            quizzes = quizzes.filter(tenant=legacy_tenant)
        quizzes = quizzes.prefetch_related("questions__choices")
        return Response(StudentQuizSerializer(quizzes, many=True).data)


class StudentQuizDetail(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, quiz_id):
        legacy_tenant = resolve_legacy_tenant_for_school(getattr(request.user, "tenant", None))
        queryset = Quiz.objects.prefetch_related("questions__choices").filter(is_published=True)
        if legacy_tenant:
            queryset = queryset.filter(tenant=legacy_tenant)
        quiz = get_object_or_404(queryset, id=quiz_id)
        return Response(StudentQuizSerializer(quiz).data)


class StudentQuizSubmit(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, quiz_id):
        legacy_tenant = resolve_legacy_tenant_for_school(getattr(request.user, "tenant", None))
        queryset = Quiz.objects.prefetch_related("questions__choices").filter(is_published=True)
        if legacy_tenant:
            queryset = queryset.filter(tenant=legacy_tenant)
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
        if legacy_tenant:
            quiz_query = quiz_query.filter(tenant=legacy_tenant)
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
        if legacy_tenant:
            quiz_query = quiz_query.filter(tenant=legacy_tenant)
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
        submitted = list(PersonalQuizAttempt.objects.filter(student=request.user, is_submitted=True).order_by("-submitted_at"))
        average = 0
        if submitted:
            average = round(sum(attempt.score / max(attempt.total_points, 1) for attempt in submitted) * 100 / len(submitted), 1)
        best = max((round((attempt.score / max(attempt.total_points, 1)) * 100, 1) for attempt in submitted), default=0)
        completed_today = sum(1 for attempt in today_attempts.values() if attempt.is_submitted)
        subject_payload = []
        for subject in subjects:
            attempt = today_attempts.get(subject.id)
            status_label = "available"
            if attempt and attempt.is_submitted:
                status_label = "completed"
            elif attempt:
                status_label = "in_progress"
            subject_payload.append(
                {
                    "id": subject.id,
                    "name": subject.name,
                    "code": subject.code,
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
                    "completed_today": completed_today,
                    "available_today": max(len(subjects) - completed_today, 0),
                    "total_subjects": len(subjects),
                },
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

        legacy_tenant = resolve_legacy_tenant_for_school(getattr(request.user, "tenant", None))
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
            return Response(_personal_attempt_payload(existing_attempt, include_questions=True), status=status.HTTP_200_OK)

        try:
            question_count = int(request.data.get("question_count", MAX_PERSONAL_QUESTIONS))
        except (TypeError, ValueError):
            question_count = MAX_PERSONAL_QUESTIONS
        question_count = max(1, min(question_count, MAX_PERSONAL_QUESTIONS))

        attempt = PersonalQuizAttempt.objects.create(
            tenant=legacy_tenant,
            student=request.user,
            subject=subject,
            class_group=profile.current_class,
            title=f"{subject.name} Daily Personal Quiz",
            time_limit_minutes=DAILY_PERSONAL_TIME_LIMIT_MINUTES,
            total_points=question_count,
            daily_date=today,
        )
        questions = _build_personal_questions(subject, profile.current_class, question_count, legacy_tenant)
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

        question = get_object_or_404(attempt.questions.all(), id=request.data.get("question_id"))
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
            .select_related("subject", "class_group")
            .prefetch_related("questions")
            .order_by("-started_at")
        )
        submitted = attempts.filter(is_submitted=True)
        total_submitted = submitted.count()
        average = 0
        if total_submitted:
            average = round(sum(attempt.score / max(attempt.total_points, 1) for attempt in submitted) * 100 / total_submitted, 1)
        best = max((round((attempt.score / max(attempt.total_points, 1)) * 100, 1) for attempt in submitted), default=0)
        return Response(
            {
                "stats": {
                    "attempts": attempts.count(),
                    "submitted": total_submitted,
                    "average_percentage": average,
                    "best_percentage": best,
                    "streak_days": _daily_streak(list(submitted)),
                },
                "history": [_personal_attempt_payload(attempt) for attempt in attempts[:20]],
            }
        )
