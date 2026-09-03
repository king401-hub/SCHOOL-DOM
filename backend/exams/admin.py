import csv
import io

from django.contrib import admin, messages
from django.core.exceptions import PermissionDenied
from django.shortcuts import redirect, render
from django.urls import path

from .bulk_import import clean_question_record, import_central_bank_topics
from .models import Exam, ExamAttempt, ExamPin, ExamPinUsage, ExamType, Question, QuestionBank, QuestionGroup, StudentAnswer, Topic

# Columns a bulk-upload CSV must have. One row is one MCQ; group rows under the
# same "topic" value to add several questions to that topic in one file.
QUESTION_BANK_CSV_COLUMNS = [
    "topic", "question", "option_1", "option_2", "option_3", "option_4",
    "correct_answer", "explanation", "points",
]


class PlatformAdminOnlyMixin:
    """Restricts a ModelAdmin to Django superusers specifically - independent of any other
    is_staff/is_super_admin() staff accounts (e.g. via the separate superadmin_dashboard
    group-based system). Used for the central JAMB/WAEC/NECO question bank content, which
    must be managed only by the actual SchoolDom platform administrator, never by school
    admins/teachers (who never reach /control-panel/ at all) nor by any other platform staff
    account that might exist."""

    def has_view_permission(self, request, obj=None):
        return bool(request.user and request.user.is_superuser)

    def has_add_permission(self, request):
        return bool(request.user and request.user.is_superuser)

    def has_change_permission(self, request, obj=None):
        return bool(request.user and request.user.is_superuser)

    def has_delete_permission(self, request, obj=None):
        return bool(request.user and request.user.is_superuser)

    def has_module_permission(self, request):
        return bool(request.user and request.user.is_superuser)


@admin.register(ExamType)
class ExamTypeAdmin(admin.ModelAdmin):
    list_display = ("name", "tenant", "created_at")
    list_filter = ("tenant",)
    search_fields = ("name", "tenant__name", "tenant__slug")


class TopicInline(admin.TabularInline):
    model = Topic
    extra = 0
    fields = ("name", "order")


@admin.register(Question)
class QuestionAdmin(PlatformAdminOnlyMixin, admin.ModelAdmin):
    list_display = ("id", "question_type", "topic", "group", "group_order", "points", "tenant", "created_at")
    list_filter = ("tenant", "question_type", "topic__bank__board", "group__group_type")
    search_fields = ("text", "topic__name", "group__title", "group__passage_text")
    autocomplete_fields = ("topic", "group")


@admin.register(QuestionGroup)
class QuestionGroupAdmin(admin.ModelAdmin):
    list_display = ("title", "group_type", "teacher", "tenant", "created_at")
    list_filter = ("tenant", "group_type", "created_at")
    search_fields = ("title", "passage_text", "teacher__email")


@admin.register(QuestionBank)
class QuestionBankAdmin(PlatformAdminOnlyMixin, admin.ModelAdmin):
    list_display = ("name", "board", "subject", "teacher", "is_shared", "tenant", "created_at")
    list_filter = ("tenant", "board", "is_shared", "subject")
    search_fields = ("name", "subject__name", "teacher__email")
    autocomplete_fields = ("subject", "teacher")
    filter_horizontal = ("questions",)
    inlines = [TopicInline]
    change_list_template = "admin/exams/questionbank/change_list.html"

    def get_urls(self):
        custom = [
            path("upload-csv/", self.admin_site.admin_view(self.upload_csv_view), name="exams_questionbank_upload_csv"),
        ]
        return custom + super().get_urls()

    def upload_csv_view(self, request):
        """Bulk-add questions to the central JAMB/WAEC/NECO bank from a CSV
        instead of the shell-only `import_central_bank` management command -
        both paths share the exact same import/dedup logic (see bulk_import.py)."""
        if not self.has_add_permission(request):
            raise PermissionDenied

        board_choices = QuestionBank.BOARD_CHOICES
        context = {
            **self.admin_site.each_context(request),
            "title": "Bulk upload questions",
            "opts": self.model._meta,
            "board_choices": board_choices,
            "csv_columns": QUESTION_BANK_CSV_COLUMNS,
        }

        if request.method != "POST":
            return render(request, "admin/exams/questionbank/upload_csv.html", context)

        board = str(request.POST.get("board") or "").strip().upper()
        subject_name = str(request.POST.get("subject") or "").strip()
        replace_topics = request.POST.get("replace_topics") == "on"
        upload = request.FILES.get("csv_file")

        if board not in dict(board_choices):
            messages.error(request, f"Choose a valid board ({', '.join(dict(board_choices))}).")
            return redirect(f"{self.admin_site.name}:exams_questionbank_upload_csv")
        if not subject_name:
            messages.error(request, "Subject is required.")
            return redirect(f"{self.admin_site.name}:exams_questionbank_upload_csv")
        if not upload:
            messages.error(request, "Choose a CSV file to upload.")
            return redirect(f"{self.admin_site.name}:exams_questionbank_upload_csv")

        try:
            decoded = upload.read().decode("utf-8-sig")
        except UnicodeDecodeError:
            messages.error(request, "That file isn't valid UTF-8 text. Save it as CSV UTF-8 and try again.")
            return redirect(f"{self.admin_site.name}:exams_questionbank_upload_csv")

        reader = csv.DictReader(io.StringIO(decoded))
        missing_columns = [col for col in ("topic", "question", "option_1", "option_2", "correct_answer") if col not in (reader.fieldnames or [])]
        if missing_columns:
            messages.error(request, f"CSV is missing required column(s): {', '.join(missing_columns)}.")
            return redirect(f"{self.admin_site.name}:exams_questionbank_upload_csv")

        topics_data = {}
        skipped = 0
        row_count = 0
        for row_index, row in enumerate(reader, start=2):  # header is row 1
            row_count += 1
            topic_name = str(row.get("topic") or "").strip()
            if not topic_name:
                messages.warning(request, f"Row {row_index}: skipped - no topic given.")
                skipped += 1
                continue
            options = [row.get(f"option_{n}") or "" for n in (1, 2, 3, 4)]
            raw_record = {
                "text": row.get("question"),
                "options": options,
                "correct_answer": row.get("correct_answer"),
                "explanation": row.get("explanation"),
                "points": row.get("points"),
            }
            cleaned_record, error = clean_question_record(raw_record, label=f"row {row_index}")
            if error:
                messages.warning(request, error.capitalize())
                skipped += 1
                continue
            topics_data.setdefault(topic_name, []).append(cleaned_record)

        if not row_count:
            messages.error(request, "That CSV had no data rows.")
            return redirect(f"{self.admin_site.name}:exams_questionbank_upload_csv")
        if not topics_data:
            messages.error(request, f"None of the {row_count} row(s) were usable - nothing was imported.")
            return redirect(f"{self.admin_site.name}:exams_questionbank_upload_csv")

        result = import_central_bank_topics(
            board=board, subject_name=subject_name, topics_data=topics_data, replace_topics=replace_topics,
        )
        messages.success(
            request,
            f"Imported into '{result['bank_name']}': {result['created_questions']} new question(s), "
            f"{result['reused_questions']} matched/updated, across {result['topics_total']} topic(s)"
            f"{f' ({skipped} row(s) skipped)' if skipped else ''}.",
        )
        return redirect(f"{self.admin_site.name}:exams_questionbank_changelist")


class TopicQuestionInline(admin.TabularInline):
    model = Question
    fk_name = "topic"
    extra = 1
    fields = ("text", "options", "correct_answer", "points", "explanation")


@admin.register(Topic)
class TopicAdmin(PlatformAdminOnlyMixin, admin.ModelAdmin):
    list_display = ("name", "bank", "order", "tenant")
    list_filter = ("bank__board", "tenant")
    search_fields = ("name", "bank__name")
    autocomplete_fields = ("bank",)
    inlines = [TopicQuestionInline]


@admin.register(Exam)
class ExamAdmin(admin.ModelAdmin):
    list_display = (
        "title",
        "subject",
        "class_group",
        "teacher",
        "tenant",
        "start_date",
        "end_date",
        "is_published",
    )
    list_filter = ("tenant", "is_published", "exam_type", "subject", "class_group")
    search_fields = ("title", "subject__name", "class_group__name", "teacher__email")


@admin.register(ExamAttempt)
class ExamAttemptAdmin(admin.ModelAdmin):
    list_display = ("exam", "student", "tenant", "is_completed", "is_submitted", "auto_submitted", "auto_submit_reason_display", "start_time", "end_time")
    list_filter = ("tenant", "is_completed", "is_submitted", "auto_submitted", "auto_submit_reason", "is_offline", "sync_status")
    search_fields = ("exam__title", "student__email", "student__first_name", "student__last_name", "auto_submit_reason_display")


@admin.register(ExamPin)
class ExamPinAdmin(admin.ModelAdmin):
    list_display = ("exam", "pin_preview", "usage_policy", "is_active", "expires_at", "created_by", "tenant", "created_at")
    list_filter = ("tenant", "usage_policy", "is_active", "expires_at")
    search_fields = ("exam__title", "exam__subject__name", "exam__class_group__name", "created_by__email", "pin_preview")
    readonly_fields = ("pin_digest", "pin_hash", "pin_preview", "created_at", "updated_at", "last_regenerated_at", "reset_at")


@admin.register(ExamPinUsage)
class ExamPinUsageAdmin(admin.ModelAdmin):
    list_display = ("exam", "pin", "student", "status", "message", "created_at")
    list_filter = ("tenant", "status", "created_at")
    search_fields = ("exam__title", "student__email", "message", "pin__pin_preview")
    readonly_fields = ("entered_pin_digest", "created_at", "updated_at")


@admin.register(StudentAnswer)
class StudentAnswerAdmin(admin.ModelAdmin):
    list_display = ("attempt", "question", "is_correct", "score", "tenant", "created_at")
    list_filter = ("tenant", "is_correct")
