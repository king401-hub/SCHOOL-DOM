import uuid

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('finance', '0040_studentbillingsubscription'),
        ('users', '0034_user_phone_otp_attempts_user_phone_otp_challenge_and_more'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='StudentOneTimeChargeApplication',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('applied_at', models.DateTimeField(auto_now_add=True)),
                ('charge', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='applications', to='finance.onetimebillingcharge')),
                ('student', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='one_time_charge_applications', to='users.studentprofile')),
                ('school_fee', models.OneToOneField(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='one_time_charge_application', to='finance.schoolfee')),
                ('applied_by', models.ForeignKey(blank=True, help_text="Null for the system's own auto-apply-on-enrollment; set for an admin's manual bulk-apply.", null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='applied_one_time_charges', to=settings.AUTH_USER_MODEL)),
            ],
        ),
        migrations.AddConstraint(
            model_name='studentonetimechargeapplication',
            constraint=models.UniqueConstraint(fields=('charge', 'student'), name='unique_one_time_charge_application'),
        ),
    ]
