import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('finance', '0041_studentonetimechargeapplication'),
    ]

    operations = [
        migrations.AddField(
            model_name='schoolfee',
            name='subscription',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='invoices', to='finance.studentbillingsubscription'),
        ),
        migrations.AddField(
            model_name='schoolfee',
            name='one_time_charge',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='invoices', to='finance.onetimebillingcharge'),
        ),
        migrations.AddConstraint(
            model_name='schoolfee',
            constraint=models.UniqueConstraint(fields=('subscription', 'due_date'), name='unique_subscription_invoice_per_cycle'),
        ),
    ]
