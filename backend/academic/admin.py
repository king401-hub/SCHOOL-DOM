from django.contrib import admin

from .models import Class, StudentClassPromotion, Subject, Term, TimetableEntry


@admin.register(Term)
class TermAdmin(admin.ModelAdmin):
    list_display = ("name", "tenant", "start_date", "end_date", "is_active")
    list_filter = ("tenant", "is_active", "start_date", "end_date")
    search_fields = ("name", "tenant__name", "tenant__slug")


@admin.register(Subject)
class SubjectAdmin(admin.ModelAdmin):
    list_display = ("name", "code", "tenant", "created_at")
    list_filter = ("tenant",)
    search_fields = ("name", "code", "tenant__name", "tenant__slug")


@admin.register(Class)
class ClassAdmin(admin.ModelAdmin):
    list_display = ("name", "section", "tenant", "created_at")
    list_filter = ("tenant", "section")
    search_fields = ("name", "section", "tenant__name", "tenant__slug")


@admin.register(StudentClassPromotion)
class StudentClassPromotionAdmin(admin.ModelAdmin):
    list_display = ("student", "from_class", "to_class", "from_term", "to_term", "scope", "promoted_by", "created_at")
    list_filter = ("tenant", "scope", "from_class", "to_class", "from_term", "to_term")
    search_fields = (
        "student__student_id",
        "student__user__email",
        "student__user__first_name",
        "student__user__last_name",
        "batch_reference",
    )


@admin.register(TimetableEntry)
class TimetableEntryAdmin(admin.ModelAdmin):
    list_display = ("class_group", "display_label", "teacher", "day_of_week", "start_time", "end_time", "room", "tenant")
    list_filter = ("tenant", "day_of_week", "class_group")
    search_fields = ("class_group__name", "subject__name", "title", "teacher__first_name", "teacher__last_name", "room")
