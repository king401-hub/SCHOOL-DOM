from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("academic", "0010_attendancerecord_geotracking"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="SchoolActivityCalendar",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("month", models.PositiveSmallIntegerField()),
                ("year", models.PositiveIntegerField(blank=True, null=True)),
                ("title", models.CharField(max_length=200)),
                ("activity_date", models.DateField(blank=True, null=True)),
                ("end_date", models.DateField(blank=True, null=True)),
                ("description", models.TextField(blank=True)),
                ("color", models.CharField(default="#2563EB", max_length=7)),
                (
                    "created_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="created_school_activities",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "tenant",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.CASCADE,
                        to="tenants.tenant",
                    ),
                ),
            ],
            options={
                "ordering": ["year", "month", "activity_date", "title"],
            },
        ),
        migrations.AddIndex(
            model_name="schoolactivitycalendar",
            index=models.Index(fields=["tenant", "year", "month"], name="academic_sc_tenant__a2e0b8_idx"),
        ),
        migrations.AddIndex(
            model_name="schoolactivitycalendar",
            index=models.Index(fields=["tenant", "activity_date"], name="academic_sc_tenant__af6e7b_idx"),
        ),
    ]
