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
from django.http import Http404, HttpResponse, JsonResponse
from django.shortcuts import redirect, render
from django.templatetags.static import static
from django.urls import NoReverseMatch, path, reverse
from django.utils.html import format_html
from django.utils.text import capfirst

from ops.models import OpsUser, Region
from ops.permissions import clear_member_override, has_permission, set_member_override, set_role_default

logger = logging.getLogger("control_panel")

# Maps a concrete model to the Ops Console module that gates it (spec section 2).
# Only models with a real, already-built feature are listed here - Lead pipeline,
# Churn dashboard, Training tools, and Slack controls have no backing model yet, so
# there's nothing to gate for them (see the Ops Console build-scope decision).
MODULE_MODEL_MAP = {
    ("finance", "activationcreditpool"): "token_assignment",
    ("finance", "activationcredittransaction"): "token_assignment",
    ("finance", "smswallet"): "token_assignment",
    ("finance", "smswallettransaction"): "token_assignment",
    ("finance", "smsbundle"): "token_assignment",
    ("finance", "tokenallocation"): "token_assignment",
    ("users", "user"): "students_staff_data",
    ("users", "studentprofile"): "students_staff_data",
    ("users", "teacherprofile"): "students_staff_data",
    ("users", "parentprofile"): "students_staff_data",
    ("hr", "staffprofile"): "students_staff_data",
}

# ---------------------------------------------------------------------------
# SaaS-style grouped navigation (spec: "Redesign the entire Control Panel" -
# Phase 1, nav restructure). Every model mirrored/auto-registered by
# register_all() gets mapped to one of these categories + a plain-language
# label, replacing the old flat "one row per Django app" sidebar. Anything not
# listed here (a future model nobody has categorized yet) falls back to an
# "Other" bucket in ControlPanelSite.build_nav_categories() instead of raising
# or silently vanishing from the nav - see the fallback there.
NAV_ICONS = {
    "dashboard": '<path d="M3 10.5 12 3l9 7.5"/><path d="M5 9v10a1 1 0 0 0 1 1h4v-6h4v6h4a1 1 0 0 0 1-1V9"/>',
    "schools": '<path d="M12 3 2 8l10 5 10-5-10-5Z"/><path d="M6 10.5V16c0 1.5 2.7 3 6 3s6-1.5 6-3v-5.5"/><path d="M22 8v6"/>',
    "academics": '<path d="M12 6.5C10 5 6 4 3 4v14c3 0 7 1 9 2.5C14 19 18 18 21 18V4c-3 0-7 1-9 2.5Z"/><path d="M12 6.5V21"/>',
    "people": '<path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M22 21v-2a4 4 0 0 0-3-3.87"/><path d="M16 3.13a4 4 0 0 1 0 7.75"/>',
    "examinations": '<rect x="6" y="4" width="12" height="16" rx="2"/><path d="M9 4V3a1 1 0 0 1 1-1h4a1 1 0 0 1 1 1v1"/><path d="m9 13 2 2 4-4"/>',
    "finance": '<path d="M3 7a2 2 0 0 1 2-2h13a1 1 0 0 1 1 1v3"/><path d="M3 7v11a2 2 0 0 0 2 2h14a1 1 0 0 0 1-1v-4"/><path d="M17 13h3a1 1 0 0 1 1 1v2a1 1 0 0 1-1 1h-3a2 2 0 0 1 0-4Z"/>',
    "sms": '<path d="M21 11.5a8.38 8.38 0 0 1-.9 3.8 8.5 8.5 0 0 1-7.6 4.7 8.38 8.38 0 0 1-3.8-.9L3 21l1.9-5.7a8.38 8.38 0 0 1-.9-3.8 8.5 8.5 0 0 1 4.7-7.6 8.38 8.38 0 0 1 3.8-.9h.5a8.48 8.48 0 0 1 8 8v.5Z"/>',
    "quizzes": '<circle cx="12" cy="12" r="10"/><path d="M9.1 9a3 3 0 0 1 5.8 1c0 2-3 2-3 4"/><path d="M12 17h.01"/>',
    "administration": '<path d="M12 3 4 6v6c0 5 3.4 8.4 8 9 4.6-.6 8-4 8-9V6l-8-3Z"/>',
    "platform_settings": '<circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.7 1.7 0 0 0 .34 1.87l.06.06a2 2 0 1 1-2.83 2.83l-.06-.06a1.7 1.7 0 0 0-1.87-.34 1.7 1.7 0 0 0-1 1.55V21a2 2 0 0 1-4 0v-.09A1.7 1.7 0 0 0 9 19.36a1.7 1.7 0 0 0-1.87.34l-.06.06a2 2 0 1 1-2.83-2.83l.06-.06A1.7 1.7 0 0 0 4.64 15a1.7 1.7 0 0 0-1.55-1H3a2 2 0 0 1 0-4h.09A1.7 1.7 0 0 0 4.64 9a1.7 1.7 0 0 0-.34-1.87l-.06-.06a2 2 0 1 1 2.83-2.83l.06.06A1.7 1.7 0 0 0 9 4.64a1.7 1.7 0 0 0 1-1.55V3a2 2 0 0 1 4 0v.09a1.7 1.7 0 0 0 1 1.55 1.7 1.7 0 0 0 1.87-.34l.06-.06a2 2 0 1 1 2.83 2.83l-.06.06A1.7 1.7 0 0 0 19.36 9a1.7 1.7 0 0 0 1.55 1H21a2 2 0 0 1 0 4h-.09a1.7 1.7 0 0 0-1.55 1Z"/>',
    "other": '<circle cx="12" cy="12" r="1.5"/><circle cx="19" cy="12" r="1.5"/><circle cx="5" cy="12" r="1.5"/>',
}

NAV_CATEGORY_ORDER = [
    ("schools", "Schools"),
    ("academics", "Academics"),
    ("people", "People"),
    ("examinations", "Examinations"),
    ("finance", "Finance"),
    ("sms", "SMS"),
    ("quizzes", "Quizzes"),
    ("administration", "Administration"),
    ("platform_settings", "Platform Settings"),
    ("other", "Other"),
]

MODEL_NAV_LABELS = {
    # Schools - school records, per-school token/activation lifecycle
    ("core", "schooltenant"): ("schools", "Schools"),
    ("core", "schoolgroup"): ("schools", "School Groups"),
    ("core", "domain"): ("schools", "School Domains"),
    ("tenants", "tenant"): ("schools", "Legacy Tenants"),
    ("finance", "tokenallocation"): ("schools", "School Tokens"),
    ("finance", "activationcreditpool"): ("schools", "School Activation Balances"),
    ("finance", "activationcredittransaction"): ("schools", "Token Transactions"),
    ("finance", "studentactivationcredit"): ("schools", "Student Activation Credits"),
    ("superadmin_dashboard", "schooltokenpaymentsetting"): ("schools", "Token Payment Settings"),

    # Academics - curriculum, calendar, attendance
    ("academic", "academicyear"): ("academics", "Academic Years"),
    ("academic", "class"): ("academics", "Classes"),
    ("academic", "subject"): ("academics", "Subjects"),
    ("academic", "term"): ("academics", "Terms"),
    ("academic", "gradescale"): ("academics", "Grade Scales"),
    ("academic", "lessonplan"): ("academics", "Lesson Plans"),
    ("academic", "timetableentry"): ("academics", "Timetables"),
    ("academic", "studentclasspromotion"): ("academics", "Student Promotions"),
    ("academic", "studentsubjectscore"): ("academics", "Student Subject Scores"),
    ("academic", "schoolactivitycalendar"): ("academics", "School Calendar"),
    ("academic", "attendancerecord"): ("academics", "Attendance"),
    ("attendance", "attendanceqrcode"): ("academics", "Attendance QR Codes"),
    ("attendance", "attendancereport"): ("academics", "Attendance Reports"),
    ("attendance", "teacherattendance"): ("academics", "Teacher Attendance"),
    ("hr", "staffattendance"): ("academics", "Staff Attendance"),
    ("ai_secretary", "studentattendance"): ("academics", "Attendance (AI Secretary)"),

    # People - directories for every role
    ("users", "studentprofile"): ("people", "Students"),
    ("users", "teacherprofile"): ("people", "Teachers"),
    ("users", "parentprofile"): ("people", "Parents"),
    ("users", "user"): ("people", "Administrators & Accounts"),
    ("users", "studentenrollment"): ("people", "Student Enrollments"),
    ("users", "studentactivitytitle"): ("people", "Student Activity Titles"),
    ("users", "studenttestimonial"): ("people", "Student Testimonials"),
    ("hr", "staffprofile"): ("people", "Non-Teaching Staff"),
    ("hr", "leaverequest"): ("people", "Leave Requests"),
    ("academic", "teachernote"): ("people", "Teacher Notes"),
    ("alumni", "archivedstudentrecord"): ("people", "Alumni Records"),

    # Examinations - CBT exams, question banks, results
    ("exams", "exam"): ("examinations", "Exams"),
    ("exams", "examtype"): ("examinations", "Exam Types"),
    ("exams", "examattempt"): ("examinations", "Exam Attempts"),
    ("exams", "exampin"): ("examinations", "Exam PINs"),
    ("exams", "exampinusage"): ("examinations", "Exam PIN Usage"),
    ("exams", "question"): ("examinations", "Exam Questions"),
    ("exams", "questionbank"): ("examinations", "Question Banks"),
    ("exams", "questiongroup"): ("examinations", "Question Groups"),
    ("exams", "studentanswer"): ("examinations", "Student Answers"),
    ("academic", "questionprompt"): ("examinations", "Question Prompts"),
    ("academic", "questionresponse"): ("examinations", "Question Responses"),
    ("academic", "resultbatch"): ("examinations", "Result Batches"),

    # Finance - money movement: fees, bills, payments, ledgers, payroll
    ("finance", "schoolfee"): ("finance", "School Fees"),
    ("finance", "classfee"): ("finance", "Class Fees"),
    ("finance", "feeallocation"): ("finance", "Fee Allocations"),
    ("finance", "bill"): ("finance", "Bills"),
    ("finance", "billitem"): ("finance", "Bill Items"),
    ("finance", "transaction"): ("finance", "Transactions"),
    ("finance", "wallet"): ("finance", "Wallets"),
    ("finance", "adminwallet"): ("finance", "Admin Wallet"),
    ("finance", "expenserecord"): ("finance", "Expenses"),
    ("finance", "financeledgerlog"): ("finance", "Finance Ledger"),
    ("finance", "parentvirtualaccount"): ("finance", "Parent Virtual Accounts"),
    ("finance", "paymentreceiptlink"): ("finance", "Payment Receipts"),
    ("finance", "bankpayment"): ("finance", "Bank Payments"),
    ("finance", "banklink"): ("finance", "Bank Links"),
    ("finance", "studentpaymentreference"): ("finance", "Student Payment References"),
    ("finance", "documentgenerationcredittransaction"): ("finance", "Document Generation Credits"),
    ("fee_collections", "feepayment"): ("finance", "Fee Payments"),
    ("fee_collections", "schoolvirtualaccount"): ("finance", "School Virtual Accounts"),
    ("fee_collections", "schoolsettlement"): ("finance", "School Settlements"),
    ("fee_collections", "schoolcollectionprofile"): ("finance", "School Collection Profiles"),
    ("fee_collections", "collectionconfig"): ("finance", "Collection Configuration"),
    ("fee_collections", "collectionauditlog"): ("finance", "Collection Audit Logs"),
    ("hr", "payrollrecord"): ("finance", "Payroll Records"),
    ("hr", "salaryadvancerequest"): ("finance", "Salary Advances"),
    ("users", "kidsmonitorsubscription"): ("finance", "Kids Monitor Subscriptions"),
    ("users", "loanapplication"): ("finance", "Loan Applications"),

    # SMS - messaging wallets/bundles/logs
    ("finance", "smswallet"): ("sms", "SMS Wallets"),
    ("finance", "smsbundle"): ("sms", "SMS Bundles"),
    ("finance", "smswallettransaction"): ("sms", "SMS Transactions"),
    ("finance", "smsmessagelog"): ("sms", "SMS Message Logs"),
    ("notifications", "smsconfiguration"): ("sms", "SMS Configuration"),

    # Quizzes
    ("quizzes", "quiz"): ("quizzes", "Quizzes"),
    ("quizzes", "question"): ("quizzes", "Quiz Questions"),
    ("quizzes", "choice"): ("quizzes", "Choices"),
    ("quizzes", "answer"): ("quizzes", "Answers"),
    ("quizzes", "submission"): ("quizzes", "Quiz Submissions"),
    ("quizzes", "personalquizfolder"): ("quizzes", "Personal Quiz Folders"),
    ("quizzes", "personalquizfolderquestion"): ("quizzes", "Personal Quiz Folder Questions"),
    ("quizzes", "personalquizquestion"): ("quizzes", "Personal Quiz Questions"),
    ("quizzes", "personalquizattempt"): ("quizzes", "Personal Quiz Attempts"),
    ("quizzes", "personalquizanswer"): ("quizzes", "Personal Quiz Answers"),

    # Administration - legal/compliance, ops team, comms, system housekeeping
    ("core", "auditlog"): ("administration", "Activity Logs"),
    ("auth", "group"): ("administration", "Permission Groups"),
    ("users", "serviceagreement"): ("administration", "Service Agreements"),
    ("users", "supportticket"): ("administration", "Support Tickets"),
    ("users", "loginhistory"): ("administration", "Login History"),
    ("users", "databaseimportjob"): ("administration", "Database Import Jobs"),
    ("hr", "staffactivity"): ("administration", "Staff Activity Logs"),
    ("ops", "opsuser"): ("administration", "Team Members"),
    ("ops", "region"): ("administration", "Regions"),
    ("ops", "rolepermission"): ("administration", "Role Permissions"),
    ("ops", "memberpermission"): ("administration", "Member Permissions"),
    ("ops", "permissionauditlog"): ("administration", "Permission Audit Log"),
    ("otp_email", "emaildevice"): ("administration", "Email OTP Devices"),
    ("request_queue", "queuedrequest"): ("administration", "Queued Requests"),
    ("request_queue", "queuedrequestevent"): ("administration", "Queued Request Events"),
    ("inventory", "inventoryitem"): ("administration", "Inventory Items"),
    ("inventory", "inventoryitemimage"): ("administration", "Inventory Item Images"),
    ("inventory", "itemassignment"): ("administration", "Inventory Assignments"),
    ("inventory", "stockmovement"): ("administration", "Stock Movements"),
    ("inventory", "inventoryauditlog"): ("administration", "Inventory Audit Logs"),
    ("notifications", "announcement"): ("administration", "Announcements"),
    ("notifications", "announcementread"): ("administration", "Announcement Reads"),
    ("notifications", "broadcastmessage"): ("administration", "Broadcast Messages"),
    ("notifications", "groupmessage"): ("administration", "Group Messages"),
    ("notifications", "inappmessage"): ("administration", "In-App Messages"),
    ("notifications", "messagegroup"): ("administration", "Message Groups"),
    ("notifications", "messagegroupmembership"): ("administration", "Message Group Members"),
    ("notifications", "notification"): ("administration", "Notifications"),
    ("notifications", "notificationdigest"): ("administration", "Notification Digests"),
    ("notifications", "notificationpreference"): ("administration", "Notification Preferences"),
    ("notifications", "notificationtemplate"): ("administration", "Notification Templates"),
    ("notifications", "pushsubscription"): ("administration", "Push Subscriptions"),

    # Platform Settings - global config, theming, feature flags
    ("settings_app", "documenttheme"): ("platform_settings", "Document Themes"),
    ("settings_app", "themeconfiguration"): ("platform_settings", "Theme Configurations"),
    ("settings_app", "featureflag"): ("platform_settings", "Feature Flags"),
    ("superadmin_dashboard", "platformnotification"): ("platform_settings", "Platform Notifications"),
    ("notifications", "emailconfiguration"): ("platform_settings", "Email Configuration"),
    ("notifications", "paymentgatewayconfiguration"): ("platform_settings", "Payment Gateway Settings"),
}


def _nav_bucket(model):
    key = (model._meta.app_label, model._meta.model_name)
    if key in MODEL_NAV_LABELS:
        return MODEL_NAV_LABELS[key]
    return ("other", capfirst(str(model._meta.verbose_name_plural)))


class OpsGatedAdminMixin:
    """Gates a ModelAdmin behind a single Ops Console module permission. Accounts
    without an ops_profile (every existing platform-staff account) are completely
    unaffected - this only restricts accounts explicitly enrolled in the Ops
    Console role system."""

    ops_module = None

    def _ops_profile(self, request):
        return getattr(request.user, "ops_profile", None)

    def _ops_allows(self, request):
        profile = self._ops_profile(request)
        if profile is None or not self.ops_module:
            return True
        return has_permission(profile, self.ops_module)

    # For an ops_profile account, the module permission is the *sole* authority -
    # it does not additionally require Django's own per-model auth.Permission
    # grants (which a freshly-created ops account won't have configured, and isn't
    # meant to need: role + module is the whole point of the Ops Console spec).
    # Accounts with no ops_profile fall through to normal Django admin behavior,
    # completely unaffected.
    def has_module_permission(self, request):
        if self._ops_profile(request) is not None:
            return self._ops_allows(request)
        return super().has_module_permission(request)

    def has_view_permission(self, request, obj=None):
        if self._ops_profile(request) is not None:
            return self._ops_allows(request)
        return super().has_view_permission(request, obj)

    def has_add_permission(self, request):
        if self._ops_profile(request) is not None:
            return self._ops_allows(request)
        return super().has_add_permission(request)

    def has_change_permission(self, request, obj=None):
        if self._ops_profile(request) is not None:
            return self._ops_allows(request)
        return super().has_change_permission(request, obj)

    def has_delete_permission(self, request, obj=None):
        if self._ops_profile(request) is not None:
            return self._ops_allows(request)
        return super().has_delete_permission(request, obj)


def _wrap_with_ops_gate(admin_class, module):
    return type(f"OpsGated{admin_class.__name__}", (OpsGatedAdminMixin, admin_class), {"ops_module": module})

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
    "ops": "Ops Console",
}

# Deliberately light-touch: admin data (school records, finance figures, ...) must
# never be served stale, so pages/API calls always go to the network. Only static
# assets (css/js/images) get cached, purely to speed up repeat loads and survive a
# flaky connection - not to make the control panel usable fully offline.
CONTROL_PANEL_SERVICE_WORKER_JS = """
const CACHE_NAME = "schooldom-control-panel-v1";

self.addEventListener("install", (event) => {
  self.skipWaiting();
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches.keys().then((keys) =>
      Promise.all(keys.filter((k) => k !== CACHE_NAME).map((k) => caches.delete(k)))
    )
  );
  self.clients.claim();
});

self.addEventListener("fetch", (event) => {
  const { request } = event;
  if (request.method !== "GET") return;

  const url = new URL(request.url);
  const isStaticAsset = url.pathname.startsWith("/static/") || /\\.(css|js|png|jpe?g|svg|woff2?)$/.test(url.pathname);

  if (isStaticAsset) {
    event.respondWith(
      caches.open(CACHE_NAME).then(async (cache) => {
        const cached = await cache.match(request);
        const network = fetch(request)
          .then((response) => {
            if (response.ok) cache.put(request, response.clone());
            return response;
          })
          .catch(() => cached);
        return cached || network;
      })
    );
    return;
  }

  event.respondWith(
    fetch(request).catch(() =>
      new Response(
        "<!doctype html><html><head><meta charset='utf-8'><title>Offline</title>" +
        "<meta name='viewport' content='width=device-width, initial-scale=1'></head>" +
        "<body style=\\"font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;" +
        "background:#0f172a;color:#e5e9f0;display:flex;align-items:center;justify-content:center;" +
        "height:100vh;margin:0;text-align:center;padding:20px;box-sizing:border-box;\\">" +
        "<div><h1 style='margin:0 0 8px;font-size:20px;'>You're offline</h1>" +
        "<p style='color:#94a3b8;margin:0;'>The control panel needs a connection for live data. Reconnect and try again.</p></div>" +
        "</body></html>",
        { headers: { "Content-Type": "text/html" }, status: 503 }
      )
    )
  );
});
""".strip()


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
        metrics["compliance_pending"] = SchoolTenant.objects.filter(compliance_status="submitted").count()
        metrics["recent_schools"] = [
            {
                "name": s.name,
                "is_active": s.is_active,
                "compliance_status": s.get_compliance_status_display(),
                "created_on": s.created_on,
                "url": reverse("control_panel:core_schooltenant_change", args=[s.pk]),
            }
            for s in SchoolTenant.objects.order_by("-created_on")[:6]
        ]
    except Exception:
        metrics["schools_total"] = metrics["schools_active"] = metrics["schools_suspended"] = "—"
        metrics["compliance_pending"] = 0
        metrics["recent_schools"] = []

    try:
        from users.models import User
        metrics["students_total"] = User.objects.filter(role="student").count()
        metrics["teachers_total"] = User.objects.filter(role="teacher").count()
        metrics["staff_total"] = User.objects.filter(
            role__in=["teacher", "staff", "principal", "school_admin", "accountant"]
        ).count()
    except Exception:
        metrics["students_total"] = metrics["teachers_total"] = metrics["staff_total"] = "—"

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

    def _sparkline(qs, field="amount"):
        """7 bar heights (0-100) from the last 7 days of a queryset, oldest first."""
        from django.db.models.functions import TruncDate

        today = timezone.localdate()
        days = [today - timezone.timedelta(days=i) for i in range(6, -1, -1)]
        rows = (
            qs.filter(created_at__date__gte=days[0])
            .annotate(day=TruncDate("created_at"))
            .values("day")
            .annotate(total=Sum(field))
        )
        by_day = {row["day"]: float(row["total"] or 0) for row in rows}
        values = [by_day.get(d, 0.0) for d in days]
        peak = max(values) or 1.0
        return [max(4, round((v / peak) * 100)) for v in values]

    try:
        from finance.models import ActivationCreditTransaction
        qs = ActivationCreditTransaction.objects.filter(tx_type="purchase", status="successful")
        metrics["tokens_revenue_total"] = _money(qs.aggregate(s=Sum("amount"))["s"] or Decimal("0"))
        metrics["tokens_revenue_30d"] = _money(qs.filter(created_at__gte=since_30d).aggregate(s=Sum("amount"))["s"] or Decimal("0"))
        metrics["tokens_credits_sold"] = qs.aggregate(s=Sum("credits"))["s"] or 0
        metrics["tokens_sparkline"] = _sparkline(qs)
    except Exception:
        metrics["tokens_revenue_total"] = metrics["tokens_revenue_30d"] = "—"
        metrics["tokens_credits_sold"] = "—"
        metrics["tokens_sparkline"] = []

    try:
        from finance.models import SmsWalletTransaction
        qs = SmsWalletTransaction.objects.filter(tx_type="purchase", status="successful")
        metrics["sms_revenue_total"] = _money(qs.aggregate(s=Sum("amount"))["s"] or Decimal("0"))
        metrics["sms_revenue_30d"] = _money(qs.filter(created_at__gte=since_30d).aggregate(s=Sum("amount"))["s"] or Decimal("0"))
        metrics["sms_credits_sold"] = qs.aggregate(s=Sum("credits"))["s"] or 0
        metrics["sms_sparkline"] = _sparkline(qs)
    except Exception:
        metrics["sms_revenue_total"] = metrics["sms_revenue_30d"] = "—"
        metrics["sms_credits_sold"] = "—"
        metrics["sms_sparkline"] = []

    try:
        from finance.models import ActivationCreditTransaction, SmsWalletTransaction
        recent = [
            {
                "tenant": tx.pool.tenant.name if tx.pool.tenant else "—",
                "kind": "Tokens",
                "amount": _money(tx.amount),
                "credits": tx.credits,
                "created_at": tx.created_at,
            }
            for tx in ActivationCreditTransaction.objects.filter(
                tx_type="purchase", status="successful"
            ).select_related("pool__tenant").order_by("-created_at")[:6]
        ] + [
            {
                "tenant": tx.wallet.tenant.name if tx.wallet.tenant else "—",
                "kind": "SMS",
                "amount": _money(tx.amount),
                "credits": tx.credits,
                "created_at": tx.created_at,
            }
            for tx in SmsWalletTransaction.objects.filter(
                tx_type="purchase", status="successful"
            ).select_related("wallet__tenant").order_by("-created_at")[:6]
        ]
        recent.sort(key=lambda r: r["created_at"], reverse=True)
        metrics["recent_payments"] = recent[:6]
    except Exception:
        metrics["recent_payments"] = []

    try:
        from finance.models import TokenAllocation
        today = timezone.localdate()
        metrics["tokens_expiring_soon"] = TokenAllocation.objects.filter(
            revoked_at__isnull=True,
            expires_at__isnull=False,
            expires_at__gte=today,
            expires_at__lte=today + timezone.timedelta(days=7),
        ).count()
        metrics["tokens_recently_expired"] = TokenAllocation.objects.filter(
            revoked_at__isnull=False,
            revoked_at__date__gte=today - timezone.timedelta(days=7),
        ).count()
    except Exception:
        metrics["tokens_expiring_soon"] = metrics["tokens_recently_expired"] = 0

    metrics["alert_count"] = (
        (metrics["compliance_pending"] or 0)
        + metrics["tokens_expiring_soon"]
        + metrics["tokens_recently_expired"]
    )

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

    def _current_app_model(self, request):
        """(app_label, model_name) of the page being viewed, derived from the URL
        rather than resolver internals - control panel URLs always follow
        <root>/<app_label>/<model_name>/... so this works for every view
        (changelist, add, change, delete, history, and our own custom ones)."""
        try:
            base = reverse(f"{self.name}:index")
        except NoReverseMatch:
            return None
        path_info = request.path_info
        if not path_info.startswith(base):
            return None
        parts = [p for p in path_info[len(base):].split("/") if p]
        if len(parts) >= 2:
            return (parts[0], parts[1])
        return None

    def build_nav_categories(self, request):
        """Groups every model this request is allowed to see (respecting the
        same has_module_permission/has_view_permission checks _build_app_dict
        already applies for the old flat app list) into the SaaS-style nav
        categories from MODEL_NAV_LABELS, for the grouped sidebar template."""
        current = self._current_app_model(request)
        buckets = {key: [] for key, _label in NAV_CATEGORY_ORDER}
        for app in self._build_app_dict(request).values():
            for model_dict in app["models"]:
                model = model_dict["model"]
                category, label = _nav_bucket(model)
                url = model_dict["admin_url"] or model_dict["add_url"]
                if not url:
                    continue
                is_current = current == (model._meta.app_label, model._meta.model_name)
                buckets.setdefault(category, []).append({"label": label, "url": url, "is_current": is_current})

        categories = []
        for key, cat_label in NAV_CATEGORY_ORDER:
            items = buckets.get(key) or []
            if not items:
                continue
            items.sort(key=lambda i: i["label"])
            categories.append({
                "key": key,
                "label": cat_label,
                "icon": NAV_ICONS.get(key, NAV_ICONS["other"]),
                "items": items,
                "has_current": any(i["is_current"] for i in items),
            })
        return categories

    def each_context(self, request):
        context = super().each_context(request)
        context["cp_nav_categories"] = self.build_nav_categories(request)
        return context

    def index(self, request, extra_context=None):
        context = {**(extra_context or {}), **_dashboard_metrics()}
        return super().index(request, extra_context=context)

    def get_urls(self):
        custom = [
            # Not wrapped in admin_view - these must be fetchable while logged out
            # too (the browser evaluates installability from the login page, and a
            # service worker registration can't tolerate being redirected to login).
            path("manifest.json", self.manifest_view, name="pwa_manifest"),
            path("sw.js", self.service_worker_view, name="pwa_service_worker"),
            path("permission-matrix/", self.admin_view(self.permission_matrix_view), name="permission_matrix"),
        ]
        return custom + super().get_urls()

    def manifest_view(self, request):
        manifest = {
            "name": "Schooldom Control Panel",
            "short_name": "Control Panel",
            "description": "Schooldom platform control panel",
            "start_url": "/control-panel/",
            "scope": "/control-panel/",
            "display": "standalone",
            "background_color": "#0f172a",
            "theme_color": "#16a34a",
            "orientation": "any",
            "icons": [
                {"src": static("img/control-panel/icon-192.png"), "sizes": "192x192", "type": "image/png", "purpose": "any"},
                {"src": static("img/control-panel/icon-512.png"), "sizes": "512x512", "type": "image/png", "purpose": "any"},
                {"src": static("img/control-panel/icon-maskable-512.png"), "sizes": "512x512", "type": "image/png", "purpose": "maskable"},
            ],
        }
        return JsonResponse(manifest, content_type="application/manifest+json")

    def service_worker_view(self, request):
        return HttpResponse(CONTROL_PANEL_SERVICE_WORKER_JS, content_type="application/javascript")

    def permission_matrix_view(self, request):
        """The "Master permissions matrix" from the spec, editable as one grid.
        Only CEO/CTO (or accounts with no ops_profile at all - regular platform
        staff, unaffected by this system) may edit it - everyone else with module
        access can still open the raw RolePermission list, just not this editor."""
        from ops.models import MODULE_CHOICES, RolePermission

        profile = getattr(request.user, "ops_profile", None)
        if profile is not None and profile.role not in (OpsUser.CEO, OpsUser.CTO):
            raise PermissionDenied

        if request.method == "POST":
            existing = {(rp.role, rp.module): rp.granted for rp in RolePermission.objects.all()}
            for role, _label in OpsUser.ROLE_CHOICES:
                if role == OpsUser.CEO:
                    continue
                for module, _mlabel in MODULE_CHOICES:
                    granted = request.POST.get(f"perm__{role}__{module}") == "on"
                    if existing.get((role, module), False) != granted:
                        set_role_default(request.user, role, module, granted)
            messages.success(request, "Permission matrix updated.")
            return redirect(f"{self.name}:permission_matrix")

        perms = {(rp.role, rp.module): rp.granted for rp in RolePermission.objects.all()}
        rows = []
        for module_slug, module_label in MODULE_CHOICES:
            cells = []
            for role_slug, _rlabel in OpsUser.ROLE_CHOICES:
                locked = role_slug == OpsUser.CEO
                cells.append({
                    "granted": True if locked else perms.get((role_slug, module_slug), False),
                    "locked": locked,
                    "field_name": f"perm__{role_slug}__{module_slug}",
                })
            rows.append({"module_label": module_label, "cells": cells})

        context = {
            **self.each_context(request),
            "title": "Permission Matrix",
            "roles": OpsUser.ROLE_CHOICES,
            "rows": rows,
        }
        return render(request, "admin/ops/permission_matrix.html", context)


control_panel = ControlPanelSite(name="control_panel")


class ControlPanelSchoolTenantAdmin(admin.ModelAdmin):
    """Adds suspend/reactivate/delete controls on top of core.admin's SchoolTenantAdmin."""

    list_display = ("name", "schema_name", "school_group", "ops_region", "school_type", "status_badge", "subscription_tier", "row_actions")
    list_filter = ("school_group", "ops_region", "school_type", "is_active", "subscription_tier")
    search_fields = ("name", "schema_name", "school_group__name")
    actions = ["suspend_schools", "activate_schools"]

    # School onboarding is the primary module for this model, but CFO (billing_plan
    # / revenue_features) and general students_staff_data holders also need to see
    # the school list even though they can't onboard/edit one - spec section 3.3.
    _view_modules = ("school_onboarding", "compliance_verification", "students_staff_data", "revenue_features", "billing_plan")
    _edit_modules = ("school_onboarding", "compliance_verification")

    def _ops_profile(self, request):
        return getattr(request.user, "ops_profile", None)

    def _ops_can_view(self, profile):
        return any(has_permission(profile, m) for m in self._view_modules)

    def _ops_can_edit(self, profile):
        return any(has_permission(profile, m) for m in self._edit_modules)

    def has_module_permission(self, request):
        profile = self._ops_profile(request)
        if profile is not None:
            return self._ops_can_view(profile)
        return super().has_module_permission(request)

    def has_view_permission(self, request, obj=None):
        profile = self._ops_profile(request)
        if profile is not None:
            return self._ops_can_view(profile)
        return super().has_view_permission(request, obj)

    def has_add_permission(self, request):
        profile = self._ops_profile(request)
        if profile is not None:
            return self._ops_can_edit(profile)
        return super().has_add_permission(request)

    def has_change_permission(self, request, obj=None):
        profile = self._ops_profile(request)
        if profile is not None:
            return self._ops_can_edit(profile)
        return super().has_change_permission(request, obj)

    def has_delete_permission(self, request, obj=None):
        profile = self._ops_profile(request)
        if profile is not None:
            return self._ops_can_edit(profile)
        return super().has_delete_permission(request, obj)

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        profile = self._ops_profile(request)
        if profile is not None and not profile.sees_all_regions():
            qs = qs.filter(ops_region=profile.region)
        return qs

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


class ControlPanelTokenAllocationAdmin(admin.ModelAdmin):
    """Every school-level token batch, its lifecycle, and an Extend/Renew action
    that modifies the existing row in place (spec: "without creating a new one")."""

    list_display = ("tenant", "credits", "start_date", "expires_at", "days_left_display", "status_badge", "row_actions")
    list_filter = ("tenant",)
    search_fields = ("tenant__name", "notes")
    readonly_fields = (
        "created_by", "created_at", "updated_at", "revoked_at",
        "notified_7d_at", "notified_1d_at", "notified_expired_at",
    )

    @admin.display(description="Days left")
    def days_left_display(self, obj):
        d = obj.days_remaining
        return "—" if d is None else d

    @admin.display(description="Status")
    def status_badge(self, obj):
        css = {"active": "cp-pill-ok", "expiring_soon": "cp-pill-warn", "expired": "cp-pill-danger"}[obj.status]
        return format_html('<span class="cp-pill {}">{}</span>', css, obj.status_label)

    @admin.display(description="Actions")
    def row_actions(self, obj):
        ns = self.admin_site.name
        url = reverse(f"{ns}:finance_tokenallocation_extend", args=[obj.pk])
        return format_html('<a class="cp-row-btn cp-row-btn-ok" href="{}">Extend / Renew</a>', url)

    def get_urls(self):
        custom = [
            path("<path:object_id>/extend/", self.admin_site.admin_view(self.extend_view), name="finance_tokenallocation_extend"),
        ]
        return custom + super().get_urls()

    def extend_view(self, request, object_id):
        from django.utils.dateparse import parse_date

        from finance.services import extend_token_allocation

        obj = self.get_object(request, object_id)
        if obj is None:
            raise Http404
        if not self.has_change_permission(request, obj):
            raise PermissionDenied

        if request.method == "POST":
            never_expires = request.POST.get("never_expires") == "on"
            new_expiry = None if never_expires else parse_date(request.POST.get("new_expires_at") or "")
            if not never_expires and new_expiry is None:
                messages.error(request, "Enter a valid new expiration date, or check 'never expires'.")
                return redirect(f"{self.admin_site.name}:finance_tokenallocation_extend", object_id)
            try:
                additional_credits = int(request.POST.get("additional_credits") or 0)
            except ValueError:
                additional_credits = 0
            extend_token_allocation(request.user, obj, new_expiry, additional_credits=max(0, additional_credits))
            self.message_user(request, f"Allocation for {obj.tenant} updated.", messages.SUCCESS)
            return redirect(f"{self.admin_site.name}:finance_tokenallocation_changelist")

        context = {
            **self.admin_site.each_context(request),
            "title": f"Extend / renew token allocation for {obj.tenant}",
            "object": obj,
            "opts": self.model._meta,
        }
        return render(request, "admin/finance/tokenallocation/extend.html", context)


class ControlPanelOpsUserAdmin(admin.ModelAdmin):
    """Team management (spec section 2/3.4): CTO/CEO hold the global team_management
    permission and can manage anyone. A Growth Manager only holds the scoped
    team_management_scoped variant - they may only see/add/edit/remove Senior
    Marketers and Marketers within their own region, never another region's roster
    and never a peer GM/CTO/CFO."""

    list_display = ("user", "role", "region", "reports_to", "is_active")
    list_filter = ("role", "region", "is_active")
    search_fields = ("user__email", "user__first_name", "user__last_name")

    def _ops_profile(self, request):
        return getattr(request.user, "ops_profile", None)

    def _can_view(self, profile):
        return has_permission(profile, "team_management") or has_permission(profile, "team_management_scoped")

    def _can_manage(self, profile, obj):
        if has_permission(profile, "team_management"):
            return True
        if has_permission(profile, "team_management_scoped"):
            if obj is None:
                return True
            return obj.role in (OpsUser.SENIOR_MARKETER, OpsUser.MARKETER) and obj.region_id == profile.region_id
        return False

    def has_module_permission(self, request):
        profile = self._ops_profile(request)
        if profile is not None:
            return self._can_view(profile)
        return super().has_module_permission(request)

    def has_view_permission(self, request, obj=None):
        profile = self._ops_profile(request)
        if profile is not None:
            return self._can_view(profile)
        return super().has_view_permission(request, obj)

    def has_add_permission(self, request):
        profile = self._ops_profile(request)
        if profile is not None:
            return self._can_view(profile)
        return super().has_add_permission(request)

    def has_change_permission(self, request, obj=None):
        profile = self._ops_profile(request)
        if profile is not None:
            return self._can_manage(profile, obj)
        return super().has_change_permission(request, obj)

    def has_delete_permission(self, request, obj=None):
        profile = self._ops_profile(request)
        if profile is not None:
            return self._can_manage(profile, obj)
        return super().has_delete_permission(request, obj)

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        profile = self._ops_profile(request)
        if profile is None or has_permission(profile, "team_management"):
            return qs
        if has_permission(profile, "team_management_scoped"):
            return qs.filter(region=profile.region, role__in=[OpsUser.SENIOR_MARKETER, OpsUser.MARKETER])
        return qs.none()

    def formfield_for_choice_field(self, db_field, request, **kwargs):
        if db_field.name == "role":
            profile = self._ops_profile(request)
            if profile is not None and not has_permission(profile, "team_management"):
                # A scoped Growth Manager can only ever create/reassign Senior
                # Marketers and Marketers - never promote someone to CEO/CTO/CFO/GM
                # via the Add/Change form, even though has_add_permission lets them
                # open the form at all.
                labels = dict(OpsUser.ROLE_CHOICES)
                kwargs["choices"] = [
                    (OpsUser.SENIOR_MARKETER, labels[OpsUser.SENIOR_MARKETER]),
                    (OpsUser.MARKETER, labels[OpsUser.MARKETER]),
                ]
        return super().formfield_for_choice_field(db_field, request, **kwargs)

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == "region":
            profile = self._ops_profile(request)
            if profile is not None and not has_permission(profile, "team_management") and profile.region_id:
                kwargs["queryset"] = Region.objects.filter(pk=profile.region_id)
                kwargs["initial"] = profile.region_id
        return super().formfield_for_foreignkey(db_field, request, **kwargs)

    def save_model(self, request, obj, form, change):
        profile = self._ops_profile(request)
        if profile is not None and not has_permission(profile, "team_management"):
            # Defense in depth behind the form-field restriction above - reject
            # anything outside a scoped GM's region/role even if the form was
            # tampered with client-side.
            in_scope = (
                has_permission(profile, "team_management_scoped")
                and obj.role in (OpsUser.SENIOR_MARKETER, OpsUser.MARKETER)
                and obj.region_id == profile.region_id
            )
            if not in_scope:
                raise PermissionDenied
        super().save_model(request, obj, form, change)
        # CEO/CTO are spec'd "Full platform" scope (section 1). The Ops Console
        # module permissions above only cover the 13 modules this spec defines, so
        # the underlying Django account also needs is_superuser for genuinely full
        # access - kept in sync here rather than left as a manual setup step.
        should_be_super = obj.role in (OpsUser.CEO, OpsUser.CTO)
        if obj.user.is_superuser != should_be_super:
            obj.user.is_superuser = should_be_super
            obj.user.save(update_fields=["is_superuser"])

    def delete_model(self, request, obj):
        user = obj.user
        drop_super = obj.role in (OpsUser.CEO, OpsUser.CTO) and user.is_superuser
        super().delete_model(request, obj)
        if drop_super:
            user.is_superuser = False
            user.save(update_fields=["is_superuser"])

    def delete_queryset(self, request, queryset):
        for obj in queryset:
            self.delete_model(request, obj)


class ControlPanelRolePermissionAdmin(admin.ModelAdmin):
    """Raw row editor for the seeded matrix. Prefer the Permission Matrix page for
    day-to-day toggling (it shows the whole grid at once); this stays available as a
    single-row fallback and both paths go through set_role_default so every change
    is audited the same way."""

    list_display = ("role", "module", "granted")
    list_filter = ("role", "module", "granted")

    def save_model(self, request, obj, form, change):
        set_role_default(request.user, obj.role, obj.module, obj.granted)

    def has_delete_permission(self, request, obj=None):
        return False


class ControlPanelMemberPermissionAdmin(admin.ModelAdmin):
    list_display = ("ops_user", "module", "granted")
    list_filter = ("module", "granted")

    def save_model(self, request, obj, form, change):
        set_member_override(request.user, obj.ops_user, obj.module, obj.granted)

    def delete_model(self, request, obj):
        clear_member_override(request.user, obj.ops_user, obj.module)

    def delete_queryset(self, request, queryset):
        for obj in queryset:
            clear_member_override(request.user, obj.ops_user, obj.module)


class ControlPanelAuditLogAdmin(admin.ModelAdmin):
    list_display = ("created_at", "actor", "change_type", "role", "target_ops_user", "module", "old_value", "new_value")
    list_filter = ("change_type", "module", "role")
    date_hierarchy = "created_at"

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


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


def _build_user_admin():
    """A real add/change form for the AUTH_USER_MODEL, in place of the generic
    auto-admin. _build_admin_class() marks any "password"-like field read-only to
    stop someone corrupting an *existing* hash by typing plain text into it - but
    that same protection makes it impossible to set a password when creating a
    brand-new account. This gives new accounts a proper two-field "set password"
    form (like Django's own UserCreationForm) and existing accounts the standard
    safe, read-only hash display (like Django's own UserAdmin) - so creating a
    user through the control panel actually produces a working login."""
    from django import forms as django_forms
    from django.contrib.auth import get_user_model, password_validation
    from django.contrib.auth.forms import ReadOnlyPasswordHashField

    User = get_user_model()

    # This model also carries internal security bookkeeping (login_attempts,
    # admin_otp_*, password_reset_otp_attempts, ...) that's `blank=False` with a
    # model-level default - Django's ModelForm still marks those *required* if
    # they're pulled in via "__all__"/exclude, even though omitting them entirely
    # would happily fall back to the default. So both forms use an explicit
    # allowlist of the fields an admin actually needs to set by hand, the same way
    # Django's own stock UserAdmin keeps its add form to just username+password.
    essential_fields = (
        "email", "first_name", "last_name", "phone", "role", "admin_title",
        "tenant", "school_group", "is_active", "is_staff", "is_superuser",
    )

    class ControlPanelUserCreationForm(django_forms.ModelForm):
        password1 = django_forms.CharField(
            label="Password", widget=django_forms.PasswordInput,
            help_text="Sets a working login password for this account.",
        )
        password2 = django_forms.CharField(label="Confirm password", widget=django_forms.PasswordInput)

        class Meta:
            model = User
            fields = essential_fields

        def clean_password2(self):
            p1 = self.cleaned_data.get("password1")
            p2 = self.cleaned_data.get("password2")
            if p1 and p2 and p1 != p2:
                raise django_forms.ValidationError("Passwords don't match.")
            if p1:
                password_validation.validate_password(p1, self.instance)
            return p2

        def save(self, commit=True):
            user = super().save(commit=False)
            user.set_password(self.cleaned_data["password1"])
            if commit:
                user.save()
            return user

    class ControlPanelUserChangeForm(django_forms.ModelForm):
        password = ReadOnlyPasswordHashField(
            label="Password",
            help_text=(
                "Raw passwords aren't stored, so there's no way to see this one. "
                "Reset it with `manage.py changepassword &lt;email&gt;` on the server."
            ),
        )

        class Meta:
            model = User
            fields = essential_fields + ("password",)

        def clean_password(self):
            return self.initial.get("password")

    class ControlPanelUserAdmin(admin.ModelAdmin):
        add_form = ControlPanelUserCreationForm
        form = ControlPanelUserChangeForm
        list_display = ("email", "first_name", "last_name", "role", "is_staff", "is_active")
        list_filter = ("role", "is_staff", "is_active", "tenant")
        search_fields = ("email", "first_name", "last_name")

        def get_form(self, request, obj=None, **kwargs):
            if obj is None:
                kwargs["form"] = self.add_form
            return super().get_form(request, obj, **kwargs)

    return User, ControlPanelUserAdmin


def register_all():
    mirrored, generated, skipped = 0, 0, 0

    try:
        from core.tenant import SchoolTenant
        control_panel.register(SchoolTenant, ControlPanelSchoolTenantAdmin)
    except Exception:
        logger.warning("control_panel: could not register custom SchoolTenant admin", exc_info=True)

    try:
        from finance.models import TokenAllocation
        control_panel.register(TokenAllocation, _wrap_with_ops_gate(ControlPanelTokenAllocationAdmin, "token_assignment"))
    except Exception:
        logger.warning("control_panel: could not register custom TokenAllocation admin", exc_info=True)

    try:
        User, ControlPanelUserAdmin = _build_user_admin()
        control_panel.register(User, _wrap_with_ops_gate(ControlPanelUserAdmin, "students_staff_data"))
    except Exception:
        logger.warning("control_panel: could not register custom User admin", exc_info=True)

    try:
        from ops.models import MemberPermission, PermissionAuditLog, RolePermission
        control_panel.register(OpsUser, ControlPanelOpsUserAdmin)
        control_panel.register(RolePermission, ControlPanelRolePermissionAdmin)
        control_panel.register(MemberPermission, ControlPanelMemberPermissionAdmin)
        control_panel.register(PermissionAuditLog, ControlPanelAuditLogAdmin)
    except Exception:
        logger.warning("control_panel: could not register ops admin classes", exc_info=True)

    for model, model_admin in list(admin.site._registry.items()):
        if model in control_panel._registry:
            continue
        try:
            admin_class = model_admin.__class__
            module = MODULE_MODEL_MAP.get((model._meta.app_label, model._meta.model_name))
            if module:
                admin_class = _wrap_with_ops_gate(admin_class, module)
            control_panel.register(model, admin_class)
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
                admin_class = _build_admin_class(model)
                module = MODULE_MODEL_MAP.get((model._meta.app_label, model._meta.model_name))
                if module:
                    admin_class = _wrap_with_ops_gate(admin_class, module)
                control_panel.register(model, admin_class)
                generated += 1
            except Exception:
                logger.warning("control_panel: could not auto-register %s", model, exc_info=True)
                skipped += 1

    logger.info(
        "control_panel: %d mirrored from /admin/, %d auto-registered, %d skipped",
        mirrored, generated, skipped,
    )


register_all()
