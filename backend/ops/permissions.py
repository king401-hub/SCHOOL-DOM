"""Permission resolution for Ops Console roles. Spec section 4, "Resolution order":
roles table holds default permissions per role; member_permissions table holds
per-user overrides. Effective permission = override ?? role default."""
from .models import MemberPermission, OpsUser, PermissionAuditLog, RolePermission


def has_permission(ops_user, module):
    if ops_user is None or not ops_user.is_active:
        return False
    if ops_user.role == OpsUser.CEO:
        # "Full, non-editable access to every module ... cannot be revoked,
        # including by CEO themself" - spec 3.1. Enforced here, not just seeded.
        return True
    override = MemberPermission.objects.filter(ops_user=ops_user, module=module).first()
    if override is not None:
        return override.granted
    role_default = RolePermission.objects.filter(role=ops_user.role, module=module).first()
    return bool(role_default and role_default.granted)


def record_permission_change(actor, *, change_type, module, old_value, new_value, role="", target_ops_user=None):
    return PermissionAuditLog.objects.create(
        actor=actor,
        change_type=change_type,
        role=role,
        target_ops_user=target_ops_user,
        module=module,
        old_value=old_value,
        new_value=new_value,
    )


def set_role_default(actor, role, module, granted):
    try:
        obj = RolePermission.objects.get(role=role, module=module)
        old_value = obj.granted
        changed = old_value != granted
        if changed:
            obj.granted = granted
            obj.save(update_fields=["granted"])
    except RolePermission.DoesNotExist:
        obj = RolePermission.objects.create(role=role, module=module, granted=granted)
        old_value = False
        changed = True

    if changed:
        record_permission_change(
            actor, change_type=PermissionAuditLog.ROLE_DEFAULT_CHANGED,
            module=module, old_value=old_value, new_value=granted, role=role,
        )
    return obj


def set_member_override(actor, ops_user, module, granted):
    existing = MemberPermission.objects.filter(ops_user=ops_user, module=module).first()
    old_value = existing.granted if existing else None
    obj, _ = MemberPermission.objects.update_or_create(
        ops_user=ops_user, module=module, defaults={"granted": granted},
    )
    record_permission_change(
        actor, change_type=PermissionAuditLog.MEMBER_OVERRIDE_SET,
        module=module, old_value=old_value, new_value=granted, target_ops_user=ops_user,
    )
    return obj


def clear_member_override(actor, ops_user, module):
    deleted, _ = MemberPermission.objects.filter(ops_user=ops_user, module=module).delete()
    if deleted:
        record_permission_change(
            actor, change_type=PermissionAuditLog.MEMBER_OVERRIDE_CLEARED,
            module=module, old_value=True, new_value=None, target_ops_user=ops_user,
        )
    return deleted
