"""Scanner-device business logic that isn't tied to an HTTP request - the
same views.py/services.py split rfid_attendance uses. _log and
_set_scanner_user_active started life in views.py; moved here so
expire_scanner_devices (run from a management command, no request in sight)
can share them instead of duplicating.
"""
from datetime import datetime, time, timedelta

from django.utils import timezone

from .models import Device, DeviceAuditLog


def _log(device, actor, action, details='', result='success'):
    DeviceAuditLog.objects.create(device=device, actor=actor, action=action, details=details, result=result)


def _set_scanner_user_active(device, is_active):
    if device.scanner_user_id:
        device.scanner_user.is_active = is_active
        device.scanner_user.save(update_fields=['is_active'])


# Non-K12 schools have no termly calendar to bound device access to - their
# one implicit Term/session (academic.models.sync_implicit_term_for_non_k12_year)
# can span the whole academic year, far longer than a sensible licensing
# window - so they get a flat window from the day the device is assigned
# instead.
NON_K12_ACCESS_DAYS = 30


def compute_device_access_expiry(school):
    """How long a device just assigned to `school` keeps working before its
    access needs renewing - see expire_scanner_devices below (the cron job
    that enforces this) and assign_school in views.py (the only way out of
    an expiry: reassigning the device, even to the same school, recomputes
    this fresh).

    K-12: tied to the school's own academic calendar - access lasts exactly
    as long as whatever term is active right now. A school licensing one
    term of terminal access shouldn't silently get the rest of the year for
    free. Returns None (never expires on its own) if the school has no
    active term yet - inventing a date would be worse than leaving this
    unbounded until a real one exists.

    Non-K12: a flat NON_K12_ACCESS_DAYS days from assignment, independent of
    the academic session.
    """
    from core.tenant import SchoolTenant

    if school.school_type == SchoolTenant.NON_K12:
        return timezone.now() + timedelta(days=NON_K12_ACCESS_DAYS)

    from academic.models import Term
    from users.models import resolve_legacy_tenant_for_school

    legacy_tenant = resolve_legacy_tenant_for_school(school)
    term = (
        Term.objects.filter(tenant=legacy_tenant, is_active=True).order_by('-end_date').first()
        if legacy_tenant else None
    )
    if not term:
        return None
    return timezone.make_aware(datetime.combine(term.end_date, time.max))


def expire_scanner_devices(*, now=None, dry_run=False):
    """Every 'active' device whose access_expires_at has passed is moved to
    'expired' and loses the ability to authenticate (the same mechanism
    suspend_device uses) - run periodically via the expire_scanner_devices
    management command (see [[project-no-celery-in-production]] for why a
    cron entry, not Celery beat). An admin renews it the same way it was
    first provisioned, by assigning it to a school again - assign_school
    recomputes a fresh access_expires_at and reactivates it.

    Returns one row per device acted on (or, with dry_run, that would be):
    {"device", "outcome"}, outcome "dry_run" or "expired".
    """
    now = now or timezone.now()
    rows = []
    devices = Device.objects.filter(status='active', access_expires_at__lte=now).select_related('tenant')
    for device in devices:
        if dry_run:
            rows.append({'device': device, 'outcome': 'dry_run'})
            continue
        device.status = 'expired'
        device.save(update_fields=['status', 'updated_at'])
        _set_scanner_user_active(device, False)
        school_name = device.tenant.name if device.tenant else 'no school'
        _log(device, None, 'access_expired', details=f'Access expired for {school_name}')
        rows.append({'device': device, 'outcome': 'expired'})
    return rows
