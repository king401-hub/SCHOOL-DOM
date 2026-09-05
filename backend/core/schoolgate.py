"""SchoolGate access gating - a SchoolGate-tier tenant (SchoolTenant.product
== 'schoolgate') only ever purchased the attendance-gate terminal, not full
school management, so every module outside Attendance/Staff/Finance/Students
returns a locked response here rather than real data. The frontend renders
this as a padlocked page with an "Activate School Management" message
(see frontend's <SchoolGateLocked/>) - this is the server-side backstop so
that lock can't be bypassed by calling the API directly.
"""
from rest_framework import status
from rest_framework.response import Response

SCHOOLGATE_LOCKED_MESSAGE = (
    "This feature isn't available on your SchoolGate plan. "
    "Activate School Management to unlock it."
)


def schoolgate_locked_response():
    return Response(
        {'success': False, 'locked': True, 'reason': 'schoolgate_plan', 'message': SCHOOLGATE_LOCKED_MESSAGE},
        status=status.HTTP_403_FORBIDDEN,
    )


def require_full_product(user):
    """Returns a locked Response if this user's school is SchoolGate-only;
    None if the caller should proceed normally. Call at the top of any view
    for a module outside Attendance/Staff/Finance/Students."""
    tenant = getattr(user, 'tenant', None)
    if tenant is not None and getattr(tenant, 'is_schoolgate', False):
        return schoolgate_locked_response()
    return None
