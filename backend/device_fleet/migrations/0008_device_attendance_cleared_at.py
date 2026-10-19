from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('device_fleet', '0007_subscription_tier'),
    ]

    operations = [
        migrations.AddField(
            model_name='device',
            name='attendance_cleared_at',
            field=models.DateTimeField(blank=True, null=True),
        ),
    ]
