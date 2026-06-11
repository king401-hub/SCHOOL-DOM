from hmac import compare_digest

from django.conf import settings
from django.db.models import Q
from django.shortcuts import get_object_or_404
from django.views.decorators.csrf import csrf_exempt
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response

from fee_collections.models import CollectionConfig, SchoolCollectionProfile, SchoolSettlement
from fee_collections.serializers import (
    CollectionConfigSerializer,
    FeePaymentSerializer,
    SchoolCollectionProfileSerializer,
    SchoolSettlementSerializer,
    SchoolVirtualAccountSerializer,
)
from fee_collections.services import (
    admin_dashboard_payload,
    approve_collection_profile,
    collection_config,
    create_due_settlements,
    create_flutterwave_virtual_account,
    process_settlement,
    record_flutterwave_payment,
    school_dashboard_payload,
)


ADMIN_ROLES = {"school_admin", "principal", "accountant"}
SUPER_ROLES = {"super_admin"}


def _is_school_finance_user(user):
    return bool(user and user.is_authenticated and user.role in ADMIN_ROLES and user.tenant_id)


def _is_super_admin(user):
    return bool(user and user.is_authenticated and user.role in SUPER_ROLES)


@api_view(["GET", "PUT", "PATCH"])
@permission_classes([IsAuthenticated])
def school_collection_profile(request):
    if not _is_school_finance_user(request.user):
        return Response({"success": False, "message": "School finance access required."}, status=status.HTTP_403_FORBIDDEN)
    profile, _ = SchoolCollectionProfile.objects.get_or_create(
        school=request.user.tenant,
        defaults={
            "bank_name": "",
            "bank_code": "",
            "account_number": "",
            "account_name": "",
        },
    )
    if request.method == "GET":
        return Response({"success": True, "profile": SchoolCollectionProfileSerializer(profile).data})

    serializer = SchoolCollectionProfileSerializer(profile, data=request.data, partial=True)
    serializer.is_valid(raise_exception=True)
    serializer.save(status=SchoolCollectionProfile.STATUS_PENDING)
    return Response({"success": True, "profile": serializer.data, "message": "Collection profile saved for approval."})


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def admin_collection_profiles(request):
    if not _is_super_admin(request.user):
        return Response({"success": False, "message": "Super admin access required."}, status=status.HTTP_403_FORBIDDEN)
    query = str(request.query_params.get("q") or "").strip()
    profiles = SchoolCollectionProfile.objects.select_related("school", "approved_by").order_by("-created_at")
    if query:
        profiles = profiles.filter(Q(school__name__icontains=query) | Q(school__schema_name__icontains=query))
    return Response({"success": True, "profiles": SchoolCollectionProfileSerializer(profiles, many=True).data})


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def approve_school_collection_profile(request, profile_id):
    if not _is_super_admin(request.user):
        return Response({"success": False, "message": "Super admin access required."}, status=status.HTTP_403_FORBIDDEN)
    profile = get_object_or_404(SchoolCollectionProfile.objects.select_related("school"), id=profile_id)
    try:
        virtual_account = approve_collection_profile(profile, actor=request.user)
    except Exception as exc:
        return Response({"success": False, "message": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
    profile.refresh_from_db()
    return Response(
        {
            "success": True,
            "profile": SchoolCollectionProfileSerializer(profile).data,
            "virtual_account": SchoolVirtualAccountSerializer(virtual_account).data,
        }
    )


@api_view(["GET", "POST"])
@permission_classes([IsAuthenticated])
def school_virtual_account(request):
    if not _is_school_finance_user(request.user):
        return Response({"success": False, "message": "School finance access required."}, status=status.HTTP_403_FORBIDDEN)
    profile = get_object_or_404(SchoolCollectionProfile.objects.select_related("school"), school=request.user.tenant)
    if request.method == "POST":
        try:
            virtual_account = create_flutterwave_virtual_account(profile, actor=request.user)
        except Exception as exc:
            return Response({"success": False, "message": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
    else:
        virtual_account = getattr(request.user.tenant, "fee_virtual_account", None)
    return Response(
        {
            "success": True,
            "virtual_account": SchoolVirtualAccountSerializer(virtual_account).data if virtual_account else None,
        }
    )


@csrf_exempt
@api_view(["POST"])
@permission_classes([AllowAny])
def flutterwave_collection_webhook(request):
    configured_hash = getattr(settings, "FLUTTERWAVE_WEBHOOK_SECRET_HASH", "")
    received_hash = request.headers.get("verif-hash", "")
    if configured_hash and not compare_digest(received_hash, configured_hash):
        return Response({"success": False, "message": "Invalid webhook signature."}, status=status.HTTP_401_UNAUTHORIZED)
    try:
        payment, created = record_flutterwave_payment(request.data)
    except ValueError as exc:
        return Response({"success": True, "message": str(exc)})
    except Exception as exc:
        return Response({"success": False, "message": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
    if not payment:
        return Response({"success": True, "message": "Webhook ignored."})
    return Response({"success": True, "created": created, "payment": FeePaymentSerializer(payment).data})


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def school_dashboard(request):
    if not _is_school_finance_user(request.user):
        return Response({"success": False, "message": "School finance access required."}, status=status.HTTP_403_FORBIDDEN)
    data = school_dashboard_payload(request.user.tenant)
    return Response(
        {
            "success": True,
            "virtual_account": SchoolVirtualAccountSerializer(data["virtual_account"]).data if data["virtual_account"] else None,
            "total_fees_received": data["total_fees_received"],
            "total_platform_fees": data["total_platform_fees"],
            "total_net_payable": data["total_net_payable"],
            "pending_settlements": SchoolSettlementSerializer(data["pending_settlements"], many=True).data,
            "completed_settlements": SchoolSettlementSerializer(data["completed_settlements"], many=True).data,
            "payment_history": FeePaymentSerializer(data["payments"], many=True).data,
            "settlement_history": SchoolSettlementSerializer(data["settlements"], many=True).data,
        }
    )


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def admin_dashboard(request):
    if not _is_super_admin(request.user):
        return Response({"success": False, "message": "Super admin access required."}, status=status.HTTP_403_FORBIDDEN)
    data = admin_dashboard_payload()
    return Response(
        {
            "success": True,
            "total_collections": data["total_collections"],
            "total_commissions_earned": data["total_commissions_earned"],
            "total_net_payable": data["total_net_payable"],
            "total_settlements": data["total_settlements"],
            "failed_settlements": SchoolSettlementSerializer(data["failed_settlements"], many=True).data,
            "recent_payments": FeePaymentSerializer(data["recent_payments"], many=True).data,
            "recent_settlements": SchoolSettlementSerializer(data["recent_settlements"], many=True).data,
            "config": CollectionConfigSerializer(data["config"]).data,
        }
    )


@api_view(["GET", "PATCH"])
@permission_classes([IsAuthenticated])
def collection_settings(request):
    if not _is_super_admin(request.user):
        return Response({"success": False, "message": "Super admin access required."}, status=status.HTTP_403_FORBIDDEN)
    config = collection_config()
    if request.method == "GET":
        return Response({"success": True, "config": CollectionConfigSerializer(config).data})
    serializer = CollectionConfigSerializer(config, data=request.data, partial=True)
    serializer.is_valid(raise_exception=True)
    serializer.save()
    return Response({"success": True, "config": serializer.data})


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def run_settlements(request):
    if not _is_super_admin(request.user):
        return Response({"success": False, "message": "Super admin access required."}, status=status.HTTP_403_FORBIDDEN)
    settlements = create_due_settlements()
    processed = []
    for settlement in settlements:
        processed.append(process_settlement(settlement.id, actor=request.user))
    return Response({"success": True, "settlements": SchoolSettlementSerializer(processed, many=True).data})


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def retry_settlement(request, settlement_id):
    if not _is_super_admin(request.user):
        return Response({"success": False, "message": "Super admin access required."}, status=status.HTTP_403_FORBIDDEN)
    settlement = get_object_or_404(SchoolSettlement, id=settlement_id)
    settlement = process_settlement(settlement.id, actor=request.user)
    return Response({"success": True, "settlement": SchoolSettlementSerializer(settlement).data})
