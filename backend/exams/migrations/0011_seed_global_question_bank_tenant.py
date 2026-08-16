from django.db import migrations

# Same slug/name already used by exams/management/commands/import_global_question_bank.py
# and referenced by GLOBAL_QUESTION_BANK_TENANT_SLUG in users/app_views.py. Seeding it here
# means the row unconditionally exists as soon as `migrate` runs, so the platform admin can
# start creating Subjects/QuestionBanks/Topics for it in Django Admin immediately, without
# needing to run any management command first.
GLOBAL_TENANT_SLUG = "schooldom-global-question-bank"
GLOBAL_TENANT_NAME = "SchoolDom Global Question Bank"


def seed_global_tenant(apps, schema_editor):
    Tenant = apps.get_model("tenants", "Tenant")
    Tenant.objects.get_or_create(slug=GLOBAL_TENANT_SLUG, defaults={"name": GLOBAL_TENANT_NAME})


def unseed_global_tenant(apps, schema_editor):
    # Deliberately a no-op: this tenant may already own real QuestionBank/Question rows
    # (created via Django Admin or the import command) by the time anyone reverses this
    # migration, and deleting it would cascade-delete that content.
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('tenants', '0001_initial'),
        ('exams', '0010_questionbank_board_topic_question_topic'),
    ]

    operations = [
        migrations.RunPython(seed_global_tenant, unseed_global_tenant),
    ]
