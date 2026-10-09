import email
import imaplib
from email.policy import default as default_policy
from email.utils import parsedate_to_datetime

from django.conf import settings
from django.core.files.base import ContentFile
from django.core.management.base import BaseCommand
from django.utils import timezone

from mail_inbox.models import InboundMessage, MailAttachment


class Command(BaseCommand):
    help = (
        "Poll every mailbox in settings.MAIL_INBOX_ACCOUNTS over IMAP and import new "
        "(UNSEEN) messages into the mail_inbox tables. Safe to re-run: a message is "
        "matched by (account_label, uid), so nothing is double-imported. Meant to be "
        "wired to a real OS cron entry on the VPS rather than Celery beat, the same "
        "way rfid_attendance.send_weekly_reports documents it - see "
        "[[project-no-celery-in-production]]."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Connect and list what would be imported, without saving anything or marking messages seen.",
        )

    def handle(self, *args, **options):
        dry_run = options["dry_run"]
        for account in settings.MAIL_INBOX_ACCOUNTS:
            if not account.get("address") or not account.get("password"):
                self.stdout.write(
                    self.style.WARNING(f"Skipping '{account.get('label')}': no address/password configured.")
                )
                continue
            self._poll_account(account, dry_run)

    def _poll_account(self, account, dry_run):
        label = account["label"]
        connection = imaplib.IMAP4_SSL(account["imap_host"], account["imap_port"])
        try:
            connection.login(account["address"], account["password"])
            connection.select("INBOX")
            status, data = connection.search(None, "UNSEEN")
            if status != "OK":
                self.stdout.write(self.style.ERROR(f"[{label}] IMAP SEARCH failed: {data}"))
                return

            uids = data[0].split()
            self.stdout.write(f"[{label}] {len(uids)} unseen message(s).")
            for raw_uid in uids:
                uid = raw_uid.decode()
                if InboundMessage.objects.filter(account_label=label, uid=uid).exists():
                    continue

                status, msg_data = connection.fetch(raw_uid, "(RFC822)")
                if status != "OK":
                    continue
                parsed = email.message_from_bytes(msg_data[0][1], policy=default_policy)

                if dry_run:
                    self.stdout.write(f"  would import uid={uid}: {parsed.get('subject', '')}")
                    continue

                message = self._save_message(label, uid, parsed)
                connection.store(raw_uid, "+FLAGS", "\\Seen")
                self.stdout.write(f"  imported uid={uid}: {message.subject}")
        finally:
            try:
                connection.close()
            except imaplib.IMAP4.error:
                pass
            connection.logout()

    def _save_message(self, label, uid, parsed):
        received_at = None
        date_header = parsed.get("date")
        if date_header:
            try:
                received_at = parsedate_to_datetime(date_header)
            except (TypeError, ValueError):
                received_at = None
        if received_at and timezone.is_naive(received_at):
            received_at = timezone.make_aware(received_at)

        body_part = parsed.get_body(preferencelist=("plain",))
        html_part = parsed.get_body(preferencelist=("html",))

        message = InboundMessage.objects.create(
            account_label=label,
            uid=uid,
            message_id=(parsed.get("message-id") or "").strip(),
            from_address=(parsed.get("from") or "").strip(),
            to_address=(parsed.get("to") or "").strip(),
            subject=(parsed.get("subject") or "").strip(),
            body_text=body_part.get_content() if body_part else "",
            body_html=html_part.get_content() if html_part else "",
            received_at=received_at,
        )

        for part in parsed.iter_attachments():
            filename = part.get_filename() or "attachment"
            content = part.get_content()
            if isinstance(content, str):
                content = content.encode("utf-8")
            attachment = MailAttachment(
                message=message, filename=filename, content_type=part.get_content_type()
            )
            attachment.file.save(filename, ContentFile(content), save=True)

        return message
