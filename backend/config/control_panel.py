"""A second, friendlier admin site that mirrors django.contrib.admin.

Every model already registered on the default ``admin.site`` is mirrored here
using its existing ModelAdmin class untouched. Any project model that isn't
registered anywhere yet gets a sensible auto-generated ModelAdmin (search,
filters, readonly handling for sensitive fields) so it's reachable too. The
default ``/admin/`` site is never modified by this module.
"""
import logging

from django.apps import apps
from django.contrib import admin, messages
from django.contrib.admin.sites import AdminSite
from django.core.exceptions import PermissionDenied
from django.http import Http404
from django.shortcuts import redirect, render
from django.urls import path, reverse
from django.utils.html import format_html

logger = logging.getLogger("control_panel")

# Third-party / framework apps we never want to dump raw model admin for.
_THIRD_PARTY_APP_LABELS = {
    "rest_framework",
    "corsheaders",
    "django_filters",
    "django_otp",
    "otp_email",
    "django_htmx",
    "django_tenants",
}

_SENSITIVE_FIELD_HINTS = ("password", "secret", "token", "otp", "pin", "api_key", "private_key")

_DISPLAYABLE_TYPES = {
    "CharField", "EmailField", "SlugField", "IntegerField", "PositiveIntegerField",
    "PositiveSmallIntegerField", "SmallIntegerField", "BigIntegerField", "DecimalField",
    "FloatField", "BooleanField", "DateField", "DateTimeField", "ForeignKey",
    "AutoField", "BigAutoField", "UUIDField",
}
_SEARCHABLE_TYPES = {"CharField", "EmailField", "SlugField"}
_FILTERABLE_TYPES = {"BooleanField", "DateField", "DateTimeField", "ForeignKey"}
_SKIP_DISPLAY_TYPES = {"TextField", "JSONField", "BinaryField", "FileField", "ImageField"}

APP_LABEL_NAMES = {
    "core": "Schools & Tenants",
    "settings_app": "Platform Settings",
    "tenants": "Legacy Tenants",
    "users": "Users & Accounts",
    "schools": "Schools",
    "academic": "Academics",
    "exams": "Exams & CBT",
    "notifications": "Notifications",
    "finance": "Finance",
    "fee_collections": "Fee Collections",
    "hr": "HR & Payroll",
    "quizzes": "Quizzes",
    "analytics": "Analytics",
    "attendance": "Attendance",
    "ai_chat": "AI Chat",
    "ai_secretary": "AI Secretary",
    "superadmin_dashboard": "Platform Admin",
}


def _money(value):
    if value is None:
        return "—"
    return f"₦{value:,.0f}"


def _dashboard_metrics():
    """Best-effort revenue/usage snapshot for the current schema. Each metric is
    isolated in its own try/except so a missing or unmigrated model never takes
    down the dashboard - it just shows "—" for that card."""
    from decimal import Decimal

    from django.db.models import Sum
    from django.utils import timezone

    metrics = {}

    try:
        from core.tenant import SchoolTenant
        total = SchoolTenant.objects.count()
        active = SchoolTenant.objects.filter(is_active=True).count()
        metrics["schools_total"] = total
        metrics["schools_active"] = active
        metrics["schools_suspended"] = total - active
    except Exception:
        metrics["schools_total"] = metrics["schools_active"] = metrics["schools_suspended"] = "—"

    try:
        from users.app_views import KIDS_MONITOR_PRICE
        from users.models import KidsMonitorSubscription
        active = KidsMonitorSubscription.objects.filter(is_active=True).count()
        metrics["kids_monitor_active"] = active
        metrics["kids_monitor_mrr"] = _money(active * KIDS_MONITOR_PRICE)
    except Exception:
        metrics["kids_monitor_active"] = "—"
        metrics["kids_monitor_mrr"] = "—"

    since_30d = timezone.now() - timezone.timedelta(days=30)

    try:
        from finance.models import ActivationCreditTransaction
        qs = ActivationCreditTransaction.objects.filter(tx_type="purchase", status="successful")
        metrics["tokens_revenue_total"] = _money(qs.aggregate(s=Sum("amount"))["s"] or Decimal("0"))
        metrics["tokens_revenue_30d"] = _money(qs.filter(created_at__gte=since_30d).aggregate(s=Sum("amount"))["s"] or Decimal("0"))
        metrics["tokens_credits_sold"] = qs.aggregate(s=Sum("credits"))["s"] or 0
    except Exception:
        metrics["tokens_revenue_total"] = metrics["tokens_revenue_30d"] = "—"
        metrics["tokens_credits_sold"] = "—"

    try:
        from finance.models import SmsWalletTransaction
        qs = SmsWalletTransaction.objects.filter(tx_type="purchase", status="successful")
        metrics["sms_revenue_total"] = _money(qs.aggregate(s=Sum("amount"))["s"] or Decimal("0"))
        metrics["sms_revenue_30d"] = _money(qs.filter(created_at__gte=since_30d).aggregate(s=Sum("amount"))["s"] or Decimal("0"))
        metrics["sms_credits_sold"] = qs.aggregate(s=Sum("credits"))["s"] or 0
    except Exception:
        metrics["sms_revenue_total"] = metrics["sms_revenue_30d"] = "—"
        metrics["sms_credits_sold"] = "—"

    return metrics


class ControlPanelSite(AdminSite):
    site_header = "Schooldom Control Panel"
    site_title = "Schooldom Control Panel"
    index_title = "Platform Control Panel"
    index_template = "admin/control_panel_index.html"
    app_index_template = "admin/control_panel_app_index.html"

    def get_app_list(self, request, app_label=None):
        app_list = super().get_app_list(request, app_label=app_label)
        for app in app_list:
            app["name"] = APP_LABEL_NAMES.get(app["app_label"], app["name"])
        return sorted(app_list, key=lambda a: a["name"].lower())

    def index(self, request, extra_context=None):
        context = {**(extra_context or {}), **_dashboard_metrics()}
        return super().index(request, extra_context=context)


control_panel = ControlPanelSite(name="control_panel")


class ControlPanelSchoolTenantAdmin(admin.ModelAdmin):
    """Adds suspend/reactivate/delete controls on top of core.admin's SchoolTenantAdmin."""

    list_display = ("name", "schema_name", "school_group", "school_type", "status_badge", "subscription_tier", "row_actions")
    list_filter = ("school_group", "school_type", "is_active", "subscription_tier")
    search_fields = ("name", "schema_name", "school_group__name")
    actions = ["suspend_schools", "activate_schools"]

    @admin.display(description="Status")
    def status_badge(self, obj):
        if obj.is_active:
            return format_html('<span class="cp-pill cp-pill-ok">Active</span>')
        return format_html('<span class="cp-pill cp-pill-danger">Suspended</span>')

    @admin.display(description="Quick actions")
    def row_actions(self, obj):
        ns = self.admin_site.name
        delete_url = reverse(f"{ns}:core_schooltenant_delete", args=[obj.pk])
        if obj.is_active:
            toggle_url = reverse(f"{ns}:core_schooltenant_suspend", args=[obj.pk])
            toggle = format_html('<a class="cp-row-btn cp-row-btn-warn" href="{}">Suspend</a>', toggle_url)
        else:
            toggle_url = reverse(f"{ns}:core_schooltenant_activate", args=[obj.pk])
            toggle = format_html('<a class="cp-row-btn cp-row-btn-ok" href="{}">Activate</a>', toggle_url)
        delete_btn = format_html('<a class="cp-row-btn cp-row-btn-danger" href="{}">Delete</a>', delete_url)
        return format_html('<div class="cp-row-actions">{}{}</div>', toggle, delete_btn)

    @admin.action(description="Suspend selected schools")
    def suspend_schools(self, request, queryset):
        count = queryset.update(is_active=False)
        self.message_user(request, f"Suspended {count} school(s).", messages.SUCCESS)

    @admin.action(description="Reactivate selected schools")
    def activate_schools(self, request, queryset):
        count = queryset.update(is_active=True)
        self.message_user(request, f"Reactivated {count} school(s).", messages.SUCCESS)

    def get_urls(self):
        custom = [
            path("<path:object_id>/suspend/", self.admin_site.admin_view(self._toggle_view(False)), name="core_schooltenant_suspend"),
            path("<path:object_id>/activate/", self.admin_site.admin_view(self._toggle_view(True)), name="core_schooltenant_activate"),
        ]
        return custom + super().get_urls()

    def _toggle_view(self, make_active):
        def view(request, object_id):
            obj = self.get_object(request, object_id)
            if obj is None:
                raise Http404
            if not self.has_change_permission(request, obj):
                raise PermissionDenied
            label = "reactivate" if make_active else "suspend"
            if request.method == "POST":
                obj.is_active = make_active
                obj.save(update_fields=["is_active"])
                self.message_user(request, f"{obj} was {'reactivated' if make_active else 'suspended'}.", messages.SUCCESS)
                return redirect(f"{self.admin_site.name}:core_schooltenant_changelist")
            context = {
                **self.admin_site.each_context(request),
                "title": f"{'Reactivate' if make_active else 'Suspend'} school?",
                "object": obj,
                "opts": self.model._meta,
                "action_label": label,
                "make_active": make_active,
            }
            return render(request, "admin/core/schooltenant/confirm_toggle.html", context)

        return view


def _is_local_app(app_config):
    if app_config.name.startswith("django."):
        return False
    return app_config.label not in _THIRD_PARTY_APP_LABELS


def _build_admin_class(model):
    meta = model._meta
    display, search, filters, readonly = [], [], [], []
    date_hierarchy = None
    select_related = []

    for field in meta.fields:
        name = field.name
        internal = field.get_internal_type()
        lowered = name.lower()

        if any(hint in lowered for hint in _SENSITIVE_FIELD_HINTS):
            readonly.append(name)
            continue

        if internal in _SKIP_DISPLAY_TYPES:
            continue

        if field.choices or internal in _FILTERABLE_TYPES:
            filters.append(name)

        if internal == "DateTimeField" and date_hierarchy is None and lowered in (
            "created_at", "created", "date_created", "timestamp",
        ):
            date_hierarchy = name

        if internal in _SEARCHABLE_TYPES:
            search.append(name)

        if internal in _DISPLAYABLE_TYPES:
            display.append(name)
            if internal == "ForeignKey":
                select_related.append(name)

    attrs = {
        "list_display": display[:6] or [meta.pk.name],
        "list_per_page": 50,
    }
    if search:
        attrs["search_fields"] = search[:6]
    if filters:
        attrs["list_filter"] = list(dict.fromkeys(filters))[:6]
    if readonly:
        attrs["readonly_fields"] = readonly
    if date_hierarchy:
        attrs["date_hierarchy"] = date_hierarchy
    if select_related:
        attrs["list_select_related"] = [f for f in select_related if f in attrs["list_display"]] or False

    return type(f"{model.__name__}AutoAdmin", (admin.ModelAdmin,), attrs)


def register_all():
    mirrored, generated, skipped = 0, 0, 0

    try:
        from core.tenant import SchoolTenant
        control_panel.register(SchoolTenant, ControlPanelSchoolTenantAdmin)
    except Exception:
        logger.warning("control_panel: could not register custom SchoolTenant admin", exc_info=True)

    for model, model_admin in list(admin.site._registry.items()):
        if model in control_panel._registry:
            continue
        try:
            control_panel.register(model, model_admin.__class__)
            mirrored += 1
        except admin.sites.AlreadyRegistered:
            pass
        except Exception:
            logger.warning("control_panel: could not mirror %s", model, exc_info=True)
            skipped += 1

    for app_config in apps.get_app_configs():
        if not _is_local_app(app_config):
            continue
        for model in app_config.get_models():
            if model in control_panel._registry:
                continue
            try:
                control_panel.register(model, _build_admin_class(model))
                generated += 1
            except Exception:
                logger.warning("control_panel: could not auto-register %s", model, exc_info=True)
                skipped += 1

    logger.info(
        "control_panel: %d mirrored from /admin/, %d auto-registered, %d skipped",
        mirrored, generated, skipped,
    )


register_all()
