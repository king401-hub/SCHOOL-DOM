from django.db import migrations

# Transcribed directly from the "Master permissions matrix" (section 2) and the
# team_management_scoped footnote/3.4 in the Schooldom User Permissions Specification.
# CEO rows are seeded True for documentation even though ops.permissions.has_permission()
# hardcodes CEO to always-True regardless of what's stored here (spec 3.1: "locked in
# schema, cannot be revoked, including by CEO themself").
MATRIX = {
    "school_onboarding":        {"ceo": True, "cto": True,  "cfo": False, "growth_manager": True,  "senior_marketer": True,  "marketer": True},
    "compliance_verification":  {"ceo": True, "cto": True,  "cfo": False, "growth_manager": True,  "senior_marketer": False, "marketer": False},
    "token_assignment":         {"ceo": True, "cto": True,  "cfo": False, "growth_manager": False, "senior_marketer": False, "marketer": False},  # GM: planned v2, off by default in v1
    "churn_dashboard":          {"ceo": True, "cto": True,  "cfo": True,  "growth_manager": True,  "senior_marketer": True,  "marketer": False},
    "revenue_features":         {"ceo": True, "cto": True,  "cfo": True,  "growth_manager": True,  "senior_marketer": False, "marketer": False},
    "lead_pipeline":            {"ceo": True, "cto": False, "cfo": False, "growth_manager": True,  "senior_marketer": True,  "marketer": True},
    "training_tools":           {"ceo": True, "cto": False, "cfo": False, "growth_manager": True,  "senior_marketer": True,  "marketer": True},
    "students_staff_data":      {"ceo": True, "cto": True,  "cfo": True,  "growth_manager": True,  "senior_marketer": True,  "marketer": True},
    "team_performance":         {"ceo": True, "cto": False, "cfo": False, "growth_manager": True,  "senior_marketer": True,  "marketer": False},
    "team_management":          {"ceo": True, "cto": True,  "cfo": False, "growth_manager": False, "senior_marketer": False, "marketer": False},  # GM's scoped variant is the next row
    "team_management_scoped":   {"ceo": True, "cto": False, "cfo": False, "growth_manager": True,  "senior_marketer": False, "marketer": False},
    "slack_controls":           {"ceo": True, "cto": True,  "cfo": False, "growth_manager": False, "senior_marketer": False, "marketer": False},
    "billing_plan":             {"ceo": True, "cto": False, "cfo": True,  "growth_manager": False, "senior_marketer": False, "marketer": False},
}


def seed_role_permissions(apps, schema_editor):
    RolePermission = apps.get_model("ops", "RolePermission")
    rows = [
        RolePermission(role=role, module=module, granted=granted)
        for module, by_role in MATRIX.items()
        for role, granted in by_role.items()
    ]
    RolePermission.objects.bulk_create(rows, ignore_conflicts=True)


def unseed_role_permissions(apps, schema_editor):
    RolePermission = apps.get_model("ops", "RolePermission")
    RolePermission.objects.all().delete()


class Migration(migrations.Migration):

    dependencies = [
        ("ops", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(seed_role_permissions, unseed_role_permissions),
    ]
