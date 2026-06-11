from django.db import migrations, models
import django.db.models.deletion
import uuid


DEFAULT_TITLES = [
    "Prefect",
    "Class Monitor",
    "Assistant Class Monitor",
    "Sports Captain",
    "Club Leader",
]


def seed_student_activity_titles(apps, schema_editor):
    SchoolTenant = apps.get_model("core", "SchoolTenant")
    StudentActivityTitle = apps.get_model("users", "StudentActivityTitle")
    for tenant in SchoolTenant.objects.all():
        for index, name in enumerate(DEFAULT_TITLES, start=1):
            StudentActivityTitle.objects.get_or_create(
                tenant=tenant,
                name=name,
                defaults={"sort_order": index * 10, "is_active": True},
            )


def unseed_student_activity_titles(apps, schema_editor):
    StudentActivityTitle = apps.get_model("users", "StudentActivityTitle")
    StudentActivityTitle.objects.filter(name__in=DEFAULT_TITLES).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0001_initial"),
        ("users", "0017_rename_users_suppo_school__5acb79_idx_users_suppo_school__d62898_idx_and_more"),
    ]

    operations = [
        migrations.CreateModel(
            name="StudentActivityTitle",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("name", models.CharField(max_length=120)),
                ("is_active", models.BooleanField(default=True)),
                ("sort_order", models.PositiveIntegerField(default=0)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "tenant",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="student_activity_titles",
                        to="core.schooltenant",
                    ),
                ),
            ],
            options={
                "verbose_name": "student activity title",
                "verbose_name_plural": "student activity titles",
                "ordering": ["sort_order", "name"],
            },
        ),
        migrations.AddField(
            model_name="studentprofile",
            name="extra_curricular_activity_title",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="students",
                to="users.studentactivitytitle",
            ),
        ),
        migrations.AddConstraint(
            model_name="studentactivitytitle",
            constraint=models.UniqueConstraint(
                fields=("tenant", "name"),
                name="unique_student_activity_title_per_school",
            ),
        ),
        migrations.RunPython(seed_student_activity_titles, unseed_student_activity_titles),
    ]
