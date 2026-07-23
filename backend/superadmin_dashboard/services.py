from decimal import Decimal

from django.apps import apps
from django.contrib.auth import get_user_model
from django.core.exceptions import FieldError
from django.db.models import Count, Q, Sum
from django.utils import timezone


def get_model(app_label, model_name):
    try:
        return apps.get_model(app_label, model_name)
    except LookupError:
        return None


def safe_count(model, filters=None):
    if model is None:
        return 0
    queryset = model.objects.all()
    if filters:
        try:
            queryset = queryset.filter(**filters)
        except FieldError:
            return 0
    return queryset.count()


def safe_sum(model, field, filters=None):
    if model is None:
        return Decimal("0.00")
    queryset = model.objects.all()
    if filters:
        try:
            queryset = queryset.filter(**filters)
        except FieldError:
            return Decimal("0.00")
    try:
        return queryset.aggregate(total=Sum(field)).get("total") or Decimal("0.00")
    except FieldError:
        return Decimal("0.00")


def has_field_path(model, field_path):
    if model is None:
        return False
    current_model = model
    for part in field_path.split("__"):
        try:
            field = current_model._meta.get_field(part)
        except Exception:
            return False
        current_model = getattr(field, "related_model", None) or current_model
    return True


def platform_models():
    return {
        "school": get_model("core", "SchoolTenant") or get_model("schools", "School") or get_model("school", "School"),
        # No dedicated Subscription model exists yet - subscription_tier lives directly
        # on SchoolTenant, so that's the closest real thing to "subscriptions" we have.
        "subscription": get_model("core", "SchoolTenant"),
        # Real fee-collection payments received into school virtual accounts.
        "payment": get_model("fee_collections", "FeePayment"),
        "transaction": get_model("fee_collections", "FeePayment"),
        "virtual_account": get_model("fee_collections", "SchoolVirtualAccount"),
        # No support-ticket app exists in this codebase yet.
        "ticket": get_model("support", "SupportTicket") or get_model("tickets", "Ticket"),
        "announcement": get_model("superadmin_dashboard", "PlatformNotification") or get_model("announcements", "Announcement") or get_model("notifications", "Announcement"),
        # core.AuditLog is defined but nothing writes to it. django admin's own
        # LogEntry is real, already populated by every admin add/change/delete,
        # and is what actually backs "Activity Tracking" below.
        "audit_log": get_model("admin", "LogEntry"),
        # Cross-cutting money-movement ledger - every finance action across the
        # whole platform (purchases, refunds, salary advances, withdrawals...).
        "finance_ledger": get_model("finance", "FinanceLedgerLog"),
    }


def _platform_revenue(since=None):
    """Real platform-side revenue: activation-token purchases + SMS bundle purchases
    + the platform's cut of fee-collection payments. Returns (total, transaction_count)."""
    from finance.models import ActivationCreditTransaction, SmsWalletTransaction

    total = Decimal("0.00")
    count = 0

    tokens = ActivationCreditTransaction.objects.filter(tx_type="purchase", status="successful")
    sms = SmsWalletTransaction.objects.filter(tx_type="purchase", status="successful")
    if since:
        tokens = tokens.filter(created_at__gte=since)
        sms = sms.filter(created_at__gte=since)
    for qs in (tokens, sms):
        agg = qs.aggregate(s=Sum("amount"), c=Count("id"))
        total += agg["s"] or Decimal("0.00")
        count += agg["c"] or 0

    fee_payment_model = get_model("fee_collections", "FeePayment")
    if fee_payment_model is not None:
        qs = fee_payment_model.objects.filter(status="successful")
        if since:
            qs = qs.filter(created_at__gte=since)
        agg = qs.aggregate(s=Sum("platform_fee"), c=Count("id"))
        total += agg["s"] or Decimal("0.00")
        count += agg["c"] or 0

    return total, count


def dashboard_context():
    models = platform_models()
    User = get_user_model()
    today = timezone.now().date()
    month_start = today.replace(day=1)

    school_model = models["school"]

    monthly_revenue, _ = _platform_revenue(since=month_start)
    _, transactions_count = _platform_revenue()

    stats = {
        "schools": safe_count(school_model),
        "pending_schools": safe_count(school_model, {"compliance_status": "submitted"}) if has_field_path(school_model, "compliance_status") else 0,
        "active_schools": safe_count(school_model, {"is_active": True}) if has_field_path(school_model, "is_active") else safe_count(school_model, {"status__iexact": "active"}),
        "suspended_schools": safe_count(school_model, {"is_active": False}) if has_field_path(school_model, "is_active") else safe_count(school_model, {"status__iexact": "suspended"}),
        "users": User.objects.count(),
        "subscriptions": safe_count(models["subscription"]),
        "open_tickets": safe_count(models["ticket"], {"status__in": ["open", "pending", "new"]}),
        "virtual_accounts": safe_count(models["virtual_account"]),
        "monthly_revenue": monthly_revenue,
        "transactions": transactions_count,
    }

    recent_schools = []
    if school_model:
        order_field = "-created_on" if has_field_path(school_model, "created_on") else "-id"
        recent_schools = school_model.objects.all().order_by(order_field)[:8]

    recent_activity = []
    notifications = []
    if models["announcement"]:
        notification_order = "-created_at" if has_field_path(models["announcement"], "created_at") else "-id"
        notifications = models["announcement"].objects.all().order_by(notification_order)[:5]

    if models["audit_log"]:
        recent_activity = models["audit_log"].objects.select_related("user").order_by("-action_time")[:10]

    return {
        "stats": stats,
        "recent_schools": recent_schools,
        "recent_activity": recent_activity,
        "notifications": notifications,
    }


def search_queryset(model, request, search_fields, default_order="-id"):
    queryset = model.objects.all()
    query = request.GET.get("q", "").strip()
    status = request.GET.get("status", "").strip()

    if query:
        search_q = Q()
        for field in search_fields:
            lookup = field.replace(".", "__")
            if has_field_path(model, lookup):
                search_q |= Q(**{f"{lookup}__icontains": query})
        if search_q:
            queryset = queryset.filter(search_q)

    if status and has_field_path(model, "status"):
        queryset = queryset.filter(status__iexact=status)
    elif status and has_field_path(model, "is_active"):
        if status.lower() in {"active", "approved", "true", "1"}:
            queryset = queryset.filter(is_active=True)
        elif status.lower() in {"inactive", "suspended", "pending", "false", "0"}:
            queryset = queryset.filter(is_active=False)

    order_field = default_order.lstrip("-")
    if not has_field_path(model, order_field):
        default_order = "pk"

    return queryset.order_by(default_order), query, status
