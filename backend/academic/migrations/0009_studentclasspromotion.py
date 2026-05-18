from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("academic", "0008_studentsubjectscore_approved_at"),
        ("users", "0013_databaseimportjob"),
    ]

    operations = [
        migrations.CreateModel(
            name="StudentClassPromotion",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "scope",
                    models.CharField(
                        choices=[
                            ("class", "Class"),
                            ("department", "Department"),
                            ("level", "Academic level"),
                            ("session", "Academic session"),
                        ],
                        default="class",
                        max_length=20,
                    ),
                ),
                ("scope_value", models.CharField(blank=True, max_length=120)),
                ("batch_reference", models.CharField(db_index=True, max_length=64)),
                ("note", models.TextField(blank=True)),
                (
                    "from_academic_year",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="promotions_from",
                        to="academic.academicyear",
                    ),
                ),
                (
                    "from_class",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="promotions_from",
                        to="academic.class",
                    ),
                ),
                (
                    "from_term",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="promotions_from",
                        to="academic.term",
                    ),
                ),
                (
                    "promoted_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="class_promotions_performed",
                        to="users.user",
                    ),
                ),
                (
                    "student",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="class_promotions",
                        to="users.studentprofile",
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
                (
                    "to_academic_year",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="promotions_to",
                        to="academic.academicyear",
                    ),
                ),
                (
                    "to_class",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="promotions_to",
                        to="academic.class",
                    ),
                ),
                (
                    "to_term",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="promotions_to",
                        to="academic.term",
                    ),
                ),
            ],
            options={
                "ordering": ["-created_at"],
                "unique_together": {
                    (
                        "student",
                        "from_class",
                        "to_class",
                        "from_term",
                        "to_term",
                        "from_academic_year",
                        "to_academic_year",
                    )
                },
            },
        ),
        migrations.AddIndex(
            model_name="studentclasspromotion",
            index=models.Index(fields=["tenant", "batch_reference"], name="academic_st_tenant__0c281f_idx"),
        ),
        migrations.AddIndex(
            model_name="studentclasspromotion",
            index=models.Index(fields=["tenant", "scope", "scope_value"], name="academic_st_tenant__462d4b_idx"),
        ),
    ]
