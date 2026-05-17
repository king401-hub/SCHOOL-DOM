from django.contrib import admin

from .models import Exam, ExamAttempt, ExamPin, ExamPinUsage, ExamType, Question, QuestionBank, QuestionGroup, StudentAnswer


@admin.register(ExamType)
class ExamTypeAdmin(admin.ModelAdmin):
    list_display = ("name", "tenant", "created_at")
    list_filter = ("tenant",)
    search_fields = ("name", "tenant__name", "tenant__slug")


@admin.register(Question)
class QuestionAdmin(admin.ModelAdmin):
    list_display = ("id", "question_type", "group", "group_order", "points", "tenant", "created_at")
    list_filter = ("tenant", "question_type", "group__group_type")
    search_fields = ("text", "group__title", "group__passage_text")


@admin.register(QuestionGroup)
class QuestionGroupAdmin(admin.ModelAdmin):
    list_display = ("title", "group_type", "teacher", "tenant", "created_at")
    list_filter = ("tenant", "group_type", "created_at")
    search_fields = ("title", "passage_text", "teacher__email")


@admin.register(QuestionBank)
class QuestionBankAdmin(admin.ModelAdmin):
    list_display = ("name", "subject", "teacher", "is_shared", "tenant", "created_at")
    list_filter = ("tenant", "is_shared", "subject")
    search_fields = ("name", "subject__name", "teacher__email")
    filter_horizontal = ("questions",)


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
