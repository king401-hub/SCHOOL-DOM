from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("quizzes", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="question",
            name="explanation",
            field=models.TextField(blank=True),
        ),
    ]
