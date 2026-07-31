"""Inventory business logic - the single choke point for every quantity
change, so item.quantity, StockMovement history, and the audit log can
never drift out of sync with each other."""
from django.db import transaction
from django.utils import timezone

from .models import CONDITION_DISPOSED, InventoryAuditLog, InventoryItem, ItemAssignment, StockMovement


def generate_inventory_id(tenant):
    from users.models import random_code_digits, school_code_letters

    school_letters = school_code_letters(tenant)
    candidate = f"INV{school_letters}{random_code_digits(4)}"
    while InventoryItem.objects.filter(inventory_id__iexact=candidate).exists():
        candidate = f"INV{school_letters}{random_code_digits(4)}"
    return candidate


def record_stock_movement(item, movement_type, quantity, actor=None, to_location="", reason="", tenant=None):
    """Handles the explicit Stock Management actions: add / remove / transfer
    / dispose. `quantity` is always given as a positive count - direction is
    implied by `movement_type`. Issuing/returning items goes through
    create_assignment/return_assignment below instead, since those don't
    change the item's total owned quantity."""
    if movement_type not in (StockMovement.TYPE_ADD, StockMovement.TYPE_REMOVE, StockMovement.TYPE_TRANSFER, StockMovement.TYPE_DISPOSE):
        raise ValueError(f"Unsupported stock movement type: {movement_type}")
    if quantity <= 0:
        raise ValueError("Quantity must be greater than zero.")

    with transaction.atomic():
        locked = InventoryItem.objects.select_for_update().get(pk=item.pk)
        from_location = locked.storage_location
        signed_change = 0
        update_fields = ["updated_at"]

        if movement_type == StockMovement.TYPE_ADD:
            locked.quantity += quantity
            signed_change = quantity
            update_fields.append("quantity")
        elif movement_type in (StockMovement.TYPE_REMOVE, StockMovement.TYPE_DISPOSE):
            if quantity > locked.quantity:
                raise ValueError(f"Cannot remove {quantity} unit(s); only {locked.quantity} currently in stock.")
            locked.quantity -= quantity
            signed_change = -quantity
            update_fields.append("quantity")
            if movement_type == StockMovement.TYPE_DISPOSE and locked.quantity == 0:
                locked.condition = CONDITION_DISPOSED
                update_fields.append("condition")
        elif movement_type == StockMovement.TYPE_TRANSFER:
            if to_location:
                locked.storage_location = to_location
                update_fields.append("storage_location")

        # A restock above the reorder level clears the low-stock marker so a
        # future dip below threshold notifies again (see inventory/tasks.py).
        if movement_type == StockMovement.TYPE_ADD and locked.notified_low_stock_at and locked.quantity_available > locked.reorder_level:
            locked.notified_low_stock_at = None
            update_fields.append("notified_low_stock_at")

        locked.save(update_fields=list(dict.fromkeys(update_fields)))

        movement = StockMovement.objects.create(
            tenant=tenant or locked.tenant,
            item=locked,
            movement_type=movement_type,
            quantity_change=signed_change,
            resulting_quantity=locked.quantity,
            from_location=from_location,
            to_location=to_location,
            reason=reason,
            performed_by=actor,
        )
        locked.log(
            f"stock_{movement_type}",
            actor=actor,
            description=reason or dict(StockMovement.TYPE_CHOICES).get(movement_type, movement_type),
            metadata={"quantity_change": signed_change, "resulting_quantity": locked.quantity},
        )
    return movement


def create_assignment(item, quantity, actor, borrower_user=None, borrower_label="", expected_return_date=None, condition_before="", tenant=None):
    if quantity <= 0:
        raise ValueError("Quantity must be greater than zero.")
    if not borrower_user and not borrower_label:
        raise ValueError("A borrower (person or department/location) is required.")

    with transaction.atomic():
        locked = InventoryItem.objects.select_for_update().get(pk=item.pk)
        available = locked.quantity_available
        if quantity > available:
            raise ValueError(f"Only {available} unit(s) of this item are currently available.")

        assignment = ItemAssignment.objects.create(
            tenant=tenant or locked.tenant,
            item=locked,
            quantity_assigned=quantity,
            borrower_user=borrower_user,
            borrower_label=borrower_label,
            expected_return_date=expected_return_date,
            condition_before=condition_before or locked.condition,
            assigned_by=actor,
        )
        who = borrower_label or getattr(borrower_user, "email", "borrower")
        StockMovement.objects.create(
            tenant=tenant or locked.tenant,
            item=locked,
            movement_type=StockMovement.TYPE_ISSUE,
            quantity_change=-quantity,
            resulting_quantity=locked.quantity,
            performed_by=actor,
            reason=f"Issued {quantity} unit(s) to {who}.",
        )
        locked.log(
            "item_issued", actor=actor, description=f"Issued {quantity} unit(s) to {who}.",
            metadata={"assignment_id": str(assignment.id), "quantity": quantity},
        )
    return assignment


def return_assignment(assignment, actor, condition_after=""):
    with transaction.atomic():
        locked_assignment = ItemAssignment.objects.select_for_update().get(pk=assignment.pk)
        if locked_assignment.status not in (ItemAssignment.STATUS_BORROWED, ItemAssignment.STATUS_OVERDUE):
            raise ValueError("This item has already been returned or is not currently borrowed.")

        locked_item = InventoryItem.objects.select_for_update().get(pk=locked_assignment.item_id)
        locked_assignment.status = ItemAssignment.STATUS_RETURNED
        locked_assignment.actual_return_date = timezone.localdate()
        locked_assignment.condition_after = condition_after or locked_item.condition
        locked_assignment.save(update_fields=["status", "actual_return_date", "condition_after", "updated_at"])

        if condition_after and condition_after != locked_item.condition:
            locked_item.condition = condition_after
            locked_item.save(update_fields=["condition", "updated_at"])

        who = locked_assignment.borrower_label or getattr(locked_assignment.borrower_user, "email", "borrower")
        StockMovement.objects.create(
            tenant=locked_item.tenant,
            item=locked_item,
            movement_type=StockMovement.TYPE_RETURN,
            quantity_change=locked_assignment.quantity_assigned,
            resulting_quantity=locked_item.quantity,
            performed_by=actor,
            reason=f"Returned {locked_assignment.quantity_assigned} unit(s) by {who}.",
        )
        locked_item.log(
            "item_returned", actor=actor, description=f"Returned {locked_assignment.quantity_assigned} unit(s) by {who}.",
            metadata={"assignment_id": str(locked_assignment.id), "condition_after": locked_assignment.condition_after},
        )
    return locked_assignment


def sync_purchase_expense(item, actor=None):
    """Opt-in Finance sync: mirrors an item's purchase onto an ExpenseRecord,
    following the exact idempotent-by-source-FK pattern already used for
    payslips (finance/views.py, admin_expense_payslip_create)."""
    from finance.models import ExpenseRecord

    if not item.purchase_price or not item.purchase_date:
        return None

    record, _created = ExpenseRecord.objects.update_or_create(
        inventory_item=item,
        defaults=dict(
            tenant=item.tenant,
            title=f"Inventory Purchase - {item.name}",
            vendor=item.supplier,
            amount=item.purchase_price,
            record_type=ExpenseRecord.TYPE_INVENTORY_PURCHASE,
            category=item.category,
            status=ExpenseRecord.STATUS_PAID,
            record_date=item.purchase_date,
            note=f"Auto-recorded from Inventory item {item.inventory_id}.",
            created_by=actor,
        ),
    )
    return record
