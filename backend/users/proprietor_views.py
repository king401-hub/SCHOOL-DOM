"""REST API for the School Superadmin (Proprietor) dashboard.

A proprietor manages several schools grouped under one SchoolGroup, unlike a
school_admin/principal who is scoped to a single SchoolTenant via
`user.tenant`. These endpoints key off `request.user.school_group` instead,
and reuse the finance/user-creation logic already proven in the legacy
Django-template dashboard at `apps/auth/views.py` rather than re-deriving it.
"""
import logging

from django.conf import settings
from django.core.mail import send_mail
from django.db import transaction
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status

from apps.auth.views import (
    export_school_superadmin_finance_csv,
    school_superadmin_finance_context,
    split_full_name,
    temporary_password,
    unique_schema_name,
)
from core.models import SchoolGroup, SchoolTenant
from users.models import User

logger = logging.getLogger(__name__)

ADMIN_INVITE_ROLES = {"school_admin", "principal", "accountant"}


def _require_proprietor(request):
    """Resolve the requester's SchoolGroup, or (None, an error Response)."""
    user = request.user
    if getattr(user, "role", "") != "school_superadmin":
        return None, Response(
            {"success": False, "message": "Only School Superadmin accounts can access this."},
            status=status.HTTP_403_FORBIDDEN,
        )
    group = user.school_group or user.owned_school_groups.first()
    if not group:
        # Mirrors apps/auth/views.py:270-274 - registration always creates a
        # group for a proprietor, but this keeps the endpoint safe either way.
        group = SchoolGroup.objects.create(name=f"{user.get_full_name() or user.email} Schools", owner=user)
        user.school_group = group
        user.save(update_fields=["school_group"])
    return group, None


def _school_summary(row):
    school = row["school"]
    return {
        "id": school.id,
        "name": school.name,
        "school_code": school.schema_name,
        "students": row["students"],
        "staff": row["staff"],
        "collected": row["collected"],
        "outstanding": row["outstanding"],
        "status": row["status"],
        "rate": float(row["rate"]),
    }


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def proprietor_overview(request):
    group, error = _require_proprietor(request)
    if error:
        return error

    context = school_superadmin_finance_context(group)
    totals = context["finance_totals"]
    return Response({
        "success": True,
        "school_group": {"id": group.id, "name": group.name, "schools_count": group.schools.count()},
        "schools": [_school_summary(row) for row in context["finance_rows"]],
        "totals": {
            "students": totals["students"],
            "staff": totals["staff"],
            "collected": totals["collected"],
            "outstanding": totals["outstanding"],
            "status": totals["status"],
            "rate": float(totals["rate"]),
        },
    })


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def proprietor_create_school(request):
    group, error = _require_proprietor(request)
    if error:
        return error

    name = (request.data.get("name") or "").strip()
    if not name:
        return Response({"success": False, "message": "Enter a school name."}, status=status.HTTP_400_BAD_REQUEST)

    school = SchoolTenant.objects.create(
        name=name,
        schema_name=unique_schema_name(name),
        school_group=group,
        address=(request.data.get("address") or "").strip(),
        email=(request.data.get("email") or "").strip(),
        currency="NGN",
    )
    return Response({
        "success": True,
        "message": f"{school.name} was added to your school group.",
        "school": {"id": school.id, "name": school.name, "school_code": school.schema_name},
    }, status=status.HTTP_201_CREATED)


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def proprietor_add_school_admin(request, school_id):
    group, error = _require_proprietor(request)
    if error:
        return error

    try:
        school = group.schools.get(pk=school_id)
    except SchoolTenant.DoesNotExist:
        return Response(
            {"success": False, "message": "That school does not belong to your group."},
            status=status.HTTP_404_NOT_FOUND,
        )

    email = (request.data.get("email") or "").strip().lower()
    full_name = (request.data.get("name") or "").strip()
    admin_role = request.data.get("role") or "school_admin"
    if admin_role not in ADMIN_INVITE_ROLES:
        admin_role = "school_admin"
    if not email or not full_name:
        return Response(
            {"success": False, "message": "Enter the admin's name and email."},
            status=status.HTTP_400_BAD_REQUEST,
        )
    if User.objects.filter(email__iexact=email).exists():
        return Response(
            {"success": False, "message": "An account with this email already exists."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    first_name, last_name = split_full_name(full_name)
    password = temporary_password()

    with transaction.atomic():
        new_admin = User.objects.create_user(
            email=email,
            password=password,
            first_name=first_name,
            last_name=last_name,
            role=admin_role,
            tenant=school,
            school_group=group,
            is_active=True,
            is_verified=True,
        )

    invited = True
    try:
        send_mail(
            f"You've been added to {school.name} on Schooldom",
            (
                f"Hi {first_name or full_name},\n\n"
                f"{request.user.get_full_name() or request.user.email} has added you as "
                f"{admin_role.replace('_', ' ')} for {school.name} on Schooldom.\n\n"
                "Sign in at https://schooldom.academy/ with:\n"
                f"  School code: {school.schema_name}\n"
                f"  Email: {email}\n"
                f"  Temporary password: {password}\n\n"
                "Please sign in and change your password as soon as possible."
            ),
            settings.DEFAULT_FROM_EMAIL,
            [email],
            fail_silently=False,
        )
    except Exception:
        logger.warning("Proprietor admin-invite email failed for %s.", email, exc_info=True)
        invited = False

    return Response({
        "success": True,
        "message": f"Admin added to {school.name}." + ("" if invited else " (invite email could not be sent)"),
        "admin": {"id": new_admin.id, "email": new_admin.email, "role": new_admin.role, "school": school.name},
        "invited": invited,
    }, status=status.HTTP_201_CREATED)


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def proprietor_finance(request):
    group, error = _require_proprietor(request)
    if error:
        return error

    context = school_superadmin_finance_context(group)
    totals = context["finance_totals"]
    defaulters = [
        {
            "student": fee.student.user.get_full_name(),
            "school": fee.student.user.tenant.name if fee.student.user.tenant else "",
            "amount": fee.amount,
            "status": fee.status,
        }
        for fee in context["top_defaulters"]
    ]
    return Response({
        "success": True,
        "schools": [_school_summary(row) for row in context["finance_rows"]],
        "totals": {**totals, "rate": float(totals["rate"])},
        "top_defaulters": defaulters,
    })


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def proprietor_finance_export(request):
    group, error = _require_proprietor(request)
    if error:
        return error
    return export_school_superadmin_finance_csv(group)
