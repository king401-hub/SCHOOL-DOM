"""Branch-aware JWT authentication.

Lets one admin login switch its *active* SchoolTenant between branches of
the same school (see users.branch_views) without re-authenticating. The
access token's "active_tenant" claim is a hint, never a grant: this class
re-verifies on every single request - never trusting the claim itself -
that the claimed tenant is still a real branch of the authenticated user's
own school_group, and overrides request.user.tenant IN-MEMORY ONLY (never
saved to the database). Every existing view in this codebase scopes its
queries by reading request.user.tenant fresh on each request, so this one
choke point is enough to make all of them resolve to whichever branch is
active - no per-view changes needed, and nothing to miss.

Fails CLOSED: a claim that no longer checks out (the branch was removed
from the group, or the token was tampered with) raises AuthenticationFailed
rather than silently falling back to the user's home tenant - the admin's
session would otherwise keep working, scoped to a *different* branch than
the one their screen still claims to be showing.
"""
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework_simplejwt.exceptions import AuthenticationFailed


class BranchAwareJWTAuthentication(JWTAuthentication):
    def get_user(self, validated_token):
        user = super().get_user(validated_token)

        active_tenant_id = validated_token.get("active_tenant")
        if not active_tenant_id:
            return user

        # Nothing to switch between without a home tenant/group - e.g. a
        # proprietor (school_superadmin) token never carries this claim in
        # the first place, but this guards against any token that does.
        if not user.tenant_id or not user.school_group_id:
            return user

        if str(user.tenant_id) == str(active_tenant_id):
            return user

        from core.models import SchoolTenant

        try:
            target = SchoolTenant.objects.get(pk=active_tenant_id)
        except (SchoolTenant.DoesNotExist, ValueError, TypeError):
            raise AuthenticationFailed("That branch is no longer available. Please sign in again.")

        if target.school_group_id != user.school_group_id:
            raise AuthenticationFailed("That branch is no longer available. Please sign in again.")

        user.tenant = target
        return user
