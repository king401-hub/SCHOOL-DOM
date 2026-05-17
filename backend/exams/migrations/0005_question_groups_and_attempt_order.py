from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("exams", "0004_exam_pin_management"),
        ("tenants", "0001_initial"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="QuestionGroup",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("title", models.CharField(blank=True, default="", max_length=200)),
                ("group_type", models.CharField(choices=[("comprehension", "Comprehension"), ("register", "Register"), ("passage", "Passage"), ("diagram", "Diagram / Chart"), ("other", "Other")], default="passage", max_length=30)),
                ("passage_text", models.TextField(blank=True, default="")),
                ("image", models.ImageField(blank=True, null=True, upload_to="question_passages/")),
                ("teacher", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="question_groups", to=settings.AUTH_USER_MODEL)),
                ("tenant", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, to="tenants.tenant")),
            ],
            options={
                "ordering": ["created_at", "id"],
            },
        ),
        migrations.AddField(
            model_name="examattempt",
            name="question_order",
            field=models.JSONField(blank=True, default=list),
        ),
        migrations.AddField(
            model_name="question",
            name="group",
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="questions", to="exams.questiongroup"),
        ),
        migrations.AddField(
            model_name="question",
            name="group_order",
            field=models.PositiveIntegerField(default=0),
        ),
    ]
