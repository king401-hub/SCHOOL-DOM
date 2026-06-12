from django.urls import path

from . import views

app_name = "superadmin_dashboard"

urlpatterns = [
    path("", views.dashboard, name="dashboard"),
    path("schools/", views.schools, name="schools"),
    path("schools/<int:pk>/tokens/", views.school_token_settings, name="school_token_settings"),
    path("schools/<int:pk>/<str:action>/", views.school_action, name="school_action"),
    path("subscriptions/", views.subscriptions, name="subscriptions"),
    path("payments/", views.payments, name="payments"),
    path("virtual-accounts/", views.virtual_accounts, name="virtual_accounts"),
    path("support/", views.support_tickets, name="support_tickets"),
    path("announcements/", views.announcements, name="announcements"),
    path("users/", views.users, name="users"),
    path("super-admins/new/", views.create_super_admin, name="create_super_admin"),
    path("super-admins/<uuid:pk>/functions/", views.edit_super_admin_functions, name="edit_super_admin_functions"),
    path("audit-logs/", views.audit_logs, name="audit_logs"),
    path("settings/", views.system_settings, name="system_settings"),
    path("reports/", views.reports, name="reports"),
]
