import uuid


class InvalidUUIDSessionMiddleware:
    """
    Clears stale auth session data when AUTH_USER_MODEL uses UUID primary keys.
    This avoids request crashes caused by old integer session user IDs.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        user_id = request.session.get("_auth_user_id")
        if user_id:
            try:
                uuid.UUID(str(user_id))
            except (ValueError, TypeError, AttributeError):
                request.session.pop("_auth_user_id", None)
                request.session.pop("_auth_user_backend", None)
                request.session.pop("_auth_user_hash", None)
                request.session.modified = True

        return self.get_response(request)

