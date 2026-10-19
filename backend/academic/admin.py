from django.contrib import admin
from django.db.models import Q
from django.utils import timezone

from exams.admin import PlatformAdminOnlyMixin

from .models import AttendanceRecord, Class, ClassResultSnapshot, LessonPlanResource, StudentClassPromotion, Subject, Term, TimetableEntry, TimetableSettings


@admin.register(AttendanceRecord)
class AttendanceRecordAdmin(admin.ModelAdmin):
    list_display = ("student", "tenant", "date", "status", "created_at")
    list_filter = ("tenant", "status", "date")
    search_fields = ("student__email", "student__first_name", "student__last_name")

    # Deleting rows here only ever touches the real server-side record - the
    # kiosk's own on-device "Today's Attendance Log" (a same-day convenience
    # cache, see AttendanceLogStore.kt) has no other way to find out, so
    # without this it kept showing names an admin had just deleted here.
    # Signalled via Device.attendance_cleared_at, picked up on the device's
    # next heartbeat (see device_fleet.views.device_heartbeat).
    @staticmethod
    def _signal_devices(tenant_ids):
        """`tenant_ids` are AttendanceRecord.tenant_id values - this model
        inherits the legacy core.models.TenantAwareModel, whose tenant FK
        targets tenants.Tenant, not core.SchoolTenant (see users.app_views.
        _tenant_for_model: tenants.Tenant is a shadow row auto-created per
        school, keyed by slug == SchoolTenant.schema_name). Device.tenant
        is the real SchoolTenant, so resolve through that slug first."""
        tenant_ids = {t for t in tenant_ids if t}
        if not tenant_ids:
            return
        from core.tenant import SchoolTenant
        from device_fleet.models import Device
        from tenants.models import Tenant
        slugs = Tenant.objects.filter(pk__in=tenant_ids).values_list("slug", flat=True)
        school_ids = list(SchoolTenant.objects.filter(schema_name__in=slugs).values_list("id", flat=True))
        if not school_ids:
            return
        Device.objects.filter(Q(tenant_id__in=school_ids) | Q(paired_tenant_id__in=school_ids)).update(
            attendance_cleared_at=timezone.now(),
        )

    def delete_queryset(self, request, queryset):
        tenant_ids = set(queryset.values_list("tenant_id", flat=True))
        super().delete_queryset(request, queryset)
        self._signal_devices(tenant_ids)

    def delete_model(self, request, obj):
        tenant_id = obj.tenant_id
        super().delete_model(request, obj)
        self._signal_devices({tenant_id})


@admin.register(LessonPlanResource)
class LessonPlanResourceAdmin(PlatformAdminOnlyMixin, admin.ModelAdmin):
    list_display = ("title", "subject", "grade_level", "tenant", "updated_at")
    list_filter = ("tenant", "subject")
    search_fields = ("title", "subject__name", "grade_level", "description")
    autocomplete_fields = ("subject",)


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


@admin.register(ClassResultSnapshot)
class ClassResultSnapshotAdmin(admin.ModelAdmin):
    list_display = ("class_group", "term", "class_size", "generated_by", "updated_at", "tenant")
    list_filter = ("tenant", "class_group", "term")
    search_fields = ("class_group__name", "term__name", "tenant__name", "tenant__slug")
    readonly_fields = ("subjects", "rows", "class_size", "generated_by", "created_at", "updated_at")


@admin.register(TimetableEntry)
class TimetableEntryAdmin(admin.ModelAdmin):
    list_display = ("class_group", "display_label", "teacher", "day_of_week", "start_time", "end_time", "room", "tenant")
    list_filter = ("tenant", "day_of_week", "class_group")
    search_fields = ("class_group__name", "subject__name", "title", "teacher__first_name", "teacher__last_name", "room")


@admin.register(TimetableSettings)
class TimetableSettingsAdmin(admin.ModelAdmin):
    list_display = ("tenant", "periods_per_day", "period_duration_minutes", "day_start_time", "school_days")
    list_filter = ("tenant",)
    search_fields = ("tenant__name", "tenant__slug")
