# Generated manually for the CBT question builder and auto-grading workflow.

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("exams", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="exam",
            name="instructions",
            field=models.TextField(blank=True),
        ),
        migrations.AddField(
            model_name="exam",
            name="questions",
            field=models.ManyToManyField(blank=True, related_name="exams", to="exams.question"),
        ),
        migrations.AddField(
            model_name="examattempt",
            name="graded_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="examattempt",
            name="percentage",
            field=models.FloatField(default=0),
        ),
        migrations.AddField(
            model_name="examattempt",
            name="score",
            field=models.FloatField(default=0),
        ),
        migrations.AddField(
            model_name="examattempt",
            name="total_points",
            field=models.FloatField(default=0),
        ),
    ]
