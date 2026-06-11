from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("users", "0021_user_account_deletion_request"),
    ]

    operations = [
        migrations.AddField(
            model_name="studentprofile",
            name="id_card_generated_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="studentprofile",
            name="id_card_viewed_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
    ]
