"""License key generation, activation, and the ₦20,000 purchase flow.

The payment side mirrors finance/services.py's activation-credit-purchase
flow (initialize_activation_credit_purchase / verify_activation_credit_purchase)
almost exactly - same dispatcher (initialize_payment_transaction /
verify_payment_transaction), same "never trust the webhook/verification
payload's amount without checking it, never skip select_for_update()"
discipline. See finance/services.py:2345 and :2402 for the originals this
was modeled on.
"""
import secrets
import string
from decimal import Decimal

from dateutil.relativedelta import relativedelta
from django.db import transaction
from django.utils import timezone

from finance.services import (
    active_payment_provider,
    generate_reference,
    initialize_payment_transaction,
    verify_payment_transaction,
)

from .models import CBTLicense, CBTLicensePayment

LICENSE_DURATION = relativedelta(months=3, days=15)
LICENSE_PRICE = Decimal("20000.00")


def _as_school_tenant(tenant):
    """Normalizes either tenant type this codebase has in play to a real
    core.SchoolTenant, which is what CBTLicense.school actually points to.

    request.user.tenant is always core.SchoolTenant (see users/views.py's
    `user.tenant.is_active` checks) - but Exam/Question and everything else
    built on core.models.TenantAwareModel point at the older tenants.Tenant
    instead (core/models.py:11-16). users/models.py:452
    resolve_legacy_tenant_for_school() already bridges SchoolTenant ->
    tenants.Tenant for academic/exams code; this is the same bridge run in
    reverse, via the shared slug/schema_name value, so callers on either
    side (a view holding request.user.tenant, or exam-side code holding
    exam.tenant) can pass either one in without needing to know the
    difference."""
    if tenant is None:
        return None
    from core.tenant import SchoolTenant

    if isinstance(tenant, SchoolTenant):
        return tenant

    from tenants.models import Tenant

    if isinstance(tenant, Tenant):
        return SchoolTenant.objects.filter(schema_name__iexact=tenant.slug).first()

    return tenant

# Excludes 0/O/1/I to avoid keys that are ambiguous to read/type over the phone.
_KEY_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"


class LicenseError(Exception):
    """Raised for any expected/user-facing license failure (bad key, wrong
    school, already active, payment not successful, etc.) - views catch this
    specifically and return its message as-is, same pattern as ValueError
    is used for expected failures elsewhere in finance/services.py."""


def _generate_key_segment(length=4):
    return "".join(secrets.choice(_KEY_ALPHABET) for _ in range(length))


def generate_license_key():
    for _ in range(10):
        key = "SCHOOLDOM-" + "-".join(_generate_key_segment() for _ in range(3))
        if not CBTLicense.objects.filter(key=key).exists():
            return key
    raise LicenseError("Could not generate a unique license key. Try again.")


def create_license(school=None, source=CBTLicense.SOURCE_MANUAL, notes="", created_by=None, activate=False):
    """Used directly by the Super Admin panel (generate-for-a-school, or leave
    school blank for an unassigned/promo-pool key) and internally by the
    ₦20,000 purchase flow below."""
    license = CBTLicense.objects.create(
        key=generate_license_key(),
        school=school,
        source=source,
        notes=notes,
        created_by=created_by,
    )
    if activate and school is not None:
        activate_license(license.key, school)
        license.refresh_from_db()
    return license


def has_active_cbt_license(tenant):
    tenant = _as_school_tenant(tenant)
    if tenant is None:
        return False
    return CBTLicense.objects.filter(
        school=tenant, status=CBTLicense.STATUS_ACTIVE, expires_at__gt=timezone.now(),
    ).exists()


def current_license_for(tenant):
    """The license shown in School Settings / the lock-screen check - the
    most recently activated one, active or not (so an expired school still
    sees what it had and when it lapsed, not nothing)."""
    tenant = _as_school_tenant(tenant)
    if tenant is None:
        return None
    return (
        CBTLicense.objects.filter(school=tenant)
        .exclude(status=CBTLicense.STATUS_PENDING)
        .order_by("-activated_at")
        .first()
    )


def activate_license(key, requesting_tenant):
    """The single activation path every route (manual key entry, Super Admin
    manual activation, and post-payment activation below) funnels through.
    select_for_update() + transaction.atomic() makes this safe against two
    near-simultaneous redemption attempts on the same key, same discipline
    as finance/services.py:2423's verify_activation_credit_purchase."""
    key = (key or "").strip().upper()
    if not key:
        raise LicenseError("Enter a license key.")
    requesting_tenant = _as_school_tenant(requesting_tenant)
    if requesting_tenant is None:
        raise LicenseError("No school is associated with this account.")
    with transaction.atomic():
        try:
            license = CBTLicense.objects.select_for_update().get(key=key)
        except CBTLicense.DoesNotExist:
            raise LicenseError("This license key was not found.")

        if license.status == CBTLicense.STATUS_REVOKED:
            raise LicenseError("This license key has been revoked.")
        if license.school_id and license.school_id != requesting_tenant.id:
            raise LicenseError("This license key belongs to a different school.")
        if license.status == CBTLicense.STATUS_ACTIVE and license.expires_at and license.expires_at > timezone.now():
            raise LicenseError("This license key is already active.")

        now = timezone.now()
        license.school = requesting_tenant
        license.status = CBTLicense.STATUS_ACTIVE
        license.activated_at = now
        license.expires_at = now + LICENSE_DURATION
        license.save(update_fields=["school", "status", "activated_at", "expires_at", "updated_at"])
        return license


def deactivate_license(license, actor=None, reason=""):
    license.status = CBTLicense.STATUS_REVOKED
    license.revoked_at = timezone.now()
    license.revoked_by = actor
    license.revoke_reason = reason
    license.save(update_fields=["status", "revoked_at", "revoked_by", "revoke_reason", "updated_at"])
    return license


def reactivate_license(license, actor=None):
    """Super Admin override - reinstates a revoked/expired key with a fresh
    3-month-15-day window from right now, without the school needing to pay
    or re-enter anything."""
    now = timezone.now()
    license.status = CBTLicense.STATUS_ACTIVE
    license.activated_at = now
    license.expires_at = now + LICENSE_DURATION
    license.revoked_at = None
    license.revoked_by = None
    license.revoke_reason = ""
    license.save(update_fields=[
        "status", "activated_at", "expires_at", "revoked_at", "revoked_by", "revoke_reason", "updated_at",
    ])
    return license


# ------------------------------------------------------------------
# ₦20,000 self-service purchase flow
# ------------------------------------------------------------------

def initialize_license_purchase(tenant, actor):
    """Creates a license pre-bound to the paying tenant (never enters the
    unassigned pool) plus a payment record, then hands off to the same
    provider-agnostic dispatcher every other SchoolDom-revenue purchase
    uses (finance/services.py:2321)."""
    license = create_license(school=tenant, source=CBTLicense.SOURCE_PAYMENT, created_by=actor)
    reference = generate_reference("LIC")
    payment = CBTLicensePayment.objects.create(
        reference=reference,
        school=tenant,
        amount=LICENSE_PRICE,
        provider=active_payment_provider(),
        license=license,
        initiated_by=actor,
    )
    init_payload = initialize_payment_transaction(
        user=actor,
        amount=LICENSE_PRICE,
        reference=reference,
        metadata={"purpose": "cbt_license", "license_id": str(license.id), "tenant_id": str(tenant.id)},
    )
    payment.metadata = {
        "authorization_url": init_payload.get("authorization_url"),
        "access_code": init_payload.get("access_code"),
    }
    payment.save(update_fields=["metadata", "updated_at"])
    return {"payment": payment, "license": license, "provider": active_payment_provider(), **init_payload}


def verify_license_purchase(reference, requesting_tenant):
    try:
        payment = CBTLicensePayment.objects.select_related("license", "school").get(reference=reference)
    except CBTLicensePayment.DoesNotExist:
        raise LicenseError("Payment reference was not found.")

    # Tenant-isolation check, same principle as finance/views.py:3841's
    # sms_wallet_verify - never let a caller verify/claim another school's
    # payment, even by guessing/leaking a reference string.
    if payment.school_id != requesting_tenant.id:
        raise LicenseError("This payment does not belong to your school.")

    if payment.status == CBTLicensePayment.STATUS_SUCCESSFUL:
        return payment.license

    verification = verify_payment_transaction(reference)
    status_value = str(verification.get("status") or "").lower()
    amount_paid = Decimal(str(verification.get("amount") or 0))
    if status_value != "successful":
        payment.status = CBTLicensePayment.STATUS_FAILED
        payment.metadata = {**payment.metadata, "verification": verification}
        payment.save(update_fields=["status", "metadata", "updated_at"])
        raise LicenseError("Payment was not successful.")
    if amount_paid < payment.amount:
        payment.status = CBTLicensePayment.STATUS_FAILED
        payment.metadata = {**payment.metadata, "verification": verification, "reason": "amount_mismatch"}
        payment.save(update_fields=["status", "metadata", "updated_at"])
        raise LicenseError("Payment amount did not match the license price.")

    with transaction.atomic():
        locked_payment = CBTLicensePayment.objects.select_for_update().get(pk=payment.pk)
        if locked_payment.status != CBTLicensePayment.STATUS_SUCCESSFUL:
            license = activate_license(locked_payment.license.key, requesting_tenant)
            locked_payment.status = CBTLicensePayment.STATUS_SUCCESSFUL
            locked_payment.metadata = {**locked_payment.metadata, "verification": verification}
            locked_payment.save(update_fields=["status", "metadata", "updated_at"])
    payment.license.refresh_from_db()
    return payment.license
