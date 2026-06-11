from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("users", "0020_user_admin_title"),
    ]

    operations = [
        migrations.AddField(
            model_name="user",
            name="account_deletion_requested_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="user",
            name="account_deletion_scheduled_for",
            field=models.DateTimeField(blank=True, null=True),
        ),
    ]
