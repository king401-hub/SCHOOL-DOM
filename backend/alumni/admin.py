from django.contrib import admin

from .models import ArchivedStudentRecord


@admin.register(ArchivedStudentRecord)
class ArchivedStudentRecordAdmin(admin.ModelAdmin):
    list_display = ("student_id", "full_name", "last_class_name", "last_academic_year", "archive_reason", "is_sealed", "archived_at")
    list_filter = ("archive_reason", "is_sealed", "last_academic_year")
    search_fields = ("student_id", "admission_number", "full_name", "email")
    readonly_fields = tuple(field.name for field in ArchivedStudentRecord._meta.fields)

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        # Sealed records raise on delete anyway; blocking it here keeps the
        # admin from offering an action that can only fail.
        return False
