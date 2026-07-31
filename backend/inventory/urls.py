from django.urls import path

from inventory import views

urlpatterns = [
    path("items/", views.inventory_items, name="inventory_items"),
    path("items/<uuid:item_id>/", views.inventory_item_detail, name="inventory_item_detail"),
    path("items/<uuid:item_id>/images/<uuid:image_id>/", views.inventory_item_image_detail, name="inventory_item_image_detail"),
    path("items/<uuid:item_id>/qr/", views.inventory_item_qr, name="inventory_item_qr"),
    path("items/<uuid:item_id>/stock/", views.inventory_item_stock, name="inventory_item_stock"),
    path("movements/", views.inventory_movements, name="inventory_movements"),
    path("assignments/", views.inventory_assignments, name="inventory_assignments"),
    path("assignments/<uuid:assignment_id>/return/", views.inventory_assignment_return, name="inventory_assignment_return"),
    path("audit-log/", views.inventory_audit_log, name="inventory_audit_log"),
    path("dashboard/", views.inventory_dashboard, name="inventory_dashboard"),
]
