import uuid

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0001_initial"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("users", "0012_teacherprofile_monthly_salary"),
    ]

    operations = [
        migrations.CreateModel(
            name="DatabaseImportJob",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                (
                    "import_type",
                    models.CharField(
                        choices=[
                            ("students", "Student records"),
                            ("teachers", "Teacher profiles"),
                            ("classes_subjects", "Classes and subjects"),
                            ("cbt_results", "CBT results"),
                            ("attendance", "Attendance records"),
                            ("payments", "Payment history"),
                            ("timetables", "Timetables"),
                            ("assignments", "Assignments"),
                            ("documents", "Uploaded documents"),
                            ("academic_records", "Academic records"),
                            ("full_school", "Full school database"),
                        ],
                        max_length=40,
                    ),
                ),
                ("source_platform", models.CharField(blank=True, max_length=120)),
                ("link_key", models.CharField(blank=True, max_length=80)),
                ("notes", models.TextField(blank=True)),
                ("upload", models.FileField(upload_to="database_imports/%Y/%m/")),
                ("original_filename", models.CharField(max_length=255)),
                ("file_size", models.PositiveBigIntegerField(default=0)),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("uploaded", "Uploaded"),
                            ("validated", "Validated"),
                            ("needs_review", "Needs review"),
                            ("failed", "Failed"),
                        ],
                        default="uploaded",
                        max_length=20,
                    ),
                ),
                ("summary", models.JSONField(blank=True, default=dict)),
                ("errors", models.JSONField(blank=True, default=list)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "tenant",
                    models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="database_import_jobs", to="core.schooltenant"),
                ),
                (
                    "uploaded_by",
                    models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="database_import_jobs", to=settings.AUTH_USER_MODEL),
                ),
            ],
            options={
                "ordering": ["-created_at"],
                "indexes": [
                    models.Index(fields=["tenant", "status"], name="users_datab_tenant__d2d7de_idx"),
                    models.Index(fields=["tenant", "import_type"], name="users_datab_tenant__705b75_idx"),
                ],
            },
        ),
    ]
