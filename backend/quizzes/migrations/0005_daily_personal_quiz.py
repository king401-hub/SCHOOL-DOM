from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("quizzes", "0004_personal_quiz_folder"),
    ]

    operations = [
        migrations.AddField(
            model_name="personalquizattempt",
            name="auto_submitted",
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name="personalquizattempt",
            name="daily_date",
            field=models.DateField(blank=True, null=True),
        ),
        migrations.AddConstraint(
            model_name="personalquizattempt",
            constraint=models.UniqueConstraint(
                fields=("student", "subject", "daily_date"),
                name="unique_personal_daily_quiz_per_subject",
            ),
        ),
    ]
