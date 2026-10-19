"""Branch switching for a single school operating as named branches (e.g.
"Primary"/"Secondary") - distinct from the proprietor / Group-of-Schools
flow (proprietor_views.py), where each school is fully separate with its
own admin login. Here one admin keeps ONE login and switches which branch
is active; each branch is still a fully separate SchoolTenant (its own
students/classes/fees/...), so data never mixes between branches - see
users.authentication.BranchAwareJWTAuthentication for how the active
branch is enforced on every request. A branch's own name defaults to the
parent school's but can be changed (e.g. a franchised campus trading
under its own name) - see branch_name in create_branch below.
"""
import logging

from django.db import IntegrityError, transaction
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status

from core.models import Domain, SchoolGroup, SchoolTenant
from device_fleet.models import Device, DeviceAuditLog
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


def _branch_label(tenant):
    return tenant.branch_label or tenant.name


def _group_devices(school_group_id):
    """Scanner terminals this school group already owns - a device's
    `tenant` is always set once it's assigned to a school (assign_school in
    device_fleet.views), so filtering on it is enough to scope strictly to
    hardware this admin's own branches already have, never another
    school's device."""
    return Device.objects.filter(tenant__school_group_id=school_group_id).select_related("tenant", "paired_tenant")


def _terminal_payload(device):
    return {
        "id": str(device.id),
        "device_id": device.device_id,
        "name": device.name,
        "active_branch_id": str(device.tenant_id) if device.tenant_id else None,
        "active_branch_label": _branch_label(device.tenant) if device.tenant else None,
        "paired_branch_id": str(device.paired_tenant_id) if device.paired_tenant_id else None,
        "paired_branch_label": _branch_label(device.paired_tenant) if device.paired_tenant else None,
        "has_open_slot": device.paired_tenant_id is None,
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
    # The branch's own display name (ID cards, receipts, certificates...) -
    # defaults to the parent school's name but an admin can give a branch a
    # genuinely different one (e.g. a franchised campus trading under its
    # own name).
    branch_name = (request.data.get("name") or "").strip() or current_branch.name

    with transaction.atomic():
        group = current_branch.school_group
        if not group:
            group = SchoolGroup.objects.create(name=current_branch.name, owner=user)
            current_branch.school_group = group
            current_branch.save(update_fields=["school_group"])
        elif group.owner_id != user.id:
            # This tenant's school_group already belongs to someone else -
            # a proprietor managing several genuinely distinct schools
            # (proprietor_views.py), who assigned this user as that one
            # school's own admin. That's a different feature: branching
            # must never insert a new tenant into a group this user
            # doesn't own, or it would show up in the proprietor's own
            # schools list/count as if it were one of their schools.
            return Response(
                {"success": False, "message": "This school is part of a multi-school group managed elsewhere - branches aren't available here."},
                status=status.HTTP_403_FORBIDDEN,
            )
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
            name=branch_name,
            branch_label=branch_label,
            schema_name=schema_name,
            school_group=group,
            school_type=current_branch.school_type,
            country=current_branch.country,
            state=current_branch.state,
            currency=current_branch.currency,
            timezone=current_branch.timezone,
            is_active=True,
            product=current_branch.product,
            # A branch is the same legal school under KYC review, not a
            # new applicant - inherit the parent's compliance standing
            # (and its 30-day clock reference, rather than restarting one)
            # so a branch can never be silently suspended by
            # core.tasks.send_compliance_reminders for paperwork nobody
            # would even know to submit on its behalf.
            compliance_status=current_branch.compliance_status,
            compliance_deadline_reference_at=current_branch.compliance_deadline_reference(),
            compliance_submitted_at=current_branch.compliance_submitted_at,
            compliance_reviewed_at=current_branch.compliance_reviewed_at,
            compliance_reviewed_by=current_branch.compliance_reviewed_by,
        )
        # Keep legacy tenant model in sync for modules still using
        # tenants.Tenant (academic.Class and friends) - same bridge
        # users.views.create_school builds for a brand new school.
        Tenant.objects.get_or_create(slug=schema_name, defaults={"name": branch_name})
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


def _transfer_student_move(student, target):
    """"Moves with them" mode: the student's own account/login is re-scoped
    to the target branch. Returns (response_payload, warnings)."""
    from academic.models import AttendanceRecord
    from exams.models import ExamAttempt
    from finance.models import BankPayment, StudentPaymentReference
    from rfid_attendance.models import CardAssignment
    from users.models import resolve_legacy_tenant_for_school

    target_legacy = resolve_legacy_tenant_for_school(target)
    student_user = student.user
    warnings = []

    with transaction.atomic():
        student_user.tenant = target
        student_user.save(update_fields=["tenant"])

        if student.current_class_id or student.current_term_id:
            student.current_class = None
            student.current_term = None
        student.save(update_fields=["current_class", "current_term"])
        student.elective_subjects.clear()

        StudentPaymentReference.objects.filter(student=student).update(tenant=target)
        BankPayment.objects.filter(student=student).update(tenant=target)

        try:
            # Its own savepoint, not just a bare try/except: on Postgres an
            # IntegrityError aborts the whole enclosing transaction until a
            # rollback happens, which would otherwise take the student's
            # tenant/class/payment-reference updates above down with it too
            # over what should be a non-fatal, extremely rare edge case.
            with transaction.atomic():
                CardAssignment.objects.filter(holder=student_user).update(tenant=target)
        except IntegrityError:
            # An active card with the same UID already exists on the new
            # branch - vanishingly rare (card readers are per-device), and
            # not worth failing the whole transfer over. The admin can
            # reassign a card on the new branch directly.
            warnings.append("A card assignment could not be moved - please reassign an RFID card on the new branch.")

        if target_legacy:
            AttendanceRecord.objects.filter(student=student_user).update(tenant=target_legacy, class_group=None)
            ExamAttempt.objects.filter(student=student_user).update(tenant=target_legacy)
        else:
            warnings.append("Could not resolve the new branch's academic records - attendance and exam history stayed linked to the old branch.")

    return {"message": f"{student_user.get_full_name()} moved to {target.branch_label or target.name}."}, warnings


def _transfer_student_fresh(student, target, request):
    """"Fresh start" mode: a brand new, unlinked student record is created
    on the target branch (its own new login - email is globally unique, so
    it can't reuse the old account's) and the old record is left completely
    untouched on the old branch except for being deactivated, so its
    history stays exactly where it was, under its own branch."""
    import types

    from users.app_views import _ensure_student_profile_for_tenant

    new_email = str(request.data.get("new_email") or "").strip().lower()
    new_password = str(request.data.get("new_student_password") or "").strip()
    confirm_new_password = str(request.data.get("confirm_new_student_password") or "").strip()
    if not new_email:
        return None, ["A new login email is required for a fresh-start transfer."], status.HTTP_400_BAD_REQUEST

    from users.models import User

    if User.objects.filter(email__iexact=new_email).exists():
        return None, ["That email is already in use by another account."], status.HTTP_400_BAD_REQUEST

    student_user = student.user
    target_proxy = types.SimpleNamespace(tenant=target, tenant_id=target.id)

    try:
        with transaction.atomic():
            new_profile = _ensure_student_profile_for_tenant(
                user=target_proxy,
                email=new_email,
                first_name=student_user.first_name,
                middle_name=student_user.middle_name,
                last_name=student_user.last_name,
                guardian_name=student.guardian_name,
                guardian_phone=student.guardian_phone,
                guardian_email=student.guardian_email,
                guardian_relation=student.guardian_relation,
                second_guardian_name=student.second_guardian_name,
                second_guardian_phone=student.second_guardian_phone,
                second_guardian_email=student.second_guardian_email,
                second_guardian_relation=student.second_guardian_relation,
                state_of_origin=student.state_of_origin,
                local_government=student.local_government,
                disability=student.disability,
                medical_records=student.medical_conditions,
                blood_group=student.blood_group,
                student_type=student.student_type,
                home_address=student.home_address,
                student_password=new_password,
                confirm_student_password=confirm_new_password,
            )
            new_user = new_profile.user
            new_user.gender = student_user.gender
            new_user.date_of_birth = student_user.date_of_birth
            new_user.save(update_fields=["gender", "date_of_birth"])

            # The old record is left exactly as it was - its fees, payment
            # references, attendance, and exam history all stay on the old
            # branch, untouched - only deactivated so it no longer appears
            # as a live, sign-in-able account.
            student_user.is_active = False
            student_user.save(update_fields=["is_active"])
    except ValueError as exc:
        return None, [str(exc)], status.HTTP_400_BAD_REQUEST

    return (
        {
            "message": (
                f"Created a new record for {new_user.get_full_name()} on {target.branch_label or target.name}. "
                f"Their old record stays on this branch, deactivated, with its history untouched."
            ),
            "new_student_id": str(new_profile.id),
        },
        [],
        None,
    )


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def transfer_student(request):
    """Transfer one student from the currently active branch to another
    branch in the same school_group - either "move" (the same account/
    login is re-scoped, full history follows - see _transfer_student_move)
    or "fresh" (a brand new, unlinked record on the new branch; the old one
    is deactivated but left untouched - see _transfer_student_fresh). The
    admin picks per transfer; there is no single right answer (a
    graduating class moving up a level usually wants "move", a one-off
    exchange usually wants "fresh")."""
    user, error = _require_branch_manager(request)
    if error:
        return error

    student_id = request.data.get("student_id")
    target_tenant_id = request.data.get("target_tenant_id")
    mode = request.data.get("mode") or "move"
    if mode not in ("move", "fresh"):
        return Response({"success": False, "message": 'mode must be "move" or "fresh".'}, status=status.HTTP_400_BAD_REQUEST)
    if not student_id or not target_tenant_id:
        return Response(
            {"success": False, "message": "student_id and target_tenant_id are required."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    try:
        target = SchoolTenant.objects.get(pk=target_tenant_id, school_group_id=user.school_group_id)
    except (SchoolTenant.DoesNotExist, ValueError, TypeError):
        return Response({"success": False, "message": "That branch does not belong to your school."}, status=status.HTTP_404_NOT_FOUND)

    if target.id == user.tenant_id:
        return Response({"success": False, "message": "That student is already on this branch."}, status=status.HTTP_400_BAD_REQUEST)

    from users.models import StudentProfile

    try:
        student = StudentProfile.objects.select_related("user").get(pk=student_id, user__tenant_id=user.tenant_id)
    except (StudentProfile.DoesNotExist, ValueError, TypeError):
        return Response({"success": False, "message": "That student does not belong to your current branch."}, status=status.HTTP_404_NOT_FOUND)

    if mode == "move":
        payload, warnings = _transfer_student_move(student, target)
    else:
        payload, warnings, error_status = _transfer_student_fresh(student, target, request)
        if payload is None:
            return Response({"success": False, "message": " ".join(warnings)}, status=error_status)

    return Response({"success": True, "warnings": warnings, **payload})


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def branch_request_delete_otp(request, branch_id):
    """Emails the signed-in admin a one-time code before they're allowed to
    delete a branch - unconditional, same as the finance subaccount
    settlement-change gate, because this protects a branch's entire record
    from being permanently destroyed, not just login."""
    user, error = _require_branch_manager(request)
    if error:
        return error

    try:
        target = SchoolTenant.objects.get(pk=branch_id, school_group_id=user.school_group_id)
    except (SchoolTenant.DoesNotExist, ValueError, TypeError):
        return Response({"success": False, "message": "That branch does not belong to your school."}, status=status.HTTP_404_NOT_FOUND)

    from users.views import ADMIN_OTP_EXPIRY_MINUTES, send_admin_otp

    challenge = send_admin_otp(user, purpose="delete_branch")
    return Response(
        {
            "success": True,
            "message": f"A verification code was sent to your email to confirm deleting {target.branch_label or target.name}.",
            "otp_challenge": challenge,
            "otp_expires_in": ADMIN_OTP_EXPIRY_MINUTES * 60,
        }
    )


def _verify_delete_branch_step_up(request, user):
    """Password + emailed-OTP gate for permanently deleting a branch.
    Returns an error Response to short-circuit the caller, or None once
    both checks pass (the OTP code is consumed on success so it can't be
    replayed) - same shape as finance._verify_subaccount_change_step_up."""
    from django.contrib.auth.hashers import check_password

    from users.views import ADMIN_OTP_MAX_ATTEMPTS, clear_admin_otp, get_admin_email_device

    current_password = str(request.data.get("current_password") or "")
    otp_code = str(request.data.get("otp_code") or "").strip()
    otp_challenge = str(request.data.get("otp_challenge") or "").strip()

    if not (current_password and otp_code and otp_challenge):
        return Response(
            {"success": False, "message": "Deleting a branch needs your password and the emailed verification code."},
            status=status.HTTP_400_BAD_REQUEST,
        )
    if not user.check_password(current_password):
        return Response({"success": False, "message": "Incorrect password."}, status=status.HTTP_400_BAD_REQUEST)

    otp_user = get_admin_email_device(user, challenge=otp_challenge)
    if not otp_user:
        return Response(
            {"success": False, "message": "Verification code expired or invalid - request a new one."},
            status=status.HTTP_400_BAD_REQUEST,
        )
    if user.admin_otp_attempts >= ADMIN_OTP_MAX_ATTEMPTS:
        return Response(
            {"success": False, "message": "Too many incorrect codes - request a new one."},
            status=status.HTTP_429_TOO_MANY_REQUESTS,
        )
    if not user.admin_otp_hash or not check_password(otp_code, user.admin_otp_hash):
        user.admin_otp_attempts += 1
        user.save(update_fields=["admin_otp_attempts"])
        remaining = max(ADMIN_OTP_MAX_ATTEMPTS - user.admin_otp_attempts, 0)
        return Response(
            {"success": False, "message": f"Invalid verification code. {remaining} attempt(s) remaining."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    clear_admin_otp(user)
    return None


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def delete_branch(request, branch_id):
    """Permanently delete a branch - password + emailed OTP required (see
    branch_request_delete_otp / _verify_delete_branch_step_up), and only
    once it has nobody left on it: transfer every student (and reassign any
    staff) off a branch before it can be deleted, so this can never
    silently destroy a live student's or teacher's record. Cannot delete
    the branch you're currently on - switch to a different one first."""
    user, error = _require_branch_manager(request)
    if error:
        return error

    try:
        target = SchoolTenant.objects.get(pk=branch_id, school_group_id=user.school_group_id)
    except (SchoolTenant.DoesNotExist, ValueError, TypeError):
        return Response({"success": False, "message": "That branch does not belong to your school."}, status=status.HTTP_404_NOT_FOUND)

    if target.id == user.tenant_id:
        return Response(
            {"success": False, "message": "Switch to a different branch before deleting this one."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    from users.models import User

    remaining = User.objects.filter(tenant=target).count()
    if remaining:
        return Response(
            {
                "success": False,
                "message": f"{target.branch_label or target.name} still has {remaining} account(s) on it - transfer students (and reassign any staff) off this branch before deleting it.",
            },
            status=status.HTTP_400_BAD_REQUEST,
        )

    step_up_error = _verify_delete_branch_step_up(request, user)
    if step_up_error:
        return step_up_error

    from django.db.models import ProtectedError

    label = target.branch_label or target.name
    try:
        with transaction.atomic():
            target.delete()
    except ProtectedError:
        return Response(
            {"success": False, "message": "This branch still has records referencing it that can't be removed automatically - contact support."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    return Response({"success": True, "message": f"{label} was deleted."})


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def list_branch_terminals(request):
    """Scanner terminal(s) already serving this admin's school group, so
    the Branches panel can offer "Add to terminal" without any superadmin
    involvement. Pairing new hardware to a school at all still only
    happens via the superadmin Control Panel (device_fleet) - this only
    ever touches a device a group already has."""
    user, error = _require_branch_manager(request)
    if error:
        return error
    if not user.school_group_id:
        return Response({"success": True, "terminals": []})

    terminals = [_terminal_payload(device) for device in _group_devices(user.school_group_id)]
    return Response({"success": True, "terminals": terminals})


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def pair_branch_terminal(request, branch_id):
    """Pair a branch onto one of this school's own scanner terminals as its
    second school - the same tenant/paired_tenant slot device_fleet's
    superadmin-only Control Panel pairing uses (see device_fleet.views.
    device_switch_active_school), just reachable by the branch's own admin
    for a device their group already owns, never new hardware or another
    school's device."""
    user, error = _require_branch_manager(request)
    if error:
        return error
    if not user.school_group_id:
        return Response({"success": False, "message": "Your school has no branches yet."}, status=status.HTTP_400_BAD_REQUEST)

    try:
        target = SchoolTenant.objects.get(pk=branch_id, school_group_id=user.school_group_id)
    except (SchoolTenant.DoesNotExist, ValueError, TypeError):
        return Response({"success": False, "message": "That branch does not belong to your school."}, status=status.HTTP_404_NOT_FOUND)

    device_id = request.data.get("device_id")
    if not device_id:
        return Response({"success": False, "message": "Select which terminal to add this branch to."}, status=status.HTTP_400_BAD_REQUEST)

    try:
        device = _group_devices(user.school_group_id).get(pk=device_id)
    except (Device.DoesNotExist, ValueError, TypeError):
        return Response({"success": False, "message": "That terminal does not belong to your school."}, status=status.HTTP_404_NOT_FOUND)

    if device.tenant_id == target.id:
        return Response(
            {"success": False, "message": f"{_branch_label(target)} is already this terminal's active school."},
            status=status.HTTP_400_BAD_REQUEST,
        )
    if device.paired_tenant_id and device.paired_tenant_id != target.id:
        return Response(
            {
                "success": False,
                "message": f"Terminal {device.device_id} is already paired with {_branch_label(device.paired_tenant)} - remove that pairing first.",
            },
            status=status.HTTP_400_BAD_REQUEST,
        )

    device.paired_tenant = target
    device.save(update_fields=["paired_tenant", "updated_at"])
    DeviceAuditLog.objects.create(
        device=device, actor=user, action="device_paired",
        details=f"Paired with {_branch_label(target)} from the Branches settings panel.",
    )

    return Response({
        "success": True,
        "message": f"{_branch_label(target)} added to terminal {device.device_id}.",
        "terminal": _terminal_payload(device),
    })


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def unpair_branch_terminal(request, branch_id):
    """Undo pair_branch_terminal - only ever clears a pairing that actually
    points at this branch, never anything else a device might be doing."""
    user, error = _require_branch_manager(request)
    if error:
        return error
    if not user.school_group_id:
        return Response({"success": False, "message": "Your school has no branches yet."}, status=status.HTTP_400_BAD_REQUEST)

    try:
        target = SchoolTenant.objects.get(pk=branch_id, school_group_id=user.school_group_id)
    except (SchoolTenant.DoesNotExist, ValueError, TypeError):
        return Response({"success": False, "message": "That branch does not belong to your school."}, status=status.HTTP_404_NOT_FOUND)

    device_id = request.data.get("device_id")
    devices = _group_devices(user.school_group_id).filter(paired_tenant_id=target.id)
    if device_id:
        devices = devices.filter(pk=device_id)
    device = devices.first()
    if not device:
        return Response({"success": False, "message": "That branch isn't paired with any of your terminals."}, status=status.HTTP_400_BAD_REQUEST)

    device.paired_tenant = None
    device.save(update_fields=["paired_tenant", "updated_at"])
    DeviceAuditLog.objects.create(
        device=device, actor=user, action="device_unpaired",
        details=f"Removed {_branch_label(target)} from the Branches settings panel.",
    )

    return Response({"success": True, "message": f"{_branch_label(target)} removed from terminal {device.device_id}."})
