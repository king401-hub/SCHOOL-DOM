from datetime import timedelta
from decimal import Decimal
import uuid

import requests
from django.conf import settings
from django.db import transaction
from django.db.models import Sum
from django.utils import timezone
from django.utils.dateparse import parse_datetime

from fee_collections.models import (
    CollectionAuditLog,
    CollectionConfig,
    FeePayment,
    SchoolCollectionProfile,
    SchoolSettlement,
    SchoolVirtualAccount,
)


def as_money(value):
    return Decimal(str(value or "0")).quantize(Decimal("0.01"))


def generate_reference(prefix):
    return f"{prefix}{uuid.uuid4().hex[:24]}".upper()


def flutterwave_headers(trace_id="", idempotency_key=""):
    secret = getattr(settings, "FLUTTERWAVE_SECRET_KEY", "")
    if not secret:
        raise RuntimeError("FLUTTERWAVE_SECRET_KEY is not configured.")
    headers = {"Authorization": f"Bearer {secret}", "Content-Type": "application/json"}
    if trace_id:
        headers["X-Trace-Id"] = trace_id
    if idempotency_key:
        headers["X-Idempotency-Key"] = idempotency_key
    scenario_key = getattr(settings, "FLUTTERWAVE_SCENARIO_KEY", "")
    if scenario_key:
        headers["X-Scenario-Key"] = scenario_key
    return headers


def flutterwave_base_url():
    return getattr(settings, "FLUTTERWAVE_BASE_URL", "https://api.flutterwave.com/v3").rstrip("/")


def flutterwave_json(response):
    try:
        data = response.json()
    except ValueError:
        response.raise_for_status()
        return {}
    if response.status_code >= 400:
        raise RuntimeError(data.get("message") or data.get("error") or "Flutterwave request failed.")
    return data


def collection_config():
    config = CollectionConfig.objects.order_by("created_at").first()
    if config:
        return config
    return CollectionConfig.objects.create()


def audit(school, actor, action, message, reference="", metadata=None):
    return CollectionAuditLog.objects.create(
        school=school,
        actor=actor,
        action=action[:80],
        message=message[:255],
        reference=str(reference or "")[:120],
        metadata=metadata or {},
    )


def calculate_commission(gross_amount, config=None):
    config = config or collection_config()
    gross = as_money(gross_amount)
    if config.commission_type == "flat":
        fee = as_money(config.commission_value)
    else:
        fee = (gross * as_money(config.commission_value) / Decimal("100")).quantize(Decimal("0.01"))
    fee = max(fee, as_money(config.minimum_commission))
    if config.maximum_commission is not None:
        fee = min(fee, as_money(config.maximum_commission))
    fee = min(fee, gross)
    return fee, gross - fee


def _virtual_account_from_response(data):
    payload = data.get("data") if isinstance(data.get("data"), dict) else data
    return {
        "account_number": str(
            payload.get("account_number")
            or payload.get("accountNumber")
            or payload.get("nuban")
            or ""
        ).strip(),
        "account_name": str(payload.get("account_name") or payload.get("accountName") or "").strip(),
        "bank_name": str(payload.get("account_bank_name") or payload.get("bank_name") or payload.get("bankName") or payload.get("bank") or "Flutterwave").strip(),
        "provider_reference": str(payload.get("id") or payload.get("reference") or "").strip(),
        "order_reference": str(payload.get("order_ref") or payload.get("orderReference") or "").strip(),
        "raw": payload,
    }


def _split_school_name(name):
    parts = [part for part in str(name or "SchoolDom").split() if part]
    if not parts:
        return "SchoolDom", "School"
    if len(parts) == 1:
        return parts[0][:50], "School"
    return parts[0][:50], " ".join(parts[1:])[:50]


def _phone_payload(raw_phone):
    digits = "".join(ch for ch in str(raw_phone or "") if ch.isdigit())
    if not digits:
        return None
    if digits.startswith("234") and len(digits) > 3:
        return {"country_code": "234", "number": digits[3:][-10:]}
    if digits.startswith("0"):
        return {"country_code": "234", "number": digits[1:][-10:]}
    return {"country_code": "234", "number": digits[-10:]}


def _customer_from_response(data):
    payload = data.get("data") if isinstance(data.get("data"), dict) else data
    return {
        "id": str(payload.get("id") or payload.get("customer_id") or "").strip(),
        "raw": payload,
    }


def ensure_flutterwave_customer(profile, actor=None):
    if profile.flutterwave_customer_id:
        return profile.flutterwave_customer_id
    school = profile.school
    endpoint = getattr(settings, "FLUTTERWAVE_CUSTOMER_ENDPOINT", "/customers")
    reference = profile.flutterwave_customer_reference or generate_reference("CUS")
    first_name, last_name = _split_school_name(school.name)
    payload = {
        "email": school.email or f"{school.schema_name}@schooldom.local",
        "name": {
            "first": first_name,
            "last": last_name,
        },
        "meta": {
            "school_id": str(school.id),
            "school_code": school.schema_name,
            "purpose": "school_fee_collection",
            "reference": reference,
        },
    }
    phone = _phone_payload(school.phone)
    if phone:
        payload["phone"] = phone
    if school.address:
        payload["address"] = {
            "line1": school.address[:120],
            "city": "Lagos",
            "state": "Lagos",
            "country": "NG",
            "postal_code": "100001",
        }

    trace_id = str(uuid.uuid4())
    response = requests.post(
        f"{flutterwave_base_url()}/{endpoint.lstrip('/')}",
        json=payload,
        headers=flutterwave_headers(trace_id=trace_id, idempotency_key=reference),
        timeout=getattr(settings, "FLUTTERWAVE_REQUEST_TIMEOUT", 25),
    )
    data = flutterwave_json(response)
    customer = _customer_from_response(data)
    if not customer["id"]:
        raise RuntimeError("Flutterwave did not return a customer id.")
    profile.flutterwave_customer_id = customer["id"]
    profile.flutterwave_customer_reference = reference
    profile.flutterwave_customer_metadata = customer["raw"]
    profile.save(update_fields=["flutterwave_customer_id", "flutterwave_customer_reference", "flutterwave_customer_metadata", "updated_at"])
    audit(
        school,
        actor,
        "flutterwave_customer_created",
        "Created Flutterwave customer for school collection profile.",
        reference=reference,
        metadata={"customer_id": customer["id"]},
    )
    return customer["id"]


def create_flutterwave_virtual_account(profile, actor=None):
    if profile.status != SchoolCollectionProfile.STATUS_APPROVED:
        raise ValueError("School must be approved before a virtual account can be created.")
    existing = SchoolVirtualAccount.objects.filter(school=profile.school).first()
    if existing and existing.status == SchoolVirtualAccount.STATUS_ACTIVE:
        return existing
    customer_id = ensure_flutterwave_customer(profile, actor=actor)

    reference = generate_reference("VA")
    endpoint = getattr(settings, "FLUTTERWAVE_VIRTUAL_ACCOUNT_ENDPOINT", "/virtual-accounts")
    trace_id = str(uuid.uuid4())
    payload = {
        "customer_id": customer_id,
        "amount": 0,
        "reference": reference,
        "currency": "NGN",
        "account_type": "static",
        "narration": f"{profile.school.name} SchoolDom fees",
        "meta": {
            "school_id": str(profile.school_id),
            "school_code": profile.school.schema_name,
            "purpose": "school_fee_collection",
        },
    }
    response = requests.post(
        f"{flutterwave_base_url()}/{endpoint.lstrip('/')}",
        json=payload,
        headers=flutterwave_headers(trace_id=trace_id, idempotency_key=reference),
        timeout=getattr(settings, "FLUTTERWAVE_REQUEST_TIMEOUT", 25),
    )
    data = flutterwave_json(response)
    account = _virtual_account_from_response(data)
    if not account["account_number"]:
        raise RuntimeError("Flutterwave did not return a virtual account number.")

    virtual_account, _ = SchoolVirtualAccount.objects.update_or_create(
        school=profile.school,
        defaults={
            "provider": "flutterwave",
            "account_number": account["account_number"],
            "account_name": account["account_name"] or f"{profile.school.name} Fees",
            "bank_name": account["bank_name"],
            "provider_reference": account["provider_reference"] or reference,
            "order_reference": account["order_reference"],
            "status": SchoolVirtualAccount.STATUS_ACTIVE,
            "raw_response": account["raw"],
        },
    )
    audit(
        profile.school,
        actor,
        "virtual_account_created",
        "Created permanent Flutterwave virtual account.",
        reference=virtual_account.provider_reference,
        metadata={"account_number": virtual_account.account_number},
    )
    return virtual_account


def approve_collection_profile(profile, actor=None):
    profile.status = SchoolCollectionProfile.STATUS_APPROVED
    profile.approved_by = actor
    profile.approved_at = timezone.now()
    profile.save(update_fields=["status", "approved_by", "approved_at", "updated_at"])
    audit(profile.school, actor, "school_collection_approved", "Approved school collection profile.")
    return create_flutterwave_virtual_account(profile, actor=actor)


def _payload_data(payload):
    return payload.get("data") if isinstance(payload.get("data"), dict) else payload


def extract_webhook_payment(payload):
    data = _payload_data(payload or {})
    payment_method = data.get("payment_method") if isinstance(data.get("payment_method"), dict) else {}
    meta = data.get("meta") if isinstance(data.get("meta"), dict) else {}
    amount = as_money(data.get("amount") or data.get("charged_amount") or data.get("credit_amount"))
    account_number = str(
        data.get("account_number")
        or data.get("destination_account")
        or data.get("nuban")
        or data.get("virtual_account_number")
        or payment_method.get("account_number")
        or payment_method.get("accountNumber")
        or ""
    ).strip()
    provider_reference = str(
        data.get("tx_ref")
        or data.get("reference")
        or data.get("flw_ref")
        or data.get("id")
        or data.get("session_id")
        or ""
    ).strip()
    paid_at = parse_datetime(str(data.get("created_datetime") or data.get("created_at") or data.get("paid_at") or data.get("date") or "")) or timezone.now()
    return {
        "account_number": account_number,
        "school_id": str(meta.get("school_id") or "").strip(),
        "provider_reference": provider_reference,
        "session_id": str(data.get("session_id") or data.get("sessionId") or "").strip(),
        "amount": amount,
        "currency": str(data.get("currency") or "NGN")[:5],
        "status": str(data.get("status") or payload.get("type") or payload.get("event") or "successful").lower(),
        "narration": str(data.get("narration") or data.get("description") or data.get("remarks") or "")[:255],
        "payer_name": str(data.get("customer_name") or data.get("payer_name") or data.get("originator_name") or "")[:160],
        "payer_account_number": str(data.get("payer_account_number") or data.get("originator_account_number") or "")[:30],
        "payer_bank_name": str(data.get("payer_bank_name") or data.get("originator_bank") or "")[:120],
        "paid_at": paid_at,
        "raw": payload,
    }


def record_flutterwave_payment(payload):
    event = str((payload or {}).get("type") or (payload or {}).get("event") or "").lower()
    if event and not any(token in event for token in ["charge", "transfer", "account"]):
        return None, False
    details = extract_webhook_payment(payload)
    if details["status"] not in {"successful", "success", "completed", "paid", "charge.completed"}:
        raise ValueError("Payment is not successful.")
    if not details["provider_reference"]:
        raise ValueError("Payment reference is required.")

    existing = FeePayment.objects.filter(provider_reference=details["provider_reference"]).first()
    if existing:
        audit(existing.school, None, "duplicate_payment_ignored", "Duplicate Flutterwave payment webhook ignored.", reference=existing.provider_reference)
        return existing, False

    virtual_account = None
    if details["account_number"]:
        virtual_account = SchoolVirtualAccount.objects.select_related("school").filter(account_number=details["account_number"]).first()
    if not virtual_account and details["school_id"]:
        virtual_account = SchoolVirtualAccount.objects.select_related("school").filter(school_id=details["school_id"]).first()
    if not virtual_account:
        raise ValueError("No school virtual account matched this payment.")

    platform_fee, net_amount = calculate_commission(details["amount"])
    with transaction.atomic():
        payment = FeePayment.objects.create(
            school=virtual_account.school,
            virtual_account=virtual_account,
            provider="flutterwave",
            provider_reference=details["provider_reference"],
            session_id=details["session_id"],
            payer_name=details["payer_name"],
            payer_account_number=details["payer_account_number"],
            payer_bank_name=details["payer_bank_name"],
            narration=details["narration"],
            currency=details["currency"],
            gross_amount=details["amount"],
            platform_fee=platform_fee,
            net_amount=net_amount,
            status=FeePayment.STATUS_SUCCESSFUL,
            paid_at=details["paid_at"],
            raw_payload=details["raw"],
        )
        audit(
            payment.school,
            None,
            "payment_recorded",
            "Recorded school fee payment from Flutterwave webhook.",
            reference=payment.provider_reference,
            metadata={"gross_amount": str(payment.gross_amount), "platform_fee": str(payment.platform_fee), "net_amount": str(payment.net_amount)},
        )
    return payment, True


def unsettled_payments_for_school(school):
    return FeePayment.objects.filter(
        school=school,
        status=FeePayment.STATUS_SUCCESSFUL,
        settlements__isnull=True,
    ).order_by("paid_at", "created_at")


def create_settlement_for_school(school, scheduled_for=None):
    profile = getattr(school, "collection_profile", None)
    if not profile or profile.status != SchoolCollectionProfile.STATUS_APPROVED:
        return None
    payments = list(unsettled_payments_for_school(school))
    if not payments:
        return None

    gross = sum((item.gross_amount for item in payments), Decimal("0.00"))
    platform_fee = sum((item.platform_fee for item in payments), Decimal("0.00"))
    net = sum((item.net_amount for item in payments), Decimal("0.00"))
    settlement = SchoolSettlement.objects.create(
        school=school,
        gross_amount=gross,
        platform_fee=platform_fee,
        net_amount=net,
        transfer_reference=generate_reference("SET"),
        scheduled_for=scheduled_for or timezone.localdate(),
    )
    settlement.payments.set(payments)
    audit(school, None, "settlement_created", "Created settlement batch.", reference=settlement.transfer_reference, metadata={"payment_count": len(payments)})
    return settlement


def initiate_flutterwave_transfer(settlement, actor=None):
    profile = settlement.school.collection_profile
    payload = {
        "account_bank": profile.bank_code,
        "account_number": profile.account_number,
        "amount": str(as_money(settlement.net_amount)),
        "narration": f"SchoolDom settlement {settlement.transfer_reference}",
        "currency": settlement.currency,
        "reference": settlement.transfer_reference,
    }
    response = requests.post(
        f"{flutterwave_base_url()}/transfers",
        json=payload,
        headers=flutterwave_headers(),
        timeout=getattr(settings, "FLUTTERWAVE_REQUEST_TIMEOUT", 25),
    )
    data = flutterwave_json(response)
    if data.get("status") != "success":
        raise RuntimeError(data.get("message") or "Flutterwave transfer failed.")
    return data


def process_settlement(settlement_id, actor=None):
    settlement = SchoolSettlement.objects.select_related("school", "school__collection_profile").get(id=settlement_id)
    if settlement.status == SchoolSettlement.STATUS_SUCCESSFUL:
        return settlement
    settlement.status = SchoolSettlement.STATUS_PROCESSING
    settlement.save(update_fields=["status", "updated_at"])
    try:
        data = initiate_flutterwave_transfer(settlement, actor=actor)
    except Exception as exc:
        settlement.status = SchoolSettlement.STATUS_FAILED
        settlement.failure_reason = str(exc)
        settlement.save(update_fields=["status", "failure_reason", "updated_at"])
        audit(settlement.school, actor, "settlement_failed", "Settlement transfer failed.", reference=settlement.transfer_reference, metadata={"error": str(exc)})
        return settlement

    transfer_data = data.get("data") or {}
    settlement.status = SchoolSettlement.STATUS_SUCCESSFUL
    settlement.provider_transfer_id = str(transfer_data.get("id") or transfer_data.get("reference") or "")
    settlement.raw_response = data
    settlement.settled_at = timezone.now()
    settlement.save(update_fields=["status", "provider_transfer_id", "raw_response", "settled_at", "updated_at"])
    audit(settlement.school, actor, "settlement_successful", "Settlement transferred to school bank account.", reference=settlement.transfer_reference)
    return settlement


def settlement_due_today(config=None, today=None):
    config = config or collection_config()
    today = today or timezone.localdate()
    if config.settlement_frequency == "weekly":
        return today.weekday() == config.settlement_weekday
    return True


def create_due_settlements():
    config = collection_config()
    if not config.auto_settlement_enabled or not settlement_due_today(config):
        return []
    schools = SchoolCollectionProfile.objects.filter(status=SchoolCollectionProfile.STATUS_APPROVED).select_related("school")
    settlements = []
    for profile in schools:
        settlement = create_settlement_for_school(profile.school)
        if settlement:
            settlements.append(settlement)
    return settlements


def school_dashboard_payload(school):
    virtual_account = SchoolVirtualAccount.objects.filter(school=school).first()
    payments = FeePayment.objects.filter(school=school)
    settlements = SchoolSettlement.objects.filter(school=school)
    aggregates = payments.aggregate(
        gross=Sum("gross_amount"),
        fees=Sum("platform_fee"),
        net=Sum("net_amount"),
    )
    pending_settlements = settlements.filter(status__in=[SchoolSettlement.STATUS_PENDING, SchoolSettlement.STATUS_PROCESSING])
    completed_settlements = settlements.filter(status=SchoolSettlement.STATUS_SUCCESSFUL)
    return {
        "virtual_account": virtual_account,
        "total_fees_received": aggregates["gross"] or Decimal("0.00"),
        "total_platform_fees": aggregates["fees"] or Decimal("0.00"),
        "total_net_payable": aggregates["net"] or Decimal("0.00"),
        "pending_settlements": pending_settlements,
        "completed_settlements": completed_settlements,
        "payments": payments.order_by("-paid_at")[:100],
        "settlements": settlements.order_by("-created_at")[:100],
    }


def admin_dashboard_payload():
    payments = FeePayment.objects.all()
    settlements = SchoolSettlement.objects.all()
    aggregates = payments.aggregate(
        gross=Sum("gross_amount"),
        fees=Sum("platform_fee"),
        net=Sum("net_amount"),
    )
    return {
        "total_collections": aggregates["gross"] or Decimal("0.00"),
        "total_commissions_earned": aggregates["fees"] or Decimal("0.00"),
        "total_net_payable": aggregates["net"] or Decimal("0.00"),
        "total_settlements": settlements.filter(status=SchoolSettlement.STATUS_SUCCESSFUL).aggregate(total=Sum("net_amount"))["total"] or Decimal("0.00"),
        "failed_settlements": settlements.filter(status=SchoolSettlement.STATUS_FAILED),
        "recent_payments": payments.order_by("-paid_at")[:100],
        "recent_settlements": settlements.order_by("-created_at")[:100],
        "config": collection_config(),
    }
