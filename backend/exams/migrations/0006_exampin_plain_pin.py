from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("exams", "0005_question_groups_and_attempt_order"),
    ]

    operations = [
        migrations.AddField(
            model_name="exampin",
            name="plain_pin",
            field=models.CharField(blank=True, default="", max_length=16),
        ),
    ]
