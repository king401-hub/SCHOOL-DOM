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


# Schools used for internal testing - never real schools, so their users
# and financial activity would otherwise dilute every platform-wide number
# on this dashboard with synthetic data.
TEST_SCHOOL_SCHEMA_NAMES = {"happy_academy_2"}

# FinanceLedgerLog.action values for money paid OUT - see
# finance.services.record_finance_activity's call sites for the full list.
# (Money IN no longer reads from FinanceLedgerLog at all - see
# _payment_channel_totals below for why.)
FINANCE_LEDGER_OUTFLOW_ACTIONS = {"salary_advance_paid", "salary_payment_sent", "payroll_processed"}


def safe_count(model, filters=None, exclude=None):
    if model is None:
        return 0
    queryset = model.objects.all()
    if filters:
        try:
            queryset = queryset.filter(**filters)
        except FieldError:
            return 0
    if exclude:
        try:
            queryset = queryset.exclude(**exclude)
        except FieldError:
            pass
    return queryset.count()


def safe_sum(model, field, filters=None, exclude=None):
    if model is None:
        return Decimal("0.00")
    queryset = model.objects.all()
    if filters:
        try:
            queryset = queryset.filter(**filters)
        except FieldError:
            return Decimal("0.00")
    if exclude:
        try:
            queryset = queryset.exclude(**exclude)
        except FieldError:
            pass
    try:
        return queryset.aggregate(total=Sum(field)).get("total") or Decimal("0.00")
    except FieldError:
        return Decimal("0.00")


def _money(value):
    """₦ + thousands separator, same convention as config/control_panel.py's
    own _money - whole naira only, no kobo, since every figure this backs is
    a coarse platform-wide total, not a single transaction receipt."""
    try:
        return f"₦{Decimal(value):,.0f}"
    except Exception:
        return "₦0"


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
        "license": get_model("licensing", "CBTLicense"),
    }


def _platform_revenue(since=None):
    """Real platform-side revenue: activation-token purchases + SMS bundle purchases
    + the platform's cut of fee-collection payments. Returns (total, transaction_count).
    Excludes TEST_SCHOOL_SCHEMA_NAMES throughout - a test school's purchases are
    never real revenue."""
    from finance.models import ActivationCreditTransaction, SmsWalletTransaction

    total = Decimal("0.00")
    count = 0

    tokens = ActivationCreditTransaction.objects.filter(
        tx_type="purchase", status="successful",
    ).exclude(pool__tenant__schema_name__in=TEST_SCHOOL_SCHEMA_NAMES)
    sms = SmsWalletTransaction.objects.filter(
        tx_type="purchase", status="successful",
    ).exclude(wallet__tenant__schema_name__in=TEST_SCHOOL_SCHEMA_NAMES)
    if since:
        tokens = tokens.filter(created_at__gte=since)
        sms = sms.filter(created_at__gte=since)
    for qs in (tokens, sms):
        agg = qs.aggregate(s=Sum("amount"), c=Count("id"))
        total += agg["s"] or Decimal("0.00")
        count += agg["c"] or 0

    fee_payment_model = get_model("fee_collections", "FeePayment")
    if fee_payment_model is not None:
        qs = fee_payment_model.objects.filter(status="successful").exclude(
            school__schema_name__in=TEST_SCHOOL_SCHEMA_NAMES
        )
        if since:
            qs = qs.filter(created_at__gte=since)
        agg = qs.aggregate(s=Sum("platform_fee"), c=Count("id"))
        total += agg["s"] or Decimal("0.00")
        count += agg["c"] or 0

    return total, count


def _excluded_tenant_ids(exclude_schema_names):
    from core.models import SchoolTenant

    if not exclude_schema_names:
        return set()
    return set(SchoolTenant.objects.filter(schema_name__in=exclude_schema_names).values_list("id", flat=True))


def _payment_channel_querysets(exclude_schema_names=None):
    """The three real ways a school actually receives money in this
    codebase, each sourced from whichever table that flow really writes to
    - NOT finance_collections.FeePayment, which has a webhook wired up at
    /api/collections/ but is never called by anything in the live product
    (AdminScreens.jsx, the parent payment pages) and so always has zero
    rows; the "Payments and Transactions" page built against it has been
    silently showing nothing.

    - Bills: a parent paying a bill/invoice link through Paystack checkout
      (finance.services.process_paystack_webhook -> allocate_split_payment).
      Transaction.tx_type is SPLIT_PAYMENT either way, so this is
      distinguished from a DVA payment by its own reference prefix - 'SPL'
      here vs 'DVA' below (see each function's generate_reference call).
    - DVA: money sent into a parent's dedicated virtual account
      (finance.services.process_virtual_account_payment).
    - Payment recorded: cash/bank transfer/POS an admin enters by hand on
      the school's own Finance page (finance.services.record_cash_payment),
      or a bank transfer auto-matched by narration
      (apply_bank_payment_to_student) - both just create/update a
      BankPayment row, so both are counted the same way here.
    """
    from finance.models import BankPayment, Transaction

    exclude_ids = _excluded_tenant_ids(exclude_schema_names)

    bills = Transaction.objects.filter(
        tx_type=Transaction.SPLIT_PAYMENT, status=Transaction.STATUS_SUCCESS, reference__startswith="SPL",
    )
    dva = Transaction.objects.filter(
        tx_type=Transaction.SPLIT_PAYMENT, status=Transaction.STATUS_SUCCESS, reference__startswith="DVA",
    )
    # Anything that isn't FAILED represents money that actually arrived at
    # the school, even if it hasn't been matched/applied to a fee yet
    # (UNMATCHED) or only partly applied (PARTIAL) - PENDING is the
    # transient state record_cash_payment starts a row in, immediately
    # before applying it.
    recorded = BankPayment.objects.exclude(status=BankPayment.STATUS_FAILED)
    if exclude_ids:
        bills = bills.exclude(school_id__in=exclude_ids)
        dva = dva.exclude(school_id__in=exclude_ids)
        recorded = recorded.exclude(tenant_id__in=exclude_ids)
    return bills, dva, recorded


def _payment_channel_totals(exclude_schema_names=None):
    """Platform-wide totals for the dashboard's summary cards - see
    _payment_channel_querysets for what each one actually counts."""
    bills, dva, recorded = _payment_channel_querysets(exclude_schema_names)
    return {
        "bills": bills.aggregate(total=Sum("amount"))["total"] or Decimal("0.00"),
        "dva": dva.aggregate(total=Sum("amount"))["total"] or Decimal("0.00"),
        "recorded": recorded.aggregate(total=Sum("amount"))["total"] or Decimal("0.00"),
    }


def _decode_transaction_school_id(uuid_value):
    """Transaction.school_id is a UUIDField, but SchoolTenant (unlike every
    other core model, which explicitly declares a UUID primary key) uses
    Django's plain integer default pk. Django's UUIDField silently encodes
    a bare int as UUID(int=value) when it's saved (see
    django.db.models.fields.UUIDField.to_python) - every real school_id in
    the database is really just a tenant's integer id wearing a UUID
    costume, written that way at both call sites that set it
    (finance/services.py's school_id=school.id / resolved_tenant.id) and
    already relied on by finance/views.py's own Q(school_id=user.tenant_id)
    lookups. .int undoes the same encoding to recover that integer id."""
    return uuid_value.int if uuid_value is not None else None


def per_school_payment_breakdown(exclude_schema_names=None):
    """Per-school rows for the Payments page - same three channels as
    _payment_channel_totals, grouped by school instead of summed
    platform-wide. Returns (rows, totals), rows sorted by total received,
    highest first."""
    from core.models import SchoolTenant

    bills, dva, recorded = _payment_channel_querysets(exclude_schema_names)
    bills_by_school = {}
    for row in bills.values("school_id").annotate(total=Sum("amount")):
        school_id = _decode_transaction_school_id(row["school_id"])
        if school_id is not None:
            bills_by_school[school_id] = row["total"]
    dva_by_school = {}
    for row in dva.values("school_id").annotate(total=Sum("amount")):
        school_id = _decode_transaction_school_id(row["school_id"])
        if school_id is not None:
            dva_by_school[school_id] = row["total"]
    # BankPayment.tenant is a real ForeignKey (unlike Transaction.school_id),
    # so tenant_id already comes back as the plain integer pk - no decoding.
    recorded_by_school = dict(
        recorded.values("tenant_id").annotate(total=Sum("amount")).values_list("tenant_id", "total")
    )

    school_ids = {sid for sid in (*bills_by_school, *dva_by_school, *recorded_by_school) if sid}
    schools_by_id = {school.id: school for school in SchoolTenant.objects.filter(id__in=school_ids)}

    rows = []
    totals = {"bills": Decimal("0.00"), "dva": Decimal("0.00"), "recorded": Decimal("0.00")}
    for school_id in school_ids:
        bills_amount = bills_by_school.get(school_id) or Decimal("0.00")
        dva_amount = dva_by_school.get(school_id) or Decimal("0.00")
        recorded_amount = recorded_by_school.get(school_id) or Decimal("0.00")
        totals["bills"] += bills_amount
        totals["dva"] += dva_amount
        totals["recorded"] += recorded_amount
        school = schools_by_id.get(school_id)
        rows.append({
            "school_id": school_id,
            "school_name": school.name if school else "Unknown school",
            "bills": bills_amount,
            "dva": dva_amount,
            "recorded": recorded_amount,
            "total": bills_amount + dva_amount + recorded_amount,
        })
    rows.sort(key=lambda row: row["total"], reverse=True)
    totals["grand_total"] = totals["bills"] + totals["dva"] + totals["recorded"]
    return rows, totals


def dashboard_context():
    models = platform_models()
    User = get_user_model()
    today = timezone.now().date()
    month_start = today.replace(day=1)

    school_model = models["school"]
    # A branch (another SchoolTenant sharing school_group with its parent -
    # see users.branch_views.create_branch) is the same real-world school,
    # not a new one - collapse those down before counting so adding a
    # branch never looks like a new signup. Only applies when the resolved
    # model actually has school_group (core.SchoolTenant does); any other
    # fallback "School" model is counted as-is.
    if has_field_path(school_model, "school_group"):
        from core.models import primary_school_tenants
        primary_schools_qs = primary_school_tenants(school_model.objects.all())
    else:
        primary_schools_qs = school_model.objects.all() if school_model else None

    def _count_primary(filters=None):
        if primary_schools_qs is None:
            return 0
        qs = primary_schools_qs
        if filters:
            try:
                qs = qs.filter(**filters)
            except FieldError:
                return 0
        return qs.count()

    monthly_revenue, _ = _platform_revenue(since=month_start)
    ledger_exclude = {"tenant__schema_name__in": TEST_SCHOOL_SCHEMA_NAMES}
    payment_totals = _payment_channel_totals(TEST_SCHOOL_SCHEMA_NAMES)

    stats = {
        "schools": _count_primary(),
        "pending_schools": _count_primary({"compliance_status": "submitted"}) if has_field_path(school_model, "compliance_status") else 0,
        "active_schools": _count_primary({"is_active": True}) if has_field_path(school_model, "is_active") else _count_primary({"status__iexact": "active"}),
        "suspended_schools": _count_primary({"is_active": False}) if has_field_path(school_model, "is_active") else _count_primary({"status__iexact": "suspended"}),
        "users": User.objects.exclude(tenant__schema_name__in=TEST_SCHOOL_SCHEMA_NAMES).count(),
        "subscriptions": safe_count(models["subscription"]),
        "open_tickets": safe_count(models["ticket"], {"status__in": ["open", "pending", "new"]}),
        "virtual_accounts": safe_count(models["virtual_account"]),
        "monthly_revenue": _money(monthly_revenue),
        # The three real ways a school receives money, each its own figure
        # rather than one blended total - see _payment_channel_querysets.
        "bills_total": _money(payment_totals["bills"]),
        "dva_total": _money(payment_totals["dva"]),
        "payments_recorded_total": _money(payment_totals["recorded"]),
        # FinanceLedgerLog is a narrower audit trail (purchases, refunds,
        # salary advances, admin actions...), not a full payments ledger -
        # bills/dva/payments_recorded above are the real money-received
        # figures. Out still reads from here since salary/payroll disbursal
        # has no other table of its own.
        "finance_ledger_logs": safe_count(models["finance_ledger"], exclude=ledger_exclude),
        "finance_ledger_out_amount": _money(
            safe_sum(models["finance_ledger"], "amount", {"action__in": FINANCE_LEDGER_OUTFLOW_ACTIONS}, exclude=ledger_exclude)
        ),
    }

    recent_schools = []
    if primary_schools_qs is not None:
        order_field = "-created_on" if has_field_path(school_model, "created_on") else "-id"
        recent_schools = primary_schools_qs.order_by(order_field)[:8]

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
