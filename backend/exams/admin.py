from django.contrib import admin

from .models import Exam, ExamAttempt, ExamType, Question, QuestionBank, StudentAnswer


@admin.register(ExamType)
class ExamTypeAdmin(admin.ModelAdmin):
    list_display = ("name", "tenant", "created_at")
    list_filter = ("tenant",)
    search_fields = ("name", "tenant__name", "tenant__slug")


@admin.register(Question)
class QuestionAdmin(admin.ModelAdmin):
    list_display = ("id", "question_type", "points", "tenant", "created_at")
    list_filter = ("tenant", "question_type")
    search_fields = ("text",)


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
    list_display = ("exam", "student", "tenant", "is_completed", "is_submitted", "start_time", "end_time")
    list_filter = ("tenant", "is_completed", "is_submitted", "is_offline", "sync_status")
    search_fields = ("exam__title", "student__email")


@admin.register(StudentAnswer)
class StudentAnswerAdmin(admin.ModelAdmin):
    list_display = ("attempt", "question", "is_correct", "score", "tenant", "created_at")
    list_filter = ("tenant", "is_correct")
