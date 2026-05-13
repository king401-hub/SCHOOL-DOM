from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("quizzes", "0005_daily_personal_quiz"),
    ]

    operations = [
        migrations.AddField(
            model_name="personalquizfolder",
            name="subject_code",
            field=models.CharField(blank=True, max_length=40),
        ),
        migrations.AddField(
            model_name="personalquizfolder",
            name="subject_name",
            field=models.CharField(blank=True, max_length=120),
        ),
    ]
