from django.db import migrations, models


def mark_existing_payments_as_not_pending(apps, schema_editor):
    """Every payment that predates receipt tracking is marked 'skipped', not
    'pending'.

    The retry sweep picks up anything left pending, and these rows have already
    been through the old send-once-and-forget path - leaving them pending would
    re-text parents about payments they were told about days ago. We cannot know
    which ones actually delivered, and a blank status is far cheaper than a
    duplicate receipt.
    """
    BankPayment = apps.get_model("finance", "BankPayment")
    BankPayment.objects.all().update(
        receipt_sms_status="skipped",
        receipt_email_status="skipped",
    )


class Migration(migrations.Migration):

    dependencies = [
        ("finance", "0033_bill_accent_color"),
    ]

    operations = [
        migrations.AddField(
            model_name="bankpayment",
            name="receipt_sms_status",
            field=models.CharField(
                choices=[("pending", "Pending"), ("sent", "Sent"), ("failed", "Failed"), ("skipped", "Skipped")],
                default="pending",
                max_length=12,
            ),
        ),
        migrations.AddField(
            model_name="bankpayment",
            name="receipt_email_status",
            field=models.CharField(
                choices=[("pending", "Pending"), ("sent", "Sent"), ("failed", "Failed"), ("skipped", "Skipped")],
                default="pending",
                max_length=12,
            ),
        ),
        migrations.AddField(
            model_name="bankpayment",
            name="receipt_notified_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="bankpayment",
            name="receipt_notification_attempts",
            field=models.PositiveIntegerField(default=0),
        ),
        migrations.AddField(
            model_name="bankpayment",
            name="receipt_notification_error",
            field=models.TextField(blank=True),
        ),
        migrations.AddField(
            model_name="bankpayment",
            name="receipt_link_url",
            field=models.CharField(blank=True, max_length=300),
        ),
        migrations.AddIndex(
            model_name="bankpayment",
            index=models.Index(
                fields=["receipt_sms_status", "receipt_email_status"],
                name="finance_ban_receipt_b914c8_idx",
            ),
        ),
        migrations.RunPython(mark_existing_payments_as_not_pending, migrations.RunPython.noop),
    ]
