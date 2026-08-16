from django.contrib import admin

from .models import Exam, ExamAttempt, ExamPin, ExamPinUsage, ExamType, Question, QuestionBank, QuestionGroup, StudentAnswer, Topic


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
