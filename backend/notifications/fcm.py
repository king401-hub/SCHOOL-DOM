"""Firebase Cloud Messaging (Android app push) dispatch.

Sends a real OS-level push to every registered Android device of a user -
separate from push.py's browser Web Push (VAPID), which only reaches the
React dashboard's service worker, never the native Flutter app. Silently
no-ops if the service account key isn't configured, matching push.py's
VAPID no-op convention, so this never blocks a request or breaks local dev.
"""
import logging

from django.conf import settings

logger = logging.getLogger(__name__)

_fcm_app = None
_fcm_init_attempted = False


def _get_fcm_app():
    global _fcm_app, _fcm_init_attempted
    if _fcm_app is not None or _fcm_init_attempted:
        return _fcm_app
    _fcm_init_attempted = True
    if not settings.FCM_SERVICE_ACCOUNT_PATH:
        return None
    try:
        import firebase_admin
        from firebase_admin import credentials

        cred = credentials.Certificate(settings.FCM_SERVICE_ACCOUNT_PATH)
        _fcm_app = firebase_admin.initialize_app(cred, name="fcm")
    except Exception:
        logger.exception("Could not initialize Firebase Admin SDK - FCM push disabled.")
        _fcm_app = None
    return _fcm_app


def _user_allows_push(user):
    from .models import NotificationPreference

    preference = NotificationPreference.objects.filter(user=user).only("disable_all", "allow_push").first()
    if not preference:
        return True
    return not preference.disable_all and preference.allow_push


def _fcm_tokens_for_user(user):
    return [
        item["token"]
        for item in (getattr(user, "device_tokens", None) or [])
        if isinstance(item, dict) and item.get("token") and item.get("provider") == "fcm"
    ]


def send_fcm_to_user(user, title, body, url=None):
    app = _get_fcm_app()
    if not app or not user or not _user_allows_push(user):
        return
    tokens = _fcm_tokens_for_user(user)
    if not tokens:
        return

    from firebase_admin import messaging

    message = messaging.MulticastMessage(
        notification=messaging.Notification(title=title or "SchoolDom", body=body or ""),
        data={"url": url or "/dashboard"},
        tokens=tokens,
    )
    try:
        response = messaging.send_each_for_multicast(message, app=app)
    except Exception:
        logger.exception("Unexpected error sending FCM push.")
        return

    if response.failure_count:
        stale = [
            token
            for token, result in zip(tokens, response.responses)
            if not result.success and isinstance(result.exception, messaging.UnregisteredError)
        ]
        if stale:
            _drop_stale_tokens(user, stale)


def _drop_stale_tokens(user, stale_tokens):
    current = list(user.device_tokens or [])
    remaining = [item for item in current if item.get("token") not in stale_tokens]
    if len(remaining) != len(current):
        user.device_tokens = remaining
        user.save(update_fields=["device_tokens"])


def fcm_for_notifications(notifications):
    """Call this right after Notification.objects.bulk_create(...), mirroring
    push.py's push_for_notifications - bulk_create bypasses post_save signals
    entirely, so the automatic dispatch in notifications/signals.py never
    fires for these rows."""
    for notification in notifications:
        send_fcm_to_user(notification.user, notification.title, notification.message, url=notification.deep_link)
