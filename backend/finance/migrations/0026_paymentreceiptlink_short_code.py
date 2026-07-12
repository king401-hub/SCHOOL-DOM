# Generated manually to add PaymentReceiptLink.short_code (compact receipt links)

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('finance', '0025_rename_finance_pay_token_idx_finance_pay_token_da7feb_idx'),
    ]

    operations = [
        migrations.AddField(
            model_name='paymentreceiptlink',
            name='short_code',
            field=models.CharField(blank=True, editable=False, max_length=12, null=True, unique=True),
        ),
        migrations.AddIndex(
            model_name='paymentreceiptlink',
            index=models.Index(fields=['short_code'], name='finance_pay_short_c_5f6a89_idx'),
        ),
    ]
