"""Serializers for Inventory API responses."""
from rest_framework import serializers

from .models import InventoryAuditLog, InventoryItem, InventoryItemImage, ItemAssignment, StockMovement


def _actor_name(user):
    if not user:
        return ""
    return user.get_full_name() or user.email


class InventoryItemImageSerializer(serializers.ModelSerializer):
    class Meta:
        model = InventoryItemImage
        fields = ["id", "image", "is_primary", "uploaded_at"]


class InventoryItemSerializer(serializers.ModelSerializer):
    images = InventoryItemImageSerializer(many=True, read_only=True)
    quantity_available = serializers.IntegerField(read_only=True)
    quantity_borrowed = serializers.IntegerField(read_only=True)
    warranty_expiry_date = serializers.DateField(read_only=True)
    stock_value = serializers.DecimalField(max_digits=16, decimal_places=2, read_only=True)

    class Meta:
        model = InventoryItem
        fields = [
            "id", "inventory_id", "name", "description", "category", "brand", "model_number",
            "serial_number", "supplier", "purchase_date", "purchase_price", "current_value",
            "quantity", "quantity_available", "quantity_borrowed", "reorder_level",
            "unit_of_measurement", "warranty_period_months", "warranty_expiry_date",
            "expected_lifespan_years", "storage_location", "assigned_department", "condition",
            "next_maintenance_date", "stock_value", "is_archived", "images", "created_at", "updated_at",
        ]
        read_only_fields = ["id", "inventory_id", "created_at", "updated_at"]


class StockMovementSerializer(serializers.ModelSerializer):
    item_name = serializers.CharField(source="item.name", read_only=True)
    item_inventory_id = serializers.CharField(source="item.inventory_id", read_only=True)
    performed_by_name = serializers.SerializerMethodField()

    class Meta:
        model = StockMovement
        fields = [
            "id", "item", "item_name", "item_inventory_id", "movement_type", "quantity_change",
            "resulting_quantity", "from_location", "to_location", "reason", "performed_by_name", "created_at",
        ]

    def get_performed_by_name(self, obj):
        return _actor_name(obj.performed_by)


class ItemAssignmentSerializer(serializers.ModelSerializer):
    item_name = serializers.CharField(source="item.name", read_only=True)
    item_inventory_id = serializers.CharField(source="item.inventory_id", read_only=True)
    borrower_name = serializers.SerializerMethodField()
    assigned_by_name = serializers.SerializerMethodField()

    class Meta:
        model = ItemAssignment
        fields = [
            "id", "item", "item_name", "item_inventory_id", "quantity_assigned", "borrower_user",
            "borrower_name", "borrower_label", "date_issued", "expected_return_date",
            "actual_return_date", "condition_before", "condition_after", "assigned_by_name",
            "status", "created_at",
        ]

    def get_borrower_name(self, obj):
        return _actor_name(obj.borrower_user) or obj.borrower_label

    def get_assigned_by_name(self, obj):
        return _actor_name(obj.assigned_by)


class InventoryAuditLogSerializer(serializers.ModelSerializer):
    item_name = serializers.CharField(source="item.name", read_only=True, default="")
    item_inventory_id = serializers.CharField(source="item.inventory_id", read_only=True, default="")
    actor_name = serializers.SerializerMethodField()

    class Meta:
        model = InventoryAuditLog
        fields = ["id", "item", "item_name", "item_inventory_id", "actor_name", "action", "description", "metadata", "created_at"]

    def get_actor_name(self, obj):
        return _actor_name(obj.actor) or "System"
