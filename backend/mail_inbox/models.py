from django.db import models


class InboundMessage(models.Model):
    """One email pulled in by poll_mail_accounts from a SchoolDom company
    mailbox (support@, and others configured in settings.MAIL_INBOX_ACCOUNTS).
    Platform-level, not tenant-scoped - see MODULE_SUPPORT_MAIL in ops/models.py
    for who may read these."""

    account_label = models.CharField(max_length=50)
    # The IMAP UID is only unique within one mailbox, not globally - paired
    # with account_label below so re-running the poller never double-imports.
    uid = models.CharField(max_length=50)
    message_id = models.CharField(max_length=255, blank=True)
    from_address = models.CharField(max_length=255)
    to_address = models.CharField(max_length=255, blank=True)
    subject = models.CharField(max_length=500, blank=True)
    body_text = models.TextField(blank=True)
    body_html = models.TextField(blank=True)
    received_at = models.DateTimeField(null=True, blank=True)
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-received_at", "-created_at"]
        constraints = [
            models.UniqueConstraint(fields=["account_label", "uid"], name="unique_account_uid"),
        ]

    def __str__(self):
        return f"[{self.account_label}] {self.subject or '(no subject)'}"


def attachment_upload_to(instance, filename):
    # instance.message_id here is Django's auto FK column accessor (the
    # related InboundMessage's pk), not InboundMessage.message_id (the email
    # header) - always present and filesystem-safe, unlike the header.
    return f"mail_inbox/{instance.message.account_label}/{instance.message_id}/{filename}"


class MailAttachment(models.Model):
    message = models.ForeignKey(InboundMessage, on_delete=models.CASCADE, related_name="attachments")
    filename = models.CharField(max_length=255)
    file = models.FileField(upload_to=attachment_upload_to)
    content_type = models.CharField(max_length=100, blank=True)

    def __str__(self):
        return self.filename
