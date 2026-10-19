import django
from django.db import migrations, models

# Django 5.1 renamed CheckConstraint's check= kwarg to condition= - this
# migration must apply cleanly under whichever Django is actually running
# it (production's is older than dev's), not just whichever generated it.
_CHECK_CONSTRAINT_KWARG = "condition" if django.VERSION >= (5, 1) else "check"


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
            constraint=models.CheckConstraint(**{
                _CHECK_CONSTRAINT_KWARG: (
                    models.Q(wallet__isnull=False, admin_wallet__isnull=True)
                    | models.Q(wallet__isnull=True, admin_wallet__isnull=False)
                    | models.Q(wallet__isnull=True, admin_wallet__isnull=True, tx_type='split_payment')
                ),
            }, name='transaction_requires_single_wallet'),
        ),
    ]
