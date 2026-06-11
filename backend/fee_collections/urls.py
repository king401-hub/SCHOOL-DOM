from django.urls import path

from fee_collections import views


urlpatterns = [
    path("school/profile/", views.school_collection_profile, name="school_collection_profile"),
    path("school/virtual-account/", views.school_virtual_account, name="school_virtual_account"),
    path("school/dashboard/", views.school_dashboard, name="school_collection_dashboard"),
    path("admin/profiles/", views.admin_collection_profiles, name="admin_collection_profiles"),
    path("admin/profiles/<uuid:profile_id>/approve/", views.approve_school_collection_profile, name="approve_school_collection_profile"),
    path("admin/dashboard/", views.admin_dashboard, name="admin_collection_dashboard"),
    path("admin/settings/", views.collection_settings, name="collection_settings"),
    path("admin/settlements/run/", views.run_settlements, name="run_settlements"),
    path("admin/settlements/<uuid:settlement_id>/retry/", views.retry_settlement, name="retry_settlement"),
    path("webhooks/flutterwave/", views.flutterwave_collection_webhook, name="flutterwave_collection_webhook"),
]
