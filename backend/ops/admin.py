from django.contrib import admin

from .models import MemberPermission, OpsUser, PermissionAuditLog, Region, RolePermission


@admin.register(Region)
class RegionAdmin(admin.ModelAdmin):
    list_display = ("name", "code", "created_at")
    search_fields = ("name", "code")


class MemberPermissionInline(admin.TabularInline):
    model = MemberPermission
    extra = 0


@admin.register(OpsUser)
class OpsUserAdmin(admin.ModelAdmin):
    list_display = ("user", "role", "region", "is_active", "reports_to")
    list_filter = ("role", "is_active", "region")
    search_fields = ("user__email", "user__first_name", "user__last_name")
    raw_id_fields = ("user", "reports_to")
    inlines = [MemberPermissionInline]


@admin.register(RolePermission)
class RolePermissionAdmin(admin.ModelAdmin):
    list_display = ("role", "module", "granted")
    list_filter = ("role", "module", "granted")


@admin.register(MemberPermission)
class MemberPermissionAdmin(admin.ModelAdmin):
    list_display = ("ops_user", "module", "granted")
    list_filter = ("module", "granted")
    raw_id_fields = ("ops_user",)


@admin.register(PermissionAuditLog)
class PermissionAuditLogAdmin(admin.ModelAdmin):
    list_display = ("created_at", "change_type", "role", "target_ops_user", "module", "old_value", "new_value", "actor")
    list_filter = ("change_type", "module")
    raw_id_fields = ("actor", "target_ops_user")
    readonly_fields = [f.name for f in PermissionAuditLog._meta.fields]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False
