"""Inventory Management: physical assets, stock levels, and borrowing."""
import uuid
from decimal import Decimal

from django.conf import settings
from django.db import models
from django.utils import timezone

# Shared condition scale - used by both InventoryItem.condition and
# ItemAssignment.condition_before/condition_after so a borrowed item's
# before/after condition is directly comparable to the item's own state.
CONDITION_NEW = "new"
CONDITION_GOOD = "good"
CONDITION_FAIR = "fair"
CONDITION_DAMAGED = "damaged"
CONDITION_UNDER_REPAIR = "under_repair"
CONDITION_LOST = "lost"
CONDITION_DISPOSED = "disposed"
CONDITION_CHOICES = [
    (CONDITION_NEW, "New"),
    (CONDITION_GOOD, "Good"),
    (CONDITION_FAIR, "Fair"),
    (CONDITION_DAMAGED, "Damaged"),
    (CONDITION_UNDER_REPAIR, "Under Repair"),
    (CONDITION_LOST, "Lost"),
    (CONDITION_DISPOSED, "Disposed"),
]

DEFAULT_CATEGORIES = [
    "Furniture",
    "ICT Equipment",
    "Laboratory",
    "Library",
    "Sports",
    "Office Supplies",
    "Classroom Materials",
    "Vehicles",
]


class InventoryItem(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(
        "core.SchoolTenant", on_delete=models.CASCADE, related_name="inventory_items", null=True, blank=True,
    )
    inventory_id = models.CharField(max_length=20, unique=True, db_index=True)

    name = models.CharField(max_length=160)
    description = models.TextField(blank=True)
    category = models.CharField(max_length=80, default="Other")
    brand = models.CharField(max_length=120, blank=True)
    model_number = models.CharField(max_length=120, blank=True)
    serial_number = models.CharField(max_length=120, blank=True)
    supplier = models.CharField(max_length=160, blank=True)

    purchase_date = models.DateField(null=True, blank=True)
    purchase_price = models.DecimalField(max_digits=14, decimal_places=2, null=True, blank=True)
    current_value = models.DecimalField(max_digits=14, decimal_places=2, null=True, blank=True)

    quantity = models.PositiveIntegerField(default=1)
    reorder_level = models.PositiveIntegerField(default=1)
    unit_of_measurement = models.CharField(max_length=40, default="unit")

    warranty_period_months = models.PositiveIntegerField(null=True, blank=True)
    expected_lifespan_years = models.PositiveIntegerField(null=True, blank=True)
    storage_location = models.CharField(max_length=160, blank=True)
    assigned_department = models.CharField(max_length=120, blank=True)

    condition = models.CharField(max_length=20, choices=CONDITION_CHOICES, default=CONDITION_NEW)
    next_maintenance_date = models.DateField(null=True, blank=True)

    # Dedup markers for scheduled Celery notifications - see inventory/tasks.py.
    notified_low_stock_at = models.DateTimeField(null=True, blank=True)
    notified_warranty_expiring_at = models.DateTimeField(null=True, blank=True)
    notified_warranty_expired_at = models.DateTimeField(null=True, blank=True)
    notified_maintenance_at = models.DateTimeField(null=True, blank=True)

    is_archived = models.BooleanField(default=False)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="created_inventory_items",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["tenant", "is_archived", "created_at"]),
            models.Index(fields=["tenant", "category"]),
            models.Index(fields=["tenant", "condition"]),
        ]

    def __str__(self):
        return f"{self.inventory_id} - {self.name}"

    @property
    def quantity_borrowed(self):
        active = self.assignments.filter(status__in=[ItemAssignment.STATUS_BORROWED, ItemAssignment.STATUS_OVERDUE])
        return sum((a.quantity_assigned for a in active), 0)

    @property
    def quantity_available(self):
        return max(self.quantity - self.quantity_borrowed, 0)

    @property
    def warranty_expiry_date(self):
        if not self.purchase_date or not self.warranty_period_months:
            return None
        # Avoid a dateutil dependency for a simple month-add: walk months by
        # normalizing to (year, month) arithmetic rather than day-count math,
        # so e.g. Jan 31 + 1 month doesn't silently skip to March.
        total_months = self.purchase_date.month - 1 + self.warranty_period_months
        year = self.purchase_date.year + total_months // 12
        month = total_months % 12 + 1
        day = min(self.purchase_date.day, 28)
        return self.purchase_date.replace(year=year, month=month, day=day)

    @property
    def stock_value(self):
        unit_value = self.current_value if self.current_value is not None else (self.purchase_price or Decimal("0.00"))
        return (unit_value or Decimal("0.00")) * self.quantity

    def log(self, action, actor=None, description="", metadata=None):
        return InventoryAuditLog.objects.create(
            tenant=self.tenant, item=self, actor=actor, action=action,
            description=description[:255], metadata=metadata or {},
        )


class InventoryItemImage(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    item = models.ForeignKey(InventoryItem, on_delete=models.CASCADE, related_name="images")
    image = models.ImageField(upload_to="inventory/items/%Y/%m/")
    is_primary = models.BooleanField(default=False)
    uploaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-is_primary", "uploaded_at"]

    def __str__(self):
        return f"Image for {self.item.inventory_id}"


class StockMovement(models.Model):
    TYPE_ADD = "add"
    TYPE_REMOVE = "remove"
    TYPE_TRANSFER = "transfer"
    TYPE_ISSUE = "issue"
    TYPE_RETURN = "return"
    TYPE_DISPOSE = "dispose"
    TYPE_CHOICES = [
        (TYPE_ADD, "Stock Added"),
        (TYPE_REMOVE, "Stock Removed"),
        (TYPE_TRANSFER, "Transferred"),
        (TYPE_ISSUE, "Issued"),
        (TYPE_RETURN, "Returned"),
        (TYPE_DISPOSE, "Disposed"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(
        "core.SchoolTenant", on_delete=models.CASCADE, related_name="inventory_stock_movements", null=True, blank=True,
    )
    item = models.ForeignKey(InventoryItem, on_delete=models.CASCADE, related_name="stock_movements")
    movement_type = models.CharField(max_length=20, choices=TYPE_CHOICES)
    quantity_change = models.IntegerField(default=0)
    resulting_quantity = models.PositiveIntegerField()
    from_location = models.CharField(max_length=160, blank=True)
    to_location = models.CharField(max_length=160, blank=True)
    reason = models.TextField(blank=True)
    performed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="inventory_stock_movements",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["item", "created_at"]),
            models.Index(fields=["tenant", "movement_type", "created_at"]),
        ]

    def __str__(self):
        return f"{self.movement_type} {self.quantity_change} - {self.item.inventory_id}"


class ItemAssignment(models.Model):
    STATUS_BORROWED = "borrowed"
    STATUS_RETURNED = "returned"
    STATUS_OVERDUE = "overdue"
    STATUS_LOST = "lost"
    STATUS_CHOICES = [
        (STATUS_BORROWED, "Borrowed"),
        (STATUS_RETURNED, "Returned"),
        (STATUS_OVERDUE, "Overdue"),
        (STATUS_LOST, "Lost"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(
        "core.SchoolTenant", on_delete=models.CASCADE, related_name="inventory_assignments", null=True, blank=True,
    )
    item = models.ForeignKey(InventoryItem, on_delete=models.CASCADE, related_name="assignments")
    quantity_assigned = models.PositiveIntegerField(default=1)

    borrower_user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="inventory_borrowings",
    )
    borrower_label = models.CharField(max_length=160, blank=True)

    date_issued = models.DateField(default=timezone.localdate)
    expected_return_date = models.DateField(null=True, blank=True)
    actual_return_date = models.DateField(null=True, blank=True)

    condition_before = models.CharField(max_length=20, choices=CONDITION_CHOICES, default=CONDITION_GOOD)
    condition_after = models.CharField(max_length=20, choices=CONDITION_CHOICES, blank=True)

    assigned_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="inventory_assignments_made",
    )
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_BORROWED)
    notified_overdue_at = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["tenant", "status", "expected_return_date"]),
            models.Index(fields=["item", "status"]),
        ]

    def __str__(self):
        who = self.borrower_label or getattr(self.borrower_user, "email", "unknown")
        return f"{self.item.inventory_id} -> {who} ({self.status})"


class InventoryAuditLog(models.Model):
    """Append-only audit trail - mirrors finance.FinanceLedgerLog's convention."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(
        "core.SchoolTenant", on_delete=models.CASCADE, related_name="inventory_audit_logs", null=True, blank=True,
    )
    item = models.ForeignKey(
        InventoryItem, on_delete=models.SET_NULL, null=True, blank=True, related_name="audit_entries",
    )
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="inventory_audit_logs",
    )
    action = models.CharField(max_length=80)
    description = models.CharField(max_length=255, blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["tenant", "created_at"]),
            models.Index(fields=["item", "created_at"]),
        ]

    def save(self, *args, **kwargs):
        if self.pk and InventoryAuditLog.objects.filter(pk=self.pk).exists():
            raise ValueError("Inventory audit logs are append-only and cannot be modified.")
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValueError("Inventory audit logs are append-only and cannot be deleted.")

    def __str__(self):
        return f"InventoryAuditLog({self.action})"
