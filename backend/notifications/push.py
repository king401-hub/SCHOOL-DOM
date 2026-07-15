"""Web Push (browser notification) dispatch.

Sends a native OS notification to every browser a user has subscribed from,
using the Push API + VAPID. Silently no-ops if VAPID keys aren't configured
(local dev without a generated keypair) so this never blocks a request.
"""
import json
import logging

from django.conf import settings

logger = logging.getLogger(__name__)


def _vapid_configured():
    return bool(settings.VAPID_PUBLIC_KEY and settings.VAPID_PRIVATE_KEY)


def _user_allows_push(user):
    from .models import NotificationPreference

    preference = NotificationPreference.objects.filter(user=user).only("disable_all", "allow_push").first()
    if not preference:
        return True
    return not preference.disable_all and preference.allow_push


def _send_to_subscription(subscription, payload):
    from pywebpush import WebPushException, webpush

    try:
        webpush(
            subscription_info={
                "endpoint": subscription.endpoint,
                "keys": {"p256dh": subscription.p256dh, "auth": subscription.auth},
            },
            data=json.dumps(payload),
            vapid_private_key=settings.VAPID_PRIVATE_KEY,
            vapid_claims={"sub": settings.VAPID_CLAIM_EMAIL},
        )
    except WebPushException as exc:
        status_code = getattr(exc.response, "status_code", None)
        if status_code in (404, 410):
            # Subscription expired or was revoked by the browser - stop trying it.
            subscription.delete()
        else:
            logger.warning("Web push delivery failed (status=%s): %s", status_code, exc)
    except Exception:  # pragma: no cover - defensive: never let push break the caller
        logger.exception("Unexpected error sending web push.")


def send_web_push_to_user(user, title, body, url=None):
    if not _vapid_configured() or not user or not _user_allows_push(user):
        return

    from .models import PushSubscription

    subscriptions = list(PushSubscription.objects.filter(user=user))
    if not subscriptions:
        return

    payload = {"title": title or "SchoolDom", "body": body or "", "url": url or "/dashboard"}
    for subscription in subscriptions:
        _send_to_subscription(subscription, payload)


def push_for_notifications(notifications):
    """Call this right after Notification.objects.bulk_create(...) - bulk_create
    bypasses post_save signals entirely, so the automatic dispatch in
    notifications/signals.py never fires for these rows."""
    if not _vapid_configured():
        return
    for notification in notifications:
        send_web_push_to_user(
            notification.user,
            notification.title,
            notification.message,
            url=notification.deep_link,
        )
