from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .models import CBTLicense
from .services import (
    LicenseError,
    activate_license,
    current_license_for,
    initialize_license_purchase,
    verify_license_purchase,
)

# Same admin+accountant role set finance/views.py's SMS wallet and
# activation-credit purchase endpoints use - a license affects the whole
# school and costs real money, so it's gated the same way those are.
LICENSE_ROLES = {"school_admin", "principal", "super_admin", "school_superadmin", "accountant"}


def _license_payload(license):
    if license is None:
        return None
    return {
        "id": str(license.id),
        "key": license.key,
        "status": license.status,
        "source": license.source,
        "activated_at": license.activated_at,
        "expires_at": license.expires_at,
        "days_remaining": license.days_remaining,
        "is_active": license.is_currently_active,
    }


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def license_status(request):
    user = request.user
    if user.role not in LICENSE_ROLES:
        return Response({"success": False, "message": "Admin access required."}, status=status.HTTP_403_FORBIDDEN)
    tenant = getattr(user, "tenant", None)
    license = current_license_for(tenant)
    return Response({"success": True, "license": _license_payload(license)})


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def license_activate(request):
    user = request.user
    if user.role not in LICENSE_ROLES:
        return Response({"success": False, "message": "Admin access required."}, status=status.HTTP_403_FORBIDDEN)
    tenant = getattr(user, "tenant", None)
    if tenant is None:
        return Response({"success": False, "message": "No school is associated with this account."}, status=status.HTTP_400_BAD_REQUEST)

    try:
        license = activate_license(request.data.get("key"), tenant)
    except LicenseError as exc:
        return Response({"success": False, "message": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

    return Response({
        "success": True,
        "message": "License activated. CBT is now unlocked.",
        "license": _license_payload(license),
    })


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def license_purchase(request):
    user = request.user
    if user.role not in LICENSE_ROLES:
        return Response({"success": False, "message": "Admin access required."}, status=status.HTTP_403_FORBIDDEN)
    tenant = getattr(user, "tenant", None)
    if tenant is None:
        return Response({"success": False, "message": "No school is associated with this account."}, status=status.HTTP_400_BAD_REQUEST)

    try:
        result = initialize_license_purchase(tenant, actor=user)
    except LicenseError as exc:
        return Response({"success": False, "message": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
    except Exception as exc:
        return Response({"success": False, "message": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

    return Response({
        "success": True,
        "reference": result.get("reference"),
        "authorization_url": result.get("authorization_url") or result.get("link"),
        "access_code": result.get("access_code"),
        "amount": result.get("amount"),
        "provider": result.get("provider"),
    }, status=status.HTTP_201_CREATED)


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def license_purchase_verify(request, reference):
    user = request.user
    if user.role not in LICENSE_ROLES:
        return Response({"success": False, "message": "Admin access required."}, status=status.HTTP_403_FORBIDDEN)
    tenant = getattr(user, "tenant", None)
    if tenant is None:
        return Response({"success": False, "message": "No school is associated with this account."}, status=status.HTTP_400_BAD_REQUEST)

    try:
        license = verify_license_purchase(reference, tenant)
    except LicenseError as exc:
        return Response({"success": False, "message": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

    return Response({
        "success": True,
        "message": "Payment confirmed. License activated.",
        "license": _license_payload(license),
    })
