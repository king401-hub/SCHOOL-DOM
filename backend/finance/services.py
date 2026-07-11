"""Service helpers for wallet operations and Flutterwave integration."""
from decimal import Decimal
from datetime import timedelta
from typing import Optional
import uuid
import re
import logging
from urllib.parse import quote

logger = logging.getLogger(__name__)

import requests
from django.conf import settings
from django.db import OperationalError, ProgrammingError
from django.db import transaction
from django.db.models import F, Q, Sum
from django.utils import timezone

from finance.models import (
    ActivationCreditPool,
    ActivationCreditTransaction,
    AdminWallet,
    BankLink,
    BankPayment,
    ClassFee,
    DocumentGenerationCreditTransaction,
    FeeAllocation,
    FinanceLedgerLog,
    PaymentReceiptLink,
    SchoolFee,
    StudentActivationCredit,
    StudentPaymentReference,
    Transaction,
    Wallet,
)


K12_ACTIVATION_CREDIT_PRICE = Decimal("500.00")
NON_K12_ACTIVATION_CREDIT_PRICE = Decimal("200.00")
ACTIVATION_CREDIT_PRICE = NON_K12_ACTIVATION_CREDIT_PRICE
ACTIVATION_CREDIT_BONUS_INTERVAL = 100
ACTIVATION_CREDIT_BONUS_AMOUNT = 10
K12_TOKEN_DURATION_MONTHS = 3
K12_TOKEN_DURATION_DAYS = 15
NON_K12_TOKEN_DURATION_MONTHS = 1
NON_K12_TOKEN_DURATION_DAYS = 0
SCHOOLDOM_PAY_BASE_URL = "https://pay.schoolom.ng"
DEFAULT_BANK_LINK_TEMPLATES = {
    "gtbank": "gtbank://pay?account={{account_number}}&amount={{amount}}&narration={{narration}}",
    "guaranty trust bank": "gtbank://pay?account={{account_number}}&amount={{amount}}&narration={{narration}}",
    "zenith": "zenith://transfer?to={{account_number}}&amt={{amount}}&desc={{student_name}}",
    "zenith bank": "zenith://transfer?to={{account_number}}&amt={{amount}}&desc={{student_name}}",
    "uba": "uba://payment?acct={{account_number}}&amt={{amount}}&ref={{student_ref}}",
    "united bank for africa": "uba://payment?acct={{account_number}}&amt={{amount}}&ref={{student_ref}}",
    "access": "access://transfer?to={{account_number}}&amt={{amount}}&ref={{student_ref}}",
    "access bank": "access://transfer?to={{account_number}}&amt={{amount}}&ref={{student_ref}}",
    "firstbank": "firstbank://transfer?account={{account_number}}&amount={{amount}}&narration={{narration}}",
    "first bank": "firstbank://transfer?account={{account_number}}&amount={{amount}}&narration={{narration}}",
}


def _as_decimal(value: object) -> Decimal:
    try:
        return Decimal(str(value)).quantize(Decimal("0.01"))
    except Exception:
        raise ValueError("Amount must be a number with up to two decimal places.")


def _digits(value: object) -> str:
    return re.sub(r"\D+", "", str(value or ""))


def normalize_phone_number(value: object) -> str:
    digits = _digits(value)
    if digits.startswith("00"):
        digits = digits[2:]
    if len(digits) == 11 and digits.startswith("0"):
        return "234" + digits[1:]
    if len(digits) == 10:
        return "234" + digits
    return digits


def _money_for_link(amount: Decimal) -> str:
    amount = _as_decimal(amount)
    if amount == amount.to_integral_value():
        return str(int(amount))
    return format(amount, "f")


def _format_naira(amount: Decimal) -> str:
    amount = _as_decimal(amount)
    return f"NGN {amount:,.2f}"


def generate_reference(prefix: str = "EDU") -> str:
    return f"{prefix}{uuid.uuid4().hex[:24]}".upper()


def activation_credit_bonus_for_purchase(credits: int) -> int:
    """Return free activation tokens earned for a paid token purchase."""
    credits = int(credits or 0)
    if credits <= 0:
        return 0
    return (credits // ACTIVATION_CREDIT_BONUS_INTERVAL) * ACTIVATION_CREDIT_BONUS_AMOUNT


def generate_student_payment_code(student_profile) -> str:
    student_code = "".join(ch for ch in (student_profile.student_id or student_profile.admission_number or "") if ch.isalnum()).upper()
    if not student_code:
        student_code = uuid.uuid4().hex[:6].upper()
    base = student_code[:24]
    code = base
    suffix = 1
    while StudentPaymentReference.objects.filter(code=code).exclude(student=student_profile).exists():
        suffix += 1
        suffix_text = str(suffix)
        code = f"{base[:24 - len(suffix_text)]}{suffix_text}"
    return code


def get_or_create_student_payment_reference(student_profile) -> StudentPaymentReference:
    reference, created = StudentPaymentReference.objects.get_or_create(
        student=student_profile,
        defaults={
            "tenant": getattr(student_profile.user, "tenant", None),
            "code": generate_student_payment_code(student_profile),
        },
    )
    if not created and not reference.tenant_id and getattr(student_profile.user, "tenant", None):
        reference.tenant = student_profile.user.tenant
        reference.save(update_fields=["tenant", "updated_at"])
    expected_code = generate_student_payment_code(student_profile)
    if not created and reference.code != expected_code:
        reference.code = expected_code
        reference.save(update_fields=["code", "updated_at"])
    return reference


# ============================================================
# NEW: PAYSTACK SPLIT PAYMENT INTEGRATION
# ============================================================

def _paystack_headers():
    """Get Paystack API headers."""
    secret = getattr(settings, "PAYSTACK_SECRET_KEY", "")
    if not secret:
        raise RuntimeError("PAYSTACK_SECRET_KEY is not configured.")
    return {
        "Authorization": f"Bearer {secret}",
        "Content-Type": "application/json",
    }


def _paystack_base_url():
    """Get Paystack base URL."""
    return getattr(settings, "PAYSTACK_BASE_URL", "https://api.paystack.co").rstrip("/")


def _paystack_json(response):
    """Parse Paystack JSON response."""
    try:
        return response.json()
    except ValueError:
        response.raise_for_status()
        return {}


def create_paystack_split_code(school_subaccount_code: str, school_name: str) -> str:
    """
    Create a split code for a school in Paystack.
    
    Args:
        school_subaccount_code: Paystack subaccount code for the school
        school_name: Name of the school
        
    Returns:
        str: Split code (SPL_xxx)
    """
    url = f"{_paystack_base_url()}/split"
    payload = {
        "name": f"Schooldom Split - {school_name}",
        "type": "flat",
        "currency": "NGN",
        "subaccounts": [
            {
                "subaccount": school_subaccount_code,
                "share": 5000000  # ₦50,000 in kobo
            },
            {
                "subaccount": getattr(settings, "PAYSTACK_SCHOOLDOM_SUBACCOUNT", ""),
                "share": 10000  # ₦100 in kobo
            }
        ],
        "bearer_type": "subaccount",  # School bears Paystack fee
        "main_account_share": 0
    }
    
    response = requests.post(url, json=payload, headers=_paystack_headers(), timeout=30)
    data = _paystack_json(response)
    
    if response.status_code not in (200, 201) or data.get("status") is not True:
        raise RuntimeError(data.get("message", "Failed to create split code"))
    
    return data["data"]["split_code"]


def list_paystack_banks() -> list:
    """Fetch the list of Nigerian banks (name + settlement code) Paystack supports for subaccounts."""
    url = f"{_paystack_base_url()}/bank"
    response = requests.get(
        url,
        params={"country": "nigeria", "currency": "NGN", "perPage": 100},
        headers=_paystack_headers(),
        timeout=30,
    )
    data = _paystack_json(response)
    if response.status_code != 200 or data.get("status") is not True:
        raise RuntimeError(data.get("message", "Failed to load bank list"))
    return [{"name": bank["name"], "code": bank["code"]} for bank in data.get("data", [])]


def resolve_paystack_account(account_number: str, bank_code: str) -> dict:
    """Resolve a Nigerian bank account number to its registered name via Paystack."""
    url = f"{_paystack_base_url()}/bank/resolve"
    response = requests.get(
        url,
        params={"account_number": account_number, "bank_code": bank_code},
        headers=_paystack_headers(),
        timeout=20,
    )
    data = _paystack_json(response)
    if response.status_code != 200 or data.get("status") is not True:
        raise RuntimeError(data.get("message", "Could not resolve account number"))
    return {
        "account_number": data["data"]["account_number"],
        "account_name": data["data"]["account_name"],
    }


def create_paystack_subaccount(
    business_name: str,
    bank_code: str,
    account_number: str,
    percentage_charge: Decimal = Decimal("0.00")
) -> dict:
    """
    Create a subaccount for a school in Paystack.
    
    Args:
        business_name: Name of the school/business
        bank_code: Bank code (e.g., "058" for GTBank)
        account_number: Bank account number
        percentage_charge: Percentage charge (default 0)
        
    Returns:
        dict: Subaccount data including subaccount_code
    """
    url = f"{_paystack_base_url()}/subaccount"
    payload = {
        "business_name": business_name,
        "settlement_bank": bank_code,
        "account_number": account_number,
        "percentage_charge": float(percentage_charge)
    }
    
    response = requests.post(url, json=payload, headers=_paystack_headers(), timeout=30)
    data = _paystack_json(response)
    
    if response.status_code not in (200, 201) or data.get("status") is not True:
        raise RuntimeError(data.get("message", "Failed to create subaccount"))
    
    return data["data"]


def verify_paystack_subaccount(subaccount_code: str):
    """
    Check whether a subaccount still exists (and is active) on Paystack.

    Returns:
        True  - subaccount exists and is active
        False - Paystack reports it deleted/not found/inactive
        None  - could not reach Paystack (unknown; do not clear anything)
    """
    if not subaccount_code:
        return False
    url = f"{_paystack_base_url()}/subaccount/{subaccount_code}"
    try:
        response = requests.get(url, headers=_paystack_headers(), timeout=20)
    except requests.RequestException:
        return None
    data = _paystack_json(response)
    if response.status_code == 200 and data.get("status") is True:
        return bool(data.get("data", {}).get("active", True))
    if response.status_code in (400, 404):
        return False
    return None


def sync_school_subaccount_with_paystack(school) -> dict:
    """
    If the school's Paystack subaccount was deleted or deactivated on the
    Paystack dashboard, clear the stale subaccount/split codes locally so
    split setup can run again with fresh bank details.
    """
    wallet = get_or_create_admin_wallet(school)
    if not wallet.subaccount_code:
        return {"cleared": False, "verified": False}
    exists = verify_paystack_subaccount(wallet.subaccount_code)
    if exists is False:
        old_code = wallet.subaccount_code
        wallet.subaccount_code = ""
        wallet.split_code = ""
        wallet.dva_split_code = ""
        wallet.save(update_fields=["subaccount_code", "split_code", "dva_split_code", "updated_at"])
        return {"cleared": True, "verified": True, "old_code": old_code}
    return {"cleared": False, "verified": exists is True}


def create_paystack_customer(email: str, first_name: str, last_name: str, phone: str = "") -> dict:
    """Get or create a Paystack customer for a parent. Returns customer data including customer_code."""
    url = f"{_paystack_base_url()}/customer"
    payload = {
        "email": email,
        "first_name": first_name or "Parent",
        "last_name": last_name or "Guardian",
    }
    if phone:
        payload["phone"] = phone

    response = requests.post(url, json=payload, headers=_paystack_headers(), timeout=30)
    data = _paystack_json(response)
    if response.status_code in (200, 201) and data.get("status"):
        return data["data"]

    # Customer may already exist for this email — look it up instead of failing.
    lookup = requests.get(f"{url}/{email}", headers=_paystack_headers(), timeout=30)
    lookup_data = _paystack_json(lookup)
    if lookup.status_code == 200 and lookup_data.get("status"):
        return lookup_data["data"]

    raise RuntimeError(data.get("message", "Failed to create Paystack customer"))


DVA_SCHOOLDOM_SHARE_PERCENT = Decimal("0.25")  # Schooldom's cut of bank-transfer (DVA) payments, in percent


def get_or_create_paystack_dva_split_code(tenant) -> str:
    """
    Get or create a percentage-type Paystack split code for a school's dedicated virtual accounts.

    Unlike the flat split used at checkout (exact kobo amounts per fee), a DVA must use one fixed
    split rule applied to every incoming transfer, so this uses a percentage split instead:
    the school's subaccount gets (100 - DVA_SCHOOLDOM_SHARE_PERCENT)%, Schooldom gets the rest.
    The school's subaccount bears the Paystack transfer fee, consistent with the checkout flow.
    """
    wallet = AdminWallet.objects.get(tenant=tenant)
    if wallet.dva_split_code:
        return wallet.dva_split_code
    if not wallet.subaccount_code:
        raise RuntimeError("This school has no Paystack subaccount configured yet.")

    school_share = Decimal("100") - DVA_SCHOOLDOM_SHARE_PERCENT
    url = f"{_paystack_base_url()}/split"
    payload = {
        "name": f"Schooldom DVA Split - {tenant.name}",
        "type": "percentage",
        "currency": "NGN",
        "subaccounts": [
            {"subaccount": wallet.subaccount_code, "share": float(school_share)},
            {"subaccount": getattr(settings, "PAYSTACK_SCHOOLDOM_SUBACCOUNT", ""), "share": float(DVA_SCHOOLDOM_SHARE_PERCENT)},
        ],
        "bearer_type": "subaccount",
        "bearer_subaccount": wallet.subaccount_code,
    }

    response = requests.post(url, json=payload, headers=_paystack_headers(), timeout=30)
    data = _paystack_json(response)
    if response.status_code not in (200, 201) or data.get("status") is not True:
        raise RuntimeError(data.get("message", "Failed to create DVA split code"))

    split_code = data["data"]["split_code"]
    wallet.dva_split_code = split_code
    wallet.save(update_fields=["dva_split_code"])
    return split_code


def create_paystack_dedicated_account(customer_code: str, split_code: str = "", preferred_bank: str = "wema-bank") -> dict:
    """Create a dedicated virtual account (NUBAN) for a Paystack customer, optionally with a split applied."""
    url = f"{_paystack_base_url()}/dedicated_account"
    payload = {
        "customer": customer_code,
        "preferred_bank": preferred_bank,
    }
    if split_code:
        payload["split_code"] = split_code

    response = requests.post(url, json=payload, headers=_paystack_headers(), timeout=30)
    data = _paystack_json(response)
    if response.status_code not in (200, 201) or data.get("status") is not True:
        raise RuntimeError(data.get("message", "Failed to create dedicated virtual account"))

    return data["data"]


def provision_parent_virtual_account(parent_user, actor=None):
    """
    Auto-provision a real Paystack dedicated virtual account for a parent, replacing the need
    to manually type in account details. The account is split so the school's share settles
    automatically to their existing subaccount on every bank transfer.

    Returns (ParentVirtualAccount, created: bool).
    """
    from finance.models import ParentVirtualAccount

    tenant = getattr(parent_user, "tenant", None)
    if not tenant:
        raise ValueError("Parent has no school/tenant assigned.")

    school_name = (getattr(tenant, "name", "") or "").strip()
    full_name = (parent_user.get_full_name() or parent_user.email or "").strip()
    first_name, _, last_name = full_name.partition(" ")
    # Append school name to last_name so the DVA account reads "Parent Name - School Name"
    last_name_field = f"{last_name} - {school_name}"[:50] if school_name else (last_name or "Guardian")
    customer = create_paystack_customer(
        email=parent_user.email,
        first_name=first_name or "Parent",
        last_name=last_name_field,
        phone=getattr(parent_user, "phone", "") or "",
    )
    customer_code = customer["customer_code"]

    split_code = get_or_create_paystack_dva_split_code(tenant)
    dva = create_paystack_dedicated_account(customer_code, split_code=split_code)

    account_number = dva.get("account_number", "")
    bank_name = (dva.get("bank") or {}).get("name", "")
    account_name = dva.get("account_name", "")

    vac, created = ParentVirtualAccount.objects.update_or_create(
        parent=parent_user,
        defaults={
            "tenant": tenant,
            "account_number": account_number,
            "bank_name": bank_name,
            "account_name": account_name,
            "provider": "paystack",
            "paystack_reference": customer_code,
            "is_active": True,
            "assigned_by": actor,
        },
    )
    return vac, created


SCHOOLDOM_RATE = Decimal("0.003")          # 0.3% of each fee's tuition amount
PAYSTACK_FLAT_FEE = Decimal("300.00")      # ₦300 flat per transaction (charged to parent)


def schooldom_fee_for(tuition: Decimal) -> Decimal:
    """Return Schooldom's 0.3% cut for a given tuition amount, rounded to kobo."""
    return (tuition * SCHOOLDOM_RATE).quantize(Decimal("0.01"))


def initialize_paystack_split_payment(
    email: str,
    amount: Decimal,
    subaccount_code: str,
    transaction_charge: Decimal = Decimal("0.00"),
    metadata: dict = None,
    callback_url: str = ""
) -> dict:
    """
    Initialize a Paystack split payment.

    Money flow:
    - `amount` (naira): total the parent pays = tuitions + 0.3% Schooldom fees + ₦300 Paystack fee
    - `transaction_charge` (naira): amount kept by Schooldom main account
                                    = sum(0.3% × each_tuition) + ₦300
    - School subaccount receives: amount − transaction_charge = exact tuition total
    - `bearer = "account"`: Schooldom main account bears Paystack's actual processing fee
      (the ₦300 in transaction_charge is the parent's contribution toward that)

    Example — parent paying one ₦50,000 fee:
      amount             = ₦50,450  (₦50,000 + ₦150 Schooldom 0.3% + ₦300 Paystack)
      transaction_charge = ₦450     → stays in Schooldom main account
      school subaccount  = ₦50,000  → school receives full tuition, nothing deducted
    """
    url = f"{_paystack_base_url()}/transaction/initialize"

    payload = {
        "email": email,
        "amount": int(amount * 100),                    # total in kobo
        "subaccount": subaccount_code,                  # school's subaccount (receives remainder)
        "transaction_charge": int(transaction_charge * 100),  # kobo → stays in main account
        "bearer": "account",                            # Schooldom main account pays Paystack fee
        "metadata": metadata or {},
        "callback_url": callback_url or getattr(settings, "PAYSTACK_CALLBACK_URL", ""),
    }

    response = requests.post(url, json=payload, headers=_paystack_headers(), timeout=30)
    data = _paystack_json(response)

    if not data.get("status"):
        raise RuntimeError(data.get("message", "Failed to initialize payment"))

    return data["data"]


def verify_paystack_transaction(reference: str) -> dict:
    """
    Verify a Paystack transaction.
    
    Args:
        reference: Paystack transaction reference
        
    Returns:
        dict: Transaction data
    """
    url = f"{_paystack_base_url()}/transaction/verify/{reference}"
    
    response = requests.get(url, headers=_paystack_headers(), timeout=30)
    data = _paystack_json(response)
    
    if response.status_code not in (200, 201) or data.get("status") is not True:
        raise RuntimeError(data.get("message", "Failed to verify transaction"))
    
    return data["data"]


def verify_paystack_webhook_signature(signature: str, payload: bytes) -> bool:
    """
    Verify Paystack webhook signature.
    
    Args:
        signature: x-paystack-signature header value
        payload: Raw request body
        
    Returns:
        bool: True if signature is valid
    """
    import hmac
    import hashlib
    
    secret = getattr(settings, "PAYSTACK_SECRET_KEY", "")
    if not secret:
        return False
    
    expected_signature = hmac.new(
        secret.encode('utf-8'),
        payload,
        hashlib.sha512
    ).hexdigest()
    
    return hmac.compare_digest(signature, expected_signature)


def get_fee_payment_breakdown(fee_ids: list) -> dict:
    """
    Get payment breakdown for a list of fees including Schooldom and Paystack fees.
    
    Args:
        fee_ids: List of SchoolFee IDs
        
    Returns:
        dict: Payment breakdown with totals
    """
    fees = SchoolFee.objects.filter(id__in=fee_ids).select_related('student', 'student__user')

    if not fees.exists():
        raise ValueError("No fees found")

    items = []
    total_tuition = Decimal("0.00")
    total_schooldom = Decimal("0.00")

    for fee in fees:
        tuition = _as_decimal(fee.amount)
        s_fee = schooldom_fee_for(tuition)   # 0.3% of tuition
        total_tuition += tuition
        total_schooldom += s_fee

        student_name = fee.student.user.get_full_name() or fee.student.user.email
        class_name = getattr(fee.student, 'current_class', None)
        class_name = class_name.name if class_name else ""

        items.append({
            'fee_id': str(fee.id),
            'student_id': str(fee.student.id),
            'student_name': student_name,
            'class': class_name,
            'tuition': float(tuition),
            'schooldom_fee': float(s_fee),        # 0.3% of this fee
            'subtotal': float(tuition + s_fee),   # per-item cost before Paystack
            'due_date': fee.due_date.strftime('%Y-%m-%d'),
            'status': fee.status,
        })

    # ₦300 Paystack flat fee is per transaction (not per fee item), paid by parent
    paystack_fee = PAYSTACK_FLAT_FEE
    transaction_charge = total_schooldom + paystack_fee  # goes to Schooldom main account

    return {
        'items': items,
        'subtotal': float(total_tuition),              # total tuition (what school receives)
        'schooldom_fee_total': float(total_schooldom), # 0.3% of all tuitions
        'paystack_fee': float(paystack_fee),           # ₦300 flat per transaction
        'transaction_charge': float(transaction_charge),  # schooldom% + ₦300
        'grand_total': float(total_tuition + transaction_charge),
        'fee_count': len(items),
    }


def _sendchamp_headers() -> dict:
    api_key = getattr(settings, "SENDCHAMP_API_KEY", "")
    if not api_key:
        raise RuntimeError("SENDCHAMP_API_KEY is not configured.")
    return {
        "Authorization": f"Bearer {api_key}",
        "Accept": "application/json",
        "Content-Type": "application/json",
    }


def send_sendchamp_sms(to_phone: str, message: str) -> dict:
    """Send SMS via Sendchamp. Logs the full request and response for debugging."""
    try:
        headers = _sendchamp_headers()
    except RuntimeError as exc:
        logger.error("Sendchamp SMS skipped: %s", exc)
        return {"status": "skipped", "reason": str(exc)}

    normalized = normalize_phone_number(to_phone)
    sender_id = getattr(settings, "SENDCHAMP_SENDER_ID", "Sendchamp")
    route = getattr(settings, "SENDCHAMP_ROUTE", "non_dnd")

    payload = {
        "to": [normalized],
        "message": message,
        "sender_name": sender_id,
        "route": route,
    }
    logger.info(
        "Sendchamp SMS → to=%s sender=%s route=%s message_len=%d",
        normalized, sender_id, route, len(message),
    )
    try:
        response = requests.post(
            "https://api.sendchamp.com/api/v1/sms/send",
            json=payload,
            headers=headers,
            timeout=15,
        )
        data = response.json()
        logger.info("Sendchamp SMS response [HTTP %s]: %s", response.status_code, data)
        return data
    except Exception as exc:
        logger.error("Sendchamp SMS request failed: %s", exc)
        return {"status": "error", "reason": str(exc)}


_SMS_CHAR_MAP = {
    "₦": "NGN ",   # ₦ naira sign
    "‘": "'", "’": "'",
    "“": '"', "”": '"',
    "–": "-", "—": "-",
    "…": "...",
    "•": "-",
    " ": " ",
}


def _sms_safe_text(text: str) -> str:
    """Transliterate/strip characters GSM handsets can't render (avoids '?' and mojibake in SMS)."""
    out = str(text or "")
    for bad, good in _SMS_CHAR_MAP.items():
        out = out.replace(bad, good)
    out = out.encode("ascii", "ignore").decode("ascii")
    return re.sub(r"[ \t]{2,}", " ", out).strip()


def send_ebulksms(to_phone: str, message: str, sender: str = "SchoolDom") -> dict:
    """Send SMS via eBulkSMS JSON API."""
    message = _sms_safe_text(message)
    username = getattr(settings, "EBULKSMS_USERNAME", "")
    apikey = getattr(settings, "EBULKSMS_APIKEY", "")
    if not username or not apikey:
        logger.error("eBulkSMS credentials not configured.")
        return {"status": "skipped", "reason": "eBulkSMS credentials not configured."}

    normalized = normalize_phone_number(to_phone)
    # eBulkSMS requires the number to start with country code digits, no + sign
    if not normalized.startswith("234"):
        logger.error("eBulkSMS: phone %s could not be normalized to Nigerian format (got %s)", to_phone, normalized)
        return {"status": "error", "reason": f"Invalid phone format: {normalized}"}

    msg_id = uuid.uuid4().hex
    payload = {
        "SMS": {
            "auth": {"username": username, "apikey": apikey},
            "message": {"sender": sender[:11], "messagetext": message, "flash": "0"},
            "recipients": {"gsm": [{"msidn": normalized, "msgid": msg_id}]},
            "dndsender": 1,
        }
    }
    logger.info("eBulkSMS → to=%s sender=%s chars=%d payload=%s", normalized, sender, len(message), payload)
    try:
        response = requests.post(
            "https://api.ebulksms.com/sendsms.json",
            json=payload,
            timeout=15,
        )
        data = response.json()
        # Log full response so delivery failures are visible in Django logs
        logger.info("eBulkSMS response [HTTP %s]: %s", response.status_code, data)
        if response.status_code != 200:
            logger.error("eBulkSMS non-200 HTTP status %s: %s", response.status_code, data)
        return data
    except Exception as exc:
        logger.error("eBulkSMS request failed: %s", exc)
        return {"status": "error", "reason": str(exc)}


def send_termii_whatsapp(to_phone: str, message: str) -> dict:
    """Send WhatsApp message via Termii."""
    api_key = getattr(settings, "TERMII_API_KEY", "")
    sender = getattr(settings, "TERMII_WHATSAPP_FROM", "")
    if not api_key or not sender:
        return {"status": "skipped", "reason": "Termii credentials not configured."}

    base_url = getattr(settings, "TERMII_BASE_URL", "https://api.ng.termii.com").rstrip("/")
    payload = {
        "api_key": api_key,
        "to": normalize_phone_number(to_phone),
        "from": sender,
        "sms": message,
        "type": "plain",
        "channel": "whatsapp",
    }
    try:
        response = requests.post(
            f"{base_url}/api/sms/send",
            json=payload,
            headers={"Content-Type": "application/json"},
            timeout=15,
        )
        data = response.json()
        if data.get("code") == "ok":
            return {"status": "success", "message_id": data.get("message_id", "")}
        return {"status": "error", "reason": data.get("message", str(response.status_code))}
    except Exception as exc:
        return {"status": "error", "reason": str(exc)}


def create_receipt_link(
    data: dict,
    tenant=None,
    receipt_type: str = "receipt",
) -> str:
    """Persist receipt/bill data and return a public URL the parent can open."""
    link = PaymentReceiptLink.objects.create(
        data=data,
        tenant=tenant,
        receipt_type=receipt_type,
        expires_at=timezone.now() + timedelta(days=90),
    )
    base_url = getattr(settings, "FRONTEND_BASE_URL", "https://schooldom.academy").rstrip("/")
    return f"{base_url}/api/finance/receipt/{link.token}/"


def send_payment_receipt(
    to_email: str,
    message: str,
    receipt_url: str = "",
    data: dict = None,
    receipt_type: str = "receipt",
) -> dict:
    """Send payment receipt/bill as an HTML email with the receipt attached as receipt.html."""
    if not to_email:
        return {"sent": False, "channel": "none", "error": "No email address"}
    try:
        from django.core.mail import EmailMultiAlternatives
        from django.template.loader import render_to_string

        d = data or {}
        school_name = d.get("school_name") or "School"
        if receipt_type == "bill":
            subject = f"Fee Statement — {school_name}"
        else:
            status_label = "Fully Paid" if d.get("payment_status") == "paid" else "Partial Payment"
            subject = f"Payment Receipt ({status_label}) — {school_name}"

        class _Link:
            pass

        link_obj = _Link()
        link_obj.receipt_type = receipt_type
        link_obj.created_at = timezone.now()
        link_obj.expires_at = timezone.now() + timedelta(days=90)

        html_body = render_to_string("finance/receipt.html", {"link": link_obj, "data": d})

        plain_body = message
        if receipt_url:
            plain_body += f"\nView online: {receipt_url}"

        em = EmailMultiAlternatives(
            subject=subject,
            body=plain_body,
            from_email=None,
            to=[to_email],
        )
        em.attach_alternative(html_body, "text/html")
        em.attach("receipt.html", html_body, "text/html")
        em.send()

        logger.info("Receipt email sent to %s (type=%s)", to_email, receipt_type)
        return {"sent": True, "channel": "email"}
    except Exception as exc:
        logger.error("Receipt email to %s failed: %s", to_email, exc)
        return {"sent": False, "channel": "none", "email_error": str(exc)}


def build_paystack_receipt_message(
    student_name: str,
    class_name: str,
    amount_paid: Decimal,
    fee_total: Decimal,
    payment_status: str,
    school_name: str = "",
) -> str:
    """Build SMS/WhatsApp receipt for a Paystack payment."""
    prefix = school_name if school_name else "School"
    school_tag = f" at {school_name}" if school_name else ""
    if payment_status == "paid":
        return (
            f"{prefix}: Payment confirmed! ₦{amount_paid:,.2f} received for "
            f"{student_name} ({class_name}){school_tag}. Fees FULLY PAID."
        )
    remaining = fee_total - amount_paid
    return (
        f"{prefix}: ₦{amount_paid:,.2f} received for {student_name} ({class_name}){school_tag}. "
        f"Outstanding balance: ₦{remaining:,.2f}."
    )


def allocate_split_payment(
    parent_id,
    amount_paid: Decimal,
    paystack_ref: str,
    transaction_id: str,
) -> dict:
    """
    Allocate a Paystack split payment across the parent's children's fees.

    `amount_paid` is what Paystack reports (total the parent paid).
    We consume fees in order (oldest-due first):
      - per fee cost to parent = tuition + 0.3% (schooldom_fee_for(tuition))
      - after all fees, ≈₦300 Paystack flat fee remains — that is NOT overpayment
      - any amount beyond that is credited to the parent's wallet

    Rules:
    - remaining >= tuition + 0.3%  → full payment (status=paid)
    - remaining > 0.3%             → partial (apply what's left minus 0.3%)
    - remaining <= 0.3%            → stop
    """
    from users.models import ParentProfile, User

    amount_paid = _as_decimal(amount_paid)

    try:
        parent_profile = ParentProfile.objects.select_related("user").get(user_id=parent_id)
        students = parent_profile.children.all()
    except ParentProfile.DoesNotExist:
        students = []

    unpaid_fees = (
        SchoolFee.objects.filter(
            student__in=students,
            status__in=[SchoolFee.STATUS_PENDING, SchoolFee.STATUS_OVERDUE, SchoolFee.STATUS_PARTIAL],
        )
        .select_related("student", "student__user", "student__user__tenant", "student__current_class")
        .order_by("due_date", "created_at")
    )

    parent_email = (parent_profile.user.email if parent_profile and parent_profile.user else "") or ""

    remaining = amount_paid
    allocations = []

    for fee in unpaid_fees:
        if remaining <= 0:
            break

        already_paid = fee.amount_paid or Decimal("0.00")
        tuition_left = fee.amount - already_paid
        if tuition_left <= 0:
            continue

        # Per-fee cost to parent = tuition + 0.3% Schooldom fee
        s_fee = schooldom_fee_for(tuition_left)
        total_due = tuition_left + s_fee

        student = fee.student
        student_name = student.user.get_full_name() if student and student.user else ""
        class_obj = getattr(student, "current_class", None)
        class_name = class_obj.name if class_obj else ""
        school_name = getattr(getattr(student, "user", None), "tenant", None)
        school_name = getattr(school_name, "name", "") if school_name else ""

        if remaining >= total_due:
            fee.amount_paid = already_paid + tuition_left
            fee.status = SchoolFee.STATUS_PAID
            fee.payment_date = timezone.now()
            fee.last_payment_date = timezone.now()
            fee.paystack_ref = paystack_ref
            fee.save(update_fields=["amount_paid", "status", "payment_date", "last_payment_date", "paystack_ref", "updated_at"])

            FeeAllocation.objects.create(
                fee=fee,
                transaction_id=transaction_id,
                amount_allocated=tuition_left,
                paystack_fee_paid=Decimal("0.00"),
                schooldom_fee_paid=s_fee,
                status=FeeAllocation.STATUS_PAID,
            )
            allocations.append({
                "fee_id": str(fee.id),
                "student_name": student_name,
                "class": class_name,
                "tuition_paid": float(tuition_left),
                "status": "paid",
                "remaining_balance": 0,
            })
            remaining -= total_due

            if parent_email:
                tenant_obj = getattr(getattr(student, "user", None), "tenant", None)
                receipt_data = {
                    "type": "receipt",
                    "school_name": school_name,
                    "student_name": student_name,
                    "class_name": class_name,
                    "amount_paid": str(tuition_left),
                    "fee_total": str(fee.amount),
                    "balance_remaining": "0.00",
                    "payment_status": "paid",
                    "payment_date": timezone.now().strftime("%d %b %Y"),
                    "reference": paystack_ref,
                }
                receipt_url = create_receipt_link(receipt_data, tenant=tenant_obj)
                send_payment_receipt(
                    parent_email,
                    build_paystack_receipt_message(student_name, class_name, tuition_left, fee.amount, "paid", school_name),
                    receipt_url=receipt_url,
                    data=receipt_data,
                    receipt_type="receipt",
                )

        elif remaining > s_fee:
            allocated = remaining - s_fee
            fee.amount_paid = already_paid + allocated
            fee.status = SchoolFee.STATUS_PARTIAL
            fee.last_payment_date = timezone.now()
            fee.paystack_ref = paystack_ref
            fee.save(update_fields=["amount_paid", "status", "last_payment_date", "paystack_ref", "updated_at"])

            FeeAllocation.objects.create(
                fee=fee,
                transaction_id=transaction_id,
                amount_allocated=allocated,
                paystack_fee_paid=Decimal("0.00"),
                schooldom_fee_paid=s_fee,
                status=FeeAllocation.STATUS_PARTIAL,
            )
            balance_left = tuition_left - allocated
            allocations.append({
                "fee_id": str(fee.id),
                "student_name": student_name,
                "class": class_name,
                "tuition_paid": float(allocated),
                "status": "partial",
                "remaining_balance": float(balance_left + schooldom_fee_for(balance_left)),
            })
            remaining = Decimal("0.00")

            if parent_email:
                tenant_obj = getattr(getattr(student, "user", None), "tenant", None)
                balance_remaining = tuition_left - allocated
                receipt_data = {
                    "type": "receipt",
                    "school_name": school_name,
                    "student_name": student_name,
                    "class_name": class_name,
                    "amount_paid": str(allocated),
                    "fee_total": str(fee.amount),
                    "balance_remaining": str(balance_remaining),
                    "payment_status": "partial",
                    "payment_date": timezone.now().strftime("%d %b %Y"),
                    "reference": paystack_ref,
                }
                receipt_url = create_receipt_link(receipt_data, tenant=tenant_obj)
                send_payment_receipt(
                    parent_email,
                    build_paystack_receipt_message(student_name, class_name, allocated, fee.amount, "partial", school_name),
                    receipt_url=receipt_url,
                    data=receipt_data,
                    receipt_type="receipt",
                )
        else:
            remaining = Decimal("0.00")
            break

    # After allocating all fees, ≈₦300 Paystack flat fee remains in `remaining`.
    # That is NOT overpayment — it was charged to parent to cover Paystack's processing.
    # Only credit to wallet if there's genuine surplus beyond the Paystack flat fee.
    overpayment = Decimal("0.00")
    surplus = remaining - PAYSTACK_FLAT_FEE
    if surplus > Decimal("0.50"):   # 50 kobo threshold to avoid floating-point noise
        overpayment = surplus
        try:
            parent_user = User.objects.get(id=parent_id)
            wallet = Wallet.objects.get(user=parent_user)
            credit_wallet(
                wallet,
                overpayment,
                Transaction.ADJUSTMENT_CREDIT,
                generate_reference("OVP"),
                f"Overpayment from Paystack transaction {paystack_ref}",
                metadata={"paystack_ref": paystack_ref},
            )
        except Exception:
            pass

    return {
        "allocations": allocations,
        "overpayment": float(overpayment),
        "total_allocated": float(amount_paid - overpayment),
        "allocated_count": len([a for a in allocations if a["status"] in ("paid", "partial")]),
    }


def process_paystack_webhook(data: dict) -> dict:
    """
    Process a Paystack webhook event for split payments.
    
    Args:
        data: Webhook payload data
        
    Returns:
        dict: Processing result
    """
    event = data.get('event')

    if event != 'charge.success':
        return {'status': 'ignored', 'event': event}

    transaction_data = data.get('data', {})
    reference = transaction_data.get('reference')
    channel = transaction_data.get('channel', '')

    # Dedicated virtual account payment (DVA / dedicated_nuban)
    if channel == 'dedicated_nuban':
        account_number = (
            transaction_data.get('authorization', {}).get('receiver_bank_account_number')
            or transaction_data.get('dedicated_account', {}).get('account_number')
            or ''
        )
        amount_kobo = transaction_data.get('amount', 0)
        amount_naira = Decimal(str(amount_kobo)) / 100

        from core.models import SchoolTenant
        # Attempt to identify tenant from metadata
        tenant = None
        customer_meta = transaction_data.get('customer', {})
        meta_tenant_id = transaction_data.get('metadata', {}).get('school_id')
        if meta_tenant_id:
            try:
                tenant = SchoolTenant.objects.get(id=meta_tenant_id)
            except SchoolTenant.DoesNotExist:
                pass

        return process_virtual_account_payment(
            tenant=tenant,
            account_number=account_number,
            amount_naira=amount_naira,
            paystack_reference=reference or f"DVA-{account_number}-{amount_kobo}",
            metadata={'webhook_data': transaction_data},
        )
    
    if not reference:
        raise ValueError("No transaction reference in webhook")
    
    # Find the transaction record
    try:
        tx = Transaction.objects.get(paystack_ref=reference)
    except Transaction.DoesNotExist:
        # Create a new transaction if not found
        # This handles webhook arriving before our callback
        tx = Transaction.objects.create(
            paystack_ref=reference,
            amount=transaction_data.get('amount', 0) / 100,
            tx_type=Transaction.SPLIT_PAYMENT,
            status=Transaction.STATUS_PENDING,
            reference=generate_reference('SPL'),
            provider='paystack',
            metadata={'webhook_data': transaction_data}
        )
    
    if tx.status == Transaction.STATUS_SUCCESS:
        return {'status': 'already_processed', 'reference': reference}
    
    # Verify the transaction
    try:
        verification = verify_paystack_transaction(reference)
    except Exception as e:
        return {'status': 'error', 'message': str(e)}
    
    # Check if successful
    if verification.get('status') != 'success':
        tx.status = Transaction.STATUS_FAILED
        tx.metadata = {**tx.metadata, 'verification': verification}
        tx.save()
        return {'status': 'failed', 'reference': reference}
    
    amount_paid = Decimal(str(verification.get('amount', 0))) / 100
    
    # Update transaction
    tx.status = Transaction.STATUS_SUCCESS
    tx.amount = amount_paid
    tx.metadata = {**tx.metadata, 'verification': verification}
    tx.save()
    
    # Allocate payment
    parent_id = tx.metadata.get('parent_id') or tx.parent_id
    if not parent_id:
        return {'status': 'error', 'message': 'No parent ID found'}
    
    allocation_result = allocate_split_payment(
        parent_id=parent_id,
        amount_paid=amount_paid,
        paystack_ref=reference,
        transaction_id=tx.id
    )
    
    # Update transaction allocation status
    if allocation_result['overpayment'] > 0:
        tx.allocation_status = Transaction.ALLOCATION_OVERPAID
    elif any(a['status'] == 'partial' for a in allocation_result['allocations']):
        tx.allocation_status = Transaction.ALLOCATION_PARTIAL
    else:
        tx.allocation_status = Transaction.ALLOCATION_ALLOCATED
    
    tx.fee_ids = [a['fee_id'] for a in allocation_result['allocations'] if a.get('fee_id')]
    tx.save()
    
    return {
        'status': 'success',
        'reference': reference,
        'allocation': allocation_result
    }


def initialize_paystack_school_fee_payment(
    parent_user,
    fee_ids: list,
    callback_url: str = ""
) -> dict:
    """
    Initialize a Paystack split payment for school fees.
    
    Args:
        parent_user: Parent user object
        fee_ids: List of SchoolFee IDs to pay
        callback_url: Optional callback URL
        
    Returns:
        dict: Payment initialization result
    """
    # Get payment breakdown
    breakdown = get_fee_payment_breakdown(fee_ids)
    
    # Get school from fees
    fees = SchoolFee.objects.filter(id__in=fee_ids)
    if not fees.exists():
        raise ValueError("No valid fees found")
    
    # Get first fee's school (assuming all fees are for same school)
    first_fee = fees.first()
    school = first_fee.student.user.tenant if first_fee.student else None
    
    if not school:
        raise ValueError("School not found for fees")
    
    # Get or create admin wallet — ensure school subaccount exists
    admin_wallet = get_or_create_admin_wallet(school)

    # Clear a subaccount that was deleted on the Paystack dashboard so a
    # fresh one is recreated below instead of failing the payment.
    if admin_wallet.subaccount_code:
        sync = sync_school_subaccount_with_paystack(school)
        if sync.get("cleared"):
            admin_wallet.refresh_from_db()

    if not admin_wallet.subaccount_code:
        if not admin_wallet.bank_account_number or not admin_wallet.bank_code:
            raise ValueError("School bank account not configured. Set up the school's bank details first.")
        subaccount = create_paystack_subaccount(
            business_name=school.name,
            bank_code=admin_wallet.bank_code,
            account_number=admin_wallet.bank_account_number,
        )
        admin_wallet.subaccount_code = subaccount['subaccount_code']
        admin_wallet.save(update_fields=['subaccount_code', 'updated_at'])

    # Create pending transaction record
    reference = generate_reference('PAY')
    fee_ids_str = [str(f) for f in fee_ids]
    tx = Transaction.objects.create(
        parent_id=parent_user.id,
        school_id=school.id,
        amount=Decimal(str(breakdown['grand_total'])),
        tuition_amount=Decimal(str(breakdown['subtotal'])),
        schooldom_markup=Decimal(str(breakdown['schooldom_fee_total'])),
        paystack_fee_amount=Decimal(str(breakdown['paystack_fee'])),
        tx_type=Transaction.SPLIT_PAYMENT,
        status=Transaction.STATUS_PENDING,
        reference=reference,
        provider='paystack',
        fee_ids=fee_ids_str,
        metadata={
            'fee_ids': fee_ids_str,
            'parent_id': str(parent_user.id),
            'breakdown': breakdown,
        },
    )

    # Initialize Paystack split payment
    # transaction_charge = 0.3% schooldom fees + ₦300 Paystack flat → all goes to main account
    # bearer = "account" → Schooldom main account pays Paystack's actual processing fee
    # school subaccount receives: grand_total − transaction_charge = exact tuition total
    payment_data = initialize_paystack_split_payment(
        email=parent_user.email,
        amount=Decimal(str(breakdown['grand_total'])),
        subaccount_code=admin_wallet.subaccount_code,
        transaction_charge=Decimal(str(breakdown['transaction_charge'])),
        metadata={
            'parent_id': str(parent_user.id),
            'transaction_id': str(tx.id),
            'fee_ids': fee_ids_str,
            'school_id': str(school.id),
        },
        callback_url=callback_url,
    )
    
    # Update transaction with Paystack reference
    tx.paystack_ref = payment_data['reference']
    tx.save()
    
    return {
        'authorization_url': payment_data['authorization_url'],
        'reference': payment_data['reference'],
        'transaction_id': str(tx.id),
        'breakdown': breakdown,
        'access_code': payment_data.get('access_code', ''),
        'amount': breakdown['grand_total']
    }


def get_school_payment_split_status(school) -> dict:
    """
    Get payment split configuration status for a school.
    
    Args:
        school: School tenant object
        
    Returns:
        dict: Split configuration status
    """
    admin_wallet = get_or_create_admin_wallet(school)

    # If the subaccount was deleted on the Paystack dashboard, clear it locally
    # so the setup screen offers a fresh setup instead of a dead code.
    sync = {"cleared": False}
    if admin_wallet.subaccount_code:
        sync = sync_school_subaccount_with_paystack(school)
        if sync.get("cleared"):
            admin_wallet.refresh_from_db()

    return {
        'school_name': school.name,
        'subaccount_cleared': sync.get('cleared', False),
        'has_subaccount': bool(admin_wallet.subaccount_code),
        'has_split': bool(admin_wallet.split_code),
        'subaccount_code': admin_wallet.subaccount_code,
        'split_code': admin_wallet.split_code,
        'has_bank_details': bool(
            admin_wallet.bank_account_number and 
            admin_wallet.bank_code and 
            admin_wallet.bank_account_name
        ),
        'bank_name': admin_wallet.bank_code,
        'account_name': admin_wallet.bank_account_name,
        'account_number': admin_wallet.bank_account_number[:4] + '****' if admin_wallet.bank_account_number else ''
    }


# ============================================================
# END OF PAYSTACK SPLIT PAYMENT INTEGRATION
# ============================================================


def _flutterwave_headers():
    secret = getattr(settings, "FLUTTERWAVE_SECRET_KEY", "")
    if not secret:
        raise RuntimeError("FLUTTERWAVE_SECRET_KEY is not configured.")
    return {
        "Authorization": f"Bearer {secret}",
        "Content-Type": "application/json",
    }


def _flutterwave_base_url():
    return getattr(settings, "FLUTTERWAVE_BASE_URL", "https://api.flutterwave.com/v3").rstrip("/")


def _flutterwave_json(response):
    try:
        return response.json()
    except ValueError:
        response.raise_for_status()
        return {}


def active_payment_provider():
    provider = str(getattr(settings, "PAYMENT_PROVIDER", "flutterwave") or "flutterwave").strip().lower()
    return provider if provider in {"flutterwave", "kuda", "paystack"} else "flutterwave"


def _provider_success_status(value):
    return str(value or "").strip().lower() in {"success", "successful", "completed", "complete", "paid"}


def _kuda_headers():
    headers = {"Content-Type": "application/json"}
    api_key = getattr(settings, "KUDA_API_KEY", "")
    client_id = getattr(settings, "KUDA_CLIENT_ID", "")
    client_secret = getattr(settings, "KUDA_CLIENT_SECRET", "")
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    if client_id:
        headers["X-Client-Id"] = client_id
    if client_secret:
        headers["X-Client-Secret"] = client_secret
    return headers


def _kuda_base_url():
    base_url = getattr(settings, "KUDA_BASE_URL", "")
    if not base_url:
        raise RuntimeError("KUDA_BASE_URL is not configured.")
    return base_url.rstrip("/")


def _kuda_json(response):
    try:
        data = response.json()
    except ValueError:
        response.raise_for_status()
        return {}
    if response.status_code >= 400:
        raise RuntimeError(data.get("message") or data.get("error") or "Kuda request failed.")
    return data


def _kuda_collection_account():
    account_number = getattr(settings, "KUDA_COLLECTION_ACCOUNT_NUMBER", "")
    if not account_number:
        raise RuntimeError("KUDA_COLLECTION_ACCOUNT_NUMBER is not configured.")
    return {
        "bank_name": getattr(settings, "KUDA_COLLECTION_BANK_NAME", "Kuda Microfinance Bank"),
        "account_name": getattr(settings, "KUDA_COLLECTION_ACCOUNT_NAME", "SchoolDom"),
        "account_number": account_number,
    }


def _kuda_account_from_response(data):
    payload = data.get("data") if isinstance(data.get("data"), dict) else data
    return {
        "account_number": str(
            payload.get("account_number")
            or payload.get("accountNumber")
            or payload.get("virtualAccountNumber")
            or payload.get("nuban")
            or ""
        ).strip(),
        "account_name": str(
            payload.get("account_name")
            or payload.get("accountName")
            or payload.get("virtualAccountName")
            or payload.get("name")
            or ""
        ).strip(),
        "bank_name": str(
            payload.get("bank_name")
            or payload.get("bankName")
            or payload.get("bank")
            or getattr(settings, "KUDA_COLLECTION_BANK_NAME", "Kuda Microfinance Bank")
        ).strip(),
        "reference": str(
            payload.get("reference")
            or payload.get("trackingReference")
            or payload.get("accountReference")
            or payload.get("id")
            or ""
        ).strip(),
        "status": str(payload.get("status") or payload.get("state") or "active").strip(),
        "raw": payload,
    }


def provision_kuda_admin_virtual_account(admin_wallet: AdminWallet, actor=None):
    """Create or return the Kuda virtual account assigned to a school admin wallet."""
    if admin_wallet.kuda_virtual_account_number:
        return admin_wallet
    if not admin_wallet.tenant_id:
        raise ValueError("A school tenant is required before creating a Kuda virtual account.")

    tenant = admin_wallet.tenant
    reference = f"SCH-{tenant.schema_name}-{admin_wallet.id}".upper()
    payload = {
        "reference": reference,
        "account_name": f"{tenant.name} Fees",
        "customer": {
            "name": tenant.name,
            "email": tenant.email or "",
            "phone": tenant.phone or "",
        },
        "metadata": {
            "tenant_id": str(tenant.id),
            "school_code": tenant.schema_name,
            "purpose": "school_fee_collection",
        },
    }
    response = requests.post(
        f"{_kuda_base_url()}/{getattr(settings, 'KUDA_VIRTUAL_ACCOUNT_ENDPOINT', '/virtual-accounts').lstrip('/')}",
        json=payload,
        headers=_kuda_headers(),
        timeout=getattr(settings, "KUDA_REQUEST_TIMEOUT", 25),
    )
    data = _kuda_json(response)
    account = _kuda_account_from_response(data)
    if not account["account_number"]:
        raise RuntimeError("Kuda did not return a virtual account number.")

    admin_wallet.kuda_virtual_account_number = account["account_number"]
    admin_wallet.kuda_virtual_account_name = account["account_name"] or payload["account_name"]
    admin_wallet.kuda_virtual_account_bank_name = account["bank_name"]
    admin_wallet.kuda_virtual_account_reference = account["reference"] or reference
    admin_wallet.kuda_virtual_account_status = account["status"]
    admin_wallet.kuda_virtual_account_metadata = account["raw"]
    admin_wallet.bank_account_number = admin_wallet.kuda_virtual_account_number
    admin_wallet.bank_account_name = admin_wallet.kuda_virtual_account_name
    admin_wallet.bank_code = admin_wallet.kuda_virtual_account_bank_name
    admin_wallet.save(
        update_fields=[
            "kuda_virtual_account_number",
            "kuda_virtual_account_name",
            "kuda_virtual_account_bank_name",
            "kuda_virtual_account_reference",
            "kuda_virtual_account_status",
            "kuda_virtual_account_metadata",
            "bank_account_number",
            "bank_account_name",
            "bank_code",
            "updated_at",
        ]
    )
    record_finance_activity(
        tenant,
        actor,
        "kuda_virtual_account_created",
        "Created Kuda school fee collection account.",
        reference=admin_wallet.kuda_virtual_account_reference,
        metadata={"account_number": admin_wallet.kuda_virtual_account_number},
    )
    return admin_wallet


def get_or_create_admin_wallet(tenant=None) -> AdminWallet:
    wallet, _ = AdminWallet.objects.get_or_create(tenant=tenant)
    return wallet


def record_finance_activity(tenant, actor, action, description, amount=Decimal("0.00"), currency="NGN", reference="", metadata=None):
    """Append an immutable finance audit record."""
    try:
        amount = Decimal(str(amount or "0.00")).quantize(Decimal("0.01"))
    except Exception:
        amount = Decimal("0.00")
    try:
        return FinanceLedgerLog.objects.create(
            tenant=tenant,
            actor=actor,
            action=str(action or "finance_activity")[:80],
            description=str(description or "Financial activity recorded.")[:255],
            amount=amount,
            currency=str(currency or "NGN")[:5],
            reference=str(reference or "")[:100],
            metadata=metadata or {},
        )
    except (OperationalError, ProgrammingError):
        return None


def get_or_create_activation_credit_pool(tenant=None) -> ActivationCreditPool:
    price = activation_credit_price_for_tenant(tenant)
    pool, _ = ActivationCreditPool.objects.get_or_create(
        tenant=tenant,
        defaults={"price_per_credit": price},
    )
    return pool


def is_non_k12_tenant(tenant) -> bool:
    return bool(tenant and (getattr(tenant, "school_type", "k12") or "k12") == "non_k12")


def activation_credit_price_for_tenant(tenant) -> Decimal:
    return NON_K12_ACTIVATION_CREDIT_PRICE if is_non_k12_tenant(tenant) else K12_ACTIVATION_CREDIT_PRICE


def activation_credit_duration_for_tenant(tenant):
    if is_non_k12_tenant(tenant):
        return NON_K12_TOKEN_DURATION_MONTHS, NON_K12_TOKEN_DURATION_DAYS
    return K12_TOKEN_DURATION_MONTHS, K12_TOKEN_DURATION_DAYS


def grant_school_registration_credits(tenant, credits=50, actor=None):
    """Gift activation tokens to a newly registered school."""
    credits = int(credits or 0)
    if credits <= 0:
        raise ValueError("tokens must be a positive number.")

    pool = get_or_create_activation_credit_pool(tenant)
    with transaction.atomic():
        locked_pool = ActivationCreditPool.objects.select_for_update().get(pk=pool.pk)
        locked_pool.balance += credits
        locked_pool.save(update_fields=["balance", "updated_at"])
        ActivationCreditTransaction.objects.create(
            pool=locked_pool,
            tx_type=ActivationCreditTransaction.ADJUSTMENT,
            status=ActivationCreditTransaction.STATUS_SUCCESS,
            credits=credits,
            price_per_credit=locked_pool.price_per_credit,
            amount=Decimal("0.00"),
            reference=generate_reference("GFT"),
            narration="New school registration bonus",
            provider="system",
            metadata={"bonus": "school_registration", "tenant_id": str(tenant.id) if tenant else ""},
            created_by=actor,
        )
    pool.refresh_from_db()
    return pool


def get_or_create_student_activation_credit(student_profile) -> StudentActivationCredit:
    credit, _ = StudentActivationCredit.objects.get_or_create(student=student_profile)
    return credit


def ensure_student_wallet(user) -> Wallet:
    if getattr(user, "role", "") != "student":
        raise ValueError("Wallets can only be created for student accounts.")
    wallet, created = Wallet.objects.get_or_create(user=user)
    return wallet


def add_activation_credits_to_pool(tenant, credits, actor=None):
    credits = int(credits or 0)
    if credits <= 0:
        raise ValueError("tokens must be a positive number.")
    pool = get_or_create_activation_credit_pool(tenant)
    bonus_credits = activation_credit_bonus_for_purchase(credits)
    total_credits = credits + bonus_credits
    amount = pool.price_per_credit * credits
    with transaction.atomic():
        locked = ActivationCreditPool.objects.select_for_update().get(pk=pool.pk)
        locked.balance += total_credits
        amount = locked.price_per_credit * credits
        locked.save(update_fields=["balance", "updated_at"])
        ActivationCreditTransaction.objects.create(
            pool=locked,
            tx_type=ActivationCreditTransaction.PURCHASE,
            credits=credits,
            price_per_credit=locked.price_per_credit,
            amount=amount,
            reference=generate_reference("CRP"),
            narration="Activation token purchase",
            status=ActivationCreditTransaction.STATUS_SUCCESS,
            metadata={
                "purchased_credits": credits,
                "bonus_credits": bonus_credits,
                "total_credits": total_credits,
                "bonus_rule": f"{ACTIVATION_CREDIT_BONUS_AMOUNT} free per {ACTIVATION_CREDIT_BONUS_INTERVAL} purchased",
            },
            created_by=actor,
        )
    pool.refresh_from_db()
    return pool


def adjust_activation_credit_pool(tenant, credits, actor=None, narration="Super admin token adjustment"):
    credits = int(credits or 0)
    if credits == 0:
        raise ValueError("tokens must not be zero.")

    pool = get_or_create_activation_credit_pool(tenant)
    with transaction.atomic():
        locked = ActivationCreditPool.objects.select_for_update().get(pk=pool.pk)
        next_balance = locked.balance + credits
        if next_balance < 0:
            raise ValueError(f"Insufficient activation tokens. Available: {locked.balance}.")
        locked.balance = next_balance
        locked.save(update_fields=["balance", "updated_at"])
        ActivationCreditTransaction.objects.create(
            pool=locked,
            tx_type=ActivationCreditTransaction.ADJUSTMENT,
            status=ActivationCreditTransaction.STATUS_SUCCESS,
            credits=credits,
            price_per_credit=locked.price_per_credit,
            amount=Decimal("0.00"),
            reference=generate_reference("ADJ"),
            narration=narration,
            provider="system",
            metadata={"manual_adjustment": True, "tenant_id": str(tenant.id) if tenant else ""},
            created_by=actor,
        )
    pool.refresh_from_db()
    return pool


def initialize_flutterwave_transaction(user, amount: Decimal, reference: str, metadata=None, callback_url=""):
    user_name = user.email
    if hasattr(user, "get_full_name") and callable(user.get_full_name):
        user_name = user.get_full_name() or user.email

    payload = {
        "tx_ref": reference,
        "amount": str(_as_decimal(amount)),
        "currency": "NGN",
        "redirect_url": callback_url or getattr(settings, "FLUTTERWAVE_CALLBACK_URL", "") or "https://your-domain.com/verify-payment",
        "customer": {
            "email": user.email,
            "name": user_name,
        },
        "customizations": {
            "title": "EduConnect",
            "description": f"Payment - {reference}",
        },
        "metadata": {
            **(metadata or {}),
            "customer_name": user_name,
        },
    }

    response = requests.post(
        f"{_flutterwave_base_url()}/payments",
        json=payload,
        headers=_flutterwave_headers(),
        timeout=25,
    )
    data = _flutterwave_json(response)
    if data.get("status") != "success":
        raise RuntimeError(data.get("message") or "Unable to initialize Flutterwave payment.")
    payment_data = data.get("data") or {}
    checkout_link = payment_data.get("link") or payment_data.get("authorization_url")
    return {
        **payment_data,
        "link": checkout_link,
        "authorization_url": checkout_link,
    }


def verify_flutterwave_transaction(reference: str):
    response = requests.get(
        f"{_flutterwave_base_url()}/transactions/verify_by_reference?tx_ref={reference}",
        headers=_flutterwave_headers(),
        timeout=25,
    )
    data = _flutterwave_json(response)
    if data.get("status") != "success":
        raise RuntimeError(data.get("message") or "Unable to verify Flutterwave payment.")
    transaction_data = data.get("data") or {}
    if transaction_data.get("status") != "successful":
        raise RuntimeError("Payment was not successful.")
    return transaction_data


def _kuda_school_collection_account(user, actor=None):
    admin_wallet = get_or_create_admin_wallet(getattr(user, "tenant", None))
    if admin_wallet.kuda_virtual_account_number:
        return {
            "bank_name": admin_wallet.kuda_virtual_account_bank_name or "Kuda Microfinance Bank",
            "account_name": admin_wallet.kuda_virtual_account_name,
            "account_number": admin_wallet.kuda_virtual_account_number,
        }
    if active_payment_provider() == "kuda" and getattr(settings, "KUDA_BASE_URL", ""):
        admin_wallet = provision_kuda_admin_virtual_account(admin_wallet, actor=actor or user)
        return {
            "bank_name": admin_wallet.kuda_virtual_account_bank_name or "Kuda Microfinance Bank",
            "account_name": admin_wallet.kuda_virtual_account_name,
            "account_number": admin_wallet.kuda_virtual_account_number,
        }
    if admin_wallet.bank_account_number:
        return {
            "bank_name": admin_wallet.bank_code or "School bank",
            "account_name": admin_wallet.bank_account_name,
            "account_number": admin_wallet.bank_account_number,
        }
    return _kuda_collection_account()


def initialize_kuda_transaction(user, amount: Decimal, reference: str, metadata=None, callback_url=""):
    user_name = user.email
    if hasattr(user, "get_full_name") and callable(user.get_full_name):
        user_name = user.get_full_name() or user.email
    account = _kuda_school_collection_account(user, actor=user)
    amount = _as_decimal(amount)
    narration = f"SCH/KUDA/{reference}"
    return {
        "provider": "kuda",
        "status": "pending_bank_transfer",
        "reference": reference,
        "authorization_url": "",
        "link": "",
        "access_code": "",
        "amount": str(amount),
        "currency": "NGN",
        "customer": {"email": user.email, "name": user_name},
        "metadata": metadata or {},
        "bank_transfer": {
            **account,
            "amount": str(amount),
            "narration": narration,
            "reference": reference,
            "instructions": "Transfer the exact amount to this Kuda collection account and use the narration/reference shown.",
        },
    }


def verify_kuda_transaction(reference: str):
    endpoint = getattr(settings, "KUDA_TRANSACTION_VERIFY_ENDPOINT", "/transactions/{reference}")
    endpoint = endpoint.replace("{reference}", quote(str(reference), safe=""))
    response = requests.get(
        f"{_kuda_base_url()}/{endpoint.lstrip('/')}",
        headers=_kuda_headers(),
        timeout=getattr(settings, "KUDA_REQUEST_TIMEOUT", 25),
    )
    data = _kuda_json(response)
    transaction_data = data.get("data") if isinstance(data.get("data"), dict) else data
    status_value = transaction_data.get("status") or transaction_data.get("transactionStatus") or transaction_data.get("state")
    if not _provider_success_status(status_value):
        raise RuntimeError("Kuda payment was not successful.")
    return {
        **transaction_data,
        "status": "successful",
        "amount": transaction_data.get("amount") or transaction_data.get("Amount") or transaction_data.get("paid_amount") or 0,
        "provider": "kuda",
    }


def _payment_provider_for_reference(reference):
    reference = str(reference or "").strip()
    tx = Transaction.objects.filter(reference=reference).only("provider").first()
    if tx:
        return tx.provider or active_payment_provider()
    credit_tx = ActivationCreditTransaction.objects.filter(reference=reference).only("provider").first()
    if credit_tx:
        return credit_tx.provider or active_payment_provider()
    return active_payment_provider()


def initialize_payment_transaction(user, amount: Decimal, reference: str, metadata=None, callback_url=""):
    provider = active_payment_provider()
    if provider == "paystack":
        raise ValueError("Use initialize_paystack_school_fee_payment for Paystack split payments")
    if provider == "kuda":
        return initialize_kuda_transaction(user, amount, reference, metadata=metadata, callback_url=callback_url)
    return initialize_flutterwave_transaction(user, amount, reference, metadata=metadata, callback_url=callback_url)


def verify_payment_transaction(reference: str):
    provider = _payment_provider_for_reference(reference)
    if provider == "paystack":
        return verify_paystack_transaction(reference)
    if provider == "kuda":
        return verify_kuda_transaction(reference)
    return verify_flutterwave_transaction(reference)


def initialize_activation_credit_purchase(tenant, credits, actor):
    credits = int(credits or 0)
    if credits <= 0:
        raise ValueError("tokens must be a positive number.")
    pool = get_or_create_activation_credit_pool(tenant)
    bonus_credits = activation_credit_bonus_for_purchase(credits)
    total_credits = credits + bonus_credits
    amount = pool.price_per_credit * credits
    reference = generate_reference("CRP")
    ActivationCreditTransaction.objects.create(
        pool=pool,
        tx_type=ActivationCreditTransaction.PURCHASE,
        status=ActivationCreditTransaction.STATUS_PENDING,
        credits=credits,
        price_per_credit=pool.price_per_credit,
        amount=amount,
        reference=reference,
        narration=f"Activation token purchase via {active_payment_provider().title()}",
        provider=active_payment_provider(),
        metadata={
            "tenant_id": str(tenant.id) if tenant else "",
            "credits": credits,
            "purchased_credits": credits,
            "bonus_credits": bonus_credits,
            "total_credits": total_credits,
            "bonus_rule": f"{ACTIVATION_CREDIT_BONUS_AMOUNT} free per {ACTIVATION_CREDIT_BONUS_INTERVAL} purchased",
        },
        created_by=actor,
    )
    init_payload = initialize_payment_transaction(
        user=actor,
        amount=amount,
        reference=reference,
        metadata={
            "purpose": "activation_tokens",
            "credits": credits,
            "purchased_credits": credits,
            "bonus_credits": bonus_credits,
            "total_credits": total_credits,
            "tenant_id": str(tenant.id) if tenant else "",
        },
    )
    ActivationCreditTransaction.objects.filter(reference=reference).update(
        metadata={
            "tenant_id": str(tenant.id) if tenant else "",
            "credits": credits,
            "purchased_credits": credits,
            "bonus_credits": bonus_credits,
            "total_credits": total_credits,
            "bonus_rule": f"{ACTIVATION_CREDIT_BONUS_AMOUNT} free per {ACTIVATION_CREDIT_BONUS_INTERVAL} purchased",
            "authorization_url": init_payload.get("authorization_url"),
            "access_code": init_payload.get("access_code"),
        }
    )
    return {"pool": pool, "reference": reference, "amount": amount, **init_payload}


def verify_activation_credit_purchase(reference, actor=None, verification: Optional[dict] = None):
    tx = ActivationCreditTransaction.objects.select_related("pool").get(reference=reference)
    if tx.tx_type != ActivationCreditTransaction.PURCHASE:
        raise ValueError("Invalid activation token purchase reference.")
    if tx.status == ActivationCreditTransaction.STATUS_SUCCESS:
        return tx.pool

    verification = verification or verify_payment_transaction(reference)
    status_value = str(verification.get("status") or "").lower()
    amount_major = Decimal(str(verification.get("amount") or 0))
    if status_value != "successful":
        tx.status = ActivationCreditTransaction.STATUS_FAILED
        tx.metadata = {**tx.metadata, "verification": verification}
        tx.save(update_fields=["status", "metadata"])
        raise ValueError("Payment not successful.")
    if amount_major < tx.amount:
        tx.status = ActivationCreditTransaction.STATUS_FAILED
        tx.metadata = {**tx.metadata, "verification": verification, "reason": "amount_mismatch"}
        tx.save(update_fields=["status", "metadata"])
        raise ValueError("Payment amount mismatch.")

    with transaction.atomic():
        locked_pool = ActivationCreditPool.objects.select_for_update().get(pk=tx.pool_id)
        locked_tx = ActivationCreditTransaction.objects.select_for_update().get(pk=tx.pk)
        if locked_tx.status != ActivationCreditTransaction.STATUS_SUCCESS:
            bonus_credits = int((locked_tx.metadata or {}).get("bonus_credits") or activation_credit_bonus_for_purchase(locked_tx.credits))
            total_credits = int((locked_tx.metadata or {}).get("total_credits") or (locked_tx.credits + bonus_credits))
            locked_pool.balance += total_credits
            locked_pool.save(update_fields=["balance", "updated_at"])
            locked_tx.status = ActivationCreditTransaction.STATUS_SUCCESS
            locked_tx.metadata = {
                **locked_tx.metadata,
                "purchased_credits": int((locked_tx.metadata or {}).get("purchased_credits") or locked_tx.credits),
                "bonus_credits": bonus_credits,
                "total_credits": total_credits,
                "bonus_rule": f"{ACTIVATION_CREDIT_BONUS_AMOUNT} free per {ACTIVATION_CREDIT_BONUS_INTERVAL} purchased",
                "verification": verification,
            }
            locked_tx.save(update_fields=["status", "metadata"])
    tx.pool.refresh_from_db()
    return tx.pool


def _sweep_student_wallet_to_admin(wallet: Wallet, actor=None, source_reference: str = ""):
    """Move any remaining student wallet balance into the school admin wallet."""
    with transaction.atomic():
        wallet_locked = Wallet.objects.select_for_update().select_related("user").get(pk=wallet.pk)
        sweep_amount = _as_decimal(wallet_locked.balance)
        if sweep_amount <= 0:
            return wallet_locked

        admin_locked = AdminWallet.objects.select_for_update().get(
            pk=get_or_create_admin_wallet(wallet_locked.user.tenant).pk
        )
        wallet_locked.balance -= sweep_amount
        admin_locked.balance += sweep_amount
        wallet_locked.save(update_fields=["balance", "updated_at"])
        admin_locked.save(update_fields=["balance", "updated_at"])
        sweep_reference = generate_reference("SWP")
        metadata = {
            "source_reference": source_reference,
            "student_id": str(wallet_locked.user_id),
            "purpose": "flutterwave_admin_wallet_sweep",
        }
        Transaction.objects.create(
            wallet=wallet_locked,
            amount=sweep_amount,
            currency=wallet_locked.currency,
            tx_type=Transaction.FEE_DEBIT,
            status=Transaction.STATUS_SUCCESS,
            reference=sweep_reference,
            narration="Flutterwave payment moved to school wallet",
            metadata=metadata,
            created_by=actor,
        )
        Transaction.objects.create(
            admin_wallet=admin_locked,
            amount=sweep_amount,
            currency=admin_locked.currency,
            tx_type=Transaction.FEE_CREDIT,
            status=Transaction.STATUS_SUCCESS,
            reference=generate_reference("ADM"),
            narration=f"Flutterwave payment received from {wallet_locked.user.email}",
            metadata={**metadata, "student_wallet_debit_reference": sweep_reference},
            created_by=actor,
        )
        wallet_locked.refresh_from_db()
    return wallet_locked


def _apply_flutterwave_payment_to_admin_and_fees(tx: Transaction, actor=None):
    """Allocate a verified Flutterwave student payment directly into the admin wallet and apply it to school fees."""
    if tx.tx_type != Transaction.FUNDING:
        raise ValueError("Invalid school fee payment reference.")
    wallet = tx.wallet
    if not wallet or not wallet.user:
        raise ValueError("Invalid student wallet transaction.")

    student_profile = getattr(wallet.user, "student_profile", None)
    admin_wallet = get_or_create_admin_wallet(wallet.user.tenant)
    remaining_amount = _as_decimal(tx.amount)
    payment_reference = get_or_create_student_payment_reference(student_profile) if student_profile else None

    with transaction.atomic():
        admin_locked = AdminWallet.objects.select_for_update().get(pk=admin_wallet.pk)
        if student_profile:
            sync_student_class_fees(student_profile, actor=actor or wallet.user)

        fees = []
        if student_profile:
            fees = list(
                SchoolFee.objects.select_for_update()
                .filter(student=student_profile)
                .exclude(status=SchoolFee.STATUS_PAID)
                .order_by("due_date", "created_at")
            )

        for fee in fees:
            if remaining_amount <= 0:
                break
            fee_balance = max(fee.amount - fee_paid_amount(fee), Decimal("0.00"))
            if fee_balance <= 0:
                fee.status = SchoolFee.STATUS_PAID
                fee.save(update_fields=["status", "updated_at"])
                continue

            allocated = min(remaining_amount, fee_balance)
            remaining_amount -= allocated
            admin_locked.balance += allocated
            Transaction.objects.create(
                admin_wallet=admin_locked,
                amount=allocated,
                currency=admin_locked.currency,
                tx_type=Transaction.FEE_CREDIT,
                status=Transaction.STATUS_SUCCESS,
                reference=generate_reference("ADM"),
                narration=f"Flutterwave payment applied to fee • {fee.title}",
                metadata={
                    "fee_id": str(fee.id),
                    "bank_payment_id": tx.reference,
                    "student_id": str(student_profile.id) if student_profile else "",
                    "payment_reference": payment_reference.code if payment_reference else "",
                },
                created_by=actor,
            )
            if allocated >= fee_balance:
                fee.status = SchoolFee.STATUS_PAID
                fee.last_attempted_at = timezone.now()
                fee.save(update_fields=["status", "last_attempted_at", "updated_at"])

        if remaining_amount > 0:
            admin_locked.balance += remaining_amount
            Transaction.objects.create(
                admin_wallet=admin_locked,
                amount=remaining_amount,
                currency=admin_locked.currency,
                tx_type=Transaction.FEE_CREDIT,
                status=Transaction.STATUS_SUCCESS,
                reference=generate_reference("ADM"),
                narration=f"Flutterwave payment received from {wallet.user.email}",
                metadata={
                    "source_reference": tx.reference,
                    "student_id": str(student_profile.id) if student_profile else "",
                },
                created_by=actor,
            )

        if tx.amount > 0:
            admin_locked.save(update_fields=["balance", "updated_at"])

    return admin_wallet


def _admin_wallet_bank_payload(admin_wallet: AdminWallet) -> dict:
    return {
        "account_number": (admin_wallet.bank_account_number or "").strip(),
        "bank_code": (admin_wallet.bank_code or "").strip(),
        "account_name": (admin_wallet.bank_account_name or "").strip(),
    }


def _has_complete_admin_bank_account(admin_wallet: AdminWallet) -> bool:
    bank_payload = _admin_wallet_bank_payload(admin_wallet)
    return all(bank_payload.values())


def settle_flutterwave_school_fee_payment(tx: Transaction, actor=None):
    """Transfer a verified checkout school-fee payment to the school's saved bank account."""
    if not getattr(settings, "FLUTTERWAVE_AUTO_SETTLE_SCHOOL_FEES", True):
        return None
    if tx.tx_type != Transaction.FUNDING or tx.status != Transaction.STATUS_SUCCESS:
        return None

    metadata = tx.metadata or {}
    settlement = metadata.get("admin_bank_settlement") or {}
    if settlement.get("status") == Transaction.STATUS_SUCCESS:
        return settlement

    wallet = tx.wallet
    if not wallet or not wallet.user:
        raise ValueError("Invalid student wallet transaction.")

    admin_wallet = get_or_create_admin_wallet(wallet.user.tenant)
    if not _has_complete_admin_bank_account(admin_wallet):
        settlement = {
            "status": Transaction.STATUS_FAILED,
            "reason": "admin_bank_account_not_configured",
            "message": "School receiving account is not fully configured.",
        }
        tx.metadata = {**metadata, "admin_bank_settlement": settlement}
        tx.save(update_fields=["metadata", "updated_at"])
        return settlement

    reference = generate_reference("SET")
    bank_payload = _admin_wallet_bank_payload(admin_wallet)
    tx.metadata = {
        **metadata,
        "admin_bank_settlement": {
            "status": Transaction.STATUS_PENDING,
            "reference": reference,
            "amount": str(_as_decimal(tx.amount)),
            "bank": bank_payload,
        },
    }
    tx.save(update_fields=["metadata", "updated_at"])

    try:
        initiate_admin_withdrawal(
            admin_wallet,
            tx.amount,
            reference,
            bank_payload=bank_payload,
            actor=actor or wallet.user,
        )
    except Exception as exc:
        tx.refresh_from_db()
        tx.metadata = {
            **(tx.metadata or {}),
            "admin_bank_settlement": {
                "status": Transaction.STATUS_FAILED,
                "reference": reference,
                "amount": str(_as_decimal(tx.amount)),
                "bank": bank_payload,
                "error": str(exc),
            },
        }
        tx.save(update_fields=["metadata", "updated_at"])
        return tx.metadata["admin_bank_settlement"]

    tx.refresh_from_db()
    settlement = {
        "status": Transaction.STATUS_SUCCESS,
        "reference": reference,
        "amount": str(_as_decimal(tx.amount)),
        "bank": bank_payload,
    }
    tx.metadata = {**(tx.metadata or {}), "admin_bank_settlement": settlement}
    tx.save(update_fields=["metadata", "updated_at"])
    admin_wallet.last_settled_at = timezone.now()
    admin_wallet.save(update_fields=["last_settled_at", "updated_at"])
    return settlement


def complete_wallet_funding(reference: str, actor=None, verification: Optional[dict] = None):
    """Verify student payment and move funds to the admin wallet once."""
    tx = Transaction.objects.select_related("wallet", "wallet__user").get(reference=reference)
    if tx.tx_type != Transaction.FUNDING:
        raise ValueError("Invalid school fee payment reference.")
    if tx.status == Transaction.STATUS_SUCCESS:
        settlement = (tx.metadata or {}).get("admin_bank_settlement") or {}
        if settlement.get("status") in {Transaction.STATUS_PENDING, Transaction.STATUS_FAILED}:
            settle_flutterwave_school_fee_payment(tx, actor=actor or tx.wallet.user)
        return tx.wallet

    verification = verification or verify_payment_transaction(reference)
    status_value = str(verification.get("status") or "").lower()
    amount_major = Decimal(str(verification.get("amount") or 0))
    if status_value != "successful":
        tx.status = Transaction.STATUS_FAILED
        tx.metadata = {**tx.metadata, "verification": verification}
        tx.save(update_fields=["status", "metadata", "updated_at"])
        raise ValueError("Payment not successful.")
    if amount_major < tx.amount:
        tx.status = Transaction.STATUS_FAILED
        tx.metadata = {**tx.metadata, "verification": verification, "reason": "amount_mismatch"}
        tx.save(update_fields=["status", "metadata", "updated_at"])
        raise ValueError("Payment amount mismatch.")

    with transaction.atomic():
        locked_tx = Transaction.objects.select_for_update().select_related("wallet", "wallet__user").get(pk=tx.pk)
        if locked_tx.status != Transaction.STATUS_SUCCESS:
            locked_tx.status = Transaction.STATUS_SUCCESS
            locked_tx.metadata = {**locked_tx.metadata, "verification": verification}
            locked_tx.save(update_fields=["status", "metadata", "updated_at"])

    tx.refresh_from_db()
    _apply_flutterwave_payment_to_admin_and_fees(tx, actor=actor or tx.wallet.user)
    settle_flutterwave_school_fee_payment(tx, actor=actor or tx.wallet.user)
    if tx.wallet:
        tx.wallet.refresh_from_db()
    return tx.wallet


def complete_flutterwave_reference(reference: str):
    """Complete any known Flutterwave payment reference from a trusted webhook."""
    return complete_payment_reference(reference)


def complete_payment_reference(reference: str, verification: Optional[dict] = None):
    """Complete any known payment reference from a trusted provider webhook."""
    reference = str(reference or "").strip()
    if not reference:
        raise ValueError("reference is required.")

    verification = verification or verify_payment_transaction(reference)
    if Transaction.objects.filter(reference=reference).exists():
        wallet = complete_wallet_funding(reference, verification=verification)
        return {"kind": "wallet", "wallet_id": str(wallet.id)}
    if ActivationCreditTransaction.objects.filter(reference=reference).exists():
        pool = verify_activation_credit_purchase(reference, verification=verification)
        return {"kind": "activation_credits", "pool_id": str(pool.id)}
    raise ValueError("Unknown payment reference.")


def _add_months(source_date, months):
    month = source_date.month - 1 + months
    year = source_date.year + month // 12
    month = month % 12 + 1
    day = min(source_date.day, 28)
    return source_date.replace(year=year, month=month, day=day)


def _add_activation_token_duration(source_date, tenant, token_units):
    token_units = int(token_units or 1)
    duration_months, duration_days = activation_credit_duration_for_tenant(tenant)
    next_date = _add_months(source_date, duration_months * token_units)
    if duration_days:
        next_date += timedelta(days=duration_days * token_units)
    return next_date


def _student_paid_ratio(student_profile):
    fees = SchoolFee.objects.filter(student=student_profile)
    expected = fees.aggregate(total=Sum("amount"))["total"] or Decimal("0.00")
    if expected <= 0:
        return Decimal("0.00")
    paid = fees.filter(status=SchoolFee.STATUS_PAID).aggregate(total=Sum("amount"))["total"] or Decimal("0.00")
    return paid / expected


def eligible_students_for_activation_credits(tenant, scope="all", include_excluded=False):
    from users.models import StudentProfile

    students = (
        StudentProfile.objects.select_related("user", "current_class")
        .filter(user__tenant=tenant, user__role="student")
        .order_by("user__last_name", "user__first_name", "created_at")
    )
    eligible = []
    for student in students:
        credit = get_or_create_student_activation_credit(student)
        if credit.is_excluded_from_auto_deductions and not include_excluded:
            continue
        if credit.has_login_credit:
            continue
        if scope == "paid_50" and _student_paid_ratio(student) < Decimal("0.50"):
            continue
        eligible.append(student)
    return eligible


def assign_monthly_activation_credits(tenant, scope="all", months=1, actor=None, auto=False, student_id=None):
    token_units = int(months or 1)
    if token_units <= 0:
        raise ValueError("tokens must be a positive number.")
    if scope not in {"all", "paid_50", "student"}:
        raise ValueError("scope must be 'all', 'paid_50', or 'student'.")

    pool = get_or_create_activation_credit_pool(tenant)
    if scope == "student":
        from users.models import StudentProfile

        if not student_id:
            raise ValueError("Select an inactive student to assign credits.")
        try:
            student = StudentProfile.objects.select_related("user", "current_class").get(
                id=student_id,
                user__tenant=tenant,
                user__role="student",
            )
        except StudentProfile.DoesNotExist:
            raise ValueError("Selected student was not found for this school.")
        credit = get_or_create_student_activation_credit(student)
        if credit.is_excluded_from_auto_deductions:
            raise ValueError("Selected student is excluded from activation credit assignment.")
        if credit.has_login_credit:
            raise ValueError("Selected student already has active login credits.")
        students = [student]
    else:
        students = eligible_students_for_activation_credits(tenant, scope=scope, include_excluded=False)
    credits_needed = len(students) * token_units
    if credits_needed <= 0:
        return {"assigned": 0, "skipped": 0, "pool": pool}
    if pool.balance < credits_needed:
        raise ValueError(f"Insufficient activation tokens. Need {credits_needed}, available {pool.balance}.")

    today = timezone.localdate()
    tx_type = ActivationCreditTransaction.AUTO_ASSIGNMENT if auto else ActivationCreditTransaction.ASSIGNMENT
    with transaction.atomic():
        locked_pool = ActivationCreditPool.objects.select_for_update().get(pk=pool.pk)
        locked_pool.balance -= credits_needed
        if auto:
            locked_pool.last_auto_assigned_month = today.strftime("%Y-%m")
        locked_pool.save(update_fields=["balance", "last_auto_assigned_month", "updated_at"])

        for student in students:
            credit = get_or_create_student_activation_credit(student)
            current_until = credit.active_until if credit.active_until and credit.active_until >= today else today
            credit.active_until = _add_activation_token_duration(current_until, tenant, token_units)
            credit.credits_assigned += token_units
            credit.last_credit_assigned_at = timezone.now()
            credit.inactive_since = None
            credit.inactive_flagged_at = None
            credit.is_excluded_from_auto_deductions = False
            credit.save(
                update_fields=[
                    "active_until",
                    "credits_assigned",
                    "last_credit_assigned_at",
                    "inactive_since",
                    "inactive_flagged_at",
                    "is_excluded_from_auto_deductions",
                    "updated_at",
                ]
            )
            ActivationCreditTransaction.objects.create(
                pool=locked_pool,
                student_credit=credit,
                tx_type=tx_type,
                credits=-token_units,
                price_per_credit=locked_pool.price_per_credit,
                amount=locked_pool.price_per_credit * token_units,
                reference=generate_reference("CRA"),
                narration="Monthly student account activation",
                metadata={
                    "scope": scope,
                    "months": token_units,
                    "token_units": token_units,
                    "duration_months_per_token": activation_credit_duration_for_tenant(tenant)[0],
                    "duration_days_per_token": activation_credit_duration_for_tenant(tenant)[1],
                    "student_id": str(student.id),
                },
                created_by=actor,
            )

    pool.refresh_from_db()
    return {"assigned": len(students), "skipped": 0, "pool": pool}


def update_student_activation_alerts(tenant):
    from notifications.models import Notification
    from users.models import StudentProfile
    from users.models import User

    today = timezone.localdate()
    flagged = 0
    admins = list(User.objects.filter(
        tenant=tenant,
        role__in=["school_admin", "principal", "super_admin"],
        is_active=True,
    ))
    students = StudentProfile.objects.select_related("user").filter(user__tenant=tenant, user__role="student")
    for student in students:
        credit = get_or_create_student_activation_credit(student)
        if credit.has_login_credit:
            if credit.inactive_since or credit.inactive_flagged_at or credit.is_excluded_from_auto_deductions:
                credit.inactive_since = None
                credit.inactive_flagged_at = None
                credit.is_excluded_from_auto_deductions = False
                credit.save(update_fields=["inactive_since", "inactive_flagged_at", "is_excluded_from_auto_deductions", "updated_at"])
            continue
        inactive_since = credit.inactive_since or (credit.active_until + timedelta(days=1) if credit.active_until else today)
        days_inactive = (today - inactive_since).days
        if not credit.inactive_since:
            credit.inactive_since = inactive_since
        if days_inactive >= 15 and not credit.is_excluded_from_auto_deductions:
            credit.is_excluded_from_auto_deductions = True
            credit.inactive_flagged_at = timezone.now()
            flagged += 1
            for admin in admins:
                Notification.objects.create(
                    tenant=tenant,
                    user=admin,
                    title="Inactive student token alert",
                    message=f"{student.user.get_full_name() or student.user.email} has been inactive for 15 days and is now excluded from automatic activation token deductions.",
                    notification_type="alert",
                    priority=4,
                    channel="in_app",
                    event_type="activation_credit_inactive_student",
                    reference_id=credit.id,
                    reference_model="finance.StudentActivationCredit",
                    action_text="Open Finance",
                    deep_link="/finance",
                    is_delivered=True,
                    delivered_at=timezone.now(),
                )
        credit.save(update_fields=["inactive_since", "inactive_flagged_at", "is_excluded_from_auto_deductions", "updated_at"])
    return flagged


def ensure_monthly_credit_reminder(tenant):
    today = timezone.localdate()
    if today.day < 25 or not tenant:
        return False
    pool = get_or_create_activation_credit_pool(tenant)
    month_key = today.strftime("%Y-%m")
    if pool.last_reminder_month == month_key:
        return False

    from notifications.models import Notification
    from users.models import User

    admins = User.objects.filter(
        tenant=tenant,
        role__in=["school_admin", "principal", "super_admin"],
        is_active=True,
    )
    for admin in admins:
        Notification.objects.create(
            tenant=tenant,
            user=admin,
            title="Activation tokens due soon",
                message="Purchase or assign student activation tokens for next month. Each token costs N200 and controls student login access only.",
            notification_type="reminder",
            priority=3,
            channel="in_app",
            event_type="activation_credit_reminder",
            action_text="Open Finance",
            deep_link="/finance",
            is_delivered=True,
            delivered_at=timezone.now(),
        )
    pool.last_reminder_month = month_key
    pool.save(update_fields=["last_reminder_month", "updated_at"])
    return True


def run_configured_monthly_auto_assignment(tenant, actor=None):
    pool = get_or_create_activation_credit_pool(tenant)
    month_key = timezone.localdate().strftime("%Y-%m")
    if not pool.auto_assign_enabled or pool.last_auto_assigned_month == month_key:
        return {"assigned": 0, "pool": pool, "ran": False}
    result = assign_monthly_activation_credits(
        tenant,
        scope=pool.auto_assign_scope,
        months=1,
        actor=actor,
        auto=True,
    )
    result["ran"] = True
    return result


def student_has_login_credit(user):
    if getattr(user, "role", "") != "student":
        return True
    profile = getattr(user, "student_profile", None)
    if not profile:
        return False
    credit = get_or_create_student_activation_credit(profile)
    return credit.has_login_credit


def sync_class_fee_for_student(student_profile, class_fee, actor=None):
    """Create or update the per-student fee generated from a class fee."""
    if not student_profile or not class_fee or not class_fee.is_active:
        return None
    if student_profile.current_class_id != class_fee.school_class_id:
        return None

    fee, created = SchoolFee.objects.get_or_create(
        student=student_profile,
        class_fee=class_fee,
        defaults={
            "title": class_fee.title,
            "amount": class_fee.amount,
            "currency": class_fee.currency,
            "due_date": class_fee.due_date,
            "auto_deduct": True,
            "created_by": actor or class_fee.created_by,
        },
    )
    if not created and fee.status != SchoolFee.STATUS_PAID and not fee.is_customized:
        update_fields = []
        for field, value in {
            "title": class_fee.title,
            "amount": class_fee.amount,
            "currency": class_fee.currency,
            "due_date": class_fee.due_date,
            "auto_deduct": True,
        }.items():
            if getattr(fee, field) != value:
                setattr(fee, field, value)
                update_fields.append(field)
        if update_fields:
            update_fields.append("updated_at")
            fee.save(update_fields=update_fields)
    return fee


def notify_students_of_class_fee(class_fee, fees):
    """Notify students that a class bill is available on their fees page."""
    if not class_fee or not fees:
        return 0

    from notifications.models import Notification

    now = timezone.now()
    notifications = []
    seen_users = set()
    for fee in fees:
        student_user = getattr(getattr(fee, "student", None), "user", None)
        if not student_user or not getattr(student_user, "tenant_id", None) or student_user.id in seen_users:
            continue
        seen_users.add(student_user.id)
        notifications.append(
            Notification(
                tenant=student_user.tenant,
                user=student_user,
                title="New school bill",
                message=f"{class_fee.title} has been added to your school fees.",
                notification_type="info",
                priority=3,
                channel="in_app",
                event_type="fee_due",
                reference_id=fee.id,
                reference_model="finance.SchoolFee",
                action_text="Open Fees",
                deep_link="/fees",
                is_delivered=True,
                delivered_at=now,
            )
        )
    if notifications:
        Notification.objects.bulk_create(notifications)
    return len(notifications)


def sync_class_fee_assignments(class_fee, actor=None, notify_students=False):
    """Ensure every student currently in a class has the active class fee."""
    if not class_fee or not class_fee.is_active:
        return 0
    from users.models import StudentProfile

    students = StudentProfile.objects.select_related("user").filter(
        user__tenant=class_fee.created_by.tenant if class_fee.created_by_id else None,
        current_class=class_fee.school_class,
    )
    if not class_fee.created_by_id:
        students = StudentProfile.objects.select_related("user").filter(current_class=class_fee.school_class)
    count = 0
    synced_fees = []
    for student in students:
        fee = sync_class_fee_for_student(student, class_fee, actor=actor)
        if fee:
            synced_fees.append(fee)
            count += 1
    if notify_students:
        notify_students_of_class_fee(class_fee, synced_fees)
    return count


def sync_student_class_fees(student_profile, actor=None):
    """Ensure a student's generated class fees match their current class."""
    if not student_profile or not student_profile.current_class_id:
        return 0

    class_fees = ClassFee.objects.filter(
        school_class=student_profile.current_class,
        is_active=True,
    )
    count = 0
    for class_fee in class_fees:
        sync_class_fee_for_student(student_profile, class_fee, actor=actor)
        count += 1
    return count


def sync_tenant_class_fees(tenant, actor=None):
    """Refresh generated school fees for active class fees in a tenant."""
    from users.models import StudentProfile

    class_fees = ClassFee.objects.filter(is_active=True).select_related("school_class", "created_by")
    if tenant:
        class_ids = (
            StudentProfile.objects.filter(user__tenant=tenant, current_class__isnull=False)
            .values_list("current_class_id", flat=True)
            .distinct()
        )
        class_fees = class_fees.filter(school_class_id__in=class_ids)

    count = 0
    for class_fee in class_fees:
        students = StudentProfile.objects.filter(current_class=class_fee.school_class).select_related("user")
        if tenant:
            students = students.filter(user__tenant=tenant)
        for student in students:
            sync_class_fee_for_student(student, class_fee, actor=actor)
            count += 1
    return count


def fee_recorded_paid_amount(fee):
    """Return successful ledger-backed payment amount booked for a fee."""
    wallet_debits = (
        Transaction.objects.filter(
            tx_type=Transaction.FEE_DEBIT,
            status=Transaction.STATUS_SUCCESS,
            metadata__fee_id=str(fee.id),
        ).aggregate(total=Sum("amount"))["total"]
        or Decimal("0.00")
    )
    bank_credits = (
        Transaction.objects.filter(
            tx_type=Transaction.FEE_CREDIT,
            status=Transaction.STATUS_SUCCESS,
            metadata__fee_id=str(fee.id),
            metadata__bank_payment_id__isnull=False,
        ).aggregate(total=Sum("amount"))["total"]
        or Decimal("0.00")
    )
    total = wallet_debits + bank_credits
    return min(total, fee.amount)


def fee_paid_amount(fee):
    """Return successful payment amount already booked for a fee."""
    recorded_total = fee_recorded_paid_amount(fee)
    if recorded_total > 0:
        return recorded_total
    if fee.status == SchoolFee.STATUS_PAID:
        return fee.amount
    return Decimal("0.00")


def reconcile_fee_status(fee):
    """Keep a fee status aligned with ledger-backed payments after manual edits."""
    recorded_paid = fee_recorded_paid_amount(fee)
    if recorded_paid <= 0:
        return fee

    if recorded_paid >= fee.amount:
        next_status = SchoolFee.STATUS_PAID
    elif fee.due_date < timezone.localdate():
        next_status = SchoolFee.STATUS_OVERDUE
    else:
        next_status = SchoolFee.STATUS_PENDING

    if fee.status != next_status:
        fee.status = next_status
        fee.save(update_fields=["status", "updated_at"])
    return fee


def outstanding_amount_for_student(student_profile):
    sync_student_class_fees(student_profile, actor=student_profile.user)
    fees = SchoolFee.objects.filter(student=student_profile)
    expected = fees.aggregate(total=Sum("amount"))["total"] or Decimal("0.00")
    paid = Decimal("0.00")
    for fee in fees:
        paid += fee_paid_amount(fee)
    return max(expected - paid, Decimal("0.00"))


def school_payment_context(student_profile, amount=None):
    tenant = getattr(student_profile.user, "tenant", None)
    admin_wallet = get_or_create_admin_wallet(tenant)
    payment_ref = get_or_create_student_payment_reference(student_profile)
    balance = _as_decimal(amount if amount is not None else outstanding_amount_for_student(student_profile))
    class_obj = getattr(student_profile, "current_class", None)
    class_name = getattr(class_obj, "name", "") or ""
    school_code = getattr(tenant, "schema_name", "") or "SCHOOLDOM"
    student_name = student_profile.user.get_full_name() or student_profile.user.email
    narration = f"SCH/{school_code.upper()}/{payment_ref.code}"
    return {
        "tenant": tenant,
        "admin_wallet": admin_wallet,
        "student_ref": payment_ref.code,
        "student_name": student_name,
        "class": class_name,
        "school_name": getattr(tenant, "name", "") or "SchoolDom",
        "school_code": school_code.upper(),
        "account_number": admin_wallet.bank_account_number or "",
        "account_name": admin_wallet.bank_account_name or "",
        "bank_name": admin_wallet.bank_code or "",
        "amount": balance,
        "amount_for_link": _money_for_link(balance),
        "amount_display": _format_naira(balance),
        "narration": narration,
    }


def _template_value(context, key):
    value = context.get(key, "")
    if isinstance(value, Decimal):
        value = _money_for_link(value)
    return quote(str(value), safe="")


def _render_bank_template(template, context):
    rendered = str(template or "")
    replacements = {
        "account_number": context["account_number"],
        "amount": context["amount_for_link"],
        "balance": context["amount_for_link"],
        "narration": context["narration"],
        "school_code": context["school_code"],
        "student_ref": context["student_ref"],
        "student_name": context["student_name"],
        "class": context["class"],
        "account_name": context["account_name"],
        "school_name": context["school_name"],
    }
    for key in replacements:
        rendered = rendered.replace("{{" + key + "}}", _template_value(replacements, key))
        rendered = rendered.replace("{{ " + key + " }}", _template_value(replacements, key))
    return rendered


def bank_link_template_for(bank_name):
    normalized = str(bank_name or "").strip().lower()
    if not normalized:
        return ""
    configured = BankLink.objects.filter(bank_name__iexact=bank_name, is_active=True).first()
    if configured:
        return configured.deep_link_template
    return DEFAULT_BANK_LINK_TEMPLATES.get(normalized, "")


def pay_fallback_url(student_ref):
    base_url = getattr(settings, "SCHOOLDOM_PAY_BASE_URL", SCHOOLDOM_PAY_BASE_URL).rstrip("/")
    return f"{base_url}/{quote(str(student_ref), safe='')}"


def generate_bank_links(school, student_profile, amount=None, extra_banks=None):
    context = school_payment_context(student_profile, amount=amount)
    primary_bank = context["bank_name"]
    bank_names = []
    if primary_bank:
        bank_names.append(primary_bank)
    bank_names.extend(extra_banks or ["GTBank", "Zenith", "Access"])

    links = []
    seen = set()
    for bank_name in bank_names:
        key = str(bank_name or "").strip().lower()
        if not key or key in seen:
            continue
        seen.add(key)
        template = bank_link_template_for(bank_name)
        if not template:
            continue
        links.append(
            {
                "bank_name": str(bank_name).strip(),
                "label": f"Pay with {str(bank_name).strip()}",
                "url": _render_bank_template(template, context),
            }
        )

    links.append(
        {
            "bank_name": "All Banks",
            "label": "Other banks",
            "url": pay_fallback_url(context["student_ref"]),
        }
    )
    return {
        "student": student_profile,
        "school": school,
        "context": context,
        "links": links,
    }


def students_for_parent_phone(parent_phone):
    normalized = normalize_phone_number(parent_phone)
    if not normalized:
        return StudentProfile.objects.none()
    candidates = {normalized}
    if normalized.startswith("234") and len(normalized) > 3:
        candidates.add("0" + normalized[3:])
        candidates.add("+" + normalized)
    return (
        StudentProfile.objects.select_related("user", "user__tenant", "current_class")
        .filter(
            Q(guardian_phone__in=candidates)
            | Q(second_guardian_phone__in=candidates)
            | Q(user__phone__in=candidates)
        )
        .order_by("user__tenant__name", "user__last_name", "user__first_name")
    )


def parent_balance_payload(parent_phone):
    rows = []
    for student in students_for_parent_phone(parent_phone):
        balance = outstanding_amount_for_student(student)
        if balance <= 0:
            continue
        payment = generate_bank_links(getattr(student.user, "tenant", None), student, amount=balance)
        rows.append(
            {
                "student_id": str(student.id),
                "student_ref": payment["context"]["student_ref"],
                "student_name": payment["context"]["student_name"],
                "school_name": payment["context"]["school_name"],
                "class": payment["context"]["class"],
                "balance": payment["context"]["amount"],
                "balance_display": payment["context"]["amount_display"],
                "account_number": payment["context"]["account_number"],
                "account_name": payment["context"]["account_name"],
                "school_bank": payment["context"]["bank_name"],
                "narration": payment["context"]["narration"],
                "links": payment["links"],
            }
        )
    return rows


def send_whatsapp_message(to_phone, text):
    """Send WhatsApp message via Termii."""
    result = send_termii_whatsapp(to_phone, text)
    if result.get("status") == "error":
        raise RuntimeError(result.get("reason", "Twilio WhatsApp delivery failed."))
    return result


def build_balance_message(row):
    link_lines = [f"{link['label']}: {link['url']}" for link in row["links"][:4]]
    return "\n".join(
        [
            f"{row['student_name']} - {row['school_name']}: {row['balance_display']} due",
            f"Account: {row['account_name']} {row['account_number']}",
            f"Narration: {row['narration']}",
            "Tap your bank to pay:",
            *link_lines,
        ]
    )


def send_parent_balance_response(parent_phone):
    rows = parent_balance_payload(parent_phone)
    if not rows:
        send_whatsapp_message(parent_phone, "SchoolDom: no unpaid school fee balance found for this WhatsApp number.")
        return rows
    for row in rows:
        send_whatsapp_message(parent_phone, build_balance_message(row))
    return rows


def send_parent_virtual_account_fee_reminder(parent_user) -> dict:
    """
    Send a fee reminder to a parent via their preferred contact channel (SMS, WhatsApp, or email).
    """
    from finance.models import ParentVirtualAccount
    from users.models import ParentProfile

    # Get parent profile and preferred channel
    parent_profile = None
    students = []
    preferred = "email"
    try:
        parent_profile = ParentProfile.objects.prefetch_related("children").get(user=parent_user)
        students = list(parent_profile.children.select_related("user").all())
        preferred = (parent_profile.preferred_contact or "email").strip().lower()
    except ParentProfile.DoesNotExist:
        pass

    # Get virtual account
    virtual_account = None
    try:
        vac = ParentVirtualAccount.objects.get(parent=parent_user, is_active=True)
        virtual_account = vac
    except ParentVirtualAccount.DoesNotExist:
        pass

    school_name = getattr(getattr(parent_user, "tenant", None), "name", "") or "School"
    lines = [f"{school_name} Fee Reminder — {parent_user.get_full_name() or parent_user.email}"]

    if not students:
        lines.append("No children linked to your account yet.")
    else:
        for student in students:
            unpaid_fees = SchoolFee.objects.filter(
                student=student,
                status__in=[SchoolFee.STATUS_PENDING, SchoolFee.STATUS_PARTIAL, SchoolFee.STATUS_OVERDUE],
            )
            total_outstanding = sum(
                (f.amount - (f.amount_paid or Decimal("0"))) for f in unpaid_fees
            )
            if total_outstanding > 0:
                student_name = student.user.get_full_name() if student.user else "Child"
                lines.append(f"\n{student_name}: {_format_naira(total_outstanding)} outstanding")
                for fee in unpaid_fees[:4]:
                    remaining = fee.amount - (fee.amount_paid or Decimal("0"))
                    lines.append(f"  • {fee.title}: {_format_naira(remaining)}")

    if virtual_account:
        lines.append(f"\nPay to:\nAccount: {virtual_account.account_number}")
        lines.append(f"Bank: {virtual_account.bank_name}")
        lines.append(f"Name: {virtual_account.account_name}")
        lines.append("Payments are matched automatically.")
    else:
        lines.append("\nContact school office for payment details.")

    message = "\n".join(lines)

    # ── Route by preferred contact ────────────────────────────
    if preferred == "sms":
        phone = (parent_user.phone or "").strip()
        if not phone:
            return {"success": False, "message": "Parent has no phone number on file."}
        result = send_ebulksms(phone, message, sender="SchoolDom")
        ok = result.get("status") not in ("error", "skipped")
        return {"success": ok, "message": "SMS reminder sent." if ok else f"SMS failed: {result.get('reason', result)}"}

    if preferred == "whatsapp":
        phone = (parent_user.phone or "").strip()
        if not phone:
            return {"success": False, "message": "Parent has no phone number on file."}
        wa_result = send_termii_whatsapp(phone, message)
        if wa_result.get("status") == "success":
            return {"success": True, "message": "WhatsApp reminder sent."}
        sms_result = send_ebulksms(phone, message, sender="SchoolDom")
        ok = sms_result.get("status") not in ("error", "skipped")
        return {"success": ok, "message": "SMS reminder sent (WhatsApp unavailable)." if ok else "WhatsApp and SMS both failed."}

    # ── Email (default) ───────────────────────────────────────
    email = (parent_user.email or "").strip()
    if not email:
        return {"success": False, "message": "Parent has no email address."}

    bill_students = []
    if students:
        for student in students:
            unpaid_fees = SchoolFee.objects.filter(
                student=student,
                status__in=[SchoolFee.STATUS_PENDING, SchoolFee.STATUS_PARTIAL, SchoolFee.STATUS_OVERDUE],
            )
            student_total = sum((f.amount - (f.amount_paid or Decimal("0"))) for f in unpaid_fees)
            if student_total > 0:
                bill_students.append({
                    "name": student.user.get_full_name() if student.user else "Child",
                    "class": getattr(getattr(student, "current_class", None), "name", ""),
                    "fees": [
                        {
                            "title": f.title,
                            "amount": str(f.amount),
                            "paid": str(f.amount_paid or Decimal("0")),
                            "balance": str(f.amount - (f.amount_paid or Decimal("0"))),
                        }
                        for f in unpaid_fees
                    ],
                    "total_outstanding": str(student_total),
                })

    total_all = sum(Decimal(s["total_outstanding"]) for s in bill_students)
    bill_data = {
        "type": "bill",
        "school_name": school_name,
        "parent_name": parent_user.get_full_name() or parent_user.email,
        "students": bill_students,
        "virtual_account": {
            "number": virtual_account.account_number if virtual_account else "",
            "bank": virtual_account.bank_name if virtual_account else "",
            "name": virtual_account.account_name if virtual_account else "",
        } if virtual_account else None,
        "total_outstanding": str(total_all),
        "generated_at": timezone.now().strftime("%d %b %Y"),
    }
    tenant_obj = getattr(parent_user, "tenant", None)
    receipt_url = create_receipt_link(bill_data, tenant=tenant_obj, receipt_type="bill")

    try:
        send_result = send_payment_receipt(email, message, receipt_url=receipt_url, data=bill_data, receipt_type="bill")
        if send_result.get("sent"):
            return {"success": True, "message": "Email reminder sent.", "email": email, "channel": send_result.get("channel")}
        err = send_result.get("email_error", "")
        return {"success": False, "message": f"Email delivery failed: {err}"}
    except Exception as exc:
        return {"success": False, "message": str(exc)}


def send_bulk_message_to_parents(tenant, parent_user_ids: list, channel: str, message: str) -> dict:
    """
    Send bulk SMS / WhatsApp / Email to a list of parents (User UUIDs).
    channel: "sms" | "whatsapp" | "email"
    Returns: {"sent": int, "failed": int, "errors": list[str]}
    """
    from django.conf import settings
    from django.core.mail import send_mail
    from users.models import User

    results: dict = {"sent": 0, "failed": 0, "errors": []}
    school_name = getattr(tenant, "name", "School") if tenant else "School"
    from_email = getattr(settings, "DEFAULT_FROM_EMAIL", "noreply@schooldom.academy")

    parents = list(User.objects.filter(id__in=parent_user_ids, role="parent", tenant=tenant))

    for parent in parents:
        raw_phone = getattr(parent, "phone", "") or ""
        phone = normalize_phone_number(raw_phone) if raw_phone else ""
        email = getattr(parent, "email", "") or ""
        name = parent.get_full_name() or email

        if channel == "email":
            if not email or "@schooldom.local" in email:
                results["failed"] += 1
                results["errors"].append(f"{name}: no valid email")
                continue
            try:
                send_mail(
                    subject=f"Message from {school_name}",
                    message=message,
                    from_email=from_email,
                    recipient_list=[email],
                    fail_silently=False,
                )
                results["sent"] += 1
            except Exception as exc:
                results["failed"] += 1
                results["errors"].append(f"{name}: {str(exc)[:100]}")

        elif channel == "whatsapp":
            if not phone:
                results["failed"] += 1
                results["errors"].append(f"{name}: no phone number")
                continue
            wa_result = send_termii_whatsapp(phone, message)
            wa_ok = wa_result.get("status") == "success"
            if wa_ok:
                results["sent"] += 1
            else:
                # Fallback to eBulkSMS
                sms_result = send_ebulksms(phone, message)
                sms_ok = sms_result.get("status") not in ("error", "skipped")
                if sms_ok:
                    results["sent"] += 1
                else:
                    results["failed"] += 1
                    results["errors"].append(f"{name}: WhatsApp and SMS both failed")

        elif channel == "sms":
            if not phone:
                results["failed"] += 1
                results["errors"].append(f"{name}: no phone number")
                continue
            sms_result = send_ebulksms(phone, message)
            sms_ok = sms_result.get("status") not in ("error", "skipped")
            if sms_ok:
                results["sent"] += 1
            else:
                results["failed"] += 1
                results["errors"].append(f"{name}: {sms_result.get('reason', 'SMS failed')}")

    return results


def send_fee_reminders(limit=None):
    fees = (
        SchoolFee.objects.select_related("student", "student__user", "student__user__tenant", "student__current_class")
        .exclude(status=SchoolFee.STATUS_PAID)
        .order_by("due_date", "created_at")
    )
    if limit:
        fees = fees[: int(limit)]
    sent = []
    seen_students = set()
    for fee in fees:
        student = fee.student
        if student.id in seen_students:
            continue
        seen_students.add(student.id)

        guardian_email = (getattr(student, "guardian_email", "") or getattr(student, "second_guardian_email", "") or "").strip()
        if not guardian_email:
            continue

        school_name = getattr(getattr(student.user, "tenant", None), "name", "") or "School"
        student_name = student.user.get_full_name() if student.user else "Student"
        class_obj = getattr(student, "current_class", None)
        class_name = class_obj.name if class_obj else ""

        unpaid_fees = SchoolFee.objects.filter(
            student=student,
            status__in=[SchoolFee.STATUS_PENDING, SchoolFee.STATUS_PARTIAL, SchoolFee.STATUS_OVERDUE],
        ).order_by("due_date", "created_at")

        total_balance = sum(
            (f.amount - (f.amount_paid or Decimal("0"))) for f in unpaid_fees
        )
        if total_balance <= 0:
            continue

        fee_lines = []
        for f in unpaid_fees[:6]:
            remaining = f.amount - (f.amount_paid or Decimal("0"))
            if remaining > 0:
                fee_lines.append(f"  • {f.title}: {_format_naira(remaining)}")

        lines = [
            f"{school_name} Fee Reminder",
            f"{student_name}" + (f" ({class_name})" if class_name else ""),
            "",
            "Outstanding fees:",
        ] + fee_lines + [
            f"Total: {_format_naira(total_balance)}",
            "\nReply STOP to opt out.",
        ]
        message = "\n".join(lines)

        try:
            tenant_obj = getattr(getattr(student.user, "tenant", None), "__class__", None) and getattr(student.user, "tenant", None)
            bill_data = {
                "type": "bill",
                "school_name": school_name,
                "student_name": student_name,
                "class_name": class_name,
                "fees": [
                    {
                        "title": f.title,
                        "amount": str(f.amount),
                        "paid": str(f.amount_paid or Decimal("0")),
                        "balance": str(f.amount - (f.amount_paid or Decimal("0"))),
                    }
                    for f in unpaid_fees if (f.amount - (f.amount_paid or Decimal("0"))) > 0
                ],
                "total_outstanding": str(total_balance),
                "generated_at": timezone.now().strftime("%d %b %Y"),
            }
            receipt_url = create_receipt_link(bill_data, tenant=tenant_obj, receipt_type="bill")
            send_payment_receipt(guardian_email, message, receipt_url=receipt_url, data=bill_data, receipt_type="bill")
        except Exception:
            pass
        sent.append({
            "student_id": str(student.id),
            "student_name": student_name,
            "school_name": school_name,
            "email": guardian_email,
            "total_balance": float(total_balance),
        })
    return sent


def receipt_message_for_payment(payment):
    student = payment.student
    school = payment.tenant
    student_name = student.user.get_full_name() or student.user.email if student else "student"
    school_name = getattr(school, "name", "") or "School"
    return (
        f"{school_name}: Payment confirmed! {_format_naira(payment.applied_amount or payment.amount)} received for "
        f"{student_name}. Auto-matched via bank transfer."
    )


def _match_payment_reference_from_narration(tenant, narration):
    narration_upper = str(narration or "").upper()
    refs = StudentPaymentReference.objects.select_related("student", "student__user").filter(is_active=True)
    if tenant:
        refs = refs.filter(tenant=tenant)
    for reference in refs.order_by("-created_at")[:5000]:
        if reference.code.upper() in narration_upper:
            return reference
    return None


def apply_bank_payment_to_student(payment, student_profile, actor=None):
    amount_remaining = _as_decimal(payment.amount)
    if amount_remaining <= 0:
        raise ValueError("Payment amount must be greater than zero.")

    sync_student_class_fees(student_profile, actor=actor)
    admin_wallet = get_or_create_admin_wallet(student_profile.user.tenant)
    applied = Decimal("0.00")

    with transaction.atomic():
        locked_admin = AdminWallet.objects.select_for_update().get(pk=admin_wallet.pk)
        fees = list(
            SchoolFee.objects.select_for_update()
            .filter(student=student_profile)
            .exclude(status=SchoolFee.STATUS_PAID)
            .order_by("due_date", "created_at")
        )
        for fee in fees:
            if amount_remaining <= 0:
                break
            paid_amount = fee_paid_amount(fee)
            fee_balance = max(fee.amount - paid_amount, Decimal("0.00"))
            if fee_balance <= 0:
                fee.status = SchoolFee.STATUS_PAID
                fee.save(update_fields=["status", "updated_at"])
                continue
            allocation = min(amount_remaining, fee_balance)
            locked_admin.balance += allocation
            applied += allocation
            amount_remaining -= allocation
            Transaction.objects.create(
                admin_wallet=locked_admin,
                amount=allocation,
                currency=payment.currency,
                tx_type=Transaction.FEE_CREDIT,
                status=Transaction.STATUS_SUCCESS,
                reference=generate_reference("BKP"),
                narration=f"Bank transfer fee payment • {fee.title}",
                metadata={
                    "fee_id": str(fee.id),
                    "bank_payment_id": str(payment.id),
                    "student_id": str(student_profile.id),
                    "payment_reference": payment.payment_reference.code if payment.payment_reference_id else "",
                },
                created_by=actor,
            )
            if allocation >= fee_balance:
                fee.status = SchoolFee.STATUS_PAID
                fee.last_attempted_at = timezone.now()
                fee.save(update_fields=["status", "last_attempted_at", "updated_at"])

        locked_admin.save(update_fields=["balance", "updated_at"])

        locked_payment = BankPayment.objects.select_for_update().get(pk=payment.pk)
        locked_payment.student = student_profile
        locked_payment.tenant = student_profile.user.tenant
        locked_payment.applied_amount = applied
        locked_payment.unapplied_amount = max(amount_remaining, Decimal("0.00"))
        locked_payment.status = (
            BankPayment.STATUS_CONFIRMED
            if amount_remaining <= 0
            else BankPayment.STATUS_PARTIAL
            if applied > 0
            else BankPayment.STATUS_PENDING
        )
        locked_payment.matched_at = timezone.now()
        locked_payment.receipt_number = locked_payment.receipt_number or generate_reference("RCT")
        locked_payment.save(
            update_fields=[
                "student",
                "tenant",
                "applied_amount",
                "unapplied_amount",
                "status",
                "matched_at",
                "receipt_number",
                "updated_at",
            ]
        )

    payment.refresh_from_db()
    return payment


def ingest_bank_payment(tenant, amount, narration, bank_reference, currency="NGN", metadata=None, actor=None):
    amount = _as_decimal(amount)
    payment, created = BankPayment.objects.get_or_create(
        bank_reference=str(bank_reference).strip(),
        defaults={
            "tenant": tenant,
            "amount": amount,
            "currency": currency or "NGN",
            "narration": str(narration or "").strip(),
            "status": BankPayment.STATUS_PENDING,
            "unapplied_amount": amount,
            "metadata": metadata or {},
        },
    )
    if not created:
        return payment, False

    matched_reference = _match_payment_reference_from_narration(tenant, narration)
    if not matched_reference:
        payment.status = BankPayment.STATUS_UNMATCHED
        payment.save(update_fields=["status", "updated_at"])
        return payment, True

    payment.payment_reference = matched_reference
    payment.student = matched_reference.student
    payment.save(update_fields=["payment_reference", "student", "updated_at"])
    payment = apply_bank_payment_to_student(payment, matched_reference.student, actor=actor)
    return payment, True


def credit_wallet(wallet: Wallet, amount: Decimal, tx_type: str, reference: str, narration: str = "", metadata=None, created_by=None):
    amount = _as_decimal(amount)
    with transaction.atomic():
        Wallet.objects.select_for_update().filter(pk=wallet.pk).update(
            balance=F("balance") + amount,
            updated_at=timezone.now(),
        )
        wallet.refresh_from_db()
        Transaction.objects.create(
            wallet=wallet,
            amount=amount,
            currency=wallet.currency,
            tx_type=tx_type,
            status=Transaction.STATUS_SUCCESS,
            reference=reference,
            narration=narration,
            metadata=metadata or {},
            created_by=created_by,
        )
    return wallet


def debit_wallet(wallet: Wallet, amount: Decimal, tx_type: str, reference: str, narration: str = "", metadata=None, created_by=None):
    amount = _as_decimal(amount)
    with transaction.atomic():
        wallet_locked = Wallet.objects.select_for_update().get(pk=wallet.pk)
        if wallet_locked.balance < amount:
            raise ValueError("Insufficient wallet balance.")
        wallet_locked.balance -= amount
        wallet_locked.save(update_fields=["balance", "updated_at"])
        Transaction.objects.create(
            wallet=wallet_locked,
            amount=amount,
            currency=wallet_locked.currency,
            tx_type=tx_type,
            status=Transaction.STATUS_SUCCESS,
            reference=reference,
            narration=narration,
            metadata=metadata or {},
            created_by=created_by,
        )
    return wallet


def deduct_document_generation_credit(
    tenant, document_type: str, student_profile=None, action: str = "generate", actor=None, credits: int = 1
):
    """Deduct credits for a student document once per document type."""
    if credits <= 0:
        raise ValueError("credits must be a positive number.")
    
    pool = get_or_create_activation_credit_pool(tenant)
    charged = False
    
    with transaction.atomic():
        locked_pool = ActivationCreditPool.objects.select_for_update().get(pk=pool.pk)
        if student_profile is not None and DocumentGenerationCreditTransaction.objects.filter(
            pool=locked_pool,
            student=student_profile,
            document_type=document_type,
        ).exists():
            locked_pool.document_credit_charged = False
            return locked_pool

        if locked_pool.balance < credits:
            raise ValueError(f"Insufficient document generation credits. Required: {credits}, Available: {locked_pool.balance}")
        
        locked_pool.balance -= credits
        locked_pool.save(update_fields=["balance", "updated_at"])
        
        DocumentGenerationCreditTransaction.objects.create(
            pool=locked_pool,
            student=student_profile,
            document_type=document_type,
            credits_deducted=credits,
            action=action,
            created_by=actor,
        )
        charged = True
    
    pool.refresh_from_db()
    pool.document_credit_charged = charged
    return pool


def process_due_fees(student_profile, actor=None, due_only=True):
    """Auto-deduct pending fees that are due; returns summary dict."""
    today = timezone.localdate()
    wallet = Wallet.objects.filter(user=student_profile.user).first()
    if not wallet:
        return {"deducted": [], "overdue": []}

    admin_wallet = get_or_create_admin_wallet(student_profile.user.tenant)
    due_fees = (
        SchoolFee.objects.select_for_update()
        .filter(student=student_profile, status=SchoolFee.STATUS_PENDING, auto_deduct=True)
        .order_by("due_date")
    )
    if due_only:
        due_fees = due_fees.filter(due_date__lte=today)

    deducted, overdue = [], []
    with transaction.atomic():
        wallet_locked = Wallet.objects.select_for_update().get(pk=wallet.pk)
        admin_locked = AdminWallet.objects.select_for_update().get(pk=admin_wallet.pk)

        for fee in due_fees:
            if wallet_locked.balance >= fee.amount:
                wallet_locked.balance -= fee.amount
                admin_locked.balance += fee.amount
                fee.status = SchoolFee.STATUS_PAID
                fee.last_attempted_at = timezone.now()
                fee.save(update_fields=["status", "last_attempted_at", "updated_at"])
                Transaction.objects.create(
                    wallet=wallet_locked,
                    amount=fee.amount,
                    currency=wallet_locked.currency,
                    tx_type=Transaction.FEE_DEBIT,
                    status=Transaction.STATUS_SUCCESS,
                    reference=generate_reference("FEE"),
                    narration=f"Auto fee deduction • {fee.title}",
                    metadata={"fee_id": str(fee.id)},
                    created_by=actor,
                )
                Transaction.objects.create(
                    admin_wallet=admin_locked,
                    amount=fee.amount,
                    currency=admin_locked.currency,
                    tx_type=Transaction.FEE_CREDIT,
                    status=Transaction.STATUS_SUCCESS,
                    reference=generate_reference("ADM"),
                    narration=f"Fee received from {student_profile.user.email}",
                    metadata={"fee_id": str(fee.id)},
                    created_by=actor,
                )
                deducted.append(str(fee.id))
            else:
                if fee.due_date <= today:
                    fee.status = SchoolFee.STATUS_OVERDUE
                fee.last_attempted_at = timezone.now()
                fee.save(update_fields=["status", "last_attempted_at", "updated_at"])
                overdue.append(str(fee.id))

        wallet_locked.save(update_fields=["balance", "updated_at"])
        admin_locked.save(update_fields=["balance", "updated_at"])

    return {"deducted": deducted, "overdue": overdue}


def initiate_admin_withdrawal(admin_wallet: AdminWallet, amount: Decimal, reference: str, bank_payload: dict, actor=None):
    """Reserve balance and kick off a provider transfer. Caller handles response messaging."""
    amount = _as_decimal(amount)
    provider = active_payment_provider()
    
    # If provider is paystack, use Paystack transfer API
    if provider == "paystack":
        return initiate_paystack_transfer(admin_wallet, amount, reference, bank_payload, actor)

    with transaction.atomic():
        locked = AdminWallet.objects.select_for_update().get(pk=admin_wallet.pk)
        if locked.balance < amount:
            raise ValueError("Insufficient admin wallet balance.")
        locked.balance -= amount
        locked.save(update_fields=["balance", "updated_at"])
        tx = Transaction.objects.create(
            admin_wallet=locked,
            amount=amount,
            currency=locked.currency,
            tx_type=Transaction.WITHDRAWAL,
            status=Transaction.STATUS_PENDING,
            reference=reference,
            narration="Admin wallet withdrawal",
            metadata={"bank": bank_payload, "provider": provider},
            created_by=actor,
        )

    try:
        if provider == "kuda":
            transfer_payload = {
                "reference": reference,
                "amount": str(amount),
                "currency": locked.currency or "NGN",
                "narration": f"Admin withdrawal - {reference}",
                "beneficiary": {
                    "account_number": bank_payload.get("account_number"),
                    "bank_code": bank_payload.get("bank_code"),
                    "account_name": bank_payload.get("account_name"),
                },
            }
            transfer_resp = requests.post(
                f"{_kuda_base_url()}/{getattr(settings, 'KUDA_TRANSFER_ENDPOINT', '/transfers').lstrip('/')}",
                json=transfer_payload,
                headers=_kuda_headers(),
                timeout=getattr(settings, "KUDA_REQUEST_TIMEOUT", 25),
            )
            transfer_data = _kuda_json(transfer_resp)
        else:
            transfer_payload = {
                "account_bank": bank_payload.get("bank_code"),
                "account_number": bank_payload.get("account_number"),
                "amount": str(amount),
                "narration": f"Admin withdrawal - {reference}",
                "currency": locked.currency or "NGN",
                "reference": reference,
            }
            transfer_resp = requests.post(
                f"{_flutterwave_base_url()}/transfers",
                json=transfer_payload,
                headers=_flutterwave_headers(),
                timeout=25,
            )
            transfer_data = _flutterwave_json(transfer_resp)
            if transfer_data.get("status") != "success":
                raise RuntimeError(transfer_data.get("message") or "Transfer failed to start.")
    except Exception as exc:
        # Roll back balance and mark failure
        with transaction.atomic():
            locked = AdminWallet.objects.select_for_update().get(pk=admin_wallet.pk)
            locked.balance += amount
            locked.save(update_fields=["balance", "updated_at"])
            Transaction.objects.filter(reference=reference).update(
                status=Transaction.STATUS_FAILED,
                metadata={"error": str(exc), "bank": bank_payload},
            )
        raise

    Transaction.objects.filter(reference=reference).update(
        status=Transaction.STATUS_SUCCESS,
        metadata={"bank": bank_payload, "provider": provider, "transfer": transfer_data.get("data") or transfer_data},
    )
    return {"status": "successful"}


# NEW: Paystack Transfer/Withdrawal
def initiate_paystack_transfer(admin_wallet: AdminWallet, amount: Decimal, reference: str, bank_payload: dict, actor=None):
    """
    Initiate a transfer from Schooldom Paystack wallet to school's bank account.
    """
    amount = _as_decimal(amount)
    
    # Get the Paystack transfer recipient code
    recipient_code = get_or_create_paystack_transfer_recipient(
        bank_payload.get("account_number"),
        bank_payload.get("bank_code"),
        bank_payload.get("account_name")
    )
    
    # Initiate transfer via Paystack
    url = f"{_paystack_base_url()}/transfer"
    payload = {
        "source": "balance",
        "amount": int(amount * 100),  # Convert to kobo
        "recipient": recipient_code,
        "reason": f"School withdrawal - {reference}",
        "reference": reference
    }
    
    response = requests.post(url, json=payload, headers=_paystack_headers(), timeout=30)
    data = _paystack_json(response)
    
    if response.status_code not in (200, 201) or data.get("status") is not True:
        raise RuntimeError(data.get("message", "Failed to initiate transfer"))
    
    # Record transaction
    with transaction.atomic():
        locked = AdminWallet.objects.select_for_update().get(pk=admin_wallet.pk)
        if locked.balance < amount:
            raise ValueError("Insufficient admin wallet balance.")
        locked.balance -= amount
        locked.save(update_fields=["balance", "updated_at"])
        
        Transaction.objects.create(
            admin_wallet=locked,
            amount=amount,
            currency=locked.currency,
            tx_type=Transaction.WITHDRAWAL,
            status=Transaction.STATUS_SUCCESS,
            reference=reference,
            narration="Admin wallet withdrawal via Paystack",
            metadata={
                "bank": bank_payload,
                "provider": "paystack",
                "transfer": data.get("data", {})
            },
            created_by=actor,
        )
    
    return {"status": "successful", "transfer_code": data.get("data", {}).get("transfer_code")}


def process_virtual_account_payment(
    tenant,
    account_number: str,
    amount_naira: Decimal,
    paystack_reference: str,
    metadata: dict = None,
) -> dict:
    """
    Process a Paystack dedicated virtual account (DVA) charge.success payment.
    Called from process_paystack_webhook when channel == 'dedicated_nuban'.
    Matches account_number → parent, allocates payment to their children's fees.
    """
    from finance.models import ParentVirtualAccount, Transaction, FeeAllocation
    from users.models import ParentProfile

    logger.info(
        "DVA payment received: ref=%s account=%s amount=%.2f",
        paystack_reference, account_number, float(amount_naira),
    )

    # Prevent duplicate processing
    if Transaction.objects.filter(paystack_ref=paystack_reference).exists():
        logger.info("DVA payment %s already processed — skipping.", paystack_reference)
        return {"status": "duplicate", "message": "Already processed"}

    # Look up parent by virtual account number
    try:
        vac = ParentVirtualAccount.objects.select_related("parent").get(
            account_number=account_number,
            is_active=True,
        )
    except ParentVirtualAccount.DoesNotExist:
        # Fall back: check if this is the school's main collection DVA (AdminWallet)
        try:
            admin_wallet = AdminWallet.objects.select_related("tenant").get(
                bank_account_number=account_number
            )
            school_tenant = admin_wallet.tenant or tenant
            narration_text = (
                (metadata or {}).get("webhook_data", {}).get("narration", "")
                or f"Paystack DVA {paystack_reference}"
            )
            payment, created = ingest_bank_payment(
                tenant=school_tenant,
                amount=amount_naira,
                narration=narration_text,
                bank_reference=paystack_reference,
                currency="NGN",
                metadata=metadata or {},
                actor=None,
            )
            logger.info(
                "DVA payment %s ingested as school BankPayment — status=%s created=%s",
                paystack_reference, payment.status, created,
            )
            return {
                "status": "ingested_school_account",
                "bank_payment_status": payment.status,
                "bank_payment_id": str(payment.id),
            }
        except AdminWallet.DoesNotExist:
            pass

        logger.error(
            "DVA payment %s: no active ParentVirtualAccount or AdminWallet for account_number=%s",
            paystack_reference, account_number,
        )
        return {"status": "error", "message": f"No active virtual account for {account_number}"}

    parent_user = vac.parent
    amount = _as_decimal(amount_naira)

    # Get parent's children's unpaid fees
    try:
        parent_profile = ParentProfile.objects.prefetch_related("children").get(user=parent_user)
        students = parent_profile.children.all()
    except ParentProfile.DoesNotExist:
        students = []

    unpaid_fees = (
        SchoolFee.objects.filter(
            student__in=students,
            status__in=[SchoolFee.STATUS_PENDING, SchoolFee.STATUS_OVERDUE, SchoolFee.STATUS_PARTIAL],
        )
        .select_related("student", "student__user", "student__current_class")
        .order_by("due_date", "created_at")
    )

    # Create the parent transaction record
    reference = generate_reference("DVA")
    tx = Transaction.objects.create(
        tx_type=Transaction.SPLIT_PAYMENT,
        status=Transaction.STATUS_SUCCESS,
        amount=amount,
        reference=reference,
        paystack_ref=paystack_reference,
        provider="paystack",
        narration=f"Virtual account payment — {parent_user.get_full_name() or parent_user.email}",
        parent_id=parent_user.id,
        school_id=tenant.id if tenant else None,
        tuition_amount=amount,
        allocation_status=Transaction.ALLOCATION_PENDING,
        metadata=metadata or {},
    )

    # Allocate payment to fees (oldest due first, no extra ₦400 markup for DVA payments)
    remaining = amount
    allocations = []

    for fee in unpaid_fees:
        if remaining <= 0:
            break
        already_paid = fee.amount_paid or Decimal("0.00")
        tuition_left = fee.amount - already_paid
        if tuition_left <= 0:
            continue

        allocated = min(remaining, tuition_left)
        new_paid = already_paid + allocated
        fully_paid = new_paid >= fee.amount

        fee.amount_paid = new_paid
        fee.status = SchoolFee.STATUS_PAID if fully_paid else SchoolFee.STATUS_PARTIAL
        if fully_paid:
            fee.payment_date = timezone.now()
        fee.last_payment_date = timezone.now()
        fee.paystack_ref = paystack_reference
        fee.save(update_fields=["amount_paid", "status", "payment_date", "last_payment_date", "paystack_ref", "updated_at"])

        FeeAllocation.objects.create(
            fee=fee,
            transaction=tx,
            amount_allocated=allocated,
            status=FeeAllocation.STATUS_PAID if fully_paid else FeeAllocation.STATUS_PARTIAL,
        )
        allocations.append({
            "fee_id": str(fee.id),
            "fee_title": fee.title,
            "allocated": float(allocated),
            "status": "paid" if fully_paid else "partial",
        })
        remaining -= allocated

        # Send receipt — email (if available) + SMS with receipt link via eBulkSMS
        student = fee.student
        student_name = student.user.get_full_name() if student and student.user else ""
        class_obj = getattr(student, "current_class", None)
        class_name = class_obj.name if class_obj else ""
        school_name = (getattr(getattr(student, "user", None), "tenant", None) or {})
        school_name = getattr(school_name, "name", "") if school_name else (tenant.name if tenant else "")
        try:
            balance_left = float(fee.amount) - float(fee.amount_paid or 0)
            receipt_data = {
                "type": "receipt",
                "school_name": school_name,
                "student_name": student_name,
                "class_name": class_name,
                "amount_paid": str(allocated),
                "fee_total": str(fee.amount),
                "balance_remaining": "0.00" if fully_paid else str(max(0, balance_left)),
                "payment_status": "paid" if fully_paid else "partial",
                "payment_date": timezone.now().strftime("%d %b %Y"),
                "reference": paystack_reference,
            }
            receipt_url = create_receipt_link(receipt_data, tenant=tenant)
            receipt_message = build_paystack_receipt_message(
                student_name=student_name,
                class_name=class_name,
                amount_paid=float(allocated),
                fee_total=float(fee.amount),
                payment_status="paid" if fully_paid else "partial",
                school_name=school_name,
            )

            recipient_email = (parent_user.email or "").strip()
            if recipient_email:
                send_payment_receipt(
                    recipient_email,
                    receipt_message,
                    receipt_url=receipt_url,
                    data=receipt_data,
                    receipt_type="receipt",
                )

            parent_phone = (getattr(parent_user, "phone", "") or "").strip()
            if parent_phone:
                send_ebulksms(parent_phone, f"{receipt_message} Receipt: {receipt_url}")
        except Exception:
            logger.exception("DVA receipt notification failed for fee %s (ref=%s)", fee.id, paystack_reference)

    tx.allocation_status = (
        Transaction.ALLOCATION_OVERPAID if remaining > 0 and not unpaid_fees
        else Transaction.ALLOCATION_ALLOCATED if remaining <= 0
        else Transaction.ALLOCATION_PARTIAL
    )
    tx.fee_ids = [a["fee_id"] for a in allocations]
    tx.save(update_fields=["allocation_status", "fee_ids", "updated_at"])

    logger.info(
        "DVA payment %s allocated: parent=%s fees_updated=%d remaining=%.2f status=%s",
        paystack_reference,
        parent_user.email,
        len(allocations),
        float(remaining),
        tx.allocation_status,
    )

    return {
        "status": "success",
        "reference": reference,
        "paystack_ref": paystack_reference,
        "amount": float(amount),
        "allocated_count": len(allocations),
        "remaining": float(remaining),
        "allocations": allocations,
    }


def get_or_create_paystack_transfer_recipient(account_number: str, bank_code: str, account_name: str) -> str:
    """
    Get or create a Paystack transfer recipient.
    """
    url = f"{_paystack_base_url()}/transferrecipient"
    
    # Check if recipient exists
    # Note: In production, you'd want to cache this or check existence first
    payload = {
        "type": "nuban",
        "name": account_name,
        "account_number": account_number,
        "bank_code": bank_code,
        "currency": "NGN"
    }
    
    response = requests.post(url, json=payload, headers=_paystack_headers(), timeout=30)
    data = _paystack_json(response)
    
    if response.status_code not in (200, 201) or data.get("status") is not True:
        raise RuntimeError(data.get("message", "Failed to create transfer recipient"))
    
    return data["data"]["recipient_code"]