from django.contrib import admin

from .models import CBTLicense, CBTLicensePayment


@admin.register(CBTLicense)
class CBTLicenseAdmin(admin.ModelAdmin):
    list_display = ("key", "school", "status", "source", "activated_at", "expires_at")
    list_filter = ("status", "source")
    search_fields = ("key", "school__name", "school__schema_name")
    readonly_fields = ("id", "created_at", "updated_at")


@admin.register(CBTLicensePayment)
class CBTLicensePaymentAdmin(admin.ModelAdmin):
    list_display = ("reference", "school", "amount", "status", "provider", "created_at")
    list_filter = ("status", "provider")
    search_fields = ("reference", "school__name")
    readonly_fields = ("id", "created_at", "updated_at")
