from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("users", "0009_studenttestimonial"),
    ]

    operations = [
        migrations.AddField(
            model_name="studentprofile",
            name="second_guardian_email",
            field=models.EmailField(blank=True, max_length=254),
        ),
        migrations.AddField(
            model_name="studentprofile",
            name="second_guardian_name",
            field=models.CharField(blank=True, max_length=255),
        ),
        migrations.AddField(
            model_name="studentprofile",
            name="second_guardian_phone",
            field=models.CharField(blank=True, max_length=17),
        ),
        migrations.AddField(
            model_name="studentprofile",
            name="second_guardian_relation",
            field=models.CharField(blank=True, max_length=100),
        ),
    ]
