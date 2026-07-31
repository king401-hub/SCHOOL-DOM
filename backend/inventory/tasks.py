"""Scheduled Inventory notifications - each mirrors the staged,
dedup-marker-driven shape of finance.tasks.process_token_allocation_expirations
so a school is notified exactly once per stage, not once per day."""
from celery import shared_task
from celery.utils.log import get_task_logger
from django.utils import timezone

from .models import InventoryItem, ItemAssignment

logger = get_task_logger(__name__)

WARRANTY_WARNING_WINDOW_DAYS = 7
MAINTENANCE_WARNING_WINDOW_DAYS = 7

ADMIN_ROLES = {"school_admin", "principal", "school_superadmin", "super_admin"}


def _admins_for(tenant):
    from users.models import User

    return list(User.objects.filter(tenant=tenant, role__in=ADMIN_ROLES, is_active=True))


def _notify(tenant, admins, title, message, event_type, action_text="View Inventory"):
    from notifications.models import Notification

    now = timezone.now()
    for admin in admins:
        try:
            Notification.objects.create(
                tenant=tenant, user=admin, title=title, message=message,
                notification_type="alert", priority=3, channel="in_app",
                event_type=event_type, action_text=action_text,
                is_delivered=True, delivered_at=now,
            )
        except Exception:
            logger.warning("Inventory notification failed for tenant=%s admin=%s", getattr(tenant, "schema_name", tenant), admin.email, exc_info=True)


@shared_task
def check_low_stock_levels():
    """Daily. Notifies once per dip below reorder_level; the marker is
    cleared automatically by services.record_stock_movement on restock."""
    notified = 0
    items = InventoryItem.objects.filter(is_archived=False, notified_low_stock_at__isnull=True).select_related("tenant")
    for item in items:
        if item.quantity_available > item.reorder_level:
            continue
        admins = _admins_for(item.tenant)
        _notify(
            item.tenant, admins,
            "Low stock alert",
            f"{item.name} ({item.inventory_id}) is low on stock: {item.quantity_available} unit(s) available (reorder level: {item.reorder_level}).",
            "inventory_low_stock",
        )
        item.notified_low_stock_at = timezone.now()
        item.save(update_fields=["notified_low_stock_at"])
        notified += 1
    logger.info("check_low_stock_levels complete: notified=%d", notified)
    return {"notified": notified}


@shared_task
def check_expiring_warranties():
    """Daily. Two stages, most-urgent first, matching
    process_token_allocation_expirations exactly: expired, then 7-day warning."""
    today = timezone.localdate()
    expired = 0
    warned = 0
    items = InventoryItem.objects.filter(
        is_archived=False, purchase_date__isnull=False, warranty_period_months__isnull=False,
    ).select_related("tenant")
    for item in items:
        expiry = item.warranty_expiry_date
        if not expiry:
            continue
        days_left = (expiry - today).days

        if days_left < 0 and not item.notified_warranty_expired_at:
            admins = _admins_for(item.tenant)
            _notify(
                item.tenant, admins, "Warranty expired",
                f"The warranty for {item.name} ({item.inventory_id}) expired on {expiry}.",
                "inventory_warranty_expired",
            )
            item.notified_warranty_expired_at = timezone.now()
            item.save(update_fields=["notified_warranty_expired_at"])
            expired += 1
        elif 0 <= days_left <= WARRANTY_WARNING_WINDOW_DAYS and not item.notified_warranty_expiring_at:
            admins = _admins_for(item.tenant)
            _notify(
                item.tenant, admins, "Warranty expiring soon",
                f"The warranty for {item.name} ({item.inventory_id}) expires on {expiry} ({days_left} day(s) left).",
                "inventory_warranty_expiring",
            )
            item.notified_warranty_expiring_at = timezone.now()
            item.save(update_fields=["notified_warranty_expiring_at"])
            warned += 1
    logger.info("check_expiring_warranties complete: expired=%d warned=%d", expired, warned)
    return {"expired": expired, "warned": warned}


@shared_task
def check_overdue_borrowed_items():
    """Daily. Flips status to overdue and notifies once."""
    today = timezone.localdate()
    flagged = 0
    assignments = ItemAssignment.objects.filter(
        status=ItemAssignment.STATUS_BORROWED, expected_return_date__lt=today,
    ).select_related("item", "item__tenant", "borrower_user")
    for assignment in assignments:
        assignment.status = ItemAssignment.STATUS_OVERDUE
        update_fields = ["status", "updated_at"]
        if not assignment.notified_overdue_at:
            who = assignment.borrower_label or getattr(assignment.borrower_user, "email", "the borrower")
            admins = _admins_for(assignment.item.tenant)
            _notify(
                assignment.item.tenant, admins, "Overdue borrowed item",
                f"{assignment.item.name} ({assignment.item.inventory_id}) issued to {who} was due {assignment.expected_return_date} and has not been returned.",
                "inventory_overdue",
            )
            assignment.notified_overdue_at = timezone.now()
            update_fields.append("notified_overdue_at")
            flagged += 1
        assignment.save(update_fields=update_fields)
    logger.info("check_overdue_borrowed_items complete: flagged=%d", flagged)
    return {"flagged": flagged}


@shared_task
def check_scheduled_maintenance():
    """Daily. Warns when next_maintenance_date is within the window or past."""
    today = timezone.localdate()
    notified = 0
    items = InventoryItem.objects.filter(
        is_archived=False, next_maintenance_date__isnull=False, notified_maintenance_at__isnull=True,
    ).select_related("tenant")
    for item in items:
        days_left = (item.next_maintenance_date - today).days
        if days_left > MAINTENANCE_WARNING_WINDOW_DAYS:
            continue
        admins = _admins_for(item.tenant)
        due_text = "is overdue for maintenance" if days_left < 0 else f"is due for maintenance on {item.next_maintenance_date}"
        _notify(
            item.tenant, admins, "Scheduled maintenance due",
            f"{item.name} ({item.inventory_id}) {due_text}.",
            "inventory_maintenance_due",
        )
        item.notified_maintenance_at = timezone.now()
        item.save(update_fields=["notified_maintenance_at"])
        notified += 1
    logger.info("check_scheduled_maintenance complete: notified=%d", notified)
    return {"notified": notified}
