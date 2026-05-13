from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("academic", "0007_gradescale_resultbatch_scores_workflow"),
        ("quizzes", "0003_personal_quiz_attempt_and_more"),
        ("tenants", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="PersonalQuizFolder",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("name", models.CharField(default="Personal Quiz Questions", max_length=160)),
                ("description", models.TextField(blank=True)),
                ("is_active", models.BooleanField(default=True)),
                ("class_group", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="personal_quiz_folders", to="academic.class")),
                ("subject", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="personal_quiz_folders", to="academic.subject")),
                ("tenant", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name="personal_quiz_folders", to="tenants.tenant")),
            ],
            options={
                "ordering": ["name", "id"],
            },
        ),
        migrations.CreateModel(
            name="PersonalQuizFolderQuestion",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("question_type", models.CharField(choices=[("objective", "Objective"), ("true_false", "True or False"), ("fill_blank", "Fill in the blank")], default="objective", max_length=20)),
                ("prompt", models.TextField()),
                ("options", models.JSONField(blank=True, default=list)),
                ("correct_answer", models.CharField(max_length=255)),
                ("explanation", models.TextField(blank=True)),
                ("order", models.PositiveIntegerField(default=1)),
                ("points", models.PositiveIntegerField(default=1)),
                ("is_active", models.BooleanField(default=True)),
                ("folder", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="folder_questions", to="quizzes.personalquizfolder")),
            ],
            options={
                "ordering": ["order", "id"],
            },
        ),
    ]
