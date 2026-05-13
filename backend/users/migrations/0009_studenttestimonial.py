from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import uuid


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0001_initial"),
        ("users", "0008_alter_user_role"),
    ]

    operations = [
        migrations.CreateModel(
            name="StudentTestimonial",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("class_of_admission", models.CharField(blank=True, max_length=120)),
                ("date_of_leaving", models.DateField(blank=True, null=True)),
                ("class_of_leaving", models.CharField(blank=True, max_length=120)),
                ("reason_for_leaving", models.CharField(blank=True, max_length=255)),
                ("educational_attainment", models.CharField(blank=True, max_length=255)),
                ("subjects_offered", models.TextField(blank=True)),
                ("co_curricular_activities", models.TextField(blank=True)),
                ("prizes_and_honors", models.TextField(blank=True)),
                ("office_held", models.CharField(blank=True, max_length=255)),
                ("administrator_remarks", models.TextField(blank=True)),
                ("issue_date", models.DateField(blank=True, null=True)),
                ("principal_name", models.CharField(blank=True, max_length=255)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "created_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="created_testimonials",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "school",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="student_testimonials",
                        to="core.schooltenant",
                    ),
                ),
                (
                    "student",
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="testimonial",
                        to="users.studentprofile",
                    ),
                ),
                (
                    "updated_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="updated_testimonials",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "verbose_name": "student testimonial",
                "verbose_name_plural": "student testimonials",
            },
        ),
        migrations.AddIndex(
            model_name="studenttestimonial",
            index=models.Index(fields=["school", "student"], name="users_stude_school__2a5d73_idx"),
        ),
        migrations.AddIndex(
            model_name="studenttestimonial",
            index=models.Index(fields=["updated_at"], name="users_stude_updated_47a959_idx"),
        ),
    ]
