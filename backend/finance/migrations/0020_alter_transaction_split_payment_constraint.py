from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('finance', '0019_feeallocation_adminwallet_split_code_and_more'),
    ]

    operations = [
        migrations.RemoveConstraint(
            model_name='transaction',
            name='transaction_requires_single_wallet',
        ),
        migrations.AddConstraint(
            model_name='transaction',
            constraint=models.CheckConstraint(
                check=(
                    models.Q(wallet__isnull=False, admin_wallet__isnull=True)
                    | models.Q(wallet__isnull=True, admin_wallet__isnull=False)
                    | models.Q(wallet__isnull=True, admin_wallet__isnull=True, tx_type='split_payment')
                ),
                name='transaction_requires_single_wallet',
            ),
        ),
    ]
