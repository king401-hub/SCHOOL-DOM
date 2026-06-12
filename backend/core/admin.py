from django.contrib import admin

from .models import Domain, SchoolGroup, SchoolTenant


class SchoolTenantInline(admin.TabularInline):
    model = SchoolTenant
    fields = ("name", "schema_name", "is_active", "subscription_tier")
    extra = 0
    show_change_link = True


@admin.register(SchoolGroup)
class SchoolGroupAdmin(admin.ModelAdmin):
    list_display = ("name", "owner", "school_count", "created_at")
    search_fields = ("name", "owner__email", "owner__first_name", "owner__last_name")
    raw_id_fields = ("owner",)
    readonly_fields = ("created_at", "updated_at")
    inlines = [SchoolTenantInline]

    @admin.display(description="Schools")
    def school_count(self, obj):
        return obj.schools.count()


@admin.register(SchoolTenant)
class SchoolTenantAdmin(admin.ModelAdmin):
    list_display = ("name", "schema_name", "school_group", "school_type", "is_active", "subscription_tier")
    list_filter = ("school_group", "school_type", "is_active", "subscription_tier")
    search_fields = ("name", "schema_name", "school_group__name")


@admin.register(Domain)
class DomainAdmin(admin.ModelAdmin):
    list_display = ("domain", "tenant", "is_primary", "created_at")
    list_filter = ("is_primary",)
    search_fields = ("domain", "tenant__name", "tenant__schema_name")
