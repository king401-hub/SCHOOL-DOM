from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("exams", "0002_cbt_exam_questions_and_grading"),
    ]

    operations = [
        migrations.AddField(
            model_name="examattempt",
            name="auto_submitted",
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name="examattempt",
            name="auto_submit_reason",
            field=models.CharField(blank=True, default="", max_length=80),
        ),
        migrations.AddField(
            model_name="examattempt",
            name="auto_submit_reason_display",
            field=models.CharField(blank=True, default="", max_length=160),
        ),
        migrations.AddField(
            model_name="examattempt",
            name="auto_submit_details",
            field=models.TextField(blank=True, default=""),
        ),
        migrations.AddField(
            model_name="examattempt",
            name="auto_submit_warning_history",
            field=models.JSONField(blank=True, default=list),
        ),
        migrations.AddField(
            model_name="examattempt",
            name="auto_submit_activity_logs",
            field=models.JSONField(blank=True, default=list),
        ),
    ]
