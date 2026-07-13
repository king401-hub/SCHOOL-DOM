from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('users', '0027_rename_users_kidsm_school__is_ac_idx_users_kidsm_school__c49958_idx'),
    ]

    operations = [
        migrations.AddField(
            model_name='user',
            name='password_reset_challenge',
            field=models.CharField(blank=True, max_length=64, null=True),
        ),
        migrations.AddField(
            model_name='user',
            name='password_reset_otp_attempts',
            field=models.PositiveIntegerField(default=0),
        ),
    ]
