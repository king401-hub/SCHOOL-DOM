from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0005_schooltenant_school_type"),
    ]

    operations = [
        migrations.AddField(
            model_name="schooltenant",
            name="motto",
            field=models.CharField(blank=True, default="", max_length=255),
        ),
    ]
