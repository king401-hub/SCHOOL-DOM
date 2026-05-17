# Generated manually for secure CBT exam PIN management.

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("exams", "0003_examattempt_auto_submission_monitoring"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="ExamPin",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("pin_digest", models.CharField(db_index=True, max_length=64, unique=True)),
                ("pin_hash", models.CharField(max_length=128)),
                ("pin_preview", models.CharField(blank=True, default="", max_length=8)),
                ("usage_policy", models.CharField(choices=[("one_time", "One-time use"), ("reusable", "Reusable")], default="one_time", max_length=20)),
                ("expires_at", models.DateTimeField(blank=True, null=True)),
                ("is_active", models.BooleanField(default=True)),
                ("deactivated_at", models.DateTimeField(blank=True, null=True)),
                ("reset_at", models.DateTimeField(blank=True, null=True)),
                ("last_regenerated_at", models.DateTimeField(blank=True, null=True)),
                ("created_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="generated_exam_pins", to=settings.AUTH_USER_MODEL)),
                ("deactivated_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="deactivated_exam_pins", to=settings.AUTH_USER_MODEL)),
                ("exam", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="pins", to="exams.exam")),
                ("last_regenerated_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="regenerated_exam_pins", to=settings.AUTH_USER_MODEL)),
                ("reset_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="reset_exam_pins", to=settings.AUTH_USER_MODEL)),
                ("tenant", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, to="tenants.tenant")),
            ],
            options={
                "ordering": ["-created_at"],
            },
        ),
        migrations.CreateModel(
            name="ExamPinUsage",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("entered_pin_digest", models.CharField(blank=True, db_index=True, default="", max_length=64)),
                ("status", models.CharField(choices=[("accepted", "Accepted"), ("rejected", "Rejected"), ("reset", "Reset"), ("regenerated", "Regenerated"), ("deactivated", "Deactivated")], max_length=20)),
                ("message", models.CharField(blank=True, default="", max_length=255)),
                ("ip_address", models.GenericIPAddressField(blank=True, null=True)),
                ("user_agent", models.CharField(blank=True, default="", max_length=255)),
                ("attempt", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="pin_usage_events", to="exams.examattempt")),
                ("exam", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="pin_usage_events", to="exams.exam")),
                ("pin", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name="usages", to="exams.exampin")),
                ("student", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="exam_pin_usage_events", to=settings.AUTH_USER_MODEL)),
                ("tenant", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, to="tenants.tenant")),
            ],
            options={
                "ordering": ["-created_at"],
            },
        ),
        migrations.AddIndex(
            model_name="exampin",
            index=models.Index(fields=["exam", "is_active", "expires_at"], name="exams_examp_exam_id_7a4358_idx"),
        ),
        migrations.AddIndex(
            model_name="exampin",
            index=models.Index(fields=["tenant", "created_at"], name="exams_examp_tenant__1843a3_idx"),
        ),
        migrations.AddIndex(
            model_name="exampinusage",
            index=models.Index(fields=["exam", "status", "created_at"], name="exams_examp_exam_id_e51e09_idx"),
        ),
        migrations.AddIndex(
            model_name="exampinusage",
            index=models.Index(fields=["pin", "status", "created_at"], name="exams_examp_pin_id_cb0e16_idx"),
        ),
    ]
