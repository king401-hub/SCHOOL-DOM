"""Branch switching for a single school operating as named branches (e.g.
"Primary"/"Secondary") under one name - distinct from the proprietor /
Group-of-Schools flow (proprietor_views.py), where each school is fully
separate with its own admin login. Here one admin keeps ONE login and
switches which branch is active; each branch is still a fully separate
SchoolTenant (its own students/classes/fees/...), so data never mixes
between branches - see users.authentication.BranchAwareJWTAuthentication
for how the active branch is enforced on every request.
"""
import logging

from django.db import transaction
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status

from core.models import Domain, SchoolGroup, SchoolTenant
from tenants.models import Tenant
from users.views import generate_unique_domain, generate_unique_schema_name, get_tokens_for_user

logger = logging.getLogger(__name__)

# Only a single school's own admin can create/manage branches - not every
# role (an accountant shouldn't be able to spin up a new branch), and not
# school_superadmin (that's the separate proprietor/Group-of-Schools flow,
# which already has its own multi-school UI with one admin per school).
BRANCH_MANAGER_ROLES = {"school_admin", "principal"}


def _require_branch_manager(request):
    """Resolve the requesting user, or (None, an error Response). Reads
    request.user.tenant, which BranchAwareJWTAuthentication has already
    resolved to whichever branch is currently active for this request."""
    user = request.user
    if getattr(user, "role", "") not in BRANCH_MANAGER_ROLES:
        return None, Response(
            {"success": False, "message": "Only a school admin or principal can manage branches."},
            status=status.HTTP_403_FORBIDDEN,
        )
    if not user.tenant_id:
        return None, Response(
            {"success": False, "message": "Your account is not linked to a school."},
            status=status.HTTP_400_BAD_REQUEST,
        )
    return user, None


def _branch_payload(tenant, active_tenant_id):
    return {
        "id": str(tenant.id),
        "name": tenant.name,
        "branch_label": tenant.branch_label,
        "school_code": tenant.schema_name,
        "is_active": str(tenant.id) == str(active_tenant_id),
    }


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def list_branches(request):
    """Every branch (SchoolTenant) under the requester's own school_group -
    empty unless they've actually created a branch, in which case it also
    includes their current/home one so the switcher can show both."""
    user, error = _require_branch_manager(request)
    if error:
        return error

    if not user.school_group_id:
        return Response({"success": True, "branches": []})

    branches = SchoolTenant.objects.filter(school_group_id=user.school_group_id).order_by("branch_label", "name")
    return Response({
        "success": True,
        "branches": [_branch_payload(tenant, user.tenant_id) for tenant in branches],
    })


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def create_branch(request):
    """Add a new branch (e.g. "Secondary") to the requester's own school,
    auto-creating a SchoolGroup around their existing school the first time
    this is called. The new branch is reached afterward by switching to it
    (see switch_branch) with the SAME login - never a separate admin
    account, which is what the proprietor flow uses for distinct schools."""
    user, error = _require_branch_manager(request)
    if error:
        return error

    branch_label = (request.data.get("branch_label") or "").strip()
    if not branch_label:
        return Response(
            {"success": False, "message": 'Enter a label for the new branch, e.g. "Secondary".'},
            status=status.HTTP_400_BAD_REQUEST,
        )

    current_branch = user.tenant

    with transaction.atomic():
        group = current_branch.school_group
        if not group:
            group = SchoolGroup.objects.create(name=current_branch.name, owner=user)
            current_branch.school_group = group
            current_branch.save(update_fields=["school_group"])
        if user.school_group_id != group.id:
            user.school_group = group
            user.save(update_fields=["school_group"])

        if SchoolTenant.objects.filter(school_group=group, branch_label__iexact=branch_label).exists():
            return Response(
                {"success": False, "message": f'A branch named "{branch_label}" already exists.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        schema_name = generate_unique_schema_name(f"{current_branch.schema_name}_{branch_label}")
        domain_name = generate_unique_domain(schema_name)

        branch = SchoolTenant.objects.create(
            name=current_branch.name,
            branch_label=branch_label,
            schema_name=schema_name,
            school_group=group,
            school_type=current_branch.school_type,
            country=current_branch.country,
            state=current_branch.state,
            currency=current_branch.currency,
            timezone=current_branch.timezone,
            is_active=True,
        )
        # Keep legacy tenant model in sync for modules still using
        # tenants.Tenant (academic.Class and friends) - same bridge
        # users.views.create_school builds for a brand new school.
        Tenant.objects.get_or_create(slug=schema_name, defaults={"name": f"{current_branch.name} ({branch_label})"})
        Domain.objects.create(tenant=branch, domain=domain_name, is_primary=True)

        # The branch this admin is creating from also needs its own label
        # once it's no longer the school's only branch, so the switcher can
        # tell them apart.
        if not current_branch.branch_label:
            current_branch.branch_label = "Main"
            current_branch.save(update_fields=["branch_label"])

    return Response(
        {
            "success": True,
            "message": f'"{branch_label}" branch created. Switch to it from the branch menu.',
            "branch": _branch_payload(branch, user.tenant_id),
        },
        status=status.HTTP_201_CREATED,
    )


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def switch_branch(request):
    """Re-issue this admin's tokens scoped to a different branch of their
    own school. Authorization is the live school_group relationship, not
    anything client-supplied: requesting a tenant_id outside the caller's
    own group is rejected here, and the same check runs again on every
    later request (see BranchAwareJWTAuthentication) so this can never
    become a stale grant if the branch is later removed from the group."""
    user, error = _require_branch_manager(request)
    if error:
        return error

    if not user.school_group_id:
        return Response({"success": False, "message": "Your school has no branches yet."}, status=status.HTTP_400_BAD_REQUEST)

    tenant_id = request.data.get("tenant_id")
    if not tenant_id:
        return Response({"success": False, "message": "tenant_id is required."}, status=status.HTTP_400_BAD_REQUEST)

    try:
        target = SchoolTenant.objects.get(pk=tenant_id, school_group_id=user.school_group_id)
    except (SchoolTenant.DoesNotExist, ValueError, TypeError):
        return Response({"success": False, "message": "That branch does not belong to your school."}, status=status.HTTP_404_NOT_FOUND)

    tokens = get_tokens_for_user(user, active_tenant=target)
    return Response(
        {
            "success": True,
            "message": f"Switched to {target.branch_label or target.name}.",
            "branch": _branch_payload(target, target.id),
            **tokens,
        }
    )
