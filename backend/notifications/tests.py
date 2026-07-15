from unittest.mock import MagicMock, patch

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from core.models import SchoolTenant
from notifications.models import Notification, NotificationPreference, PushSubscription
from notifications.push import push_for_notifications, send_web_push_to_user

User = get_user_model()

TEST_VAPID_PUBLIC = "BItest-public-key-not-real-0123456789abcdefghijklmno"
TEST_VAPID_PRIVATE = "test-private-key-not-real-0123456789"


def _make_school_and_user(email="teacher@push.test"):
    tenant = SchoolTenant.objects.create(name="Push Test School", schema_name=email.split("@")[0].replace(".", "_"))
    user = User.objects.create_user(
        email=email, password="TeacherPass123", first_name="Push", last_name="Tester",
        role="teacher", tenant=tenant, is_active=True, is_verified=True,
    )
    return tenant, user


@override_settings(VAPID_PUBLIC_KEY=TEST_VAPID_PUBLIC, VAPID_PRIVATE_KEY=TEST_VAPID_PRIVATE)
class PushSubscriptionEndpointTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.tenant, self.user = _make_school_and_user()
        self.other_tenant, self.other_user = _make_school_and_user(email="teacher2@push.test")
        self.client.force_authenticate(user=self.user)

    def test_vapid_public_key_endpoint_returns_configured_key(self):
        response = self.client.get("/api/app/push/vapid-public-key/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["public_key"], TEST_VAPID_PUBLIC)

    def test_subscribe_creates_a_subscription(self):
        response = self.client.post(
            "/api/app/push/subscribe/",
            data={
                "endpoint": "https://fcm.googleapis.com/fcm/send/abc123",
                "keys": {"p256dh": "p256dh-value", "auth": "auth-value"},
                "user_agent": "TestBrowser/1.0",
            },
            format="json",
        )
        self.assertEqual(response.status_code, 201, response.data)
        subscription = PushSubscription.objects.get(endpoint="https://fcm.googleapis.com/fcm/send/abc123")
        self.assertEqual(subscription.user, self.user)
        self.assertEqual(subscription.tenant, self.tenant)

    def test_subscribe_requires_endpoint_and_keys(self):
        response = self.client.post("/api/app/push/subscribe/", data={"endpoint": ""}, format="json")
        self.assertEqual(response.status_code, 400)
        self.assertFalse(PushSubscription.objects.exists())

    def test_resubscribing_same_endpoint_updates_rather_than_duplicates(self):
        endpoint = "https://fcm.googleapis.com/fcm/send/same-endpoint"
        payload = {"endpoint": endpoint, "keys": {"p256dh": "old-p256dh", "auth": "old-auth"}}
        self.client.post("/api/app/push/subscribe/", data=payload, format="json")
        payload["keys"] = {"p256dh": "new-p256dh", "auth": "new-auth"}
        self.client.post("/api/app/push/subscribe/", data=payload, format="json")

        self.assertEqual(PushSubscription.objects.filter(endpoint=endpoint).count(), 1)
        self.assertEqual(PushSubscription.objects.get(endpoint=endpoint).p256dh, "new-p256dh")

    def test_unsubscribe_removes_own_subscription(self):
        subscription = PushSubscription.objects.create(
            tenant=self.tenant, user=self.user, endpoint="https://push.test/endpoint-a",
            p256dh="p", auth="a",
        )
        response = self.client.post("/api/app/push/unsubscribe/", data={"endpoint": subscription.endpoint}, format="json")
        self.assertEqual(response.status_code, 200)
        self.assertFalse(PushSubscription.objects.filter(id=subscription.id).exists())

    def test_unsubscribe_cannot_remove_another_users_subscription(self):
        subscription = PushSubscription.objects.create(
            tenant=self.other_tenant, user=self.other_user, endpoint="https://push.test/endpoint-b",
            p256dh="p", auth="a",
        )
        response = self.client.post("/api/app/push/unsubscribe/", data={"endpoint": subscription.endpoint}, format="json")
        self.assertEqual(response.status_code, 200)
        self.assertTrue(PushSubscription.objects.filter(id=subscription.id).exists())


@override_settings(VAPID_PUBLIC_KEY=TEST_VAPID_PUBLIC, VAPID_PRIVATE_KEY=TEST_VAPID_PRIVATE)
class WebPushDispatchTests(TestCase):
    def setUp(self):
        self.tenant, self.user = _make_school_and_user(email="dispatch@push.test")
        self.subscription = PushSubscription.objects.create(
            tenant=self.tenant, user=self.user, endpoint="https://push.test/dispatch-endpoint",
            p256dh="p", auth="a",
        )

    @patch("pywebpush.webpush")
    def test_send_web_push_to_user_calls_webpush_with_subscription_and_vapid(self, mock_webpush):
        send_web_push_to_user(self.user, "Title", "Body", url="/messages")

        mock_webpush.assert_called_once()
        _, kwargs = mock_webpush.call_args
        self.assertEqual(kwargs["subscription_info"]["endpoint"], self.subscription.endpoint)
        self.assertEqual(kwargs["subscription_info"]["keys"], {"p256dh": "p", "auth": "a"})
        self.assertEqual(kwargs["vapid_private_key"], TEST_VAPID_PRIVATE)
        self.assertIn("Title", kwargs["data"])

    @patch("pywebpush.webpush")
    def test_no_op_when_vapid_not_configured(self, mock_webpush):
        with override_settings(VAPID_PUBLIC_KEY="", VAPID_PRIVATE_KEY=""):
            send_web_push_to_user(self.user, "Title", "Body")
        mock_webpush.assert_not_called()

    @patch("pywebpush.webpush")
    def test_expired_subscription_is_deleted_on_410(self, mock_webpush):
        from pywebpush import WebPushException

        response = MagicMock(status_code=410)
        mock_webpush.side_effect = WebPushException("Gone", response=response)

        send_web_push_to_user(self.user, "Title", "Body")

        self.assertFalse(PushSubscription.objects.filter(id=self.subscription.id).exists())

    @patch("pywebpush.webpush")
    def test_non_expiry_failure_keeps_subscription(self, mock_webpush):
        from pywebpush import WebPushException

        response = MagicMock(status_code=500)
        mock_webpush.side_effect = WebPushException("Server error", response=response)

        send_web_push_to_user(self.user, "Title", "Body")

        self.assertTrue(PushSubscription.objects.filter(id=self.subscription.id).exists())

    @patch("pywebpush.webpush")
    def test_respects_disable_all_preference(self, mock_webpush):
        NotificationPreference.objects.create(tenant=self.tenant, user=self.user, disable_all=True)
        send_web_push_to_user(self.user, "Title", "Body")
        mock_webpush.assert_not_called()

    @patch("pywebpush.webpush")
    def test_respects_allow_push_false_preference(self, mock_webpush):
        NotificationPreference.objects.create(tenant=self.tenant, user=self.user, allow_push=False)
        send_web_push_to_user(self.user, "Title", "Body")
        mock_webpush.assert_not_called()

    @patch("pywebpush.webpush")
    def test_creating_a_single_notification_triggers_push_via_signal(self, mock_webpush):
        Notification.objects.create(
            tenant=self.tenant, user=self.user, title="New grade", message="Your score was posted.",
            notification_type="info", priority=2, channel="in_app",
        )
        mock_webpush.assert_called_once()

    @patch("pywebpush.webpush")
    def test_bulk_created_notifications_need_explicit_push_for_notifications_call(self, mock_webpush):
        # bulk_create() bypasses post_save signals entirely - this proves the
        # gap the signal alone can't cover, and that push_for_notifications()
        # fills it when called explicitly (see the 6 bulk_create call sites
        # across app_views.py / quizzes / finance / exams).
        notifications = Notification.objects.bulk_create([
            Notification(
                tenant=self.tenant, user=self.user, title="Bulk", message="Bulk message",
                notification_type="info", priority=2, channel="in_app",
            )
        ])
        mock_webpush.assert_not_called()

        push_for_notifications(notifications)
        mock_webpush.assert_called_once()
