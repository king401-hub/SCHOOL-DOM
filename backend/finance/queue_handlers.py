"""request_queue handlers for finance flows.

These are intentionally separate from initiate_admin_withdrawal /
initiate_paystack_transfer (finance/services.py) rather than rewrites of
them - that pair is also called from the auto-settlement path
(_auto_settle_school_fee_payment, finance/services.py:2800) which is out of
scope here, and touching its retry/rollback semantics could regress money
already flowing through it in production. Instead, each queued withdrawal
gets its own idempotent-per-reference implementation: a retry of the same
QueuedRequest reuses the same `reference` and never re-deducts the wallet
(Transaction.get_or_create keyed on reference), it only re-attempts the
provider call.
"""
from decimal import Decimal

import requests
from django.conf import settings
from django.db import transaction

from request_queue.exceptions import RequestRejectedError, RetriableRequestError

from .models import AdminWallet, Transaction
from .services import (
    _flutterwave_base_url,
    _flutterwave_headers,
    _kuda_base_url,
    _kuda_headers,
    _paystack_base_url,
    _paystack_headers,
    active_payment_provider,
    get_or_create_paystack_transfer_recipient,
)


class _ProviderServerError(Exception):
    """5xx from the payment provider - transient, safe to retry."""


class _ProviderRejected(Exception):
    """4xx / explicit failure status from the payment provider - permanent."""


def _rollback_and_fail(admin_wallet_id, amount, reference, error_message):
    with transaction.atomic():
        locked = AdminWallet.objects.select_for_update().get(pk=admin_wallet_id)
        locked.balance += amount
        locked.save(update_fields=["balance", "updated_at"])
        Transaction.objects.filter(reference=reference).update(
            status=Transaction.STATUS_FAILED,
            metadata={"error": error_message},
        )


def handle_wallet_withdrawal(queued_request):
    """Process (or resume) a queued admin-wallet withdrawal.

    Safe to call repeatedly for the same queued_request across Celery
    retries: the wallet deduction + Transaction row are created exactly
    once (first attempt); later attempts see the existing pending
    Transaction and only re-attempt the provider call.
    """
    payload = queued_request.payload
    amount = Decimal(str(payload["amount"]))
    reference = payload["reference"]
    bank_payload = payload["bank_payload"]
    admin_wallet_id = payload["admin_wallet_id"]
    provider = payload.get("provider") or active_payment_provider()

    with transaction.atomic():
        locked_wallet = AdminWallet.objects.select_for_update().get(pk=admin_wallet_id)
        tx, tx_created = Transaction.objects.get_or_create(
            reference=reference,
            defaults=dict(
                admin_wallet=locked_wallet,
                amount=amount,
                currency=locked_wallet.currency,
                tx_type=Transaction.WITHDRAWAL,
                status=Transaction.STATUS_PENDING,
                narration="Admin wallet withdrawal",
                metadata={"bank": bank_payload, "provider": provider},
                created_by_id=payload.get("actor_id"),
            ),
        )
        if tx_created:
            if locked_wallet.balance < amount:
                tx.status = Transaction.STATUS_FAILED
                tx.metadata = {**tx.metadata, "error": "Insufficient admin wallet balance."}
                tx.save(update_fields=["status", "metadata"])
                raise RequestRejectedError("Insufficient admin wallet balance.")
            locked_wallet.balance -= amount
            locked_wallet.save(update_fields=["balance", "updated_at"])
        elif tx.status == Transaction.STATUS_SUCCESS:
            # A previous attempt already completed (e.g. task redelivered
            # after a worker restart) - nothing left to do.
            return {"status": "successful", "reference": reference, "already_completed": True}
        elif tx.status == Transaction.STATUS_FAILED:
            # A previous attempt already rolled back and failed permanently -
            # don't resurrect it; a genuinely new withdrawal needs a new
            # submission (new reference) from the admin.
            raise RequestRejectedError(tx.metadata.get("error") or "Withdrawal previously failed permanently.")
        # else: tx.status == PENDING from an earlier retriable-failure attempt
        # - wallet already deducted, just re-attempt the provider call below.

        currency = locked_wallet.currency

    try:
        if provider == "kuda":
            transfer_data = _send_kuda_transfer(currency, amount, reference, bank_payload)
        elif provider == "paystack":
            transfer_data = _send_paystack_transfer(amount, reference, bank_payload)
        else:
            transfer_data = _send_flutterwave_transfer(currency, amount, reference, bank_payload)
    except (requests.exceptions.Timeout, requests.exceptions.ConnectionError) as exc:
        raise RetriableRequestError(f"Network error contacting {provider}: {exc}") from exc
    except _ProviderServerError as exc:
        raise RetriableRequestError(str(exc)) from exc
    except _ProviderRejected as exc:
        _rollback_and_fail(admin_wallet_id, amount, reference, str(exc))
        raise RequestRejectedError(str(exc)) from exc
    except Exception as exc:  # noqa: BLE001 - never leave a wallet deduction stranded
        # Anything else (misconfiguration, unexpected provider response
        # shape, etc.) is treated as permanent: retrying blindly would just
        # repeat the same failure, so roll back and require a fresh
        # submission instead of looping forever.
        _rollback_and_fail(admin_wallet_id, amount, reference, str(exc))
        raise RequestRejectedError(f"Withdrawal failed: {exc}") from exc

    Transaction.objects.filter(reference=reference).update(
        status=Transaction.STATUS_SUCCESS,
        metadata={"bank": bank_payload, "provider": provider, "transfer": transfer_data},
    )
    return {"status": "successful", "reference": reference, "provider": provider}


def _parse_provider_response(response):
    try:
        data = response.json()
    except ValueError:
        data = {}
    if response.status_code >= 500:
        raise _ProviderServerError(data.get("message") or f"Upstream server error ({response.status_code}).")
    if response.status_code >= 400:
        raise _ProviderRejected(data.get("message") or f"Request rejected ({response.status_code}).")
    return data


def _send_kuda_transfer(currency, amount, reference, bank_payload):
    transfer_payload = {
        "reference": reference,
        "amount": str(amount),
        "currency": currency or "NGN",
        "narration": f"Admin withdrawal - {reference}",
        "beneficiary": {
            "account_number": bank_payload.get("account_number"),
            "bank_code": bank_payload.get("bank_code"),
            "account_name": bank_payload.get("account_name"),
        },
    }
    response = requests.post(
        f"{_kuda_base_url()}/{getattr(settings, 'KUDA_TRANSFER_ENDPOINT', '/transfers').lstrip('/')}",
        json=transfer_payload,
        headers=_kuda_headers(),
        timeout=getattr(settings, "KUDA_REQUEST_TIMEOUT", 25),
    )
    return _parse_provider_response(response)


def _send_flutterwave_transfer(currency, amount, reference, bank_payload):
    transfer_payload = {
        "account_bank": bank_payload.get("bank_code"),
        "account_number": bank_payload.get("account_number"),
        "amount": str(amount),
        "narration": f"Admin withdrawal - {reference}",
        "currency": currency or "NGN",
        "reference": reference,
    }
    response = requests.post(
        f"{_flutterwave_base_url()}/transfers",
        json=transfer_payload,
        headers=_flutterwave_headers(),
        timeout=25,
    )
    data = _parse_provider_response(response)
    if data.get("status") != "success":
        raise _ProviderRejected(data.get("message") or "Transfer failed to start.")
    return data


def _send_paystack_transfer(amount, reference, bank_payload):
    try:
        recipient_code = get_or_create_paystack_transfer_recipient(
            bank_payload.get("account_number"), bank_payload.get("bank_code"), bank_payload.get("account_name"),
        )
    except RuntimeError as exc:
        raise _ProviderRejected(str(exc)) from exc

    response = requests.post(
        f"{_paystack_base_url()}/transfer",
        json={
            "source": "balance",
            "amount": int(amount * 100),
            "recipient": recipient_code,
            "reason": f"School withdrawal - {reference}",
            "reference": reference,
        },
        headers=_paystack_headers(),
        timeout=30,
    )
    data = _parse_provider_response(response)
    if data.get("status") is not True:
        raise _ProviderRejected(data.get("message") or "Failed to initiate transfer")
    return data
