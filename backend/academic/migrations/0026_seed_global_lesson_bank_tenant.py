from django.db import migrations

# Same slug/name used by academic/bulk_import.py and the import_lesson_resources
# management command. Seeding it here means the row unconditionally exists as
# soon as `migrate` runs, so the platform admin can start adding
# LessonPlanResources to it (via the management command) without needing to
# run any other setup step first. Mirrors exams/migrations/
# 0011_seed_global_question_bank_tenant.py for the central question bank.
GLOBAL_TENANT_SLUG = "schooldom-global-lesson-bank"
GLOBAL_TENANT_NAME = "SchoolDom Global Lesson Resource Bank"


def seed_global_tenant(apps, schema_editor):
    Tenant = apps.get_model("tenants", "Tenant")
    Tenant.objects.get_or_create(slug=GLOBAL_TENANT_SLUG, defaults={"name": GLOBAL_TENANT_NAME})


def unseed_global_tenant(apps, schema_editor):
    # Deliberately a no-op: this tenant may already own real LessonPlanResource
    # rows by the time anyone reverses this migration, and deleting it would
    # cascade-delete that content.
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('tenants', '0001_initial'),
        ('academic', '0025_lessonplanresource'),
    ]

    operations = [
        migrations.RunPython(seed_global_tenant, unseed_global_tenant),
    ]
