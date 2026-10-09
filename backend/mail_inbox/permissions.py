from rest_framework.permissions import BasePermission

from ops.models import MODULE_SUPPORT_MAIL
from ops.permissions import has_permission


class IsSupportMailStaff(BasePermission):
    """Gates the mail inbox API by the Ops Console's own permission matrix
    (ops/permissions.py) rather than a one-off check - a CEO/CTO/CFO always
    passes, everyone else needs MODULE_SUPPORT_MAIL granted on their role or
    as a personal override."""

    message = "You do not have access to the support mail inbox."

    def has_permission(self, request, view):
        ops_user = getattr(request.user, "ops_profile", None)
        return has_permission(ops_user, MODULE_SUPPORT_MAIL)
