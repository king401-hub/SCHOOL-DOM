from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('device_fleet', '0004_apprelease_device_app_version_code_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='provisioningkey',
            name='subscription_tier',
            field=models.CharField(choices=[('basic', 'Basic'), ('premium', 'Premium')], default='premium', max_length=10),
        ),
        migrations.AddField(
            model_name='device',
            name='pending_subscription_tier',
            field=models.CharField(blank=True, choices=[('basic', 'Basic'), ('premium', 'Premium')], default='', max_length=10),
        ),
    ]
