from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0006_schooltenant_motto"),
    ]

    operations = [
        migrations.AddField(
            model_name="schooltenant",
            name="staff_rules",
            field=models.TextField(blank=True, default=""),
        ),
        migrations.AddField(
            model_name="schooltenant",
            name="student_rules",
            field=models.TextField(blank=True, default=""),
        ),
    ]
