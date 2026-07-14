from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('users', '0028_user_password_reset_otp_fields'),
    ]

    operations = [
        migrations.AddField(
            model_name='kidsmonitorsubscription',
            name='expires_at',
            field=models.DateTimeField(blank=True, null=True),
        ),
    ]
