"""API endpoints for wallet and fee management."""
from decimal import Decimal
import hashlib
import hmac
from hmac import compare_digest
from datetime import datetime
from html import escape
import re

from django.conf import settings
from django.db import OperationalError, ProgrammingError, transaction
from django.db.models import Count, Q, Sum
from django.utils import timezone
from django.utils.dateparse import parse_date
from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from django.views.decorators.csrf import csrf_exempt
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response

from academic.models import AcademicYear, Class, Term
from core.models import SchoolTenant
from finance.models import (
    ActivationCreditPool,
    ActivationCreditTransaction,
    AdminWallet,
    BankPayment,
    Bill,
    BillItem,
    ClassFee,
    ExpenseRecord,
    FeeAllocation,
    FinanceLedgerLog,
    ParentVirtualAccount,
    PaymentReceiptLink,
    SchoolFee,
    SmsMessageLog,
    SmsWalletTransaction,
    StudentActivationCredit,
    StudentPaymentReference,
    Transaction,
    Wallet,
)
from finance.serializers import (
    ActivationCreditPoolSerializer,
    AdminWalletSerializer,
    BankPaymentSerializer,
    BillInvoiceSerializer,
    BillItemSerializer,
    BillSerializer,
    ClassFeeSerializer,
    ExpenseRecordSerializer,
    FinanceLedgerLogSerializer,
    FinanceSummarySerializer,
    SchoolFeeSerializer,
    StudentPaymentReferenceSerializer,
    TransactionSerializer,
    WalletSerializer,
)
from finance.services import (
    activation_credit_bonus_for_purchase,
    activation_credit_duration_for_tenant,
    bill_invoice_status,
    bulk_bill_status_counts,
    credit_wallet,
    debit_wallet,
    ensure_student_wallet,
    add_activation_credits_to_pool,
    active_payment_provider,
    assign_monthly_activation_credits,
    bulk_fee_paid_amounts,
    bulk_get_or_create_activation_credits,
    bulk_get_or_create_payment_references,
    compute_finance_summary,
    eligible_students_for_activation_credits,
    fee_totals_by_student,
    ensure_monthly_credit_reminder,
    generate_reference,
    get_or_create_admin_wallet,
    get_or_create_activation_credit_pool,
    get_or_create_student_activation_credit,
    initialize_activation_credit_purchase,
    initialize_payment_transaction,
    process_due_fees,
    reconcile_fee_status,
    send_bill_invoices,
    sync_bill_invoices,
    sync_class_fee_assignments,
    sync_student_class_fees,
    sync_tenant_class_fees,
    complete_payment_reference,
    complete_wallet_funding,
    get_or_create_student_payment_reference,
    generate_bank_links,
    ingest_bank_payment,
    apply_bank_payment_to_student,
    record_cash_payment,
    provision_kuda_admin_virtual_account,
    record_finance_activity,
    dispatch_payment_receipt_notifications,
    send_payment_receipt_notifications,
    send_fee_reminders,
    send_parent_balance_response,
    send_payment_receipt,
    send_whatsapp_message,
    update_student_activation_alerts,
    verify_activation_credit_purchase,
    # Paystack split payment + fee reminders
    send_parent_virtual_account_fee_reminder,
    send_bulk_message_to_parents,
    send_sendchamp_sms,
    normalize_phone_number,
    allocate_split_payment,
    create_paystack_subaccount,
    sync_school_subaccount_with_paystack,
    list_paystack_banks,
    resolve_paystack_account,
    get_fee_payment_breakdown,
    get_school_payment_split_status,
    initialize_paystack_school_fee_payment,
    process_paystack_webhook,
    provision_parent_virtual_account,
    verify_paystack_transaction,
    verify_paystack_webhook_signature,
    # SMS wallet
    get_or_create_sms_wallet,
    initialize_sms_credit_purchase,
    credit_sms_wallet_from_purchase,
    cancel_sms_wallet_purchase,
    InsufficientSmsCreditsError,
    SmsWalletLockedError,
    SMS_UNIT_BLOCK_SIZE,
    SMS_UNIT_BLOCK_PRICE,
    SMS_UNIT_CURRENCY,
    create_receipt_link,
    send_wallet_sms,
    send_payslip_email,
    sms_compact_url,
    sms_failure_reason,
    _format_naira,
)
from hr.models import PayrollRecord, StaffProfile
from request_queue.services import enqueue_request
from tenants.models import Tenant
from users.models import StudentProfile, User


ADMIN_ROLES = {"school_admin", "principal", "super_admin", "school_superadmin"}
FINANCE_ROLES = ADMIN_ROLES | {"accountant"}


def _get_tenant_scoped_or_404(queryset, tenant, tenant_field="tenant", **lookup):
    """
    Fetch a single object by `lookup` (e.g. id=x, reference=y), 404ing unless it
    belongs to `tenant`. The tenant filter is applied to the DB query itself (not
    checked after fetching), so a wrong-tenant id is indistinguishable from a
    non-existent one - never fetch a tenant-owned model by id/reference alone.
    `tenant_field` supports indirect paths, e.g. "student__user__tenant".
    """
    return get_object_or_404(queryset.filter(**{tenant_field: tenant}), **lookup)


def _parse_amount(raw_amount):
    try:
        amount = Decimal(str(raw_amount))
        if amount <= 0:
            raise ValueError
        return amount.quantize(Decimal("0.01"))
    except Exception:
        raise ValueError("Enter a valid positive amount.")


def _parse_non_negative_amount(raw_amount):
    """Like _parse_amount, but accepts zero - for optional amount fields
    (e.g. a bill's discount/tax) where 0 is the valid "none" value, not
    an error."""
    try:
        amount = Decimal(str(raw_amount))
        if amount < 0:
            raise ValueError
        return amount.quantize(Decimal("0.01"))
    except Exception:
        raise ValueError("Enter a valid amount (0 or more).")


_HEX_COLOR_RE = re.compile(r"^#[0-9A-Fa-f]{6}$")


def _parse_hex_color(raw_color, default="#0f766e"):
    """Validates a #rrggbb hex string before it's ever interpolated into a
    <style> block (invoice accent color) - never trust an admin-supplied
    string there unvalidated."""
    value = str(raw_color or "").strip()
    if not _HEX_COLOR_RE.match(value):
        raise ValueError("Enter a valid color as #rrggbb.")
    return value


def _parse_bool(value, default=True):
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


def _legacy_tenant_for_user(user):
    if not getattr(user, "tenant", None):
        return None
    tenant, _ = Tenant.objects.get_or_create(
        slug=user.tenant.schema_name,
        defaults={"name": user.tenant.name},
    )
    return tenant


def _class_label(class_obj):
    if not class_obj:
        return "Unassigned"
    section = getattr(class_obj, "section", "") or ""
    return f"{class_obj.name} - {section}" if section else class_obj.name


def _school_payload(request, school):
    if not school:
        return {}
    try:
        logo = request.build_absolute_uri(school.logo.url) if request and school.logo else school.logo.url if school.logo else ""
    except Exception:
        logo = ""
    return {
        "id": school.id,
        "name": school.name,
        "school_code": school.schema_name,
        "email": school.email or "",
        "phone": school.phone or "",
        "address": school.address or "",
        "logo": logo,
    }


def _extract_whatsapp_messages(payload):
    messages = []
    for entry in payload.get("entry", []) or []:
        for change in entry.get("changes", []) or []:
            value = change.get("value", {}) or {}
            messages.extend(value.get("messages", []) or [])
    return messages


def _bank_webhook_authorized(request):
    secret = getattr(settings, "SCHOOLDOM_BANK_WEBHOOK_SECRET", "")
    if not secret:
        # Fail closed: an unconfigured secret must reject every request,
        # not accept every request. There's no external provider API to
        # cross-check a bank credit against (unlike Paystack/Flutterwave/
        # Kuda), so this signature check is the ONLY authenticity gate.
        return False
    supplied = (
        request.headers.get("X-SchoolDom-Signature")
        or request.headers.get("X-Webhook-Secret")
        or request.headers.get("Authorization", "").replace("Bearer ", "", 1)
    )
    return compare_digest(str(supplied or ""), str(secret))


def _first_present(data, names, default=""):
    for name in names:
        value = data.get(name)
        if value not in (None, ""):
            return value
    return default


def _whatsapp_signature_valid(request):
    """Verify Meta's X-Hub-Signature-256 header: sha256=<hmac-hex of raw body,
    keyed with the WhatsApp app secret>. Fails closed - an unconfigured
    secret rejects every request, since this is the only authenticity gate
    on an endpoint that triggers real outbound WhatsApp/SMS sends."""
    app_secret = getattr(settings, "WHATSAPP_BUSINESS_APP_SECRET", "")
    if not app_secret:
        return False
    header = request.headers.get("X-Hub-Signature-256", "")
    if not header.startswith("sha256="):
        return False
    expected = hmac.new(app_secret.encode("utf-8"), request.body, hashlib.sha256).hexdigest()
    return compare_digest(header[len("sha256="):], expected)


@api_view(["GET", "POST"])
@permission_classes([AllowAny])
def whatsapp_business_webhook(request):
    """Central SchoolDom WhatsApp webhook for parent balance checks."""
    if request.method == "GET":
        verify_token = getattr(settings, "WHATSAPP_BUSINESS_VERIFY_TOKEN", "")
        mode = request.query_params.get("hub.mode")
        token = request.query_params.get("hub.verify_token")
        challenge = request.query_params.get("hub.challenge", "")
        if mode == "subscribe" and verify_token and compare_digest(token or "", verify_token):
            return HttpResponse(challenge)
        return Response({"success": False, "message": "Verification failed."}, status=status.HTTP_403_FORBIDDEN)

    if not _whatsapp_signature_valid(request):
        return Response({"success": False, "message": "Invalid webhook signature."}, status=status.HTTP_401_UNAUTHORIZED)

    processed = []
    for message in _extract_whatsapp_messages(request.data):
        from_phone = message.get("from", "")
        text = ((message.get("text") or {}).get("body") or "").strip().lower()
        if not from_phone:
            continue
        if text == "stop":
            processed.append({"from": from_phone, "action": "stop_ignored"})
            continue
        if "balance" in text or text in {"bal", "fees", "fee"}:
            try:
                rows = send_parent_balance_response(from_phone)
                processed.append({"from": from_phone, "action": "balance", "children": len(rows)})
            except Exception as exc:
                processed.append({"from": from_phone, "action": "balance", "error": str(exc)})
        else:
            try:
                send_whatsapp_message(from_phone, "SchoolDom: reply BALANCE to see your children and instant bank payment links.")
                processed.append({"from": from_phone, "action": "help"})
            except Exception as exc:
                processed.append({"from": from_phone, "action": "help", "error": str(exc)})
    return Response({"success": True, "processed": processed})


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def admin_whatsapp_fee_reminders(request):
    user = request.user
    if user.role not in FINANCE_ROLES:
        return Response({"success": False, "message": "Finance access required."}, status=status.HTTP_403_FORBIDDEN)
    limit = request.data.get("limit")
    sent = send_fee_reminders(limit=limit)
    return Response({"success": True, "sent_count": len(sent), "sent": sent})


@api_view(["POST"])
@permission_classes([AllowAny])
def bank_credit_webhook(request):
    """Receive NIBSS/Paystack/Moniepoint credit events and auto-match by narration."""
    if not _bank_webhook_authorized(request):
        return Response({"success": False, "message": "Unauthorized webhook."}, status=status.HTTP_403_FORBIDDEN)

    payload = request.data.get("data") if isinstance(request.data.get("data"), dict) else request.data
    amount = _first_present(payload, ["amount", "paid_amount", "credit_amount"])
    narration = _first_present(payload, ["narration", "description", "remark", "reference_narration"])
    bank_reference = _first_present(payload, ["bank_reference", "reference", "transaction_reference", "session_id", "id"])
    currency = _first_present(payload, ["currency"], "NGN")
    account_number = str(_first_present(payload, ["account_number", "destination_account", "settlement_account"])).strip()

    tenant = None
    if account_number:
        wallet = AdminWallet.objects.select_related("tenant").filter(bank_account_number=account_number).first()
        tenant = wallet.tenant if wallet else None
    if not bank_reference:
        return Response({"success": False, "message": "bank_reference/reference is required."}, status=status.HTTP_400_BAD_REQUEST)

    try:
        payment, created = ingest_bank_payment(
            tenant=tenant,
            amount=amount,
            narration=narration,
            bank_reference=bank_reference,
            currency=currency or "NGN",
            metadata={"provider_payload": payload},
            actor=None,
        )
    except Exception as exc:
        return Response({"success": False, "message": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

    if payment.student_id and payment.status in {BankPayment.STATUS_CONFIRMED, BankPayment.STATUS_PARTIAL}:
        dispatch_payment_receipt_notifications(payment)
    return Response({"success": True, "created": created, "payment": BankPaymentSerializer(payment).data})


def payment_fallback_page(request, student_ref):
    reference = get_object_or_404(
        StudentPaymentReference.objects.select_related("student", "student__user", "student__user__tenant", "student__current_class"),
        code__iexact=student_ref,
        is_active=True,
    )
    payment = generate_bank_links(reference.tenant, reference.student)
    context = payment["context"]
    amount = context["amount_for_link"]
    account_number = context["account_number"]
    ussd = f"*737*2*{amount}*{account_number}#" if amount and account_number else ""
    bank_links = "".join(
        f'<a class="button" href="{escape(link["url"], quote=True)}">{escape(link["label"])}</a>'
        for link in payment["links"]
        if link["bank_name"] != "All Banks"
    )
    school_name = escape(context["school_name"])
    student_name = escape(context["student_name"])
    amount_display = escape(context["amount_display"])
    bank_name = escape(context["bank_name"] or "School bank")
    account_name = escape(context["account_name"])
    account_number_html = escape(account_number)
    narration = escape(context["narration"])
    ussd_html = escape(ussd)
    html = f"""<!doctype html>
<html>
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>SchoolDom Payment</title>
  <style>
    body {{ font-family: Arial, sans-serif; margin: 0; background: #f6f8fb; color: #111827; }}
    main {{ max-width: 560px; margin: 32px auto; background: #fff; padding: 24px; border: 1px solid #e5e7eb; border-radius: 8px; }}
    h1 {{ font-size: 24px; margin: 0 0 16px; }}
    dl {{ display: grid; grid-template-columns: 140px 1fr; gap: 12px; }}
    dt {{ color: #6b7280; }}
    dd {{ margin: 0; font-weight: 700; }}
    .button {{ display: block; padding: 12px 14px; margin-top: 10px; background: #0f766e; color: #fff; text-decoration: none; border-radius: 6px; text-align: center; }}
    button {{ padding: 8px 10px; border: 1px solid #d1d5db; background: #fff; border-radius: 6px; cursor: pointer; }}
    .copy {{ display: flex; gap: 8px; align-items: center; justify-content: space-between; border-top: 1px solid #e5e7eb; padding-top: 12px; margin-top: 12px; }}
  </style>
</head>
<body>
  <main>
    <h1>{school_name} Payment</h1>
    <dl>
      <dt>Student</dt><dd>{student_name}</dd>
      <dt>Amount</dt><dd>{amount_display}</dd>
      <dt>Bank</dt><dd>{bank_name}</dd>
      <dt>Account name</dt><dd id="accountName">{account_name}</dd>
      <dt>Account number</dt><dd id="accountNumber">{account_number_html}</dd>
      <dt>Narration</dt><dd id="narration">{narration}</dd>
      <dt>USSD</dt><dd id="ussd">{ussd_html}</dd>
    </dl>
    {bank_links}
    <div class="copy"><span>Account number</span><button onclick="copyText('accountNumber')">Copy</button></div>
    <div class="copy"><span>Narration</span><button onclick="copyText('narration')">Copy</button></div>
    <div class="copy"><span>USSD</span><button onclick="copyText('ussd')">Copy</button></div>
  </main>
  <script>
    function copyText(id) {{
      navigator.clipboard.writeText(document.getElementById(id).innerText);
    }}
  </script>
</body>
</html>"""
    return HttpResponse(html)


def _render_receipt_link(request, link):
    if link.expires_at and link.expires_at < timezone.now():
        return HttpResponse(
            "<html><body style='font-family:sans-serif;text-align:center;padding:40px'>"
            "<h2>This receipt link has expired.</h2>"
            "<p>Please contact your school for a copy.</p></body></html>",
            status=410,
        )
    if link.receipt_type == "invoice":
        fee_id = link.data.get("fee_id")
        if fee_id:
            SchoolFee.objects.filter(id=fee_id, viewed_at__isnull=True).update(viewed_at=timezone.now())
    from django.shortcuts import render as django_render
    from settings_app.models import DocumentTheme

    theme = None
    data = dict(link.data or {})
    if link.tenant_id:
        theme = DocumentTheme.objects.filter(school_tenant_id=link.tenant_id).first()
        if not data.get("school_logo") and getattr(link.tenant, "logo", None):
            try:
                data["school_logo"] = request.build_absolute_uri(link.tenant.logo.url)
            except Exception:
                pass
    if theme is None:
        theme = DocumentTheme(school_tenant=link.tenant)
    return django_render(request, "finance/receipt.html", {"link": link, "data": data, "theme": theme})


def receipt_page(request, token):
    """Public receipt/bill page linked in SMS (legacy long-token URL). No authentication required."""
    from finance.models import PaymentReceiptLink
    link = get_object_or_404(PaymentReceiptLink, token=token)
    return _render_receipt_link(request, link)


def receipt_page_short(request, short_code):
    """Public receipt/bill page via the compact /r/<code> link used in SMS. No authentication required."""
    from finance.models import PaymentReceiptLink
    link = get_object_or_404(PaymentReceiptLink, short_code=short_code)
    return _render_receipt_link(request, link)


def _classes_for_user(user):
    legacy_tenant = _legacy_tenant_for_user(user)
    if not legacy_tenant:
        return Class.objects.none()
    return Class.objects.filter(tenant=legacy_tenant)


def _admin_finance_snapshot(user):
    sync_tenant_class_fees(user.tenant, actor=user)

    students = list(
        StudentProfile.objects.select_related("user", "current_class")
        .filter(user__tenant=user.tenant)
        .order_by("user__last_name", "user__first_name", "created_at")
    )
    # Fetched once and shared across the alert sweep, the main per-student
    # loop below, and the eligible-student counts at the end of this
    # function - each of those used to independently re-fetch/re-create the
    # same rows per student, which is the main source of this endpoint's
    # query-count blowup on tenants with many students.
    credits_by_student_id = bulk_get_or_create_activation_credits(students)
    update_student_activation_alerts(user.tenant, credits_by_student_id=credits_by_student_id)
    ensure_monthly_credit_reminder(user.tenant)
    # Deliberately NOT calling run_configured_monthly_auto_assignment here -
    # this function backs plain GET reads (Finance page, Expense Tracker,
    # etc.), and a newly-created student is immediately "eligible" for
    # auto-assignment, so simply loading a finance page right after adding a
    # student would silently spend a token on them before anyone clicked
    # "Assign tokens". Auto-assignment now runs only from the explicit "Run
    # auto assign" button (admin_activation_credit_run_auto) and the
    # scheduled finance.tasks.auto_assign_monthly_credits Celery task.

    payment_refs_by_student_id = bulk_get_or_create_payment_references(students)

    class_ids = list(_classes_for_user(user).values_list("id", flat=True))
    # fee_totals_by_student is the single shared helper also used by
    # compute_finance_summary (Expected Fees / Fees Collected) - reusing it
    # here (rather than recomputing per-student totals inline) is what
    # guarantees the Finance Dashboard and the finance_summary payload can
    # never silently diverge.
    per_student_fee_totals, fee_data = fee_totals_by_student(students, class_ids)
    class_fees = fee_data["class_fees"]
    generated_fees = fee_data["generated_fees"]
    manual_fees = fee_data["manual_fees"]
    paid_amounts = fee_data["paid_amounts"]

    student_rows = []
    activation_rows = []
    expected_total = Decimal("0.00")
    amount_received = Decimal("0.00")
    pending_payments = 0
    active_credit_count = 0
    inactive_credit_count = 0
    excluded_credit_count = 0

    for student in students:
        activation_credit = credits_by_student_id.get(student.id) or get_or_create_student_activation_credit(student)
        has_login_credit = activation_credit.has_login_credit
        if has_login_credit:
            active_credit_count += 1
        else:
            inactive_credit_count += 1
        if activation_credit.is_excluded_from_auto_deductions:
            excluded_credit_count += 1

        expected_for_student, paid_for_student = per_student_fee_totals.get(
            student.id, (Decimal("0.00"), Decimal("0.00"))
        )

        remaining = max(expected_for_student - paid_for_student, Decimal("0.00"))
        if expected_for_student <= 0:
            payment_status = "unassigned"
        elif remaining <= 0:
            payment_status = "paid"
        elif paid_for_student > 0:
            payment_status = "partial"
        else:
            payment_status = "pending"

        if remaining > 0:
            pending_payments += 1
        expected_total += expected_for_student
        amount_received += paid_for_student
        payment_reference = payment_refs_by_student_id.get(student.id) or get_or_create_student_payment_reference(student)
        student_rows.append(
            {
                "id": str(student.id),
                "name": student.user.get_full_name() or student.user.email,
                "student_id": student.student_id or student.admission_number,
                "class_name": _class_label(student.current_class),
                "payment_reference": payment_reference.code,
                "payment_status": payment_status,
                "expected_amount": expected_for_student,
                "amount_paid": paid_for_student,
                "remaining_balance": remaining,
                "has_login_credit": has_login_credit,
                "activation_active_until": activation_credit.active_until,
                "credit_excluded": activation_credit.is_excluded_from_auto_deductions,
            }
        )
        activation_rows.append(
            {
                "id": str(activation_credit.id),
                "student_id": str(student.id),
                "student_name": student.user.get_full_name() or student.user.email,
                "student_email": student.user.email,
                "student_identifier": student.student_id or student.admission_number,
                "class_name": _class_label(student.current_class),
                "active_until": activation_credit.active_until,
                "credits_assigned": activation_credit.credits_assigned,
                "inactive_since": activation_credit.inactive_since,
                "inactive_flagged_at": activation_credit.inactive_flagged_at,
                "is_excluded_from_auto_deductions": activation_credit.is_excluded_from_auto_deductions,
                "has_login_credit": has_login_credit,
                "paid_ratio": float(_student_paid_ratio_for_snapshot(expected_for_student, paid_for_student)),
            }
        )

    class_counts = (
        StudentProfile.objects.filter(user__tenant=user.tenant, current_class__isnull=False)
        .values("current_class")
        .annotate(total=Count("id"))
    )
    count_by_class = {entry["current_class"]: entry["total"] for entry in class_counts}
    class_fee_rows = []
    for class_fee in class_fees:
        student_count = count_by_class.get(class_fee.school_class_id, 0)
        generated_for_fee = [fee for fee in generated_fees if fee.class_fee_id == class_fee.id]
        paid_for_fee = sum((paid_amounts.get(fee.id, Decimal("0.00")) for fee in generated_for_fee), Decimal("0.00"))
        expected_for_fee = sum((fee.amount for fee in generated_for_fee), Decimal("0.00"))
        missing_count = max(student_count - len(generated_for_fee), 0)
        expected_for_fee += class_fee.amount * missing_count
        class_fee_rows.append(
            {
                "id": str(class_fee.id),
                "school_class": class_fee.school_class_id,
                "class_label": _class_label(class_fee.school_class),
                "title": class_fee.title,
                "amount": class_fee.amount,
                "currency": class_fee.currency,
                "due_date": class_fee.due_date,
                "is_active": class_fee.is_active,
                "student_count": student_count,
                "expected_amount": expected_for_fee,
                "amount_received": paid_for_fee,
                "outstanding_amount": max(expected_for_fee - paid_for_fee, Decimal("0.00")),
            }
        )
    student_fee_rows = SchoolFeeSerializer(
        sorted([*generated_fees, *manual_fees], key=lambda fee: (fee.student.user.last_name, fee.student.user.first_name, fee.due_date, fee.title)),
        many=True,
        context={"paid_amounts": paid_amounts},
    ).data

    pool = get_or_create_activation_credit_pool(user.tenant)
    token_duration_months, token_duration_days = activation_credit_duration_for_tenant(user.tenant)
    bank_payments = BankPayment.objects.select_related("student", "student__user", "payment_reference").filter(tenant=user.tenant)
    transaction_history = Transaction.objects.filter(
        Q(admin_wallet__tenant=user.tenant)
        | Q(tx_type=Transaction.SPLIT_PAYMENT, school_id=user.tenant_id)
    ).order_by("-created_at")[:100]
    try:
        finance_ledger_logs = FinanceLedgerLog.objects.select_related("actor").filter(tenant=user.tenant).order_by("-created_at")[:100]
        finance_ledger_log_rows = FinanceLedgerLogSerializer(finance_ledger_logs, many=True).data
    except (OperationalError, ProgrammingError):
        finance_ledger_log_rows = []
    credit_purchase_history = [
        {
            "id": str(item.id),
            "reference": item.reference,
            "credits": item.credits,
            "purchased_credits": (item.metadata or {}).get("purchased_credits", item.credits),
            "bonus_credits": (item.metadata or {}).get("bonus_credits", 0),
            "total_credits": (item.metadata or {}).get("total_credits", item.credits),
            "amount": item.amount,
            "currency": pool.currency,
            "price_per_credit": item.price_per_credit,
            "status": item.status,
            "provider": item.provider,
            "narration": item.narration,
            "created_by": item.created_by.get_full_name() if item.created_by else "",
            "created_at": item.created_at,
        }
        for item in pool.transactions.filter(tx_type=ActivationCreditTransaction.PURCHASE)
        .select_related("created_by")
        .order_by("-created_at")[:100]
    ]
    return {
        "school": _school_payload(None, user.tenant),
        "expected_fee_amount": expected_total,
        "amount_received": amount_received,
        "outstanding_balance": max(expected_total - amount_received, Decimal("0.00")),
        "finance_summary": compute_finance_summary(user, per_student_fee_totals),
        "pending_payments": pending_payments,
        "debtors_count": sum(1 for row in student_rows if row["remaining_balance"] > 0),
        "confirmed_bank_payments": bank_payments.filter(status__in=[BankPayment.STATUS_CONFIRMED, BankPayment.STATUS_PARTIAL]).count(),
        "unmatched_bank_payments": bank_payments.filter(status=BankPayment.STATUS_UNMATCHED).count(),
        "student_payment_rows": student_rows,
        "student_fee_rows": student_fee_rows,
        "class_fee_rows": class_fee_rows,
        "bank_payment_rows": BankPaymentSerializer(bank_payments[:100], many=True).data,
        "transaction_history": TransactionSerializer(transaction_history, many=True).data,
        "finance_ledger_logs": finance_ledger_log_rows,
        "activation_credit_pool": ActivationCreditPoolSerializer(pool).data,
        "activation_credit_summary": {
            "price_per_credit": pool.price_per_credit,
            "duration_months_per_token": token_duration_months,
            "duration_days_per_token": token_duration_days,
            "available_credits": pool.balance,
            "active_students": active_credit_count,
            "inactive_students": inactive_credit_count,
            "excluded_students": excluded_credit_count,
            "eligible_all": len(eligible_students_for_activation_credits(user.tenant, scope="all", credits_by_student_id=credits_by_student_id)),
            "eligible_paid_50": len(eligible_students_for_activation_credits(user.tenant, scope="paid_50", credits_by_student_id=credits_by_student_id)),
        },
        "activation_credit_rows": activation_rows,
        "activation_credit_purchase_history": credit_purchase_history,
        # Prepaid balances held on students' wallets (e.g. from overpayment)
        # that will automatically apply to their next due fees.
        "total_student_credit_balance": Wallet.objects.filter(
            user__tenant=user.tenant, user__role="student"
        ).aggregate(total=Sum("balance"))["total"] or Decimal("0.00"),
    }


def _student_paid_ratio_for_snapshot(expected, paid):
    if not expected:
        return Decimal("0.00")
    return min(Decimal("1.00"), Decimal(paid) / Decimal(expected))


def _get_parent_virtual_account_for_student(user):
    """Return parent virtual account dict for a student user, or None."""
    try:
        student_profile = StudentProfile.objects.filter(user=user).first()
        if not student_profile:
            return None
        vac = ParentVirtualAccount.objects.filter(
            parent__parent_profile__children=student_profile,
            tenant=user.tenant,
            is_active=True,
        ).first()
        if vac:
            return {
                "account_number": vac.account_number,
                "bank_name": vac.bank_name,
                "account_name": vac.account_name,
                "provider": vac.provider,
            }
    except Exception:
        pass
    return None


def _student_wallet_snapshot(user):
    """
    Shared helper to return wallet, transactions, and fees for a student.
    Ensures the wallet exists and processes due fees before serialization.
    """
    if user.role != "student":
        return None, None, None, None, None

    wallet = Wallet.objects.filter(user=user).first()
    if not wallet:
        wallet = ensure_student_wallet(user)

    student_profile = StudentProfile.objects.filter(user=user).first()
    if student_profile:
        sync_student_class_fees(student_profile, actor=user)
        process_due_fees(student_profile, actor=user)
    payment_reference = get_or_create_student_payment_reference(student_profile) if student_profile else None
    bank_payments = BankPayment.objects.filter(student=student_profile).order_by("-created_at")[:20] if student_profile else BankPayment.objects.none()

    wallet = (
        Wallet.objects.select_related("user")
        .prefetch_related("transactions")
        .get(pk=wallet.pk)
    )
    # Paystack split/DVA payments (paid by a parent's virtual account) never
    # attach to this wallet FK - they're only linked via FeeAllocation against
    # this student's fees, so pull those in too.
    split_tx_ids = (
        FeeAllocation.objects.filter(fee__student=student_profile).values_list("transaction_id", flat=True)
        if student_profile else []
    )
    transactions = Transaction.objects.filter(
        Q(wallet=wallet) | Q(id__in=split_tx_ids)
    ).order_by("-created_at")[:20]
    fees = SchoolFee.objects.filter(
        student__user=user
    ).filter(
        Q(class_fee__isnull=True) | Q(class_fee__is_active=True)
    ).order_by("due_date")[:12]
    return wallet, transactions, fees, payment_reference, bank_payments


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def wallet_summary(request):
    """Return the student's wallet, transactions, and fees."""
    user = request.user
    wallet, transactions, fees, payment_reference, bank_payments = _student_wallet_snapshot(user)
    if wallet is None:
        return Response({"success": False, "message": "Only students have wallets."}, status=status.HTTP_403_FORBIDDEN)

    admin_wallet = get_or_create_admin_wallet(user.tenant)
    return Response(
        {
            "success": True,
            "school": _school_payload(request, user.tenant),
            "wallet": WalletSerializer(wallet).data,
            "transactions": TransactionSerializer(transactions, many=True).data,
            "fees": SchoolFeeSerializer(fees, many=True).data,
            "payment_reference": StudentPaymentReferenceSerializer(payment_reference).data if payment_reference else None,
            "bank_payments": BankPaymentSerializer(bank_payments, many=True).data,
            "payment_instructions": {
                "bank_account_name": admin_wallet.bank_account_name,
                "bank_account_number": admin_wallet.bank_account_number,
                "bank_name": admin_wallet.bank_code,
                "bank_code": admin_wallet.bank_code,
                "reference_code": payment_reference.code if payment_reference else "",
                "narration": f"School fees {payment_reference.code}" if payment_reference else "",
                "parent_virtual_account": _get_parent_virtual_account_for_student(user),
            },
        }
    )


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def wallet_fund(request):
    """Initialize school-fee payment for a student."""
    user = request.user
    if user.role != "student":
        return Response({"success": False, "message": "Only students can fund this wallet."}, status=status.HTTP_403_FORBIDDEN)

    wallet = ensure_student_wallet(user)
    try:
        amount = _parse_amount(request.data.get("amount"))
    except ValueError as exc:
        return Response({"success": False, "message": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

    reference = generate_reference("PAY")
    provider = active_payment_provider()
    tx = Transaction.objects.create(
        wallet=wallet,
        amount=amount,
        currency=wallet.currency,
        tx_type=Transaction.FUNDING,
        status=Transaction.STATUS_PENDING,
        reference=reference,
        provider=provider,
        narration=f"School fee payment via {provider.title()}",
        created_by=user,
        metadata={"requested_amount": float(amount)},
    )

    try:
        init_payload = initialize_payment_transaction(
            user=user,
            amount=amount,
            reference=reference,
            metadata={"user_id": str(user.id), "wallet_id": str(wallet.id)},
        )
    except Exception as exc:
        tx.status = Transaction.STATUS_FAILED
        tx.metadata = {"error": str(exc)}
        tx.save(update_fields=["status", "metadata", "updated_at"])
        return Response(
            {"success": False, "message": str(exc)},
            status=status.HTTP_400_BAD_REQUEST,
        )

    tx.metadata.update(
        {
            "access_code": init_payload.get("access_code"),
            "bank_transfer": init_payload.get("bank_transfer") or {},
            "provider": provider,
        }
    )
    tx.save(update_fields=["metadata", "updated_at"])

    return Response(
        {
            "success": True,
            "authorization_url": init_payload.get("authorization_url") or init_payload.get("link"),
            "link": init_payload.get("link") or init_payload.get("authorization_url"),
            "reference": reference,
            "access_code": init_payload.get("access_code"),
            "bank_transfer": init_payload.get("bank_transfer") or {},
            "provider": provider,
            "message": f"{provider.title()} payment initialized for school fee payment.",
        },
        status=status.HTTP_201_CREATED,
    )


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def wallet_verify(request):
    """Verify Flutterwave payment and move the funds to the admin wallet."""
    user = request.user
    if user.role != "student":
        return Response({"success": False, "message": "Only students can verify their wallet payments."}, status=status.HTTP_403_FORBIDDEN)

    reference = str(request.data.get("reference", "")).strip()
    if not reference:
        return Response({"success": False, "message": "reference is required."}, status=status.HTTP_400_BAD_REQUEST)

    tx = get_object_or_404(Transaction, reference=reference, wallet__user=user)
    if tx.status == Transaction.STATUS_SUCCESS:
        complete_wallet_funding(reference, actor=user)
        wallet, transactions, fees, payment_reference, bank_payments = _student_wallet_snapshot(user)
        admin_wallet = get_or_create_admin_wallet(user.tenant)
        return Response(
            {
                "success": True,
                "school": _school_payload(request, user.tenant),
                "wallet": WalletSerializer(wallet).data,
                "transactions": TransactionSerializer(transactions, many=True).data,
                "fees": SchoolFeeSerializer(fees, many=True).data,
                "payment_reference": StudentPaymentReferenceSerializer(payment_reference).data if payment_reference else None,
                "bank_payments": BankPaymentSerializer(bank_payments, many=True).data,
                "payment_instructions": {
                    "bank_account_name": admin_wallet.bank_account_name,
                    "bank_account_number": admin_wallet.bank_account_number,
                    "bank_name": admin_wallet.bank_code,
                    "bank_code": admin_wallet.bank_code,
                    "reference_code": payment_reference.code if payment_reference else "",
                    "narration": f"School fees {payment_reference.code}" if payment_reference else "",
                },
            }
        )

    try:
        complete_wallet_funding(reference, actor=user)
    except Exception as exc:
        return Response({"success": False, "message": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

    wallet, transactions, fees, payment_reference, bank_payments = _student_wallet_snapshot(user)
    admin_wallet = get_or_create_admin_wallet(user.tenant)
    return Response(
        {
            "success": True,
            "school": _school_payload(request, user.tenant),
            "wallet": WalletSerializer(wallet).data,
            "transactions": TransactionSerializer(transactions, many=True).data,
            "fees": SchoolFeeSerializer(fees, many=True).data,
            "payment_reference": StudentPaymentReferenceSerializer(payment_reference).data if payment_reference else None,
            "bank_payments": BankPaymentSerializer(bank_payments, many=True).data,
            "payment_instructions": {
                "bank_account_name": admin_wallet.bank_account_name,
                "bank_account_number": admin_wallet.bank_account_number,
                "bank_name": admin_wallet.bank_code,
                "bank_code": admin_wallet.bank_code,
                "reference_code": payment_reference.code if payment_reference else "",
                "narration": f"School fees {payment_reference.code}" if payment_reference else "",
                "parent_virtual_account": _get_parent_virtual_account_for_student(user),
            },
        }
    )


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def admin_overview(request):
    """Finance overview for administrators."""
    user = request.user
    if user.role not in FINANCE_ROLES:
        return Response({"success": False, "message": "Finance access required."}, status=status.HTTP_403_FORBIDDEN)

    admin_wallet = get_or_create_admin_wallet(user.tenant)
    finance_snapshot = _admin_finance_snapshot(user)
    overdue_fees = SchoolFee.objects.filter(
        student__user__tenant=user.tenant,
        status=SchoolFee.STATUS_OVERDUE,
    ).count()
    pending_fees = SchoolFee.objects.filter(
        student__user__tenant=user.tenant,
        status=SchoolFee.STATUS_PENDING,
    ).count()
    recent_student_wallets = Wallet.objects.filter(user__tenant=user.tenant).select_related("user").order_by("-created_at")[:8]
    recent_students_payload = []
    try:
        recent_students = (
            StudentProfile.objects.select_related("user", "current_class")
            .filter(user__tenant=user.tenant)
            .order_by("-created_at")[:8]
        )
        recent_students_payload = [
            {
                "id": str(s.id),
                "name": s.user.get_full_name() or s.user.email,
                "student_id": getattr(s, "student_id", "") or getattr(s, "admission_number", "") or getattr(s, "registration_no", ""),
                "class_name": getattr(s, "current_class", None).name if getattr(s, "current_class", None) else "",
                "created_at": s.created_at,
            }
            for s in recent_students
        ]
    except Exception:
        # If anything goes wrong (e.g., legacy data mismatch), don't fail the entire overview.
        recent_students_payload = []
    return Response(
        {
            "success": True,
            "admin_wallet": AdminWalletSerializer(admin_wallet).data,
            "pending_fees": pending_fees,
            "overdue_fees": overdue_fees,
            "expected_fee_amount": finance_snapshot["expected_fee_amount"],
            "amount_received": finance_snapshot["amount_received"],
            "outstanding_balance": finance_snapshot["outstanding_balance"],
            "finance_summary": FinanceSummarySerializer(finance_snapshot["finance_summary"]).data,
            "pending_payments": finance_snapshot["pending_payments"],
            "debtors_count": finance_snapshot["debtors_count"],
            "confirmed_bank_payments": finance_snapshot["confirmed_bank_payments"],
            "unmatched_bank_payments": finance_snapshot["unmatched_bank_payments"],
            "student_payment_rows": finance_snapshot["student_payment_rows"],
            "student_fee_rows": finance_snapshot["student_fee_rows"],
            "class_fee_rows": finance_snapshot["class_fee_rows"],
            "bank_payment_rows": finance_snapshot["bank_payment_rows"],
            "transaction_history": finance_snapshot["transaction_history"],
            "finance_ledger_logs": finance_snapshot["finance_ledger_logs"],
            "activation_credit_pool": finance_snapshot["activation_credit_pool"],
            "activation_credit_summary": finance_snapshot["activation_credit_summary"],
            "activation_credit_rows": finance_snapshot["activation_credit_rows"],
            "activation_credit_purchase_history": finance_snapshot["activation_credit_purchase_history"],
            "total_student_credit_balance": finance_snapshot["total_student_credit_balance"],
            "class_options": [
                {
                    "id": item.id,
                    "label": _class_label(item),
                }
                for item in _classes_for_user(user).order_by("name", "section")[:200]
            ],
            "recent_student_wallets": [
                {
                    "id": str(w.user.id),
                    "name": w.user.get_full_name() or w.user.email,
                    "balance": w.balance,
                    "currency": w.currency,
                }
                for w in recent_student_wallets
            ],
            "recent_students": recent_students_payload,
            "announcements": [],
        }
    )


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def admin_finance_transactions(request):
    """Lightweight recent-transactions feed for the mobile Finance section.

    Deliberately separate from admin_overview (which computes a large
    finance snapshot with fee rows, ledger logs, activation credits, etc.)
    so this can be polled frequently for a "live" feed without the extra cost.
    """
    user = request.user
    if user.role not in FINANCE_ROLES:
        return Response({"success": False, "message": "Finance access required."}, status=status.HTTP_403_FORBIDDEN)
    if not user.tenant:
        return Response({"success": False, "message": "Your account is not linked to a school."}, status=status.HTTP_400_BAD_REQUEST)

    try:
        limit = max(1, min(int(request.query_params.get("limit") or 50), 100))
    except (TypeError, ValueError):
        limit = 50

    transactions = Transaction.objects.filter(
        Q(admin_wallet__tenant=user.tenant)
        | Q(tx_type=Transaction.SPLIT_PAYMENT, school_id=user.tenant_id)
    ).order_by("-created_at")[:limit]

    return Response(
        {
            "success": True,
            "transactions": TransactionSerializer(transactions, many=True).data,
            "server_time": timezone.now(),
        }
    )


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def admin_payment_account(request):
    """Save the school bank account shown to students for fee transfers."""
    user = request.user
    if user.role not in FINANCE_ROLES:
        return Response({"success": False, "message": "Finance access required."}, status=status.HTTP_403_FORBIDDEN)

    bank_account_name = str(request.data.get("bank_account_name") or request.data.get("account_name") or "").strip()
    bank_account_number = str(request.data.get("bank_account_number") or request.data.get("account_number") or "").strip()
    bank_code = str(request.data.get("bank_name") or request.data.get("bank_code") or "").strip()

    if not bank_account_name:
        return Response({"success": False, "message": "Account name is required."}, status=status.HTTP_400_BAD_REQUEST)
    if not bank_account_number:
        return Response({"success": False, "message": "Account number is required."}, status=status.HTTP_400_BAD_REQUEST)
    if not bank_account_number.isdigit() or not 6 <= len(bank_account_number) <= 20:
        return Response(
            {"success": False, "message": "Enter a valid account number using 6 to 20 digits."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    admin_wallet = get_or_create_admin_wallet(user.tenant)
    admin_wallet.bank_account_name = bank_account_name
    admin_wallet.bank_account_number = bank_account_number
    admin_wallet.bank_code = bank_code
    admin_wallet.save(update_fields=["bank_account_name", "bank_account_number", "bank_code", "updated_at"])
    record_finance_activity(
        user.tenant,
        user,
        "payment_account_updated",
        "Updated school fee receiving account.",
        metadata={"bank_account_name": bank_account_name, "bank_account_number": bank_account_number, "bank_code": bank_code},
    )

    return Response(
        {
            "success": True,
            "admin_wallet": AdminWalletSerializer(admin_wallet).data,
            "message": "School fee receiving account saved.",
        }
    )


@api_view(["GET", "POST"])
@permission_classes([IsAuthenticated])
def admin_kuda_virtual_account(request):
    """Create or return the Kuda virtual account for the current school admin wallet."""
    user = request.user
    if user.role not in FINANCE_ROLES:
        return Response({"success": False, "message": "Finance access required."}, status=status.HTTP_403_FORBIDDEN)
    admin_wallet = get_or_create_admin_wallet(user.tenant)
    if request.method == "POST":
        try:
            admin_wallet = provision_kuda_admin_virtual_account(admin_wallet, actor=user)
        except Exception as exc:
            return Response({"success": False, "message": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        message = "Kuda virtual account is ready for school fee collections."
    else:
        message = "Kuda virtual account loaded." if admin_wallet.kuda_virtual_account_number else "No Kuda virtual account has been created for this school yet."
    return Response(
        {
            "success": True,
            "admin_wallet": AdminWalletSerializer(admin_wallet).data,
            "virtual_account": {
                "bank_name": admin_wallet.kuda_virtual_account_bank_name,
                "account_name": admin_wallet.kuda_virtual_account_name,
                "account_number": admin_wallet.kuda_virtual_account_number,
                "reference": admin_wallet.kuda_virtual_account_reference,
                "status": admin_wallet.kuda_virtual_account_status,
            },
            "message": message,
        }
    )


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def admin_class_fee_create(request):
    """Create a class fee and sync it to students in that class."""
    user = request.user
    if user.role not in FINANCE_ROLES:
        return Response({"success": False, "message": "Finance access required."}, status=status.HTTP_403_FORBIDDEN)

    title = str(request.data.get("title", "")).strip() or "School Fee"
    school_class_id = request.data.get("school_class") or request.data.get("class_id")
    due_date = parse_date(str(request.data.get("due_date", "")).strip())
    if not due_date:
        return Response({"success": False, "message": "due_date must be YYYY-MM-DD."}, status=status.HTTP_400_BAD_REQUEST)

    try:
        amount = _parse_amount(request.data.get("amount"))
    except ValueError as exc:
        return Response({"success": False, "message": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

    school_class = get_object_or_404(_classes_for_user(user), id=school_class_id)
    class_fee, _ = ClassFee.objects.update_or_create(
        school_class=school_class,
        title=title,
        due_date=due_date,
        defaults={
            "amount": amount,
            "currency": "NGN",
            "is_active": _parse_bool(request.data.get("is_active"), default=True),
            "created_by": user,
        },
    )
    assigned_count = sync_class_fee_assignments(class_fee, actor=user, notify_students=True)
    record_finance_activity(
        user.tenant,
        user,
        "class_fee_saved",
        f"Saved class fee '{class_fee.title}' for {_class_label(class_fee.school_class)}.",
        amount=class_fee.amount,
        currency=class_fee.currency,
        reference=str(class_fee.id),
    )
    return Response(
        {
            "success": True,
            "class_fee": ClassFeeSerializer(class_fee).data,
            "assigned_count": assigned_count,
            "message": f"Bill sent to {assigned_count} student{'s' if assigned_count != 1 else ''} in {_class_label(school_class)}.",
            "finance": _admin_finance_snapshot(user),
        },
        status=status.HTTP_201_CREATED,
    )


@api_view(["PATCH", "DELETE"])
@permission_classes([IsAuthenticated])
def admin_class_fee_detail(request, fee_id):
    """Edit or deactivate a class fee."""
    user = request.user
    if user.role not in FINANCE_ROLES:
        return Response({"success": False, "message": "Finance access required."}, status=status.HTTP_403_FORBIDDEN)

    class_fee = get_object_or_404(
        ClassFee.objects.select_related("school_class").filter(school_class__in=_classes_for_user(user)),
        id=fee_id,
    )
    if request.method == "DELETE":
        class_fee.is_active = False
        class_fee.save(update_fields=["is_active", "updated_at"])
        record_finance_activity(
            user.tenant,
            user,
            "class_fee_deactivated",
            f"Deactivated class fee '{class_fee.title}' for {_class_label(class_fee.school_class)}.",
            amount=class_fee.amount,
            currency=class_fee.currency,
            reference=str(class_fee.id),
        )
        return Response({"success": True, "message": "Class fee deactivated.", "finance": _admin_finance_snapshot(user)})

    update_fields = []
    if "title" in request.data:
        title = str(request.data.get("title") or "").strip()
        if not title:
            return Response({"success": False, "message": "title cannot be blank."}, status=status.HTTP_400_BAD_REQUEST)
        class_fee.title = title
        update_fields.append("title")
    if "amount" in request.data:
        try:
            class_fee.amount = _parse_amount(request.data.get("amount"))
        except ValueError as exc:
            return Response({"success": False, "message": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        update_fields.append("amount")
    if "due_date" in request.data:
        due_date = parse_date(str(request.data.get("due_date") or "").strip())
        if not due_date:
            return Response({"success": False, "message": "due_date must be YYYY-MM-DD."}, status=status.HTTP_400_BAD_REQUEST)
        class_fee.due_date = due_date
        update_fields.append("due_date")
    if "is_active" in request.data:
        class_fee.is_active = _parse_bool(request.data.get("is_active"), default=True)
        update_fields.append("is_active")
    if "school_class" in request.data or "class_id" in request.data:
        school_class_id = request.data.get("school_class") or request.data.get("class_id")
        class_fee.school_class = get_object_or_404(_classes_for_user(user), id=school_class_id)
        update_fields.append("school_class")

    if update_fields:
        update_fields.append("updated_at")
        class_fee.save(update_fields=sorted(set(update_fields)))
        assigned_count = sync_class_fee_assignments(class_fee, actor=user, notify_students=True)
        record_finance_activity(
            user.tenant,
            user,
            "class_fee_updated",
            f"Updated class fee '{class_fee.title}' for {_class_label(class_fee.school_class)}.",
            amount=class_fee.amount,
            currency=class_fee.currency,
            reference=str(class_fee.id),
            metadata={"updated_fields": sorted(set(update_fields))},
        )
    else:
        assigned_count = sync_class_fee_assignments(class_fee, actor=user, notify_students=True)
    return Response(
        {
            "success": True,
            "class_fee": ClassFeeSerializer(class_fee).data,
            "assigned_count": assigned_count,
            "message": f"Bill sent to {assigned_count} student{'s' if assigned_count != 1 else ''} in {_class_label(class_fee.school_class)}.",
            "finance": _admin_finance_snapshot(user),
        }
    )


def _bills_for_user(user):
    return Bill.objects.filter(tenant=user.tenant).prefetch_related("items", "classes")


@api_view(["GET", "POST"])
@permission_classes([IsAuthenticated])
def admin_bills(request):
    """List (filtered) bills, or create a new draft bill."""
    user = request.user
    if user.role not in FINANCE_ROLES:
        return Response({"success": False, "message": "Finance access required."}, status=status.HTTP_403_FORBIDDEN)

    if request.method == "POST":
        title = str(request.data.get("title", "")).strip()
        if not title:
            return Response({"success": False, "message": "title is required."}, status=status.HTTP_400_BAD_REQUEST)

        class_ids = request.data.get("class_ids") or request.data.get("classes") or []
        classes = list(_classes_for_user(user).filter(id__in=class_ids))
        if not classes:
            return Response({"success": False, "message": "Select at least one class."}, status=status.HTTP_400_BAD_REQUEST)

        items_data = request.data.get("items") or []
        if not items_data:
            return Response({"success": False, "message": "Add at least one fee item."}, status=status.HTTP_400_BAD_REQUEST)

        due_date = None
        due_date_raw = str(request.data.get("due_date") or "").strip()
        if due_date_raw:
            due_date = parse_date(due_date_raw)
            if not due_date:
                return Response({"success": False, "message": "due_date must be YYYY-MM-DD."}, status=status.HTTP_400_BAD_REQUEST)

        academic_year = None
        academic_year_id = request.data.get("academic_year_id") or request.data.get("academic_year")
        legacy_tenant = _legacy_tenant_for_user(user)
        if academic_year_id:
            academic_year = get_object_or_404(AcademicYear, id=academic_year_id, tenant=legacy_tenant)
        else:
            academic_year = AcademicYear.objects.filter(tenant=legacy_tenant, is_active=True).first()
        term = None
        term_id = request.data.get("term_id") or request.data.get("term")
        if term_id:
            term = get_object_or_404(Term, id=term_id, tenant=legacy_tenant)
        else:
            term = Term.objects.filter(tenant=legacy_tenant, is_active=True).first()

        try:
            discount_raw = request.data.get("discount_amount")
            discount_amount = _parse_non_negative_amount(discount_raw) if discount_raw not in (None, "") else Decimal("0.00")
            tax_raw = request.data.get("tax_amount")
            tax_amount = _parse_non_negative_amount(tax_raw) if tax_raw not in (None, "") else Decimal("0.00")
            accent_color_raw = request.data.get("accent_color")
            accent_color = _parse_hex_color(accent_color_raw) if accent_color_raw else "#0f766e"
        except ValueError as exc:
            return Response({"success": False, "message": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        bill_items = []
        for idx, item in enumerate(items_data):
            description = str(item.get("description", "")).strip()
            if not description:
                continue
            try:
                amount = _parse_amount(item.get("amount"))
            except ValueError as exc:
                return Response({"success": False, "message": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
            bill_items.append((description, amount))
        if not bill_items:
            return Response({"success": False, "message": "Add at least one valid fee item."}, status=status.HTTP_400_BAD_REQUEST)

        bill = Bill.objects.create(
            tenant=user.tenant,
            title=title,
            academic_year=academic_year,
            term=term,
            due_date=due_date,
            discount_amount=discount_amount,
            tax_amount=tax_amount,
            accent_color=accent_color,
            payment_instructions=str(request.data.get("payment_instructions", "")).strip(),
            footer_note=str(request.data.get("footer_note", "")).strip(),
            created_by=user,
        )
        bill.classes.set(classes)
        BillItem.objects.bulk_create(
            [BillItem(bill=bill, description=desc, amount=amt, sort_order=idx) for idx, (desc, amt) in enumerate(bill_items)]
        )

        record_finance_activity(
            user.tenant,
            user,
            "bill_created",
            f"Created draft bill '{bill.title}'.",
            amount=bill.total,
            currency="NGN",
            reference=str(bill.id),
        )
        return Response(
            {"success": True, "bill": BillSerializer(bill, context={"bill_status_rollups": {}}).data},
            status=status.HTTP_201_CREATED,
        )

    # GET - list, filtered
    bills_qs = _bills_for_user(user)
    class_id = request.query_params.get("class_id")
    if class_id:
        bills_qs = bills_qs.filter(classes__id=class_id)
    academic_year_id = request.query_params.get("academic_year_id")
    if academic_year_id:
        bills_qs = bills_qs.filter(academic_year_id=academic_year_id)
    term_id = request.query_params.get("term_id")
    if term_id:
        bills_qs = bills_qs.filter(term_id=term_id)
    title_search = request.query_params.get("title")
    if title_search:
        bills_qs = bills_qs.filter(title__icontains=title_search)
    bill_status_filter = request.query_params.get("status")
    if bill_status_filter:
        bills_qs = bills_qs.filter(status=bill_status_filter)
    due_date_from = request.query_params.get("due_date_from")
    if due_date_from:
        bills_qs = bills_qs.filter(due_date__gte=due_date_from)
    due_date_to = request.query_params.get("due_date_to")
    if due_date_to:
        bills_qs = bills_qs.filter(due_date__lte=due_date_to)

    bills = list(bills_qs.distinct().order_by("-created_at"))
    rollups = bulk_bill_status_counts(bills)

    payment_status_filter = request.query_params.get("payment_status")
    if payment_status_filter:
        bills = [b for b in bills if rollups.get(b.id, {}).get("status") == payment_status_filter]

    serializer = BillSerializer(bills, many=True, context={"bill_status_rollups": rollups})
    return Response({"success": True, "bills": serializer.data})


@api_view(["GET", "PATCH", "DELETE"])
@permission_classes([IsAuthenticated])
def admin_bill_detail(request, bill_id):
    """View, edit, or cancel (soft-delete) a bill. Once a bill is Published,
    only due_date/payment_instructions/footer_note stay editable - title,
    items, classes, and discount/tax are locked to protect already-generated
    invoices; use Duplicate for a real change."""
    user = request.user
    if user.role not in FINANCE_ROLES:
        return Response({"success": False, "message": "Finance access required."}, status=status.HTTP_403_FORBIDDEN)

    bill = get_object_or_404(_bills_for_user(user), id=bill_id)

    if request.method == "DELETE":
        bill.status = Bill.STATUS_CANCELLED
        bill.save(update_fields=["status", "updated_at"])
        record_finance_activity(
            user.tenant, user, "bill_cancelled", f"Cancelled bill '{bill.title}'.",
            amount=bill.total, currency="NGN", reference=str(bill.id),
        )
        return Response({"success": True, "message": "Bill cancelled."})

    if request.method == "GET":
        rollups = bulk_bill_status_counts([bill])
        return Response({"success": True, "bill": BillSerializer(bill, context={"bill_status_rollups": rollups}).data})

    if bill.status == Bill.STATUS_CANCELLED:
        return Response({"success": False, "message": "Cannot edit a cancelled bill."}, status=status.HTTP_400_BAD_REQUEST)

    editable_core = bill.status == Bill.STATUS_DRAFT
    update_fields = []

    if editable_core and "title" in request.data:
        title = str(request.data.get("title") or "").strip()
        if not title:
            return Response({"success": False, "message": "title cannot be blank."}, status=status.HTTP_400_BAD_REQUEST)
        bill.title = title
        update_fields.append("title")
    if "due_date" in request.data:
        due_date_raw = str(request.data.get("due_date") or "").strip()
        bill.due_date = parse_date(due_date_raw) if due_date_raw else None
        update_fields.append("due_date")
    if "payment_instructions" in request.data:
        bill.payment_instructions = str(request.data.get("payment_instructions") or "").strip()
        update_fields.append("payment_instructions")
    if "footer_note" in request.data:
        bill.footer_note = str(request.data.get("footer_note") or "").strip()
        update_fields.append("footer_note")
    if "accent_color" in request.data:
        try:
            bill.accent_color = _parse_hex_color(request.data.get("accent_color"))
        except ValueError as exc:
            return Response({"success": False, "message": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        update_fields.append("accent_color")
    if editable_core and "discount_amount" in request.data:
        try:
            raw = request.data.get("discount_amount")
            bill.discount_amount = _parse_non_negative_amount(raw) if raw not in (None, "") else Decimal("0.00")
        except ValueError as exc:
            return Response({"success": False, "message": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        update_fields.append("discount_amount")
    if editable_core and "tax_amount" in request.data:
        try:
            raw = request.data.get("tax_amount")
            bill.tax_amount = _parse_non_negative_amount(raw) if raw not in (None, "") else Decimal("0.00")
        except ValueError as exc:
            return Response({"success": False, "message": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        update_fields.append("tax_amount")
    if editable_core and ("class_ids" in request.data or "classes" in request.data):
        class_ids = request.data.get("class_ids") or request.data.get("classes") or []
        classes = list(_classes_for_user(user).filter(id__in=class_ids))
        if not classes:
            return Response({"success": False, "message": "Select at least one class."}, status=status.HTTP_400_BAD_REQUEST)
        bill.classes.set(classes)
    if editable_core and "items" in request.data:
        items_data = request.data.get("items") or []
        bill_items = []
        for idx, item in enumerate(items_data):
            description = str(item.get("description", "")).strip()
            if not description:
                continue
            try:
                amount = _parse_amount(item.get("amount"))
            except ValueError as exc:
                return Response({"success": False, "message": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
            bill_items.append(BillItem(bill=bill, description=description, amount=amount, sort_order=idx))
        if not bill_items:
            return Response({"success": False, "message": "Add at least one valid fee item."}, status=status.HTTP_400_BAD_REQUEST)
        bill.items.all().delete()
        BillItem.objects.bulk_create(bill_items)

    if update_fields:
        update_fields.append("updated_at")
        bill.save(update_fields=sorted(set(update_fields)))

    record_finance_activity(
        user.tenant, user, "bill_updated", f"Updated bill '{bill.title}'.",
        amount=bill.total, currency="NGN", reference=str(bill.id),
    )
    rollups = bulk_bill_status_counts([bill])
    return Response({"success": True, "bill": BillSerializer(bill, context={"bill_status_rollups": rollups}).data})


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def admin_bill_recipients(request, bill_id):
    """Parents who would receive this bill's invoices - works even before
    publishing, so the Invoice Designer can preview "who would receive
    this". Computed lazily, mirrors class_broadsheet_parents."""
    user = request.user
    if user.role not in FINANCE_ROLES:
        return Response({"success": False, "message": "Finance access required."}, status=status.HTTP_403_FORBIDDEN)

    bill = get_object_or_404(_bills_for_user(user), id=bill_id)
    from users.models import ParentProfile

    class_ids = list(bill.classes.values_list("id", flat=True))
    parents = list(
        ParentProfile.objects.filter(children__current_class_id__in=class_ids, user__tenant=user.tenant)
        .distinct()
        .select_related("user")
        .prefetch_related("children")
    )
    accounts_by_parent = set(
        ParentVirtualAccount.objects.filter(
            parent_id__in=[p.user_id for p in parents], is_active=True
        ).values_list("parent_id", flat=True)
    )
    payload = []
    for parent in parents:
        in_class_children = [c for c in parent.children.all() if c.current_class_id in class_ids]
        payload.append(
            {
                "user_id": str(parent.user.id),
                "name": parent.user.get_full_name(),
                "phone": parent.user.phone or "",
                "email": parent.user.email or "",
                "has_virtual_account": parent.user_id in accounts_by_parent,
                "children": [
                    {"id": str(c.id), "name": c.user.get_full_name(), "student_id": c.student_id}
                    for c in in_class_children
                ],
            }
        )
    return Response({"success": True, "parents": payload})


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def admin_bill_publish(request, bill_id):
    """Publish (or re-publish/regenerate) a bill - fans out to per-student
    SchoolFee invoices. Calling this again after editing a published bill's
    due_date/notes, or after new students join a targeted class, is exactly
    "regenerate/resync" - idempotent, no separate endpoint needed."""
    user = request.user
    if user.role not in FINANCE_ROLES:
        return Response({"success": False, "message": "Finance access required."}, status=status.HTTP_403_FORBIDDEN)

    bill = get_object_or_404(_bills_for_user(user), id=bill_id)
    if bill.status == Bill.STATUS_CANCELLED:
        return Response({"success": False, "message": "Cannot publish a cancelled bill."}, status=status.HTTP_400_BAD_REQUEST)
    if not bill.classes.exists():
        return Response({"success": False, "message": "Select at least one class first."}, status=status.HTTP_400_BAD_REQUEST)
    if not bill.items.exists():
        return Response({"success": False, "message": "Add at least one fee item first."}, status=status.HTTP_400_BAD_REQUEST)

    synced_count = sync_bill_invoices(bill, actor=user)
    was_draft = bill.status == Bill.STATUS_DRAFT
    if was_draft:
        bill.status = Bill.STATUS_PUBLISHED
        bill.published_at = timezone.now()
        bill.save(update_fields=["status", "published_at", "updated_at"])

    record_finance_activity(
        user.tenant,
        user,
        "bill_published" if was_draft else "bill_regenerated",
        f"{'Published' if was_draft else 'Regenerated'} bill '{bill.title}' ({synced_count} invoice(s) synced).",
        amount=bill.total,
        currency="NGN",
        reference=str(bill.id),
    )
    rollups = bulk_bill_status_counts([bill])
    return Response(
        {
            "success": True,
            "synced_count": synced_count,
            "bill": BillSerializer(bill, context={"bill_status_rollups": rollups}).data,
            "finance": _admin_finance_snapshot(user),
        }
    )


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def admin_bill_duplicate(request, bill_id):
    """Clone a bill (title/classes/items/discount/tax/notes) into a new
    draft. due_date is intentionally left blank to force a fresh one."""
    user = request.user
    if user.role not in FINANCE_ROLES:
        return Response({"success": False, "message": "Finance access required."}, status=status.HTTP_403_FORBIDDEN)

    original = get_object_or_404(_bills_for_user(user), id=bill_id)
    clone = Bill.objects.create(
        tenant=user.tenant,
        title=f"{original.title} (Copy)",
        academic_year=original.academic_year,
        term=original.term,
        due_date=None,
        discount_amount=original.discount_amount,
        tax_amount=original.tax_amount,
        accent_color=original.accent_color,
        payment_instructions=original.payment_instructions,
        footer_note=original.footer_note,
        created_by=user,
    )
    clone.classes.set(original.classes.all())
    BillItem.objects.bulk_create(
        [
            BillItem(bill=clone, description=item.description, amount=item.amount, sort_order=item.sort_order)
            for item in original.items.all()
        ]
    )
    record_finance_activity(
        user.tenant, user, "bill_duplicated", f"Duplicated bill '{original.title}' as '{clone.title}'.",
        amount=clone.total, currency="NGN", reference=str(clone.id),
    )
    return Response(
        {"success": True, "bill": BillSerializer(clone, context={"bill_status_rollups": {}}).data},
        status=status.HTTP_201_CREATED,
    )


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def admin_bill_send(request, bill_id):
    """Send a published bill's invoices to selected parents or a whole
    class. Auto-provisions a virtual account for any recipient who doesn't
    have one yet (see finance.services.send_bill_invoices)."""
    user = request.user
    if user.role not in FINANCE_ROLES:
        return Response({"success": False, "message": "Finance access required."}, status=status.HTTP_403_FORBIDDEN)

    bill = get_object_or_404(_bills_for_user(user), id=bill_id)
    if bill.status != Bill.STATUS_PUBLISHED:
        return Response({"success": False, "message": "Publish the bill before sending it."}, status=status.HTTP_400_BAD_REQUEST)

    scope = request.data.get("scope") or "selected"
    channels = [c for c in (request.data.get("channels") or ["sms"]) if c in ("sms", "email")]
    if not channels:
        return Response({"success": False, "message": "Select at least one channel (sms/email)."}, status=status.HTTP_400_BAD_REQUEST)

    from users.models import ParentProfile

    bill_class_ids = set(bill.classes.values_list("id", flat=True))
    if scope == "class":
        target_class = get_object_or_404(_classes_for_user(user), id=request.data.get("class_id"))
        if target_class.id not in bill_class_ids:
            return Response({"success": False, "message": "That class is not part of this bill."}, status=status.HTTP_400_BAD_REQUEST)
        parent_ids = list(
            ParentProfile.objects.filter(children__current_class=target_class, user__tenant=user.tenant)
            .distinct()
            .values_list("user_id", flat=True)
        )
    else:
        parent_ids = request.data.get("parent_ids") or []

    if not parent_ids:
        return Response({"success": False, "message": "No parents selected."}, status=status.HTTP_400_BAD_REQUEST)

    school = _school_payload(request, bill.tenant)
    result = send_bill_invoices(bill, parent_ids, channels, actor=user, school=school)
    record_finance_activity(
        user.tenant,
        user,
        "bill_sent",
        f"Sent bill '{bill.title}' to {result['sent']} parent(s) ({result['failed']} failed, {result['skipped']} skipped).",
        amount=bill.total,
        currency="NGN",
        reference=str(bill.id),
        metadata=result,
    )
    return Response({"success": True, **result})


@api_view(["PATCH"])
@permission_classes([IsAuthenticated])
def admin_school_fee_detail(request, fee_id):
    """Edit one student's school-fee bill without changing the whole class fee."""
    user = request.user
    if user.role not in FINANCE_ROLES:
        return Response({"success": False, "message": "Finance access required."}, status=status.HTTP_403_FORBIDDEN)

    fee = get_object_or_404(
        SchoolFee.objects.select_related("student", "student__user", "student__current_class", "class_fee").filter(
            student__user__tenant=user.tenant
        ),
        id=fee_id,
    )

    update_fields = []
    if "title" in request.data:
        title = str(request.data.get("title") or "").strip()
        if not title:
            return Response({"success": False, "message": "title cannot be blank."}, status=status.HTTP_400_BAD_REQUEST)
        fee.title = title
        update_fields.append("title")
    if "amount" in request.data:
        try:
            fee.amount = _parse_amount(request.data.get("amount"))
        except ValueError as exc:
            return Response({"success": False, "message": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        update_fields.append("amount")
    if "due_date" in request.data:
        due_date = parse_date(str(request.data.get("due_date") or "").strip())
        if not due_date:
            return Response({"success": False, "message": "due_date must be YYYY-MM-DD."}, status=status.HTTP_400_BAD_REQUEST)
        fee.due_date = due_date
        update_fields.append("due_date")
    if "status" in request.data:
        fee_status = str(request.data.get("status") or "").strip()
        if fee_status not in {choice[0] for choice in SchoolFee.STATUS_CHOICES}:
            return Response({"success": False, "message": "status must be pending, paid, or overdue."}, status=status.HTTP_400_BAD_REQUEST)
        fee.status = fee_status
        update_fields.append("status")
    if "auto_deduct" in request.data:
        fee.auto_deduct = _parse_bool(request.data.get("auto_deduct"), default=True)
        update_fields.append("auto_deduct")

    if update_fields:
        fee.is_customized = True
        update_fields.extend(["is_customized", "updated_at"])
        fee.save(update_fields=sorted(set(update_fields)))
        reconcile_fee_status(fee)
        fee.refresh_from_db()
        record_finance_activity(
            user.tenant,
            user,
            "student_fee_updated",
            f"Updated fee '{fee.title}' for {fee.student.user.get_full_name() or fee.student.user.email}.",
            amount=fee.amount,
            currency=fee.currency,
            reference=str(fee.id),
            metadata={"updated_fields": sorted(set(update_fields))},
        )

    return Response({"success": True, "fee": SchoolFeeSerializer(fee).data, "finance": _admin_finance_snapshot(user)})


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def admin_activation_credit_purchase(request):
    """Add purchased activation tokens to the school pool at the configured token price."""
    user = request.user
    if user.role not in FINANCE_ROLES:
        return Response({"success": False, "message": "Finance access required."}, status=status.HTTP_403_FORBIDDEN)

    try:
        credits = int(request.data.get("credits") or 0)
        init_payload = initialize_activation_credit_purchase(user.tenant, credits, actor=user)
        bonus_credits = activation_credit_bonus_for_purchase(credits)
    except ValueError as exc:
        return Response({"success": False, "message": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
    except Exception as exc:
        return Response({"success": False, "message": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
    record_finance_activity(
        user.tenant,
        user,
        "token_purchase_started",
        f"Started purchase for {credits} activation tokens.",
        amount=init_payload.get("amount") or Decimal("0.00"),
        reference=init_payload.get("reference") or "",
        metadata={"credits": credits, "bonus_credits": bonus_credits, "total_credits": credits + bonus_credits},
    )

    return Response(
        {
            "success": True,
            "authorization_url": init_payload.get("authorization_url") or init_payload.get("link"),
            "link": init_payload.get("link") or init_payload.get("authorization_url"),
            "access_code": init_payload.get("access_code"),
            "reference": init_payload.get("reference"),
            "amount": init_payload.get("amount"),
            "credits": credits,
            "bonus_credits": bonus_credits,
            "total_credits": credits + bonus_credits,
            "message": f"{active_payment_provider().title()} payment initialized for {credits} activation tokens plus {bonus_credits} free bonus tokens.",
        },
        status=status.HTTP_201_CREATED,
    )


@csrf_exempt
@api_view(["POST"])
@permission_classes([])
def flutterwave_webhook(request):
    """Complete successful Flutterwave payments as soon as Flutterwave notifies us."""
    configured_hash = getattr(settings, "FLUTTERWAVE_WEBHOOK_SECRET_HASH", "")
    received_hash = request.headers.get("verif-hash", "")
    if not configured_hash or not compare_digest(received_hash, configured_hash):
        return Response({"success": False, "message": "Invalid webhook signature."}, status=status.HTTP_401_UNAUTHORIZED)

    payload = request.data or {}
    event = str(payload.get("event") or "").lower()
    data = payload.get("data") or {}
    reference = str(data.get("tx_ref") or data.get("reference") or payload.get("tx_ref") or "").strip()
    provider_status = str(data.get("status") or "").lower()

    if event and "charge" not in event:
        return Response({"success": True, "message": "Webhook ignored."})
    if provider_status and provider_status != "successful":
        return Response({"success": True, "message": "Payment is not successful yet."})
    if not reference:
        return Response({"success": False, "message": "Missing payment reference."}, status=status.HTTP_400_BAD_REQUEST)

    try:
        result = complete_payment_reference(reference)
    except ValueError as exc:
        return Response({"success": True, "message": str(exc)})
    except Exception as exc:
        return Response({"success": False, "message": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

    return Response({"success": True, "message": "Payment completed.", **result})


@csrf_exempt
@api_view(["POST"])
@permission_classes([AllowAny])
def kuda_webhook(request):
    """Complete successful Kuda payments as soon as Kuda notifies us.

    Security note: this webhook is intentionally NOT trusted for payment
    facts (amount/status) - it only uses the notification to learn WHICH
    reference to re-verify. The actual completion always goes through
    complete_payment_reference(reference) with no pre-built verification,
    so it falls through to a real verify_kuda_transaction() API call
    (mirrors flutterwave_webhook). This closes off forging a payment by
    POSTing a fabricated amount/status to this endpoint.
    """
    configured_secret = getattr(settings, "KUDA_WEBHOOK_SECRET", "")
    received_secret = (
        request.headers.get("X-Kuda-Signature")
        or request.headers.get("X-Webhook-Secret")
        or request.headers.get("Authorization", "").replace("Bearer ", "", 1)
    )
    if not configured_secret or not compare_digest(received_secret or "", configured_secret):
        return Response({"success": False, "message": "Invalid webhook signature."}, status=status.HTTP_401_UNAUTHORIZED)

    payload = request.data or {}
    data = payload.get("data") if isinstance(payload.get("data"), dict) else payload
    reference = str(
        data.get("reference")
        or data.get("transactionReference")
        or data.get("paymentReference")
        or data.get("session_id")
        or data.get("id")
        or ""
    ).strip()
    if not reference:
        return Response({"success": False, "message": "Missing payment reference."}, status=status.HTTP_400_BAD_REQUEST)

    try:
        result = complete_payment_reference(reference)
    except ValueError as exc:
        return Response({"success": True, "message": str(exc)})
    except Exception as exc:
        return Response({"success": False, "message": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

    return Response({"success": True, "message": "Payment completed.", **result})


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def admin_activation_credit_verify(request):
    """Verify a Flutterwave activation-token purchase and add tokens to the pool."""
    user = request.user
    if user.role not in FINANCE_ROLES:
        return Response({"success": False, "message": "Finance access required."}, status=status.HTTP_403_FORBIDDEN)

    reference = str(request.data.get("reference") or "").strip()
    if not reference:
        return Response({"success": False, "message": "reference is required."}, status=status.HTTP_400_BAD_REQUEST)

    try:
        pool = verify_activation_credit_purchase(reference, actor=user)
    except (ActivationCreditTransaction.DoesNotExist, ValueError) as exc:
        return Response({"success": False, "message": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
    except Exception as exc:
        return Response({"success": False, "message": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
    record_finance_activity(
        user.tenant,
        user,
        "token_purchase_verified",
        "Verified activation token purchase.",
        reference=reference,
        metadata={"available_tokens": pool.balance},
    )

    return Response({"success": True, "pool": ActivationCreditPoolSerializer(pool).data})


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def admin_activation_credit_assign(request):
    """Assign monthly activation tokens to inactive students."""
    user = request.user
    if user.role not in FINANCE_ROLES:
        return Response({"success": False, "message": "Finance access required."}, status=status.HTTP_403_FORBIDDEN)

    scope = str(request.data.get("scope") or "all").strip()
    student_id = request.data.get("student_id")
    try:
        months = int(request.data.get("months") or 1)
        result = assign_monthly_activation_credits(
            user.tenant,
            scope=scope,
            months=months,
            actor=user,
            auto=False,
            student_id=student_id,
        )
    except ValueError as exc:
        return Response({"success": False, "message": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
    record_finance_activity(
        user.tenant,
        user,
        "tokens_assigned",
        f"Assigned activation tokens to {result['assigned']} student account(s).",
        amount=result["assigned"] * months * result["pool"].price_per_credit,
        reference=str(student_id or scope),
        metadata={"scope": scope, "token_units": months, "assigned": result["assigned"]},
    )

    return Response(
        {
            "success": True,
            "assigned": result["assigned"],
            "pool": ActivationCreditPoolSerializer(result["pool"]).data,
        }
    )


@api_view(["POST", "PATCH"])
@permission_classes([IsAuthenticated])
def admin_activation_credit_price(request):
    """Allow platform super admins to change a school's activation-token price."""
    user = request.user
    if user.role != "super_admin" and not user.is_superuser:
        return Response({"success": False, "message": "Super admin access required."}, status=status.HTTP_403_FORBIDDEN)

    tenant = user.tenant
    tenant_id = request.data.get("tenant_id") or request.data.get("school_id")
    school_code = str(request.data.get("school_code") or request.data.get("schema_name") or "").strip()
    if tenant_id:
        tenant = SchoolTenant.objects.filter(id=tenant_id).first()
    elif school_code:
        tenant = SchoolTenant.objects.filter(schema_name__iexact=school_code).first()

    if not tenant:
        return Response({"success": False, "message": "Select a school to update token price."}, status=status.HTTP_400_BAD_REQUEST)

    try:
        price = _parse_amount(request.data.get("price_per_credit") or request.data.get("price"))
    except ValueError as exc:
        return Response({"success": False, "message": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
    if price <= 0:
        return Response({"success": False, "message": "price_per_credit must be greater than zero."}, status=status.HTTP_400_BAD_REQUEST)

    pool = get_or_create_activation_credit_pool(tenant)
    old_price = pool.price_per_credit
    pool.price_per_credit = price
    pool.save(update_fields=["price_per_credit", "updated_at"])
    record_finance_activity(
        tenant,
        user,
        "token_price_updated",
        "Updated activation token price.",
        amount=price,
        currency=pool.currency,
        reference=str(pool.id),
        metadata={"old_price": str(old_price), "new_price": str(price)},
    )
    return Response({"success": True, "pool": ActivationCreditPoolSerializer(pool).data})


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def admin_activation_credit_settings(request):
    """Enable or disable monthly auto-assignment of activation tokens."""
    user = request.user
    if user.role not in FINANCE_ROLES:
        return Response({"success": False, "message": "Finance access required."}, status=status.HTTP_403_FORBIDDEN)

    pool = get_or_create_activation_credit_pool(user.tenant)
    scope = str(request.data.get("scope") or pool.auto_assign_scope or "all").strip()
    if scope not in {"all", "paid_50"}:
        return Response({"success": False, "message": "scope must be 'all' or 'paid_50'."}, status=status.HTTP_400_BAD_REQUEST)
    pool.auto_assign_enabled = _parse_bool(request.data.get("enabled"), default=pool.auto_assign_enabled)
    pool.auto_assign_scope = scope
    pool.save(update_fields=["auto_assign_enabled", "auto_assign_scope", "updated_at"])
    record_finance_activity(
        user.tenant,
        user,
        "token_auto_settings_updated",
        "Updated activation token auto-assignment settings.",
        metadata={"enabled": pool.auto_assign_enabled, "scope": pool.auto_assign_scope},
    )
    return Response({"success": True, "pool": ActivationCreditPoolSerializer(pool).data})


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def admin_activation_credit_run_auto(request):
    """Run configured monthly auto-assignment now."""
    user = request.user
    if user.role not in FINANCE_ROLES:
        return Response({"success": False, "message": "Finance access required."}, status=status.HTTP_403_FORBIDDEN)

    pool = get_or_create_activation_credit_pool(user.tenant)
    if not pool.auto_assign_enabled:
        return Response({"success": False, "message": "Auto-assignment is disabled."}, status=status.HTTP_400_BAD_REQUEST)
    try:
        result = assign_monthly_activation_credits(
            user.tenant,
            scope=pool.auto_assign_scope,
            months=1,
            actor=user,
            auto=True,
        )
    except ValueError as exc:
        return Response({"success": False, "message": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
    record_finance_activity(
        user.tenant,
        user,
        "token_auto_assign_run",
        f"Ran auto-assignment for {result['assigned']} student account(s).",
        amount=result["assigned"] * result["pool"].price_per_credit,
        metadata={"assigned": result["assigned"], "scope": pool.auto_assign_scope},
    )
    return Response({"success": True, "assigned": result["assigned"], "pool": ActivationCreditPoolSerializer(result["pool"]).data})


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def admin_bank_payment_ingest(request):
    """Ingest bank statement rows and match transfer narrations to student references."""
    user = request.user
    if user.role not in FINANCE_ROLES:
        return Response({"success": False, "message": "Finance access required."}, status=status.HTTP_403_FORBIDDEN)

    rows = request.data.get("transactions")
    if not isinstance(rows, list):
        rows = [request.data]

    processed = []
    for row in rows:
        try:
            payment, created = ingest_bank_payment(
                tenant=user.tenant,
                amount=row.get("amount"),
                narration=row.get("narration") or row.get("description") or "",
                bank_reference=row.get("bank_reference") or row.get("reference"),
                currency=row.get("currency") or "NGN",
                metadata={"raw": row},
                actor=user,
            )
            processed.append({"created": created, "payment": BankPaymentSerializer(payment).data})
            if created and payment.student_id and payment.status in {BankPayment.STATUS_CONFIRMED, BankPayment.STATUS_PARTIAL}:
                dispatch_payment_receipt_notifications(payment)
            record_finance_activity(
                user.tenant,
                user,
                "bank_payment_ingested",
                f"{'Created' if created else 'Updated'} bank payment record.",
                amount=payment.amount,
                currency=payment.currency,
                reference=payment.bank_reference,
                metadata={"status": payment.status, "student_id": str(payment.student_id or "")},
            )
        except Exception as exc:
            processed.append({"created": False, "error": str(exc), "raw": row})

    return Response({"success": True, "processed": processed, "finance": _admin_finance_snapshot(user)})


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def admin_bank_payment_recover(request, payment_id):
    """Manually attach an unmatched or wrong-narration payment to the correct student."""
    user = request.user
    if user.role not in FINANCE_ROLES:
        return Response({"success": False, "message": "Finance access required."}, status=status.HTTP_403_FORBIDDEN)

    payment = get_object_or_404(BankPayment.objects.filter(tenant=user.tenant), id=payment_id)
    student_lookup = str(request.data.get("student_id") or request.data.get("student") or "").strip()
    reference_code = str(request.data.get("reference_code") or "").strip()
    student = None

    if reference_code:
        reference = get_object_or_404(StudentPaymentReference.objects.filter(tenant=user.tenant), code__iexact=reference_code)
        student = reference.student
    elif student_lookup:
        student_qs = StudentProfile.objects.select_related("user").filter(user__tenant=user.tenant)
        student = student_qs.filter(
            Q(student_id__iexact=student_lookup)
            | Q(admission_number__iexact=student_lookup)
            | Q(user__email__iexact=student_lookup)
        ).first()
        if not student:
            try:
                student = student_qs.filter(id=student_lookup).first()
            except Exception:
                student = None
    if not student:
        return Response({"success": False, "message": "Student not found."}, status=status.HTTP_404_NOT_FOUND)

    reference = get_or_create_student_payment_reference(student)
    payment.payment_reference = reference
    payment.save(update_fields=["payment_reference", "updated_at"])
    payment = apply_bank_payment_to_student(payment, student, actor=user)
    if payment.student_id and payment.status in {BankPayment.STATUS_CONFIRMED, BankPayment.STATUS_PARTIAL}:
        dispatch_payment_receipt_notifications(payment)
    record_finance_activity(
        user.tenant,
        user,
        "bank_payment_recovered",
        f"Matched bank payment to {student.user.get_full_name() or student.user.email}.",
        amount=payment.amount,
        currency=payment.currency,
        reference=payment.bank_reference,
        metadata={"student_id": str(student.id), "status": payment.status},
    )
    return Response({"success": True, "payment": BankPaymentSerializer(payment).data, "finance": _admin_finance_snapshot(user)})


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def admin_cash_payment_record(request):
    """Record a walk-in cash payment for a known student and apply it immediately."""
    user = request.user
    if user.role not in FINANCE_ROLES:
        return Response({"success": False, "message": "Finance access required."}, status=status.HTTP_403_FORBIDDEN)

    student_lookup = str(request.data.get("student_id") or request.data.get("student") or "").strip()
    if not student_lookup:
        return Response({"success": False, "message": "Select a student."}, status=status.HTTP_400_BAD_REQUEST)

    student_qs = StudentProfile.objects.select_related("user").filter(user__tenant=user.tenant)
    student = student_qs.filter(
        Q(student_id__iexact=student_lookup)
        | Q(admission_number__iexact=student_lookup)
        | Q(user__email__iexact=student_lookup)
    ).first()
    if not student:
        try:
            student = student_qs.filter(id=student_lookup).first()
        except Exception:
            student = None
    if not student:
        return Response({"success": False, "message": "Student not found."}, status=status.HTTP_404_NOT_FOUND)

    try:
        payment = record_cash_payment(student, request.data.get("amount"), note=request.data.get("note"), actor=user)
    except ValueError as exc:
        return Response({"success": False, "message": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

    if payment.status in {BankPayment.STATUS_CONFIRMED, BankPayment.STATUS_PARTIAL}:
        dispatch_payment_receipt_notifications(payment)

    record_finance_activity(
        user.tenant,
        user,
        "cash_payment_recorded",
        f"Recorded cash payment from {student.user.get_full_name() or student.user.email}.",
        amount=payment.amount,
        currency=payment.currency,
        reference=payment.bank_reference,
        metadata={"student_id": str(student.id), "status": payment.status},
    )
    return Response({"success": True, "payment": BankPaymentSerializer(payment).data, "finance": _admin_finance_snapshot(user)})


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def admin_payment_receipt_resend(request, payment_id):
    """Re-send a receipt that never reached the parent.

    Receipts go out automatically on every recorded payment and are retried on
    a schedule, so this is the escape hatch for the case the sweep gives up on
    - a wrong phone number corrected after the fact, a mailbox that was full.
    Channels that already delivered are skipped by the notification service, so
    pressing this twice cannot double-notify a parent.
    """
    user = request.user
    if user.role not in FINANCE_ROLES:
        return Response({"success": False, "message": "Finance access required."}, status=status.HTTP_403_FORBIDDEN)

    payment = get_object_or_404(BankPayment.objects.filter(tenant=user.tenant), id=payment_id)
    if not payment.student_id:
        return Response(
            {"success": False, "message": "This payment is not matched to a student yet."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    # Resending is an explicit admin action on an existing payment, so it runs
    # inline - the admin gets the delivery outcome in the response instead of
    # having to reload to find out whether it worked.
    result = send_payment_receipt_notifications(payment)
    record_finance_activity(
        user.tenant,
        user,
        "payment_receipt_resent",
        f"Re-sent payment receipt for {payment.bank_reference}.",
        amount=payment.amount,
        currency=payment.currency,
        reference=payment.bank_reference,
        metadata={"status": result.get("status"), "attempts": payment.receipt_notification_attempts},
    )
    return Response({
        "success": True,
        "notification": {"status": result.get("status"), "receipt_url": result.get("receipt_url")},
        "payment": BankPaymentSerializer(payment).data,
    })


@api_view(["GET", "POST"])
@permission_classes([IsAuthenticated])
def admin_expense_records(request):
    """List or create tenant-scoped bills, expenses, and receipts."""
    user = request.user
    if user.role not in FINANCE_ROLES:
        return Response({"success": False, "message": "Finance access required."}, status=status.HTTP_403_FORBIDDEN)

    if request.method == "GET":
        records = ExpenseRecord.objects.filter(tenant=user.tenant)
        finance_snapshot = _admin_finance_snapshot(user)
        payroll_records = PayrollRecord.objects.select_related("staff").filter(staff__tenant=user.tenant).order_by("-year", "-month")[:80]
        staff_salary_total = StaffProfile.objects.filter(tenant=user.tenant).aggregate(total=Sum("base_salary"))["total"] or Decimal("0.00")
        unsettled_payroll = [
            item
            for item in payroll_records
            if item.status != PayrollRecord.PAID or item.balance_after_payment > 0
        ]
        unsettled_payroll_total = sum((item.balance_after_payment for item in unsettled_payroll), Decimal("0.00"))
        return Response(
            {
                "success": True,
                "records": ExpenseRecordSerializer(records, many=True).data,
                "class_fee_rows": finance_snapshot["class_fee_rows"],
                "finance_summary": FinanceSummarySerializer(finance_snapshot["finance_summary"]).data,
                "salary_payment_summary": {
                    "records": len(payroll_records),
                    "staff_salary_amount": staff_salary_total,
                    "unsettled_count": len(unsettled_payroll),
                    "unsettled_amount": unsettled_payroll_total,
                },
                "salary_payment_rows": [
                    {
                        "id": str(item.id),
                        "staff_id": str(item.staff_id),
                        "staff_name": item.staff.full_name,
                        "period": item.period_label,
                        "net_salary": item.net_salary,
                        "amount_paid": item.amount_paid,
                        "balance_after_payment": item.balance_after_payment,
                        "status": item.status,
                    }
                    for item in payroll_records
                ],
                "class_options": [
                    {
                        "id": item.id,
                        "label": _class_label(item),
                    }
                    for item in _classes_for_user(user).order_by("name", "section")[:200]
                ],
            }
        )

    serializer = ExpenseRecordSerializer(data=request.data)
    if not serializer.is_valid():
        return Response({"success": False, "message": "Invalid expense record.", "errors": serializer.errors}, status=status.HTTP_400_BAD_REQUEST)
    with transaction.atomic():
        record = serializer.save(tenant=user.tenant, created_by=user, currency="NGN")
        record_finance_activity(
            user.tenant,
            user,
            "expense_record_created",
            f"Created {record.record_type} record '{record.title}'.",
            amount=record.amount,
            currency=record.currency,
            reference=str(record.id),
            metadata={"status": record.status, "category": record.category},
        )
        finance_summary = compute_finance_summary(user)
    records = ExpenseRecord.objects.filter(tenant=user.tenant)
    return Response(
        {
            "success": True,
            "record": ExpenseRecordSerializer(record).data,
            "records": ExpenseRecordSerializer(records, many=True).data,
            "finance_summary": FinanceSummarySerializer(finance_summary).data,
        },
        status=status.HTTP_201_CREATED,
    )


@api_view(["GET", "PATCH", "DELETE"])
@permission_classes([IsAuthenticated])
def admin_expense_record_detail(request, record_id):
    """Get, update (e.g. settle an unsettled record), or delete one
    tenant-scoped expense tracker record."""
    user = request.user
    if user.role not in FINANCE_ROLES:
        return Response({"success": False, "message": "Finance access required."}, status=status.HTTP_403_FORBIDDEN)

    record = get_object_or_404(ExpenseRecord.objects.filter(tenant=user.tenant), id=record_id)

    if request.method == "GET":
        return Response({"success": True, "record": ExpenseRecordSerializer(record).data})

    if request.method == "PATCH":
        previous_status = record.status
        serializer = ExpenseRecordSerializer(record, data=request.data, partial=True)
        if not serializer.is_valid():
            return Response({"success": False, "message": "Invalid expense record.", "errors": serializer.errors}, status=status.HTTP_400_BAD_REQUEST)
        with transaction.atomic():
            record = serializer.save()
            if previous_status != ExpenseRecord.STATUS_PAID and record.status == ExpenseRecord.STATUS_PAID:
                record_finance_activity(
                    user.tenant,
                    user,
                    "expense_record_settled",
                    f"Settled {record.record_type} record '{record.title}'.",
                    amount=record.amount,
                    currency=record.currency,
                    reference=str(record.id),
                    metadata={"previous_status": previous_status, "status": record.status, "category": record.category},
                )
            else:
                record_finance_activity(
                    user.tenant,
                    user,
                    "expense_record_updated",
                    f"Updated {record.record_type} record '{record.title}'.",
                    amount=record.amount,
                    currency=record.currency,
                    reference=str(record.id),
                    metadata={"previous_status": previous_status, "status": record.status, "category": record.category},
                )
            finance_summary = compute_finance_summary(user)
        records = ExpenseRecord.objects.filter(tenant=user.tenant)
        return Response(
            {
                "success": True,
                "record": ExpenseRecordSerializer(record).data,
                "records": ExpenseRecordSerializer(records, many=True).data,
                "finance_summary": FinanceSummarySerializer(finance_summary).data,
            }
        )

    with transaction.atomic():
        record_finance_activity(
            user.tenant,
            user,
            "expense_record_deleted",
            f"Deleted {record.record_type} record '{record.title}'.",
            amount=record.amount,
            currency=record.currency,
            reference=str(record.id),
            metadata={"status": record.status, "category": record.category},
        )
        record.delete()
        finance_summary = compute_finance_summary(user)
    records = ExpenseRecord.objects.filter(tenant=user.tenant)
    return Response(
        {
            "success": True,
            "records": ExpenseRecordSerializer(records, many=True).data,
            "finance_summary": FinanceSummarySerializer(finance_summary).data,
        }
    )


def _payslip_payload(record, payroll, staff, payment_method, remarks):
    return {
        "expense_record_id": str(record.id),
        "payroll_record_id": str(payroll.id),
        "staff_id": str(staff.id),
        "staff_name": staff.full_name,
        "staff_code": staff.staff_code,
        "department": staff.department,
        "role": staff.role,
        "period": payroll.period_label,
        "basic_salary": payroll.base_salary,
        "allowances": payroll.allowances,
        "deductions": payroll.deductions,
        "advances_applied": payroll.advances_applied,
        "gross_salary": payroll.gross_salary,
        "net_salary": payroll.net_salary,
        "payment_date": record.record_date,
        "payment_method": payment_method,
        "status": payroll.status,
        "remarks": remarks,
    }


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def admin_expense_payslip_create(request):
    """Create or update a Payslip-typed ExpenseRecord backed by a real
    hr.PayrollRecord. Regenerating a payslip for the same staff/month updates
    the existing PayrollRecord (process_payroll's update_or_create, keyed on
    staff+year+month) and the same linked ExpenseRecord (keyed on the
    OneToOneField) instead of creating duplicate salary records."""
    user = request.user
    if user.role not in FINANCE_ROLES:
        return Response({"success": False, "message": "Finance access required."}, status=status.HTTP_403_FORBIDDEN)

    staff = get_object_or_404(StaffProfile.objects.filter(tenant=user.tenant), id=request.data.get("staff_id"))
    today = timezone.localdate()
    try:
        year = int(request.data.get("year") or today.year)
        month = int(request.data.get("month") or today.month)
    except (TypeError, ValueError):
        return Response({"success": False, "message": "Valid pay period year and month are required."}, status=status.HTTP_400_BAD_REQUEST)

    def _money(value):
        try:
            return Decimal(str(value or "0")).quantize(Decimal("0.01"))
        except Exception:
            return Decimal("0.00")

    allowances = _money(request.data.get("allowances"))
    deductions = _money(request.data.get("deductions"))
    payslip_status = str(request.data.get("status") or PayrollRecord.APPROVED).strip().lower()
    if payslip_status not in {PayrollRecord.DRAFT, PayrollRecord.APPROVED, PayrollRecord.PAID}:
        return Response({"success": False, "message": "Status must be draft, approved, or paid."}, status=status.HTTP_400_BAD_REQUEST)
    payment_method = str(request.data.get("payment_method") or "").strip()
    remarks = str(request.data.get("remarks") or "").strip()
    notes = " ".join(part for part in [f"Payment method: {payment_method}." if payment_method else "", remarks] if part)

    payment_date = parse_date(str(request.data.get("payment_date"))) if request.data.get("payment_date") else None
    payment_date = payment_date or today

    from hr.views import process_payroll  # local import: HR views already import finance.services at module level

    try:
        payroll, created, _transfer_reference, _transfer_result = process_payroll(
            staff, year, month, allowances, deductions, Decimal("0.00"),
            pay_with_flutterwave=False, actor=user, notes=notes,
            status_override=payslip_status, mark_fully_paid=(payslip_status == PayrollRecord.PAID),
        )
    except ValueError as exc:
        return Response({"success": False, "message": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

    expense_status = {
        PayrollRecord.DRAFT: ExpenseRecord.STATUS_PENDING,
        PayrollRecord.APPROVED: ExpenseRecord.STATUS_DUE,
        PayrollRecord.PAID: ExpenseRecord.STATUS_PAID,
    }[payroll.status]

    record, _record_created = ExpenseRecord.objects.update_or_create(
        payroll_record=payroll,
        defaults={
            "tenant": user.tenant,
            "title": f"Payslip - {staff.full_name} - {payroll.period_label}",
            "vendor": staff.full_name,
            "phone_number": staff.phone or "",
            "amount": payroll.net_salary,
            "currency": "NGN",
            "record_type": ExpenseRecord.TYPE_PAYSLIP,
            "category": "Payroll",
            "color": "#7c3aed",
            "status": expense_status,
            "record_date": payment_date,
            "note": notes,
            "created_by": user,
        },
    )

    record_finance_activity(
        user.tenant,
        user,
        "payslip_generated",
        f"Payslip generated for {staff.full_name} ({payroll.period_label}).",
        amount=payroll.net_salary,
        reference=str(record.id),
        metadata={"staff_id": str(staff.id), "period": payroll.period_label, "payroll_id": str(payroll.id)},
    )

    records = ExpenseRecord.objects.filter(tenant=user.tenant)
    return Response(
        {
            "success": True,
            "record": ExpenseRecordSerializer(record).data,
            "records": ExpenseRecordSerializer(records, many=True).data,
            "payslip": _payslip_payload(record, payroll, staff, payment_method, remarks),
            "finance_summary": FinanceSummarySerializer(compute_finance_summary(user)).data,
        },
        status=status.HTTP_201_CREATED if created else status.HTTP_200_OK,
    )


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def admin_expense_payslip_send(request, record_id):
    """Send a previously-generated payslip to the employee via email or a
    secure SMS link, reusing this session's existing SMS-wallet/receipt-link
    infrastructure (create_receipt_link + send_wallet_sms) rather than a new
    pipeline - so a payslip SMS is wallet-billed and only charged after the
    provider confirms delivery, exactly like every other SMS feature."""
    user = request.user
    if user.role not in FINANCE_ROLES:
        return Response({"success": False, "message": "Finance access required."}, status=status.HTTP_403_FORBIDDEN)

    record = get_object_or_404(
        ExpenseRecord.objects.filter(tenant=user.tenant, record_type=ExpenseRecord.TYPE_PAYSLIP).select_related("payroll_record", "payroll_record__staff"),
        id=record_id,
    )
    payroll = record.payroll_record
    if not payroll:
        return Response({"success": False, "message": "This payslip is not linked to a payroll record."}, status=status.HTTP_400_BAD_REQUEST)
    staff = payroll.staff

    channel = str(request.data.get("channel") or "").strip().lower()
    if channel not in {"email", "sms"}:
        return Response({"success": False, "message": "channel must be 'email' or 'sms'."}, status=status.HTTP_400_BAD_REQUEST)

    school_name = getattr(user.tenant, "name", "") or "School"
    payslip_data = {
        "type": "payslip",
        "school_name": school_name,
        "staff_name": staff.full_name,
        "staff_code": staff.staff_code,
        "department": staff.department,
        "role": staff.role,
        "period": payroll.period_label,
        "basic_salary": str(payroll.base_salary),
        "allowances": str(payroll.allowances),
        "deductions": str(payroll.deductions),
        "net_salary": str(payroll.net_salary),
        "payment_date": record.record_date.strftime("%d %b %Y") if record.record_date else "",
        "status": payroll.status,
        "generated_at": timezone.now().strftime("%d %b %Y"),
    }

    if channel == "email":
        recipient = str(request.data.get("recipient") or staff.email or "").strip()
        if not recipient:
            return Response({"success": False, "message": "No employee email on file - provide a recipient."}, status=status.HTTP_400_BAD_REQUEST)
        receipt_url = create_receipt_link(payslip_data, tenant=user.tenant, receipt_type="payslip")
        result = send_payslip_email(recipient, payslip_data, receipt_url=receipt_url)
        if not result.get("sent"):
            return Response({"success": False, "message": result.get("email_error") or "Could not send payslip email."}, status=status.HTTP_502_BAD_GATEWAY)
        return Response({"success": True, "message": f"Payslip emailed to {recipient}."})

    recipient = str(request.data.get("recipient") or staff.phone or "").strip()
    if not recipient:
        return Response({"success": False, "message": "No employee phone number on file - provide a recipient."}, status=status.HTTP_400_BAD_REQUEST)
    receipt_url = create_receipt_link(payslip_data, tenant=user.tenant, phone=recipient, receipt_type="payslip")
    message = f"{school_name} Payslip: {staff.full_name} ({payroll.period_label}). Net pay: {_format_naira(payroll.net_salary)}. View: {sms_compact_url(receipt_url)}"
    try:
        log = send_wallet_sms(user.tenant, recipient, message, category=SmsMessageLog.OTHER, actor=user, narration="Payslip")
    except (InsufficientSmsCreditsError, SmsWalletLockedError) as exc:
        return Response({"success": False, "message": str(exc)}, status=status.HTTP_402_PAYMENT_REQUIRED)
    if log.delivery_status not in (SmsMessageLog.SENT, SmsMessageLog.DELIVERED):
        return Response({"success": False, "message": sms_failure_reason(log)}, status=status.HTTP_502_BAD_GATEWAY)
    return Response({"success": True, "message": f"Payslip SMS sent to {recipient}."})


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def bank_payment_receipt(request, payment_id):
    """Download a lightweight receipt for a confirmed/partial bank payment."""
    user = request.user
    payments = BankPayment.objects.select_related("student", "student__user", "payment_reference", "tenant")
    if user.role == "student":
        payments = payments.filter(student__user=user)
    elif user.role in FINANCE_ROLES:
        payments = payments.filter(tenant=user.tenant)
    else:
        return Response({"success": False, "message": "Access denied."}, status=status.HTTP_403_FORBIDDEN)

    payment = get_object_or_404(payments, id=payment_id)
    if payment.status not in {BankPayment.STATUS_CONFIRMED, BankPayment.STATUS_PARTIAL}:
        return Response({"success": False, "message": "Receipt is available after a payment is confirmed."}, status=status.HTTP_400_BAD_REQUEST)

    school = payment.tenant
    student_name = payment.student.user.get_full_name() or payment.student.user.email if payment.student_id else "Unmatched"
    content = "\n".join(
        [
            f"{school.name if school else 'SchoolDom'} Payment Receipt",
            f"Logo: {getattr(school, 'logo', '') or 'School logo'}",
            f"Receipt: {payment.receipt_number or payment.bank_reference}",
            f"Student: {student_name}",
            f"Reference Code: {payment.payment_reference.code if payment.payment_reference_id else ''}",
            f"Amount: {payment.currency} {payment.amount}",
            f"Applied: {payment.currency} {payment.applied_amount}",
            f"Status: {payment.status.title()}",
            f"Bank Reference: {payment.bank_reference}",
            f"Narration: {payment.narration}",
            f"Date: {payment.matched_at or payment.created_at}",
        ]
    )
    response = HttpResponse(content, content_type="text/plain")
    response["Content-Disposition"] = f'attachment; filename="receipt-{payment.receipt_number or payment.bank_reference}.txt"'
    return response


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def admin_adjust_wallet(request):
    """Allow admins to adjust an existing student wallet balance."""
    user = request.user
    if user.role not in FINANCE_ROLES:
        return Response({"success": False, "message": "Finance access required."}, status=status.HTTP_403_FORBIDDEN)

    student_id = request.data.get("student_id")
    direction = str(request.data.get("direction", "")).lower()
    note = str(request.data.get("note", "")).strip() or "Manual adjustment"

    try:
        amount = _parse_amount(request.data.get("amount"))
    except ValueError as exc:
        return Response({"success": False, "message": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

    lookup_value = str(student_id or "").strip()
    student_qs = StudentProfile.objects.select_related("user").filter(user__tenant=user.tenant)
    student_profile = None
    # Try UUID lookup first; if it fails, fall back to student identifiers
    try:
        student_profile = student_qs.get(id=lookup_value)
    except Exception:
        student_profile = student_qs.filter(
            Q(student_id=lookup_value) | Q(admission_number=lookup_value) | Q(user__email=lookup_value)
        ).first()
    if not student_profile:
        return Response({"success": False, "message": "Student not found."}, status=status.HTTP_404_NOT_FOUND)
    wallet = Wallet.objects.filter(user=student_profile.user).first()
    if not wallet:
        return Response(
            {"success": False, "message": "Student wallet not provisioned (wallets are created via student registration)."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    reference = generate_reference("ADJ")
    try:
        if direction == "credit":
            wallet = credit_wallet(wallet, amount, Transaction.ADJUSTMENT_CREDIT, reference, narration=note, created_by=user)
        elif direction == "debit":
            wallet = debit_wallet(wallet, amount, Transaction.ADJUSTMENT_DEBIT, reference, narration=note, created_by=user)
        else:
            return Response(
                {"success": False, "message": "direction must be 'credit' or 'debit'."},
                status=status.HTTP_400_BAD_REQUEST,
            )
    except ValueError as exc:
        return Response({"success": False, "message": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
    record_finance_activity(
        user.tenant,
        user,
        "wallet_adjusted",
        f"{direction.title()} adjustment for {student_profile.user.get_full_name() or student_profile.user.email}.",
        amount=amount,
        reference=reference,
        metadata={"direction": direction, "student_id": str(student_profile.id), "note": note},
    )

    return Response(
        {
            "success": True,
            "wallet": WalletSerializer(wallet).data,
            "reference": reference,
        }
    )


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def admin_assign_fee(request):
    """Create or update a manual school fee schedule for a student."""
    user = request.user
    if user.role not in FINANCE_ROLES:
        return Response({"success": False, "message": "Finance access required."}, status=status.HTTP_403_FORBIDDEN)

    student_id = request.data.get("student_id")
    title = str(request.data.get("title", "")).strip() or "School Fee"
    due_date_raw = str(request.data.get("due_date", "")).strip()
    auto_deduct = bool(request.data.get("auto_deduct", True))

    try:
        amount = _parse_amount(request.data.get("amount"))
    except ValueError as exc:
        return Response({"success": False, "message": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

    try:
        due_date = datetime.strptime(due_date_raw, "%Y-%m-%d").date()
    except Exception:
        return Response({"success": False, "message": "due_date must be YYYY-MM-DD."}, status=status.HTTP_400_BAD_REQUEST)

    student_profile = get_object_or_404(
        StudentProfile.objects.select_related("user").filter(user__tenant=user.tenant),
        id=student_id,
    )
    fee, created = SchoolFee.objects.update_or_create(
        student=student_profile,
        class_fee__isnull=True,
        title=title,
        due_date=due_date,
        defaults={
            "amount": amount,
            "currency": "NGN",
            "auto_deduct": auto_deduct,
            "is_customized": True,
            "created_by": user,
        },
    )
    reconcile_fee_status(fee)
    fee.refresh_from_db()
    record_finance_activity(
        user.tenant,
        user,
        "manual_fee_assigned",
        f"{'Created' if created else 'Updated'} manual fee '{fee.title}' for {student_profile.user.get_full_name() or student_profile.user.email}.",
        amount=fee.amount,
        currency=fee.currency,
        reference=str(fee.id),
        metadata={"student_id": str(student_profile.id), "due_date": str(fee.due_date)},
    )
    return Response(
        {"success": True, "fee": SchoolFeeSerializer(fee).data, "finance": _admin_finance_snapshot(user)},
        status=status.HTTP_201_CREATED if created else status.HTTP_200_OK,
    )


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def admin_withdraw(request):
    """Withdraw funds from the admin wallet to a bank account."""
    user = request.user
    if user.role != "super_admin":
        return Response({"success": False, "message": "School-fee withdrawals are restricted."}, status=status.HTTP_403_FORBIDDEN)

    try:
        amount = _parse_amount(request.data.get("amount"))
    except ValueError as exc:
        return Response({"success": False, "message": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

    bank_account_number = str(request.data.get("account_number", "")).strip()
    bank_code = str(request.data.get("bank_name") or request.data.get("bank_code", "")).strip()
    bank_account_name = str(request.data.get("account_name", "")).strip()
    if not (bank_account_number and bank_code and bank_account_name):
        return Response(
            {"success": False, "message": "account_number, bank_name, and account_name are required."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    admin_wallet = get_or_create_admin_wallet(user.tenant)
    if admin_wallet.balance < amount:
        return Response({"success": False, "message": "Insufficient admin wallet balance."}, status=status.HTTP_400_BAD_REQUEST)

    reference = generate_reference("WD")
    bank_payload = {
        "account_number": bank_account_number,
        "bank_code": bank_code,
        "account_name": bank_account_name,
    }

    admin_wallet.bank_account_name = bank_account_name
    admin_wallet.bank_account_number = bank_account_number
    admin_wallet.bank_code = bank_code
    admin_wallet.last_settled_at = timezone.now()
    admin_wallet.save(
        update_fields=[
            "bank_account_name",
            "bank_account_number",
            "bank_code",
            "last_settled_at",
            "updated_at",
        ]
    )

    # Submitted through the request queue rather than processed inline: a
    # Paystack/Flutterwave/Kuda timeout or 5xx no longer fails the withdrawal
    # outright - it's retried in the background with exponential backoff
    # (see finance/queue_handlers.py::handle_wallet_withdrawal). Re-submitting
    # the same amount/account while a withdrawal is still in flight is
    # deduplicated automatically instead of double-processing.
    queued_request, created = enqueue_request(
        tenant=user.tenant,
        requester=user,
        request_type="wallet_withdrawal",
        payload={
            "admin_wallet_id": str(admin_wallet.id),
            "amount": str(amount),
            "reference": reference,
            "bank_payload": bank_payload,
            "actor_id": str(user.id),
            "provider": active_payment_provider(),
        },
        # `reference` above is freshly generated on every call and must NOT
        # affect deduplication - only the actual withdrawal content
        # (amount + destination account) defines "the same request".
        dedupe_payload={"amount": str(amount), "bank_payload": bank_payload},
    )
    record_finance_activity(
        user.tenant,
        user,
        "admin_withdrawal_requested",
        "Requested withdrawal from admin wallet.",
        amount=amount,
        currency=admin_wallet.currency,
        reference=reference,
        metadata={"queued_request_id": str(queued_request.id), "account_number": bank_account_number, "bank_code": bank_code},
    )

    if not created:
        return Response(
            {
                "success": True,
                "status": queued_request.status,
                "request_id": str(queued_request.id),
                "admin_wallet": AdminWalletSerializer(admin_wallet).data,
                "message": "A matching withdrawal is already being processed.",
            }
        )

    return Response(
        {
            "success": True,
            "status": queued_request.status,
            "request_id": str(queued_request.id),
            "admin_wallet": AdminWalletSerializer(admin_wallet).data,
            "reference": reference,
            "message": f"Withdrawal queued for processing via {active_payment_provider().title()}.",
        }
    )


# ============================================================
# PAYSTACK SPLIT PAYMENT VIEWS
# ============================================================

@csrf_exempt
@api_view(["POST"])
@permission_classes([AllowAny])
def paystack_webhook(request):
    """Receive and process Paystack webhook events (charge.success)."""
    signature = request.META.get("HTTP_X_PAYSTACK_SIGNATURE", "")
    if not verify_paystack_webhook_signature(signature, request.body):
        return Response({"success": False, "message": "Invalid signature."}, status=status.HTTP_401_UNAUTHORIZED)

    try:
        data = request.data
        result = process_paystack_webhook(data)
    except Exception as exc:
        return Response({"success": False, "message": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

    return Response({"success": True, "result": result})


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def paystack_initialize_payment(request):
    """
    Initialize a Paystack split payment for one or more school fees.

    Body: { "fee_ids": ["uuid", ...], "callback_url": "https://..." }
    """
    user = request.user
    fee_ids = request.data.get("fee_ids") or []
    callback_url = str(request.data.get("callback_url") or "").strip()

    if not fee_ids:
        return Response({"success": False, "message": "fee_ids is required."}, status=status.HTTP_400_BAD_REQUEST)

    # Verify all fees belong to the parent's children
    from users.models import ParentProfile
    try:
        parent_profile = ParentProfile.objects.get(user=user)
    except ParentProfile.DoesNotExist:
        return Response({"success": False, "message": "Parent profile not found."}, status=status.HTTP_403_FORBIDDEN)

    student_ids = list(parent_profile.children.values_list("id", flat=True))
    fees = SchoolFee.objects.filter(id__in=fee_ids, student_id__in=student_ids).exclude(status=SchoolFee.STATUS_PAID)
    if not fees.exists():
        return Response({"success": False, "message": "No valid unpaid fees found."}, status=status.HTTP_404_NOT_FOUND)
    if fees.count() != len(fee_ids):
        return Response({"success": False, "message": "Some fee IDs are invalid or already paid."}, status=status.HTTP_400_BAD_REQUEST)

    try:
        result = initialize_paystack_school_fee_payment(
            parent_user=user,
            fee_ids=list(fees.values_list("id", flat=True)),
            callback_url=callback_url,
        )
    except ValueError as exc:
        return Response({"success": False, "message": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
    except Exception as exc:
        return Response({"success": False, "message": str(exc)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    return Response({"success": True, **result})


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def paystack_verify_payment(request):
    """
    Verify a Paystack payment after redirect callback.

    Query: ?reference=PAY_xxx
    """
    reference = str(request.query_params.get("reference") or "").strip()
    if not reference:
        return Response({"success": False, "message": "reference is required."}, status=status.HTTP_400_BAD_REQUEST)

    user = request.user
    try:
        tx = Transaction.objects.get(paystack_ref=reference)
    except Transaction.DoesNotExist:
        return Response({"success": False, "message": "Transaction not found."}, status=status.HTTP_404_NOT_FOUND)

    is_owner = tx.parent_id == user.id
    is_school_finance = user.role in FINANCE_ROLES and user.tenant_id and str(tx.school_id) == str(user.tenant_id)
    if not (is_owner or is_school_finance):
        return Response({"success": False, "message": "Transaction not found."}, status=status.HTTP_404_NOT_FOUND)

    if tx.status == Transaction.STATUS_SUCCESS:
        return Response({
            "success": True,
            "status": "already_processed",
            "allocation_status": tx.allocation_status,
            "transaction": TransactionSerializer(tx).data,
        })

    try:
        verification = verify_paystack_transaction(reference)
    except Exception as exc:
        return Response({"success": False, "message": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

    if verification.get("status") != "success":
        tx.status = Transaction.STATUS_FAILED
        tx.save(update_fields=["status", "updated_at"])
        return Response({"success": False, "message": "Payment not successful.", "paystack_status": verification.get("status")})

    amount_paid = Decimal(str(verification.get("amount", 0))) / 100

    from django.db import transaction as db_transaction
    with db_transaction.atomic():
        locked_tx = Transaction.objects.select_for_update().get(pk=tx.pk)
        if locked_tx.status == Transaction.STATUS_SUCCESS:
            return Response({
                "success": True,
                "status": "already_processed",
                "allocation_status": locked_tx.allocation_status,
                "transaction": TransactionSerializer(locked_tx).data,
            })
        locked_tx.status = Transaction.STATUS_SUCCESS
        locked_tx.amount = amount_paid
        locked_tx.metadata = {**(locked_tx.metadata or {}), "verification": verification}
        locked_tx.save(update_fields=["status", "amount", "metadata", "updated_at"])

    tx.refresh_from_db()
    parent_id = tx.parent_id
    allocation_result = allocate_split_payment(
        parent_id=parent_id,
        amount_paid=amount_paid,
        paystack_ref=reference,
        transaction_id=tx.id,
    )

    if allocation_result["overpayment"] > 0:
        tx.allocation_status = Transaction.ALLOCATION_OVERPAID
    elif any(a["status"] == "partial" for a in allocation_result["allocations"]):
        tx.allocation_status = Transaction.ALLOCATION_PARTIAL
    else:
        tx.allocation_status = Transaction.ALLOCATION_ALLOCATED
    tx.save(update_fields=["allocation_status", "updated_at"])

    return Response({
        "success": True,
        "status": "processed",
        "allocation": allocation_result,
        "transaction": TransactionSerializer(tx).data,
    })


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def paystack_payment_breakdown(request):
    """
    Return the fee breakdown a parent sees before paying.

    Body: { "fee_ids": ["uuid", ...] }
    Shows: student name, class, tuition, ₦100 Schooldom fee, ₦300 Paystack fee, total per fee.
    """
    fee_ids = request.data.get("fee_ids") or []
    if not fee_ids:
        return Response({"success": False, "message": "fee_ids is required."}, status=status.HTTP_400_BAD_REQUEST)

    from users.models import ParentProfile
    try:
        parent_profile = ParentProfile.objects.get(user=request.user)
    except ParentProfile.DoesNotExist:
        return Response({"success": False, "message": "Parent profile not found."}, status=status.HTTP_403_FORBIDDEN)
    student_ids = list(parent_profile.children.values_list("id", flat=True))

    try:
        breakdown = get_fee_payment_breakdown(fee_ids, student_ids)
    except ValueError as exc:
        return Response({"success": False, "message": str(exc)}, status=status.HTTP_404_NOT_FOUND)

    return Response({"success": True, **breakdown})


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def admin_test_sms(request):
    """Send a test SMS via Sendchamp and return the raw provider response. Finance admin only."""
    user = request.user
    if user.role not in FINANCE_ROLES:
        return Response({"success": False, "message": "Permission denied."}, status=status.HTTP_403_FORBIDDEN)
    to_phone = str(request.data.get("phone", "")).strip()
    message = str(request.data.get("message", "SchoolDom SMS test message.")).strip()
    if not to_phone:
        return Response({"success": False, "message": "phone is required."}, status=status.HTTP_400_BAD_REQUEST)
    normalized = normalize_phone_number(to_phone)
    result = send_sendchamp_sms(to_phone, message)
    return Response({
        "success": True,
        "normalized_phone": normalized,
        "sendchamp_response": result,
    })


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def admin_test_email(request):
    """Send a test receipt email and return the result. Finance admin only."""
    user = request.user
    if user.role not in FINANCE_ROLES:
        return Response({"success": False, "message": "Permission denied."}, status=status.HTTP_403_FORBIDDEN)
    to_email = str(request.data.get("email", "")).strip() or user.email
    if not to_email:
        return Response({"success": False, "message": "email is required."}, status=status.HTTP_400_BAD_REQUEST)

    from finance.services import send_payment_receipt
    sample_data = {
        "school_name": user.tenant.name if hasattr(user, "tenant") and user.tenant else "Test School",
        "student_name": "Test Student",
        "class_name": "JSS 1",
        "amount_paid": "15000.00",
        "fee_total": "15000.00",
        "balance_remaining": "0.00",
        "payment_status": "paid",
        "payment_date": timezone.now().strftime("%d %b %Y"),
        "reference": "TEST-REF-001",
    }
    result = send_payment_receipt(
        to_email,
        "Test receipt from SchoolDom",
        data=sample_data,
        receipt_type="receipt",
    )
    return Response({"success": result.get("sent", False), "to": to_email, "result": result})


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def admin_paystack_banks(request):
    """List Nigerian banks (name + settlement code) for the subaccount setup form. Finance roles only."""
    user = request.user
    if user.role not in FINANCE_ROLES:
        return Response({"success": False, "message": "Permission denied."}, status=status.HTTP_403_FORBIDDEN)
    try:
        banks = list_paystack_banks()
    except Exception as exc:
        return Response({"success": False, "message": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
    return Response({"success": True, "banks": banks})


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def admin_paystack_resolve_account(request):
    """Resolve a bank account number to its registered name via Paystack. Finance roles only."""
    user = request.user
    if user.role not in FINANCE_ROLES:
        return Response({"success": False, "message": "Permission denied."}, status=status.HTTP_403_FORBIDDEN)
    account_number = request.query_params.get("account_number", "").strip()
    bank_code = request.query_params.get("bank_code", "").strip()
    if not account_number or not bank_code:
        return Response({"success": False, "message": "account_number and bank_code are required."}, status=status.HTTP_400_BAD_REQUEST)
    try:
        result = resolve_paystack_account(account_number, bank_code)
    except Exception as exc:
        return Response({"success": False, "message": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
    return Response({"success": True, **result})


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def admin_paystack_split_setup(request):
    """
    Create a Paystack subaccount for the school so parents can pay via split.

    Body: { "account_number": "...", "bank_code": "...", "account_name": "..." }
    (Uses existing bank details on AdminWallet if not supplied.)
    Admin / principal / accountant only.
    """
    user = request.user
    if user.role not in FINANCE_ROLES:
        return Response({"success": False, "message": "Permission denied."}, status=status.HTTP_403_FORBIDDEN)

    admin_wallet = get_or_create_admin_wallet(user.tenant)

    account_number = str(request.data.get("account_number") or admin_wallet.bank_account_number or "").strip()
    bank_code = str(request.data.get("bank_code") or admin_wallet.bank_code or "").strip()
    account_name = str(request.data.get("account_name") or admin_wallet.bank_account_name or "").strip()

    if not (account_number and bank_code and account_name):
        return Response(
            {"success": False, "message": "account_number, bank_code, and account_name are required."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    # Persist bank details if they changed
    changed = []
    for field, val in [("bank_account_number", account_number), ("bank_code", bank_code), ("bank_account_name", account_name)]:
        if getattr(admin_wallet, field) != val:
            setattr(admin_wallet, field, val)
            changed.append(field)
    if changed:
        changed.append("updated_at")
        admin_wallet.save(update_fields=changed)

    if admin_wallet.subaccount_code:
        # The subaccount may have been deleted on the Paystack dashboard —
        # verify and clear the stale code so setup can proceed.
        sync = sync_school_subaccount_with_paystack(user.tenant)
        if sync.get("cleared"):
            admin_wallet.refresh_from_db()
            record_finance_activity(
                user.tenant, user,
                "paystack_subaccount_cleared",
                "Paystack subaccount was deleted on Paystack; cleared stale code.",
                reference=sync.get("old_code", ""),
            )
        else:
            return Response({
                "success": True,
                "message": "Subaccount already exists.",
                "subaccount_code": admin_wallet.subaccount_code,
            })

    try:
        subaccount = create_paystack_subaccount(
            business_name=user.tenant.name if user.tenant else account_name,
            bank_code=bank_code,
            account_number=account_number,
        )
    except Exception as exc:
        return Response({"success": False, "message": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

    admin_wallet.subaccount_code = subaccount["subaccount_code"]
    admin_wallet.save(update_fields=["subaccount_code", "updated_at"])

    record_finance_activity(
        user.tenant, user,
        "paystack_subaccount_created",
        "Created Paystack subaccount for split payments.",
        reference=subaccount["subaccount_code"],
    )
    return Response({
        "success": True,
        "message": "Paystack subaccount created.",
        "subaccount_code": admin_wallet.subaccount_code,
        "subaccount": subaccount,
    })


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def admin_paystack_split_status(request):
    """Get Paystack split payment configuration status for the school."""
    user = request.user
    if user.role not in FINANCE_ROLES:
        return Response({"success": False, "message": "Permission denied."}, status=status.HTTP_403_FORBIDDEN)

    split_status = get_school_payment_split_status(user.tenant)
    return Response({"success": True, **split_status})


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def parent_transaction_history(request):
    """
    Return Paystack split payment history for the authenticated parent.

    Query: ?page=1&limit=20&status=successful
    """
    user = request.user
    qs = Transaction.objects.filter(parent_id=user.id, tx_type=Transaction.SPLIT_PAYMENT).order_by("-created_at")

    status_filter = str(request.query_params.get("status") or "").strip()
    if status_filter:
        qs = qs.filter(status=status_filter)

    try:
        limit = max(1, min(int(request.query_params.get("limit") or 20), 100))
        page = max(1, int(request.query_params.get("page") or 1))
    except (ValueError, TypeError):
        limit, page = 20, 1

    offset = (page - 1) * limit
    total = qs.count()
    transactions = qs[offset: offset + limit]

    return Response({
        "success": True,
        "count": total,
        "page": page,
        "limit": limit,
        "results": TransactionSerializer(transactions, many=True).data,
    })


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def transaction_detail(request, reference):
    """Return full detail for a single split payment transaction."""
    user = request.user
    try:
        tx = Transaction.objects.get(paystack_ref=reference)
    except Transaction.DoesNotExist:
        try:
            tx = Transaction.objects.get(reference=reference)
        except Transaction.DoesNotExist:
            return Response({"success": False, "message": "Transaction not found."}, status=status.HTTP_404_NOT_FOUND)

    # Parents see only their own; admin/finance see only their own school's.
    if user.role == "parent":
        if tx.parent_id != user.id:
            return Response({"success": False, "message": "Not found."}, status=status.HTTP_404_NOT_FOUND)
    elif user.role not in FINANCE_ROLES or str(tx.school_id) != str(user.tenant_id):
        return Response({"success": False, "message": "Not found."}, status=status.HTTP_404_NOT_FOUND)

    allocations = list(
        tx.allocations.select_related("fee", "fee__student", "fee__student__user", "fee__student__current_class")
        .values(
            "id", "amount_allocated", "paystack_fee_paid", "schooldom_fee_paid", "status",
            "fee__id", "fee__title", "fee__amount",
            "fee__student__user__first_name", "fee__student__user__last_name",
        )
    )

    return Response({
        "success": True,
        "transaction": TransactionSerializer(tx).data,
        "breakdown": tx.get_breakdown(),
        "allocations": allocations,
    })


# ─── Parent Dashboard ────────────────────────────────────────────────────────


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def parent_dashboard(request):
    """
    Return a parent's full dashboard: virtual account, children fee summaries, and recent payments.
    Only accessible by the authenticated parent or finance/admin roles.
    """
    user = request.user
    from users.models import ParentProfile

    try:
        parent_profile = ParentProfile.objects.prefetch_related(
            "children", "children__fees"
        ).get(user=user)
    except ParentProfile.DoesNotExist:
        return Response(
            {"success": False, "message": "Parent profile not found."},
            status=status.HTTP_404_NOT_FOUND,
        )

    # Virtual account
    virtual_account = None
    try:
        vac = ParentVirtualAccount.objects.get(parent=user, is_active=True)
        virtual_account = {
            "account_number": vac.account_number,
            "bank_name": vac.bank_name,
            "account_name": vac.account_name,
            "provider": vac.provider,
            "paystack_reference": vac.paystack_reference,
        }
    except ParentVirtualAccount.DoesNotExist:
        pass

    # Build per-child fee summary
    children_data = []
    total_expected = Decimal("0")
    total_paid = Decimal("0")

    for student in parent_profile.children.select_related("user", "current_class").all():
        fees_qs = list(SchoolFee.objects.filter(student=student).order_by("due_date"))
        # fee_paid_amount, not the amount_paid column: offline payments (cash,
        # POS, matched bank transfer) never write that column, so reading it
        # here showed parents who had already paid at the front desk a balance
        # of the full fee.
        paid_amounts = bulk_fee_paid_amounts(fees_qs)
        student_expected = sum((Decimal(str(f.amount or 0)) for f in fees_qs), Decimal("0"))
        student_paid = sum((paid_amounts.get(f.id, Decimal("0.00")) for f in fees_qs), Decimal("0"))
        student_remaining = max(student_expected - student_paid, Decimal("0"))

        fee_rows = []
        for f in fees_qs:
            paid = paid_amounts.get(f.id, Decimal("0.00"))
            remaining = max(Decimal(str(f.amount or 0)) - paid, Decimal("0"))
            fee_rows.append({
                "id": str(f.id),
                "title": f.title,
                "amount": float(f.amount),
                "amount_paid": float(paid),
                "remaining": float(remaining),
                "status": f.status,
                "due_date": f.due_date.isoformat() if f.due_date else None,
                "last_payment_date": f.last_payment_date.isoformat() if f.last_payment_date else None,
            })

        student_obj = student
        class_obj = getattr(student_obj, "current_class", None)
        children_data.append({
            "id": str(student_obj.id),
            "name": student_obj.user.get_full_name() if student_obj.user else "",
            "class_name": class_obj.name if class_obj else "",
            "student_id": getattr(student_obj, "student_id", "") or getattr(student_obj, "admission_number", ""),
            "fees": fee_rows,
            "total_expected": float(student_expected),
            "total_paid": float(student_paid),
            "total_remaining": float(student_remaining),
        })
        total_expected += student_expected
        total_paid += student_paid

    # Recent payments
    recent_txs = (
        Transaction.objects.filter(
            parent_id=user.id,
            tx_type=Transaction.SPLIT_PAYMENT,
            status=Transaction.STATUS_SUCCESS,
        )
        .order_by("-created_at")[:15]
    )

    return Response({
        "success": True,
        "parent": {
            "name": user.get_full_name() or user.email,
            "email": user.email,
            "preferred_contact": parent_profile.preferred_contact,
        },
        "virtual_account": virtual_account,
        "summary": {
            "total_expected": float(total_expected),
            "total_paid": float(total_paid),
            "total_remaining": float(max(total_expected - total_paid, Decimal("0"))),
            "children_count": len(children_data),
            # Prepaid balance held on the children's wallets (e.g. from
            # overpayment) that will automatically apply to their next fees.
            "total_credit_balance": float(
                Wallet.objects.filter(user__student_profile__in=parent_profile.children.all())
                .aggregate(total=Sum("balance"))["total"] or Decimal("0")
            ),
        },
        "children": children_data,
        "recent_payments": TransactionSerializer(recent_txs, many=True).data,
    })


# ─── Admin: Virtual Account Management ───────────────────────────────────────


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def admin_list_virtual_accounts(request):
    """List all parent virtual account assignments for this school (finance roles only)."""
    user = request.user
    if user.role not in FINANCE_ROLES:
        return Response({"success": False, "message": "Permission denied."}, status=status.HTTP_403_FORBIDDEN)

    vacs = (
        ParentVirtualAccount.objects.filter(tenant=user.tenant)
        .select_related("parent", "assigned_by")
        .order_by("-created_at")
    )
    data = [
        {
            "parent_id": str(v.parent.id),
            "parent_name": v.parent.get_full_name() or v.parent.email,
            "parent_email": v.parent.email,
            "account_number": v.account_number,
            "bank_name": v.bank_name,
            "account_name": v.account_name,
            "provider": v.provider,
            "paystack_reference": v.paystack_reference,
            "is_active": v.is_active,
            "notes": v.notes,
            "assigned_at": v.created_at.isoformat(),
            "assigned_by": v.assigned_by.get_full_name() if v.assigned_by else None,
        }
        for v in vacs
    ]

    parents_with_account = {v.parent_id for v in vacs}
    parents_without_account = [
        {
            "parent_id": str(p.id),
            "parent_name": p.get_full_name() or p.email,
            "parent_email": p.email,
        }
        for p in User.objects.filter(tenant=user.tenant, role="parent").order_by("first_name", "last_name")
        if p.id not in parents_with_account
    ]

    return Response({
        "success": True,
        "virtual_accounts": data,
        "count": len(data),
        "parents_without_account": parents_without_account,
    })


@api_view(["GET", "POST", "PUT", "DELETE"])
@permission_classes([IsAuthenticated])
def admin_manage_virtual_account(request, parent_id):
    """
    GET  – fetch current virtual account for a parent (returns null if none).
    POST/PUT – assign or update virtual account for a parent.
    DELETE – deactivate virtual account for a parent.
    Finance roles only.
    """
    user = request.user
    if user.role not in FINANCE_ROLES:
        return Response({"success": False, "message": "Permission denied."}, status=status.HTTP_403_FORBIDDEN)

    try:
        parent_user = User.objects.get(id=parent_id, tenant=user.tenant, role="parent")
    except User.DoesNotExist:
        return Response({"success": False, "message": "Parent not found."}, status=status.HTTP_404_NOT_FOUND)

    if request.method == "GET":
        try:
            vac = ParentVirtualAccount.objects.get(parent=parent_user, tenant=user.tenant)
            return Response({
                "success": True,
                "virtual_account": {
                    "account_number": vac.account_number,
                    "bank_name": vac.bank_name,
                    "account_name": vac.account_name,
                    "provider": vac.provider,
                    "paystack_reference": vac.paystack_reference,
                    "is_active": vac.is_active,
                    "notes": vac.notes,
                    "assigned_at": vac.created_at.isoformat(),
                    "assigned_by": vac.assigned_by.get_full_name() if vac.assigned_by else None,
                },
            })
        except ParentVirtualAccount.DoesNotExist:
            return Response({"success": True, "virtual_account": None})

    if request.method == "DELETE":
        try:
            vac = ParentVirtualAccount.objects.get(parent=parent_user, tenant=user.tenant)
            vac.is_active = False
            vac.save(update_fields=["is_active", "updated_at"])
            return Response({"success": True, "message": "Virtual account deactivated."})
        except ParentVirtualAccount.DoesNotExist:
            return Response({"success": False, "message": "No virtual account assigned."}, status=status.HTTP_404_NOT_FOUND)

    # POST / PUT – assign or update
    account_number = str(request.data.get("account_number") or "").strip()
    bank_name = str(request.data.get("bank_name") or "").strip()
    account_name = str(request.data.get("account_name") or "").strip()
    provider = str(request.data.get("provider") or "paystack").strip()
    paystack_reference = str(request.data.get("paystack_reference") or "").strip()
    is_active = bool(request.data.get("is_active", True))
    notes = str(request.data.get("notes") or "").strip()

    if not all([account_number, bank_name, account_name]):
        return Response(
            {"success": False, "message": "account_number, bank_name, and account_name are required."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    vac, created = ParentVirtualAccount.objects.update_or_create(
        parent=parent_user,
        tenant=user.tenant,
        defaults={
            "account_number": account_number,
            "bank_name": bank_name,
            "account_name": account_name,
            "provider": provider,
            "paystack_reference": paystack_reference,
            "is_active": is_active,
            "assigned_by": user,
            "notes": notes,
        },
    )

    record_finance_activity(
        user.tenant,
        user,
        "virtual_account_assigned" if created else "virtual_account_updated",
        f"{'Assigned' if created else 'Updated'} virtual account {account_number} for {parent_user.get_full_name() or parent_user.email}.",
        reference=account_number,
    )

    return Response({
        "success": True,
        "message": "Virtual account assigned." if created else "Virtual account updated.",
        "virtual_account": {
            "account_number": vac.account_number,
            "bank_name": vac.bank_name,
            "account_name": vac.account_name,
            "provider": vac.provider,
            "paystack_reference": vac.paystack_reference,
            "is_active": vac.is_active,
            "notes": vac.notes,
        },
    })


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def admin_provision_paystack_virtual_account(request, parent_id):
    """
    Auto-provision a real Paystack dedicated virtual account (DVA) for a parent, replacing the
    need to manually type in account details. Splits automatically to the school's subaccount.
    Finance roles only.
    """
    user = request.user
    if user.role not in FINANCE_ROLES:
        return Response({"success": False, "message": "Permission denied."}, status=status.HTTP_403_FORBIDDEN)

    try:
        parent_user = User.objects.get(id=parent_id, tenant=user.tenant, role="parent")
    except User.DoesNotExist:
        return Response({"success": False, "message": "Parent not found."}, status=status.HTTP_404_NOT_FOUND)

    try:
        vac, created = provision_parent_virtual_account(parent_user, actor=user)
    except Exception as exc:
        return Response({"success": False, "message": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

    record_finance_activity(
        user.tenant,
        user,
        "virtual_account_paystack_provisioned" if created else "virtual_account_paystack_reprovisioned",
        f"Auto-provisioned Paystack virtual account {vac.account_number} for {parent_user.get_full_name() or parent_user.email}.",
        reference=vac.account_number,
    )

    return Response({
        "success": True,
        "message": "Paystack virtual account provisioned." if created else "Paystack virtual account re-provisioned.",
        "virtual_account": {
            "account_number": vac.account_number,
            "bank_name": vac.bank_name,
            "account_name": vac.account_name,
            "provider": vac.provider,
            "paystack_reference": vac.paystack_reference,
            "is_active": vac.is_active,
            "notes": vac.notes,
        },
    })


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def admin_send_fee_reminder(request, parent_id):
    """
    Send a fee statement email to a parent.
    Includes their virtual account details and outstanding fee balance per child.
    Finance roles only.
    """
    user = request.user
    if user.role not in FINANCE_ROLES:
        return Response({"success": False, "message": "Permission denied."}, status=status.HTTP_403_FORBIDDEN)

    try:
        parent_user = User.objects.get(id=parent_id, tenant=user.tenant, role="parent")
    except User.DoesNotExist:
        return Response({"success": False, "message": "Parent not found."}, status=status.HTTP_404_NOT_FOUND)

    result = send_parent_virtual_account_fee_reminder(parent_user)
    if result.get("success"):
        record_finance_activity(
            user.tenant, user,
            "fee_reminder_sent",
            f"Fee statement emailed to {parent_user.get_full_name() or parent_user.email} ({result.get('email', parent_user.email)}).",
        )
    return Response({
        "success": result.get("success", False),
        "message": result.get("message", ""),
        "channel": result.get("channel", "email"),
    })


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def admin_bulk_message_parents(request):
    """
    Send bulk SMS / WhatsApp / Email to selected parents.
    Finance and admin roles only.
    Body: { parent_ids: [uuid...], channel: "sms"|"whatsapp"|"email", message: str }
    """
    user = request.user
    if user.role not in FINANCE_ROLES:
        return Response({"success": False, "message": "Permission denied."}, status=status.HTTP_403_FORBIDDEN)

    parent_ids = request.data.get("parent_ids") or []
    channel = str(request.data.get("channel") or "sms").lower().strip()
    message = str(request.data.get("message") or "").strip()
    personalize = bool(request.data.get("personalize"))

    if not parent_ids:
        return Response({"success": False, "message": "No parents selected."}, status=status.HTTP_400_BAD_REQUEST)
    if not message and not personalize:
        return Response({"success": False, "message": "Message cannot be empty."}, status=status.HTTP_400_BAD_REQUEST)
    if channel not in ("sms", "whatsapp", "email"):
        return Response(
            {"success": False, "message": "Invalid channel. Use sms, whatsapp, or email."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    result = send_bulk_message_to_parents(user.tenant, parent_ids, channel, message, personalize=personalize)

    record_finance_activity(
        user.tenant,
        user,
        "bulk_message_sent",
        f"Bulk {channel.upper()} sent to {result['sent']} of {result['sent'] + result['failed']} parents.",
    )

    return Response({
        "success": True,
        "sent": result["sent"],
        "failed": result["failed"],
        "skipped": result.get("skipped", 0),
        "errors": result["errors"][:10],
    })


def _sms_wallet_transaction_payload(tx):
    return {
        "id": str(tx.id),
        "reference": tx.reference,
        "tx_type": tx.tx_type,
        "status": tx.status,
        "credits": tx.credits,
        "balance_before": tx.balance_before,
        "balance_after": tx.balance_after,
        "amount": str(tx.amount),
        "narration": tx.narration,
        "created_at": tx.created_at,
    }


def _sms_wallet_transaction_list_payload(tx):
    """Same as _sms_wallet_transaction_payload but with the raw Paystack reference
    stripped - used for every response that feeds a user-facing transaction list.
    The reference stays available server-side (Django admin) for reconciliation."""
    payload = _sms_wallet_transaction_payload(tx)
    payload.pop("reference", None)
    return payload


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def sms_wallet_overview(request):
    """SMS wallet balance + unit pricing + recent transactions for the admin's school."""
    user = request.user
    if user.role not in FINANCE_ROLES:
        return Response({"success": False, "message": "Finance access required."}, status=status.HTTP_403_FORBIDDEN)
    if not user.tenant:
        return Response({"success": False, "message": "Your account is not linked to a school."}, status=status.HTTP_400_BAD_REQUEST)

    wallet = get_or_create_sms_wallet(user.tenant)
    recent_transactions = wallet.transactions.all()[:3]

    return Response({
        "success": True,
        "wallet": {
            "balance": wallet.balance,
            "low_balance_threshold": wallet.low_balance_threshold,
            "is_locked": wallet.is_locked,
        },
        "unit_pricing": {
            "block_size": SMS_UNIT_BLOCK_SIZE,
            "block_price": str(SMS_UNIT_BLOCK_PRICE),
            "minimum_units": SMS_UNIT_BLOCK_SIZE,
            "currency": SMS_UNIT_CURRENCY,
        },
        "recent_transactions": [_sms_wallet_transaction_list_payload(tx) for tx in recent_transactions],
        "paystack_public_key": getattr(settings, "PAYSTACK_PUBLIC_KEY", ""),
    })


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def sms_wallet_transaction_history(request):
    """Paginated, searchable, filterable SMS wallet transaction history for the
    'View More' modal. Query: ?page=1&limit=20&status=successful&tx_type=purchase&
    search=...&start_date=YYYY-MM-DD&end_date=YYYY-MM-DD"""
    user = request.user
    if user.role not in FINANCE_ROLES:
        return Response({"success": False, "message": "Finance access required."}, status=status.HTTP_403_FORBIDDEN)
    if not user.tenant:
        return Response({"success": False, "message": "Your account is not linked to a school."}, status=status.HTTP_400_BAD_REQUEST)

    wallet = get_or_create_sms_wallet(user.tenant)
    qs = wallet.transactions.all()

    status_filter = str(request.query_params.get("status") or "").strip()
    if status_filter:
        qs = qs.filter(status=status_filter)
    type_filter = str(request.query_params.get("tx_type") or "").strip()
    if type_filter:
        qs = qs.filter(tx_type=type_filter)
    search = str(request.query_params.get("search") or "").strip()
    if search:
        qs = qs.filter(narration__icontains=search)
    start_date = request.query_params.get("start_date")
    if start_date:
        qs = qs.filter(created_at__date__gte=start_date)
    end_date = request.query_params.get("end_date")
    if end_date:
        qs = qs.filter(created_at__date__lte=end_date)

    try:
        limit = max(1, min(int(request.query_params.get("limit") or 20), 100))
        page = max(1, int(request.query_params.get("page") or 1))
    except (ValueError, TypeError):
        limit, page = 20, 1

    offset = (page - 1) * limit
    total = qs.count()
    transactions = qs[offset: offset + limit]

    return Response({
        "success": True,
        "count": total,
        "page": page,
        "limit": limit,
        "results": [_sms_wallet_transaction_list_payload(tx) for tx in transactions],
    })


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def sms_wallet_cancel(request, reference):
    """Mark a pending SMS bundle purchase as cancelled (Paystack popup closed without
    paying). No-op if the transaction already resolved to successful/failed/cancelled."""
    user = request.user
    if user.role not in FINANCE_ROLES:
        return Response({"success": False, "message": "Finance access required."}, status=status.HTTP_403_FORBIDDEN)
    if not user.tenant:
        return Response({"success": False, "message": "Your account is not linked to a school."}, status=status.HTTP_400_BAD_REQUEST)

    try:
        tx_lookup = SmsWalletTransaction.objects.select_related("wallet").get(reference=reference)
    except SmsWalletTransaction.DoesNotExist:
        return Response({"success": False, "message": "Purchase reference not found."}, status=status.HTTP_404_NOT_FOUND)
    if tx_lookup.wallet.tenant_id != user.tenant_id:
        return Response({"success": False, "message": "Purchase reference not found."}, status=status.HTTP_404_NOT_FOUND)

    try:
        tx = cancel_sms_wallet_purchase(reference, tenant=user.tenant)
    except ValueError as exc:
        return Response({"success": False, "message": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

    return Response({"success": True, "status": tx.status})


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def sms_wallet_purchase(request):
    """Start a Paystack-funded SMS credit purchase. Body: { units: int } - must be a
    positive multiple of SMS_UNIT_BLOCK_SIZE."""
    user = request.user
    if user.role not in FINANCE_ROLES:
        return Response({"success": False, "message": "Finance access required."}, status=status.HTTP_403_FORBIDDEN)
    if not user.tenant:
        return Response({"success": False, "message": "Your account is not linked to a school."}, status=status.HTTP_400_BAD_REQUEST)

    units = request.data.get("units")
    try:
        result = initialize_sms_credit_purchase(user.tenant, units, actor=user)
    except ValueError as exc:
        return Response({"success": False, "message": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
    except Exception as exc:
        return Response({"success": False, "message": str(exc)}, status=status.HTTP_502_BAD_GATEWAY)

    return Response({
        "success": True,
        "reference": result["reference"],
        "authorization_url": result["authorization_url"],
        "access_code": result["access_code"],
        "amount": str(result["amount"]),
        "credits": result["credits"],
    })


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def sms_wallet_verify(request, reference):
    """Verify a Paystack SMS bundle payment and credit the wallet (also self-heals if the
    webhook already credited it — credit_sms_wallet_from_purchase is idempotent)."""
    user = request.user
    if user.role not in FINANCE_ROLES:
        return Response({"success": False, "message": "Finance access required."}, status=status.HTTP_403_FORBIDDEN)
    if not user.tenant:
        return Response({"success": False, "message": "Your account is not linked to a school."}, status=status.HTTP_400_BAD_REQUEST)

    # Check tenant ownership BEFORE crediting - never let a guessed cross-tenant
    # reference actually credit the wrong school's wallet.
    try:
        tx_lookup = SmsWalletTransaction.objects.select_related("wallet").get(reference=reference)
    except SmsWalletTransaction.DoesNotExist:
        return Response({"success": False, "message": "Purchase reference not found."}, status=status.HTTP_404_NOT_FOUND)
    if tx_lookup.wallet.tenant_id != user.tenant_id:
        return Response({"success": False, "message": "Purchase reference not found."}, status=status.HTTP_404_NOT_FOUND)

    try:
        tx = credit_sms_wallet_from_purchase(reference)
    except ValueError as exc:
        return Response({"success": False, "message": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

    wallet = get_or_create_sms_wallet(user.tenant)
    return Response({
        "success": True,
        "message": "SMS wallet credited.",
        "wallet": {"balance": wallet.balance},
        "transaction": _sms_wallet_transaction_payload(tx),
    })
