"""A second, friendlier admin site that mirrors django.contrib.admin.

Every model already registered on the default ``admin.site`` is mirrored here
using its existing ModelAdmin class untouched. Any project model that isn't
registered anywhere yet gets a sensible auto-generated ModelAdmin (search,
filters, readonly handling for sensitive fields) so it's reachable too. The
default ``/admin/`` site is never modified by this module.
"""
import logging

from django.apps import apps
from django.contrib import admin
from django.contrib.admin.sites import AdminSite

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


class ControlPanelSite(AdminSite):
    site_header = "Schooldom Control Panel"
    site_title = "Schooldom Control Panel"
    index_title = "Platform Control Panel"

    def get_app_list(self, request, app_label=None):
        app_list = super().get_app_list(request, app_label=app_label)
        for app in app_list:
            app["name"] = APP_LABEL_NAMES.get(app["app_label"], app["name"])
        return sorted(app_list, key=lambda a: a["name"].lower())


control_panel = ControlPanelSite(name="control_panel")


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
