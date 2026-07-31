from django.contrib import admin

from .models import InventoryAuditLog, InventoryItem, InventoryItemImage, ItemAssignment, StockMovement


class InventoryItemImageInline(admin.TabularInline):
    model = InventoryItemImage
    extra = 0


@admin.register(InventoryItem)
class InventoryItemAdmin(admin.ModelAdmin):
    list_display = ["inventory_id", "name", "category", "condition", "quantity", "tenant", "is_archived", "created_at"]
    list_filter = ["category", "condition", "is_archived"]
    search_fields = ["inventory_id", "name", "serial_number", "brand"]
    readonly_fields = ["id", "inventory_id", "created_at", "updated_at"]
    inlines = [InventoryItemImageInline]


@admin.register(StockMovement)
class StockMovementAdmin(admin.ModelAdmin):
    list_display = ["item", "movement_type", "quantity_change", "resulting_quantity", "performed_by", "created_at"]
    list_filter = ["movement_type"]
    readonly_fields = ["id", "created_at"]


@admin.register(ItemAssignment)
class ItemAssignmentAdmin(admin.ModelAdmin):
    list_display = ["item", "borrower_label", "borrower_user", "status", "date_issued", "expected_return_date"]
    list_filter = ["status"]
    readonly_fields = ["id", "created_at", "updated_at"]


@admin.register(InventoryAuditLog)
class InventoryAuditLogAdmin(admin.ModelAdmin):
    list_display = ["action", "item", "actor", "created_at"]
    list_filter = ["action"]
    readonly_fields = ["id", "created_at"]
