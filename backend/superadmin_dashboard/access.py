from functools import wraps

from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied


def is_super_admin(user):
    if not user or not user.is_authenticated:
        return False

    if user.is_superuser:
        return True

    role = getattr(user, "role", None)
    if isinstance(role, str) and role.lower() in {"super_admin", "superadmin", "platform_admin"}:
        return True

    profile = getattr(user, "profile", None)
    profile_role = getattr(profile, "role", None)
    if isinstance(profile_role, str) and profile_role.lower() in {"super_admin", "superadmin", "platform_admin"}:
        return True

    return user.groups.filter(name__in=["Super Admin", "SuperAdmin", "Platform Admin"]).exists()


def function_group_name(function):
    return f"Super Admin: {function.replace('_', ' ').title()}"


def has_super_admin_function(user, function):
    if not is_super_admin(user):
        return False
    if user.is_superuser:
        return True
    if not function:
        return True
    return user.groups.filter(name=function_group_name(function)).exists()


def super_admin_required(view_func=None, function=None):
    def decorator(func):
        @login_required(login_url="/login/")
        @wraps(func)
        def wrapped(request, *args, **kwargs):
            if not has_super_admin_function(request.user, function):
                raise PermissionDenied("Super Admin access is required.")
            return func(request, *args, **kwargs)

        return wrapped

    if view_func is None:
        return decorator

    @login_required(login_url="/login/")
    @wraps(view_func)
    def wrapped(request, *args, **kwargs):
        if not has_super_admin_function(request.user, function):
            raise PermissionDenied("Super Admin access is required.")
        return view_func(request, *args, **kwargs)

    return wrapped
