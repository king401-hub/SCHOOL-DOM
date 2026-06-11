from django.contrib import admin

from fee_collections.models import (
    CollectionAuditLog,
    CollectionConfig,
    FeePayment,
    SchoolCollectionProfile,
    SchoolSettlement,
    SchoolVirtualAccount,
)


@admin.register(CollectionConfig)
class CollectionConfigAdmin(admin.ModelAdmin):
    list_display = ("commission_type", "commission_value", "settlement_frequency", "auto_settlement_enabled", "updated_at")


@admin.register(SchoolCollectionProfile)
class SchoolCollectionProfileAdmin(admin.ModelAdmin):
    list_display = ("school", "status", "bank_name", "account_number", "approved_at")
    list_filter = ("status", "bank_name")
    search_fields = ("school__name", "school__schema_name", "account_number", "account_name")


@admin.register(SchoolVirtualAccount)
class SchoolVirtualAccountAdmin(admin.ModelAdmin):
    list_display = ("school", "account_number", "bank_name", "status", "provider_reference")
    list_filter = ("status", "provider")
    search_fields = ("school__name", "account_number", "provider_reference")
    readonly_fields = ("raw_response", "created_at", "updated_at")


@admin.register(FeePayment)
class FeePaymentAdmin(admin.ModelAdmin):
    list_display = ("provider_reference", "school", "gross_amount", "platform_fee", "net_amount", "status", "paid_at")
    list_filter = ("status", "currency", "paid_at")
    search_fields = ("provider_reference", "session_id", "school__name", "narration", "payer_name")
    readonly_fields = ("raw_payload", "created_at")


@admin.register(SchoolSettlement)
class SchoolSettlementAdmin(admin.ModelAdmin):
    list_display = ("transfer_reference", "school", "net_amount", "status", "scheduled_for", "settled_at")
    list_filter = ("status", "scheduled_for")
    search_fields = ("transfer_reference", "provider_transfer_id", "school__name")
    readonly_fields = ("raw_response", "created_at", "updated_at")


@admin.register(CollectionAuditLog)
class CollectionAuditLogAdmin(admin.ModelAdmin):
    list_display = ("created_at", "school", "action", "reference", "actor")
    list_filter = ("action", "created_at")
    search_fields = ("school__name", "action", "reference", "message")
    readonly_fields = ("school", "actor", "action", "reference", "message", "metadata", "created_at")

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
