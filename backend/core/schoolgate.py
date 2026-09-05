"""SchoolGate access gating and billing - a SchoolGate-tier tenant
(SchoolTenant.product == 'schoolgate') only ever purchased the
attendance-gate terminal, not full school management, so every module
outside Attendance/Staff/Finance/Students returns a locked response here
rather than real data. Those four modules are themselves ALSO locked until
the school has paid its one-time device fee and the current term's
per-student subscription (product decision: hard block, not track-only).
The frontend renders both kinds of lock as the same padlocked page (see
frontend's <SchoolGateLocked/>) - this module is the server-side backstop
so the lock can't be bypassed by calling the API directly.
"""
import uuid

from django.db import models
from rest_framework import status
from rest_framework.response import Response

SCHOOLGATE_LOCKED_MESSAGE = (
    "This feature isn't available on your SchoolGate plan. "
    "Activate School Management to unlock it."
)
SCHOOLGATE_UNPAID_MESSAGE = (
    "Pay your SchoolGate device fee and this term's subscription to unlock this page."
)

# Naira - flat regardless of plan; only the recurring per-student price
# differs between plans.
SCHOOLGATE_DEVICE_FEE = 50000
SCHOOLGATE_PLAN_PRICES = {
    'basic': 700,
    'premium': 1500,
}


class SchoolGatePayment(models.Model):
    """Ledger for the two SchoolGate charges: the one-time device fee and
    each term's per-student subscription. Mirrors
    finance.ActivationCreditTransaction's pending/successful/failed pattern
    and is completed the same way, through
    finance.services.complete_payment_reference - see the new branch added
    there rather than a separate webhook path."""

    TYPE_DEVICE = 'device'
    TYPE_TERMLY = 'termly'
    TYPE_CHOICES = [(TYPE_DEVICE, 'Device Fee'), (TYPE_TERMLY, 'Termly Subscription')]

    STATUS_PENDING = 'pending'
    STATUS_SUCCESSFUL = 'successful'
    STATUS_FAILED = 'failed'
    STATUS_CHOICES = [
        (STATUS_PENDING, 'Pending'),
        (STATUS_SUCCESSFUL, 'Successful'),
        (STATUS_FAILED, 'Failed'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey('core.SchoolTenant', on_delete=models.CASCADE, related_name='schoolgate_payments')
    payment_type = models.CharField(max_length=10, choices=TYPE_CHOICES)
    # Only set for TYPE_TERMLY - which term this payment covers. String FK
    # (not an eager import) since academic.models already imports from
    # core.models, so an eager core -> academic import would be circular.
    term = models.ForeignKey('academic.Term', on_delete=models.SET_NULL, null=True, blank=True)
    # Snapshot of plan/student_count/per_student_price at payment time, so a
    # later plan change or enrolment change never rewrites the amount this
    # specific payment actually covered.
    plan = models.CharField(max_length=20, blank=True, default='')
    student_count = models.PositiveIntegerField(default=0)
    per_student_price = models.PositiveIntegerField(default=0)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    reference = models.CharField(max_length=100, unique=True)
    status = models.CharField(max_length=12, choices=STATUS_CHOICES, default=STATUS_PENDING)
    created_at = models.DateTimeField(auto_now_add=True)
    paid_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        indexes = [models.Index(fields=['tenant', 'payment_type', 'status'])]

    def __str__(self):
        return f'{self.get_payment_type_display()} - {self.tenant_id} - {self.status}'


def schoolgate_locked_response(message=None):
    return Response(
        {'success': False, 'locked': True, 'reason': 'schoolgate_plan', 'message': message or SCHOOLGATE_LOCKED_MESSAGE},
        status=status.HTTP_403_FORBIDDEN,
    )


def schoolgate_device_paid(tenant):
    return SchoolGatePayment.objects.filter(
        tenant=tenant, payment_type=SchoolGatePayment.TYPE_DEVICE, status=SchoolGatePayment.STATUS_SUCCESSFUL,
    ).exists()


def schoolgate_current_term(tenant):
    """Term.tenant is a legacy FK to tenants.Tenant, not core.SchoolTenant -
    resolve_legacy_tenant_for_school does that slug-based mapping already
    (see users.models), so reuse it rather than reinventing the lookup."""
    from academic.models import Term
    from users.models import resolve_legacy_tenant_for_school

    legacy_tenant = resolve_legacy_tenant_for_school(tenant)
    if not legacy_tenant:
        return None
    return (
        Term.objects.select_related('academic_year')
        .filter(tenant=legacy_tenant, is_active=True)
        .order_by('-start_date')
        .first()
    )


def schoolgate_term_paid(tenant, term):
    if not term:
        return False
    return SchoolGatePayment.objects.filter(
        tenant=tenant, payment_type=SchoolGatePayment.TYPE_TERMLY, term=term, status=SchoolGatePayment.STATUS_SUCCESSFUL,
    ).exists()


def schoolgate_is_unlocked(tenant):
    """Both the device fee (once, ever) and the current term's per-student
    subscription must be paid - matches the confirmed "hard block until
    paid" product decision, not a track-only reminder."""
    term = schoolgate_current_term(tenant)
    return schoolgate_device_paid(tenant) and schoolgate_term_paid(tenant, term)


def require_full_product(user):
    """Returns a locked Response if this user's school is SchoolGate-only
    OR is SchoolGate but hasn't paid; None if the caller should proceed
    normally. Call at the top of any view for a module outside Attendance/
    Staff/Finance/Students, or one of those four gated additionally on
    payment status."""
    tenant = getattr(user, 'tenant', None)
    if tenant is None or not getattr(tenant, 'is_schoolgate', False):
        return None
    if not schoolgate_is_unlocked(tenant):
        return schoolgate_locked_response(SCHOOLGATE_UNPAID_MESSAGE)
    return None


def require_full_product_only(user):
    """Same as require_full_product but ignores payment status - for the
    modules outside Attendance/Staff/Finance/Students, which are locked for
    every SchoolGate tenant regardless of whether they've paid."""
    tenant = getattr(user, 'tenant', None)
    if tenant is not None and getattr(tenant, 'is_schoolgate', False):
        return schoolgate_locked_response()
    return None
