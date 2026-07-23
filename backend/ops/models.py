from django.conf import settings
from django.db import models

# Stable slugs for every module in the "Master permissions matrix" (section 2 of the
# Schooldom User Permissions Specification). team_management_scoped is not a row in
# that matrix - it's the "distinct manage_own_team permission" section 3.4 calls for,
# kept as its own module so Growth Manager's region-limited team access never collides
# with the global team_management permission CTO/CEO hold.
MODULE_SCHOOL_ONBOARDING = "school_onboarding"
MODULE_COMPLIANCE_VERIFICATION = "compliance_verification"
MODULE_TOKEN_ASSIGNMENT = "token_assignment"
MODULE_CHURN_DASHBOARD = "churn_dashboard"
MODULE_REVENUE_FEATURES = "revenue_features"
MODULE_LEAD_PIPELINE = "lead_pipeline"
MODULE_TRAINING_TOOLS = "training_tools"
MODULE_STUDENTS_STAFF_DATA = "students_staff_data"
MODULE_TEAM_PERFORMANCE = "team_performance"
MODULE_TEAM_MANAGEMENT = "team_management"
MODULE_TEAM_MANAGEMENT_SCOPED = "team_management_scoped"
MODULE_SLACK_CONTROLS = "slack_controls"
MODULE_BILLING_PLAN = "billing_plan"

MODULE_CHOICES = [
    (MODULE_SCHOOL_ONBOARDING, "School onboarding"),
    (MODULE_COMPLIANCE_VERIFICATION, "Compliance verification"),
    (MODULE_TOKEN_ASSIGNMENT, "Token assignment"),
    (MODULE_CHURN_DASHBOARD, "Churn & adoption dashboard"),
    (MODULE_REVENUE_FEATURES, "Revenue features"),
    (MODULE_LEAD_PIPELINE, "Lead pipeline"),
    (MODULE_TRAINING_TOOLS, "School training tools"),
    (MODULE_STUDENTS_STAFF_DATA, "Students & staff data"),
    (MODULE_TEAM_PERFORMANCE, "Team performance & reporting"),
    (MODULE_TEAM_MANAGEMENT, "Team management"),
    (MODULE_TEAM_MANAGEMENT_SCOPED, "Team management (own region only)"),
    (MODULE_SLACK_CONTROLS, "Slack channel controls"),
    (MODULE_BILLING_PLAN, "Billing & plan"),
]


class Region(models.Model):
    name = models.CharField(max_length=100, unique=True)
    # Not unique: it's an optional short label, and leaving it blank on more than
    # one Region (a real scenario - it's blank=True) would otherwise collide, since
    # SQL unique constraints treat "" as a real, non-distinct value.
    code = models.CharField(max_length=20, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class OpsUser(models.Model):
    """A Schooldom company staff account (growth/ops team), not a school-tenant user.
    Login/password/session all still come from the linked users.User row - this just
    carries the role + region + reporting-line data the Ops Console spec needs, kept
    off the tenant-shaped User model on purpose."""

    CEO = "ceo"
    CTO = "cto"
    CFO = "cfo"
    GROWTH_MANAGER = "growth_manager"
    SENIOR_MARKETER = "senior_marketer"
    MARKETER = "marketer"
    ROLE_CHOICES = [
        (CEO, "CEO"),
        (CTO, "CTO"),
        (CFO, "CFO"),
        (GROWTH_MANAGER, "Growth Manager"),
        (SENIOR_MARKETER, "Senior Marketer"),
        (MARKETER, "Marketer"),
    ]
    # CEO/CTO/CFO see the full platform; Growth Manager/Senior Marketer/Marketer are
    # scoped to one region (spec section 1, "Scope" column).
    FULL_PLATFORM_ROLES = {CEO, CTO, CFO}
    REGION_SCOPED_ROLES = {GROWTH_MANAGER, SENIOR_MARKETER, MARKETER}

    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="ops_profile")
    role = models.CharField(max_length=20, choices=ROLE_CHOICES)
    region = models.ForeignKey(Region, on_delete=models.PROTECT, null=True, blank=True, related_name="ops_users")
    reports_to = models.ForeignKey(
        "self", on_delete=models.SET_NULL, null=True, blank=True, related_name="direct_reports",
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["role", "region__name"]

    def __str__(self):
        label = f"{self.user.get_full_name() or self.user.get_username()} ({self.get_role_display()})"
        return f"{label} - {self.region}" if self.region else label

    def sees_all_regions(self):
        return self.role in self.FULL_PLATFORM_ROLES


class RolePermission(models.Model):
    """Default permission for a role/module pair. CEO rows exist here for
    documentation, but the resolver (ops/permissions.py) always returns True for CEO
    regardless of what's stored - "locked in schema, cannot be revoked" per spec 3.1."""

    role = models.CharField(max_length=20, choices=OpsUser.ROLE_CHOICES)
    module = models.CharField(max_length=40, choices=MODULE_CHOICES)
    granted = models.BooleanField(default=False)

    class Meta:
        unique_together = ("role", "module")
        ordering = ["module", "role"]

    def __str__(self):
        return f"{self.get_role_display()} / {self.get_module_display()}: {'granted' if self.granted else 'not granted'}"


class MemberPermission(models.Model):
    """Per-user override. Resolution order per spec section 4: override ?? role default."""

    ops_user = models.ForeignKey(OpsUser, on_delete=models.CASCADE, related_name="permission_overrides")
    module = models.CharField(max_length=40, choices=MODULE_CHOICES)
    granted = models.BooleanField()

    class Meta:
        unique_together = ("ops_user", "module")

    def __str__(self):
        return f"{self.ops_user} override / {self.get_module_display()}: {'granted' if self.granted else 'revoked'}"


class PermissionAuditLog(models.Model):
    """Every permission change, who made it, for whom, when - spec section 4."""

    ROLE_DEFAULT_CHANGED = "role_default_changed"
    MEMBER_OVERRIDE_SET = "member_override_set"
    MEMBER_OVERRIDE_CLEARED = "member_override_cleared"
    CHANGE_TYPE_CHOICES = [
        (ROLE_DEFAULT_CHANGED, "Role default changed"),
        (MEMBER_OVERRIDE_SET, "Member override set"),
        (MEMBER_OVERRIDE_CLEARED, "Member override cleared"),
    ]

    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name="ops_permission_changes_made",
    )
    change_type = models.CharField(max_length=30, choices=CHANGE_TYPE_CHOICES)
    role = models.CharField(max_length=20, choices=OpsUser.ROLE_CHOICES, blank=True)
    target_ops_user = models.ForeignKey(
        OpsUser, on_delete=models.SET_NULL, null=True, blank=True, related_name="permission_change_log",
    )
    module = models.CharField(max_length=40, choices=MODULE_CHOICES)
    old_value = models.BooleanField(null=True)
    new_value = models.BooleanField(null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.get_change_type_display()}: {self.module} -> {self.new_value}"
