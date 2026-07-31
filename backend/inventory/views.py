"""Admin-facing Inventory Management API."""
import io

import qrcode
from django.db.models import Q
from django.http import FileResponse
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .models import CONDITION_CHOICES, DEFAULT_CATEGORIES, InventoryAuditLog, InventoryItem, InventoryItemImage, ItemAssignment, StockMovement
from .serializers import InventoryAuditLogSerializer, InventoryItemImageSerializer, InventoryItemSerializer, ItemAssignmentSerializer, StockMovementSerializer
from .services import create_assignment, generate_inventory_id, record_stock_movement, return_assignment, sync_purchase_expense

ADMIN_ROLES = {"school_admin", "principal", "super_admin", "school_superadmin"}
LIST_CAP = 500


def _require_admin(request):
    if request.user.role not in ADMIN_ROLES:
        return Response({"success": False, "message": "Admin access required."}, status=status.HTTP_403_FORBIDDEN)
    return None


def _parse_decimal(value):
    if value in (None, ""):
        return None
    from decimal import Decimal, InvalidOperation

    try:
        return Decimal(str(value))
    except InvalidOperation:
        raise ValueError("Amount must be a valid number.")


@api_view(["GET", "POST"])
@permission_classes([IsAuthenticated])
def inventory_items(request):
    user = request.user
    denied = _require_admin(request)
    if denied:
        return denied

    if request.method == "GET":
        items = InventoryItem.objects.filter(tenant=user.tenant).prefetch_related("images")
        if str(request.query_params.get("include_archived", "")).lower() not in {"1", "true", "yes"}:
            items = items.filter(is_archived=False)

        inventory_id = request.query_params.get("inventory_id")
        if inventory_id:
            items = items.filter(inventory_id__icontains=inventory_id)
        category = request.query_params.get("category")
        if category:
            items = items.filter(category__iexact=category)
        department = request.query_params.get("department")
        if department:
            items = items.filter(assigned_department__icontains=department)
        supplier = request.query_params.get("supplier")
        if supplier:
            items = items.filter(supplier__icontains=supplier)
        location = request.query_params.get("location")
        if location:
            items = items.filter(storage_location__icontains=location)
        condition = request.query_params.get("condition")
        if condition:
            items = items.filter(condition=condition)
        date_from = request.query_params.get("purchase_date_from")
        if date_from:
            items = items.filter(purchase_date__gte=date_from)
        date_to = request.query_params.get("purchase_date_to")
        if date_to:
            items = items.filter(purchase_date__lte=date_to)
        search = request.query_params.get("search", "").strip()
        if search:
            items = items.filter(
                Q(name__icontains=search) | Q(inventory_id__icontains=search) | Q(serial_number__icontains=search) | Q(brand__icontains=search)
            )

        return Response(
            {
                "success": True,
                "items": InventoryItemSerializer(items[:LIST_CAP], many=True).data,
                "categories": DEFAULT_CATEGORIES,
                "conditions": CONDITION_CHOICES,
            }
        )

    data = request.data
    try:
        purchase_price = _parse_decimal(data.get("purchase_price"))
        current_value = _parse_decimal(data.get("current_value"))
    except ValueError as exc:
        return Response({"success": False, "message": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

    name = str(data.get("name") or "").strip()
    if not name:
        return Response({"success": False, "message": "Item name is required."}, status=status.HTTP_400_BAD_REQUEST)

    item = InventoryItem.objects.create(
        tenant=user.tenant,
        inventory_id=generate_inventory_id(user.tenant),
        name=name,
        description=data.get("description", ""),
        category=data.get("category") or "Other",
        brand=data.get("brand", ""),
        model_number=data.get("model_number", ""),
        serial_number=data.get("serial_number", ""),
        supplier=data.get("supplier", ""),
        purchase_date=data.get("purchase_date") or None,
        purchase_price=purchase_price,
        current_value=current_value,
        quantity=int(data.get("quantity") or 1),
        reorder_level=int(data.get("reorder_level") or 1),
        unit_of_measurement=data.get("unit_of_measurement") or "unit",
        warranty_period_months=data.get("warranty_period_months") or None,
        expected_lifespan_years=data.get("expected_lifespan_years") or None,
        storage_location=data.get("storage_location", ""),
        assigned_department=data.get("assigned_department", ""),
        condition=data.get("condition") or "new",
        next_maintenance_date=data.get("next_maintenance_date") or None,
        created_by=user,
    )
    for image in request.FILES.getlist("images"):
        InventoryItemImage.objects.create(item=item, image=image, is_primary=not item.images.exists())

    item.log("item_created", actor=user, description=f"Created item '{item.name}'.", metadata={"inventory_id": item.inventory_id})

    if str(data.get("record_finance_expense", "")).lower() in {"1", "true", "yes"}:
        sync_purchase_expense(item, actor=user)

    return Response({"success": True, "item": InventoryItemSerializer(item).data}, status=status.HTTP_201_CREATED)


@api_view(["GET", "PATCH", "DELETE"])
@permission_classes([IsAuthenticated])
def inventory_item_detail(request, item_id):
    user = request.user
    denied = _require_admin(request)
    if denied:
        return denied

    item = get_object_or_404(InventoryItem.objects.prefetch_related("images"), id=item_id, tenant=user.tenant)

    if request.method == "GET":
        return Response({"success": True, "item": InventoryItemSerializer(item).data})

    if request.method == "DELETE":
        # `hard` is read from the body, not a query param: IdempotencyMiddleware
        # fingerprints on (user, method, path, body) using request.path, which
        # excludes the query string - an archive DELETE and a hard=true DELETE
        # to the same URL would otherwise collide and the second call could
        # replay the first (archive) response within the 10s idempotency window.
        if str(request.data.get("hard", "")).lower() in {"1", "true", "yes"}:
            item.log("item_deleted", actor=user, description=f"Deleted item '{item.name}'.", metadata={"inventory_id": item.inventory_id})
            item.delete()
            return Response({"success": True, "message": "Item permanently deleted."})
        item.is_archived = True
        item.save(update_fields=["is_archived", "updated_at"])
        item.log("item_archived", actor=user, description=f"Archived item '{item.name}'.")
        return Response({"success": True, "item": InventoryItemSerializer(item).data})

    data = request.data
    try:
        purchase_price = _parse_decimal(data.get("purchase_price")) if "purchase_price" in data else item.purchase_price
        current_value = _parse_decimal(data.get("current_value")) if "current_value" in data else item.current_value
    except ValueError as exc:
        return Response({"success": False, "message": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

    # Note: `quantity` is deliberately not editable here - it only ever
    # changes via record_stock_movement (add/remove/dispose), so item.quantity
    # and StockMovement history can never drift apart.
    editable_fields = [
        "name", "description", "category", "brand", "model_number", "serial_number", "supplier",
        "purchase_date", "unit_of_measurement", "warranty_period_months",
        "expected_lifespan_years", "storage_location", "assigned_department", "condition",
        "next_maintenance_date", "reorder_level", "is_archived",
    ]
    for field in editable_fields:
        if field not in data:
            continue
        setattr(item, field, data.get(field))
    item.purchase_price = purchase_price
    item.current_value = current_value
    item.save()

    for image in request.FILES.getlist("images"):
        InventoryItemImage.objects.create(item=item, image=image, is_primary=not item.images.exists())

    item.log("item_edited", actor=user, description=f"Updated item '{item.name}'.")

    if str(data.get("record_finance_expense", "")).lower() in {"1", "true", "yes"}:
        sync_purchase_expense(item, actor=user)

    return Response({"success": True, "item": InventoryItemSerializer(item).data})


@api_view(["DELETE"])
@permission_classes([IsAuthenticated])
def inventory_item_image_detail(request, item_id, image_id):
    user = request.user
    denied = _require_admin(request)
    if denied:
        return denied
    image = get_object_or_404(InventoryItemImage, id=image_id, item_id=item_id, item__tenant=user.tenant)
    image.delete()
    return Response({"success": True})


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def inventory_item_qr(request, item_id):
    user = request.user
    denied = _require_admin(request)
    if denied:
        return denied
    item = get_object_or_404(InventoryItem, id=item_id, tenant=user.tenant)

    qr = qrcode.QRCode(error_correction=qrcode.constants.ERROR_CORRECT_M, box_size=10, border=3)
    qr.add_data(item.inventory_id)
    qr.make(fit=True)
    image = qr.make_image(fill_color="#08111f", back_color="white")
    image_io = io.BytesIO()
    image.save(image_io, "PNG")
    image_io.seek(0)
    response = FileResponse(image_io, content_type="image/png")
    response["Content-Disposition"] = f'inline; filename="{item.inventory_id}_qr.png"'
    return response


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def inventory_item_stock(request, item_id):
    user = request.user
    denied = _require_admin(request)
    if denied:
        return denied
    item = get_object_or_404(InventoryItem, id=item_id, tenant=user.tenant)

    action = request.data.get("action")
    try:
        quantity = int(request.data.get("quantity") or 0)
    except (TypeError, ValueError):
        return Response({"success": False, "message": "Quantity must be a whole number."}, status=status.HTTP_400_BAD_REQUEST)

    try:
        record_stock_movement(
            item, action, quantity, actor=user,
            to_location=request.data.get("to_location", ""),
            reason=request.data.get("reason", ""),
        )
    except ValueError as exc:
        return Response({"success": False, "message": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

    item.refresh_from_db()
    return Response({"success": True, "item": InventoryItemSerializer(item).data})


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def inventory_movements(request):
    user = request.user
    denied = _require_admin(request)
    if denied:
        return denied
    movements = StockMovement.objects.filter(tenant=user.tenant).select_related("item", "performed_by")
    item_id = request.query_params.get("item")
    if item_id:
        movements = movements.filter(item_id=item_id)
    movement_type = request.query_params.get("movement_type")
    if movement_type:
        movements = movements.filter(movement_type=movement_type)
    return Response({"success": True, "movements": StockMovementSerializer(movements[:LIST_CAP], many=True).data})


@api_view(["GET", "POST"])
@permission_classes([IsAuthenticated])
def inventory_assignments(request):
    user = request.user
    denied = _require_admin(request)
    if denied:
        return denied

    if request.method == "GET":
        assignments = ItemAssignment.objects.filter(tenant=user.tenant).select_related("item", "borrower_user", "assigned_by")
        status_filter = request.query_params.get("status")
        if status_filter:
            assignments = assignments.filter(status=status_filter)
        return Response({"success": True, "assignments": ItemAssignmentSerializer(assignments[:LIST_CAP], many=True).data})

    data = request.data
    item = get_object_or_404(InventoryItem, id=data.get("item"), tenant=user.tenant)
    borrower_user = None
    if data.get("borrower_user"):
        from users.models import User

        borrower_user = get_object_or_404(User, id=data.get("borrower_user"), tenant=user.tenant)

    try:
        quantity = int(data.get("quantity_assigned") or 1)
        assignment = create_assignment(
            item, quantity, actor=user,
            borrower_user=borrower_user,
            borrower_label=data.get("borrower_label", ""),
            expected_return_date=data.get("expected_return_date") or None,
            condition_before=data.get("condition_before", ""),
        )
    except ValueError as exc:
        return Response({"success": False, "message": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

    return Response({"success": True, "assignment": ItemAssignmentSerializer(assignment).data}, status=status.HTTP_201_CREATED)


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def inventory_assignment_return(request, assignment_id):
    user = request.user
    denied = _require_admin(request)
    if denied:
        return denied
    assignment = get_object_or_404(ItemAssignment, id=assignment_id, tenant=user.tenant)
    try:
        assignment = return_assignment(assignment, actor=user, condition_after=request.data.get("condition_after", ""))
    except ValueError as exc:
        return Response({"success": False, "message": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
    return Response({"success": True, "assignment": ItemAssignmentSerializer(assignment).data})


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def inventory_audit_log(request):
    user = request.user
    denied = _require_admin(request)
    if denied:
        return denied
    logs = InventoryAuditLog.objects.filter(tenant=user.tenant).select_related("item", "actor")
    item_id = request.query_params.get("item")
    if item_id:
        logs = logs.filter(item_id=item_id)
    return Response({"success": True, "audit_log": InventoryAuditLogSerializer(logs[:LIST_CAP], many=True).data})


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def inventory_dashboard(request):
    user = request.user
    denied = _require_admin(request)
    if denied:
        return denied

    items = InventoryItem.objects.filter(tenant=user.tenant, is_archived=False)
    total_items = items.count()
    total_stock_value = sum((item.stock_value for item in items), start=0)
    low_stock = [item for item in items if item.quantity_available <= item.reorder_level and item.quantity_available > 0]
    out_of_stock = [item for item in items if item.quantity_available == 0]
    damaged = items.filter(condition__in=["damaged", "under_repair"]).count()

    active_assignments = ItemAssignment.objects.filter(tenant=user.tenant, status__in=["borrowed", "overdue"])
    overdue_assignments = active_assignments.filter(status="overdue")

    recently_added = items.order_by("-created_at")[:8]
    recent_activity = InventoryAuditLog.objects.filter(tenant=user.tenant).select_related("item", "actor")[:15]

    return Response(
        {
            "success": True,
            "stats": {
                "total_items": total_items,
                "total_stock_value": total_stock_value,
                "low_stock_count": len(low_stock),
                "out_of_stock_count": len(out_of_stock),
                "borrowed_count": active_assignments.count(),
                "overdue_count": overdue_assignments.count(),
                "damaged_count": damaged,
            },
            "recently_added": InventoryItemSerializer(recently_added, many=True).data,
            "recent_activity": InventoryAuditLogSerializer(recent_activity, many=True).data,
            "low_stock_items": InventoryItemSerializer(low_stock[:20], many=True).data,
        }
    )
