from datetime import timedelta
from decimal import Decimal

from django.test import TestCase
from django.utils import timezone

from core.models import SchoolTenant
from finance.models import ExpenseRecord
from inventory.models import InventoryAuditLog, InventoryItem, ItemAssignment, StockMovement
from inventory.services import create_assignment, generate_inventory_id, record_stock_movement, return_assignment, sync_purchase_expense
from inventory.tasks import check_expiring_warranties, check_low_stock_levels, check_overdue_borrowed_items, check_scheduled_maintenance
from notifications.models import Notification
from users.models import User


def _make_user(school, email, role="school_admin"):
    return User.objects.create_user(
        email=email, password="Pass12345", first_name="Inv", last_name="User",
        role=role, tenant=school, is_active=True, is_verified=True,
    )


def _make_item(school, actor, **overrides):
    defaults = dict(
        tenant=school, inventory_id=generate_inventory_id(school), name="Projector",
        category="ICT Equipment", quantity=10, reorder_level=2, condition="new", created_by=actor,
    )
    defaults.update(overrides)
    return InventoryItem.objects.create(**defaults)


class InventoryIdGenerationTests(TestCase):
    def setUp(self):
        self.school = SchoolTenant.objects.create(name="Inventory School", schema_name="inventory_school", is_active=True)

    def test_generated_id_is_unique_and_prefixed(self):
        first = generate_inventory_id(self.school)
        InventoryItem.objects.create(tenant=self.school, inventory_id=first, name="Item A", quantity=1)
        second = generate_inventory_id(self.school)
        self.assertTrue(first.startswith("INV"))
        self.assertNotEqual(first, second)


class StockMovementTests(TestCase):
    def setUp(self):
        self.school = SchoolTenant.objects.create(name="Stock School", schema_name="stock_school", is_active=True)
        self.admin = _make_user(self.school, "stock.admin@school.edu")
        self.item = _make_item(self.school, self.admin, quantity=10)

    def test_add_stock_increases_quantity_and_logs_movement(self):
        record_stock_movement(self.item, StockMovement.TYPE_ADD, 5, actor=self.admin, reason="Restock")
        self.item.refresh_from_db()
        self.assertEqual(self.item.quantity, 15)
        movement = StockMovement.objects.get(item=self.item)
        self.assertEqual(movement.quantity_change, 5)
        self.assertEqual(movement.resulting_quantity, 15)
        self.assertTrue(InventoryAuditLog.objects.filter(item=self.item, action="stock_add").exists())

    def test_remove_stock_cannot_exceed_current_quantity(self):
        with self.assertRaises(ValueError):
            record_stock_movement(self.item, StockMovement.TYPE_REMOVE, 999, actor=self.admin)
        self.item.refresh_from_db()
        self.assertEqual(self.item.quantity, 10)

    def test_dispose_reduces_quantity_and_flags_condition_when_fully_disposed(self):
        record_stock_movement(self.item, StockMovement.TYPE_DISPOSE, 10, actor=self.admin, reason="Broken beyond repair")
        self.item.refresh_from_db()
        self.assertEqual(self.item.quantity, 0)
        self.assertEqual(self.item.condition, "disposed")

    def test_transfer_updates_location_without_changing_quantity(self):
        record_stock_movement(self.item, StockMovement.TYPE_TRANSFER, 3, actor=self.admin, to_location="Annex Store")
        self.item.refresh_from_db()
        self.assertEqual(self.item.quantity, 10)
        self.assertEqual(self.item.storage_location, "Annex Store")
        movement = StockMovement.objects.get(item=self.item)
        self.assertEqual(movement.quantity_change, 0)

    def test_restock_above_reorder_level_clears_low_stock_marker(self):
        self.item.notified_low_stock_at = timezone.now()
        self.item.quantity = 1
        self.item.save(update_fields=["notified_low_stock_at", "quantity"])
        record_stock_movement(self.item, StockMovement.TYPE_ADD, 10, actor=self.admin)
        self.item.refresh_from_db()
        self.assertIsNone(self.item.notified_low_stock_at)


class BorrowingTests(TestCase):
    def setUp(self):
        self.school = SchoolTenant.objects.create(name="Borrow School", schema_name="borrow_school", is_active=True)
        self.admin = _make_user(self.school, "borrow.admin@school.edu")
        self.item = _make_item(self.school, self.admin, quantity=5)

    def test_issuing_does_not_change_total_quantity_but_reduces_availability(self):
        create_assignment(self.item, 2, actor=self.admin, borrower_label="Classroom 3B")
        self.item.refresh_from_db()
        self.assertEqual(self.item.quantity, 5)
        self.assertEqual(self.item.quantity_available, 3)
        movement = StockMovement.objects.get(item=self.item, movement_type=StockMovement.TYPE_ISSUE)
        self.assertEqual(movement.quantity_change, -2)
        self.assertEqual(movement.resulting_quantity, 5)

    def test_cannot_issue_more_than_available(self):
        with self.assertRaises(ValueError):
            create_assignment(self.item, 999, actor=self.admin, borrower_label="Classroom 3B")

    def test_return_restores_availability_and_updates_condition(self):
        assignment = create_assignment(self.item, 2, actor=self.admin, borrower_label="Classroom 3B")
        return_assignment(assignment, actor=self.admin, condition_after="damaged")

        self.item.refresh_from_db()
        assignment.refresh_from_db()
        self.assertEqual(self.item.quantity, 5)
        self.assertEqual(self.item.quantity_available, 5)
        self.assertEqual(assignment.status, ItemAssignment.STATUS_RETURNED)
        self.assertEqual(assignment.condition_after, "damaged")
        self.assertEqual(self.item.condition, "damaged")
        self.assertTrue(StockMovement.objects.filter(item=self.item, movement_type=StockMovement.TYPE_RETURN).exists())

    def test_cannot_return_an_already_returned_assignment(self):
        assignment = create_assignment(self.item, 1, actor=self.admin, borrower_label="Lab 1")
        return_assignment(assignment, actor=self.admin, condition_after="good")
        with self.assertRaises(ValueError):
            return_assignment(assignment, actor=self.admin, condition_after="good")

    def test_requires_a_borrower(self):
        with self.assertRaises(ValueError):
            create_assignment(self.item, 1, actor=self.admin)


class ScheduledNotificationTaskTests(TestCase):
    def setUp(self):
        self.school = SchoolTenant.objects.create(name="Notify School", schema_name="notify_school", is_active=True)
        self.admin = _make_user(self.school, "notify.admin@school.edu")

    def test_low_stock_notifies_once(self):
        item = _make_item(self.school, self.admin, quantity=1, reorder_level=5)
        check_low_stock_levels()
        item.refresh_from_db()
        self.assertIsNotNone(item.notified_low_stock_at)
        self.assertEqual(Notification.objects.filter(user=self.admin, event_type="inventory_low_stock").count(), 1)

        # Running again should not send a second notification for the same dip.
        check_low_stock_levels()
        self.assertEqual(Notification.objects.filter(user=self.admin, event_type="inventory_low_stock").count(), 1)

    def test_warranty_expiring_and_expired_stages(self):
        today = timezone.localdate()
        # 1-month warranty starting 25 days ago lands 3-6 days in the future
        # (same day-of-month, next calendar month) regardless of which month
        # we're in - safely inside the 7-day warning window either way.
        expiring_item = _make_item(
            self.school, self.admin, name="Laptop",
            purchase_date=today - timedelta(days=25), warranty_period_months=1,
        )
        expired_item = _make_item(
            self.school, self.admin, name="Printer",
            purchase_date=today - timedelta(days=400), warranty_period_months=12,
        )
        check_expiring_warranties()
        expiring_item.refresh_from_db()
        expired_item.refresh_from_db()
        self.assertIsNotNone(expiring_item.notified_warranty_expiring_at)
        self.assertIsNotNone(expired_item.notified_warranty_expired_at)
        self.assertEqual(Notification.objects.filter(event_type="inventory_warranty_expiring").count(), 1)
        self.assertEqual(Notification.objects.filter(event_type="inventory_warranty_expired").count(), 1)

    def test_overdue_borrowed_item_is_flagged_and_notified_once(self):
        item = _make_item(self.school, self.admin, quantity=3)
        assignment = create_assignment(
            item, 1, actor=self.admin, borrower_label="Classroom 1A",
            expected_return_date=timezone.localdate() - timedelta(days=3),
        )
        check_overdue_borrowed_items()
        assignment.refresh_from_db()
        self.assertEqual(assignment.status, ItemAssignment.STATUS_OVERDUE)
        self.assertEqual(Notification.objects.filter(event_type="inventory_overdue").count(), 1)

        check_overdue_borrowed_items()
        self.assertEqual(Notification.objects.filter(event_type="inventory_overdue").count(), 1)

    def test_scheduled_maintenance_due_notifies_once(self):
        item = _make_item(self.school, self.admin, next_maintenance_date=timezone.localdate() + timedelta(days=2))
        check_scheduled_maintenance()
        item.refresh_from_db()
        self.assertIsNotNone(item.notified_maintenance_at)
        self.assertEqual(Notification.objects.filter(event_type="inventory_maintenance_due").count(), 1)


class FinanceSyncTests(TestCase):
    def setUp(self):
        self.school = SchoolTenant.objects.create(name="Finance Sync School", schema_name="finance_sync_school", is_active=True)
        self.admin = _make_user(self.school, "finance.admin@school.edu")

    def test_sync_creates_one_expense_record_even_after_repeated_edits(self):
        item = _make_item(
            self.school, self.admin, purchase_date=timezone.localdate(), purchase_price=Decimal("50000.00"),
        )
        sync_purchase_expense(item, actor=self.admin)
        item.purchase_price = Decimal("55000.00")
        item.save(update_fields=["purchase_price"])
        sync_purchase_expense(item, actor=self.admin)

        records = ExpenseRecord.objects.filter(inventory_item=item)
        self.assertEqual(records.count(), 1)
        self.assertEqual(records.first().amount, Decimal("55000.00"))
        self.assertEqual(records.first().record_type, ExpenseRecord.TYPE_INVENTORY_PURCHASE)

    def test_sync_is_a_no_op_without_purchase_price_or_date(self):
        item = _make_item(self.school, self.admin)
        result = sync_purchase_expense(item, actor=self.admin)
        self.assertIsNone(result)
        self.assertFalse(ExpenseRecord.objects.filter(inventory_item=item).exists())


class InventoryApiTests(TestCase):
    def setUp(self):
        self.school = SchoolTenant.objects.create(name="Api School", schema_name="api_school", is_active=True)
        self.admin = _make_user(self.school, "api.admin@school.edu")
        self.client.force_login(self.admin)

    def test_non_admin_role_is_forbidden(self):
        student = _make_user(self.school, "api.student@school.edu", role="student")
        self.client.force_login(student)
        response = self.client.get("/api/inventory/items/")
        self.assertEqual(response.status_code, 403)

    def test_create_and_list_item(self):
        response = self.client.post("/api/inventory/items/", {"name": "Chair", "category": "Furniture", "quantity": "20"})
        self.assertEqual(response.status_code, 201, response.content)
        item_id = response.json()["item"]["id"]

        response = self.client.get("/api/inventory/items/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.json()["items"]), 1)
        self.assertEqual(response.json()["items"][0]["id"], item_id)

    def test_archive_then_hard_delete(self):
        item = _make_item(self.school, self.admin)
        response = self.client.delete(f"/api/inventory/items/{item.id}/")
        self.assertEqual(response.status_code, 200)
        item.refresh_from_db()
        self.assertTrue(item.is_archived)

        response = self.client.delete(f"/api/inventory/items/{item.id}/", {"hard": "true"}, content_type="application/json")
        self.assertEqual(response.status_code, 200)
        self.assertFalse(InventoryItem.objects.filter(id=item.id).exists())

    def test_dashboard_reflects_low_stock_and_borrowed_counts(self):
        # quantity=3, reorder_level=5: issuing 1 leaves quantity_available=2,
        # which is >0 (not "out of stock") and <=5 (still "low stock").
        low_item = _make_item(self.school, self.admin, name="Low Stock Item", quantity=3, reorder_level=5)
        _make_item(self.school, self.admin, name="Healthy Item", quantity=50, reorder_level=5)
        create_assignment(low_item, 1, actor=self.admin, borrower_label="Room 1")

        response = self.client.get("/api/inventory/dashboard/")
        self.assertEqual(response.status_code, 200)
        stats = response.json()["stats"]
        self.assertEqual(stats["total_items"], 2)
        self.assertEqual(stats["low_stock_count"], 1)
        self.assertEqual(stats["borrowed_count"], 1)
