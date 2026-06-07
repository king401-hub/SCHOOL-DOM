from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0004_auditlog_user_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="schooltenant",
            name="school_type",
            field=models.CharField(
                choices=[("k12", "K-12 school"), ("non_k12", "Non K-12 school")],
                default="k12",
                max_length=20,
            ),
        ),
    ]
