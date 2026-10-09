from io import BytesIO
from unittest.mock import MagicMock, patch

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from ops.models import MODULE_SUPPORT_MAIL, OpsUser, RolePermission

from .management.commands.poll_mail_accounts import Command as PollCommand
from .models import InboundMessage

User = get_user_model()

RAW_EMAIL = (
    b"From: Parent <parent@example.com>\r\n"
    b"To: Support <support@schooldom.com>\r\n"
    b"Subject: Can't log in\r\n"
    b"Date: Mon, 01 Jan 2024 10:00:00 +0000\r\n"
    b"Message-ID: <abc123@example.com>\r\n"
    b"Content-Type: text/plain\r\n"
    b"\r\n"
    b"My child's account is locked out.\r\n"
)

TEST_ACCOUNT = {
    "label": "support",
    "address": "support@schooldom.com",
    "password": "irrelevant",
    "imap_host": "imap.example.com",
    "imap_port": 993,
}


def _fake_imap_connection(uids=(b"1",)):
    """A MagicMock standing in for imaplib.IMAP4_SSL, wired up so the poller's
    search -> fetch -> store sequence sees exactly one UNSEEN message."""
    connection = MagicMock()
    connection.search.return_value = ("OK", [b" ".join(uids)])
    connection.fetch.return_value = ("OK", [(None, RAW_EMAIL)])
    return connection


@override_settings(MAIL_INBOX_ACCOUNTS=[TEST_ACCOUNT])
class PollMailAccountsTests(TestCase):
    @patch("mail_inbox.management.commands.poll_mail_accounts.imaplib.IMAP4_SSL")
    def test_imports_one_unseen_message(self, imap_ssl):
        imap_ssl.return_value = _fake_imap_connection()

        PollCommand().handle(dry_run=False)

        message = InboundMessage.objects.get()
        self.assertEqual(message.account_label, "support")
        self.assertEqual(message.uid, "1")
        self.assertEqual(message.subject, "Can't log in")
        self.assertIn("locked out", message.body_text)

    @patch("mail_inbox.management.commands.poll_mail_accounts.imaplib.IMAP4_SSL")
    def test_rerunning_does_not_duplicate(self, imap_ssl):
        imap_ssl.return_value = _fake_imap_connection()
        PollCommand().handle(dry_run=False)

        imap_ssl.return_value = _fake_imap_connection()
        PollCommand().handle(dry_run=False)

        self.assertEqual(InboundMessage.objects.count(), 1)

    @patch("mail_inbox.management.commands.poll_mail_accounts.imaplib.IMAP4_SSL")
    def test_dry_run_saves_nothing(self, imap_ssl):
        imap_ssl.return_value = _fake_imap_connection()

        PollCommand().handle(dry_run=True)

        self.assertEqual(InboundMessage.objects.count(), 0)

    @override_settings(MAIL_INBOX_ACCOUNTS=[{**TEST_ACCOUNT, "address": "", "password": ""}])
    @patch("mail_inbox.management.commands.poll_mail_accounts.imaplib.IMAP4_SSL")
    def test_skips_unconfigured_account(self, imap_ssl):
        PollCommand().handle(dry_run=False)

        imap_ssl.assert_not_called()


class MailInboxApiPermissionTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.message = InboundMessage.objects.create(
            account_label="support", uid="1", from_address="parent@example.com", subject="Help",
        )

    def test_user_without_ops_profile_is_forbidden(self):
        user = User.objects.create_user(email="plain@schooldom.com", password="pw")
        self.client.force_authenticate(user)

        response = self.client.get("/api/mail-inbox/messages/")

        self.assertEqual(response.status_code, 403)

    def test_ops_user_without_module_granted_is_forbidden(self):
        user = User.objects.create_user(email="marketer@schooldom.com", password="pw")
        OpsUser.objects.create(user=user, role=OpsUser.MARKETER)
        self.client.force_authenticate(user)

        response = self.client.get("/api/mail-inbox/messages/")

        self.assertEqual(response.status_code, 403)

    def test_ops_user_with_module_granted_can_list(self):
        user = User.objects.create_user(email="growth@schooldom.com", password="pw")
        OpsUser.objects.create(user=user, role=OpsUser.GROWTH_MANAGER)
        RolePermission.objects.create(role=OpsUser.GROWTH_MANAGER, module=MODULE_SUPPORT_MAIL, granted=True)
        self.client.force_authenticate(user)

        response = self.client.get("/api/mail-inbox/messages/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["results"][0]["id"], self.message.id)

    def test_ceo_always_has_access(self):
        user = User.objects.create_user(email="ceo@schooldom.com", password="pw")
        OpsUser.objects.create(user=user, role=OpsUser.CEO)
        self.client.force_authenticate(user)

        response = self.client.get("/api/mail-inbox/messages/")

        self.assertEqual(response.status_code, 200)
