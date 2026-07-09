# backend/core/models/tenant.py
from django.db import models
from django.utils import timezone as django_timezone


class SchoolGroup(models.Model):
    name = models.CharField(max_length=255)
    owner = models.ForeignKey(
        "users.User",
        on_delete=models.CASCADE,
        related_name="owned_school_groups",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "School Group"
        verbose_name_plural = "School Groups"
        ordering = ["name"]

    def __str__(self):
        return self.name


class SchoolTenant(models.Model):
    K12 = "k12"
    NON_K12 = "non_k12"
    SCHOOL_TYPE_CHOICES = [
        (K12, "K-12 school"),
        (NON_K12, "Non K-12 school"),
    ]

    name = models.CharField(max_length=255)
    schema_name = models.CharField(max_length=63, unique=True)
    created_on = models.DateField(auto_now_add=True)
    school_type = models.CharField(max_length=20, choices=SCHOOL_TYPE_CHOICES, default=K12)
    school_group = models.ForeignKey(
        SchoolGroup,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="schools",
    )
    
    # School Information
    address = models.TextField(blank=True, null=True)
    phone = models.CharField(max_length=20, blank=True, null=True)
    email = models.EmailField(blank=True, null=True)
    motto = models.CharField(max_length=255, blank=True, default="")
    student_rules = models.TextField(blank=True, default="")
    staff_rules = models.TextField(blank=True, default="")
    
    # Branding
    logo = models.ImageField(upload_to='school_logos/', null=True, blank=True)
    favicon = models.ImageField(upload_to='school_favicons/', null=True, blank=True)
    primary_color = models.CharField(max_length=7, default='#3B82F6')
    secondary_color = models.CharField(max_length=7, default='#1E40AF')

    # Compliance / KYC documents
    cac_registered_name = models.CharField(max_length=255, blank=True, default="")
    cac_certificate = models.FileField(upload_to='school_compliance/cac_certificates/%Y/%m/', null=True, blank=True)
    entrance_photo = models.ImageField(upload_to='school_compliance/entrance_photos/%Y/%m/', null=True, blank=True)
    proof_of_address = models.FileField(upload_to='school_compliance/proof_of_address/%Y/%m/', null=True, blank=True)
    ministry_approval_number = models.CharField(max_length=100, blank=True, default="")

    # Compliance review workflow
    COMPLIANCE_STATUS_CHOICES = [
        ('not_submitted', 'Not Submitted'),
        ('submitted', 'Submitted - Pending Review'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
    ]
    compliance_status = models.CharField(max_length=20, choices=COMPLIANCE_STATUS_CHOICES, default='not_submitted')
    compliance_deadline_reference_at = models.DateTimeField(null=True, blank=True)
    compliance_submitted_at = models.DateTimeField(null=True, blank=True)
    compliance_reviewed_at = models.DateTimeField(null=True, blank=True)
    compliance_reviewed_by = models.ForeignKey(
        'users.User', null=True, blank=True, on_delete=models.SET_NULL, related_name='compliance_reviews',
    )
    compliance_suspended_at = models.DateTimeField(null=True, blank=True)
    compliance_reminder_stage = models.PositiveSmallIntegerField(default=0)
    signup_notification_sent_at = models.DateTimeField(null=True, blank=True)

    # Configuration
    timezone = models.CharField(max_length=50, default='UTC')
    currency = models.CharField(max_length=3, default='USD')
    language = models.CharField(max_length=10, default='en')
    
    # Status
    is_active = models.BooleanField(default=True)
    subscription_tier = models.CharField(
        max_length=20,
        choices=[
            ('free', 'Free'),
            ('basic', 'Basic'),
            ('premium', 'Premium'),
            ('enterprise', 'Enterprise')
        ],
        default='free'
    )
    
    # Relationships to new configurations (will be created by related apps)
    # These are auto-created OneToOneFields from the related apps:
    # - email_config (from notifications.EmailConfiguration)
    # - sms_config (from notifications.SMSConfiguration)
    # - payment_config (from notifications.PaymentGatewayConfiguration)
    # - theme (from settings_app.ThemeConfiguration)
    
    # Feature flags
    enabled_features = models.ManyToManyField(
        'settings_app.FeatureFlag',
        blank=True,
        related_name='schools'
    )
    
    class Meta:
        verbose_name = "School"
        verbose_name_plural = "Schools"
    
    def __str__(self):
        return self.name
    
    def compliance_documents_complete(self):
        """Whether all required school + director compliance documents have been uploaded."""
        school_ok = bool(
            (self.cac_registered_name or "").strip()
            and self.cac_certificate
            and self.entrance_photo
            and (self.address or "").strip()
            and self.proof_of_address
        )
        if not school_ok:
            return False

        from users.models import User

        return (
            User.objects.filter(tenant=self)
            .exclude(director_address="")
            .exclude(director_id_type="")
            .exclude(director_id_document="")
            .exclude(director_proof_of_address="")
            .exclude(profile_picture="")
            .exists()
        )

    def compliance_deadline_reference(self):
        """The moment the 30-day compliance clock started for this school."""
        if self.compliance_deadline_reference_at:
            return self.compliance_deadline_reference_at
        return django_timezone.make_aware(
            django_timezone.datetime.combine(self.created_on, django_timezone.datetime.min.time())
        )

    def is_feature_enabled(self, feature_code):
        """Check if a feature is enabled for this school"""
        from settings_app.models import FeatureFlag
        
        # Check school-specific feature flag
        if self.enabled_features.filter(code=feature_code, is_enabled=True).exists():
            return True
        
        # Check global feature flag
        return FeatureFlag.objects.filter(
            school_tenant=None,
            code=feature_code,
            is_enabled=True
        ).exists()

class Domain(models.Model):
    """Simple domain model without django-tenants dependency"""
    tenant = models.ForeignKey(SchoolTenant, on_delete=models.CASCADE, related_name='domains')
    domain = models.CharField(max_length=255, unique=True)
    is_primary = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True, null=True)
    
    class Meta:
        verbose_name = "Domain"
        verbose_name_plural = "Domains"
    
    def __str__(self):
        return self.domain
