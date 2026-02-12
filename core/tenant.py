# backend/core/models/tenant.py
from django.db import models


class SchoolTenant(models.Model):
    name = models.CharField(max_length=255)
    schema_name = models.CharField(max_length=63, unique=True)
    created_on = models.DateField(auto_now_add=True)
    
    # School Information
    address = models.TextField(blank=True, null=True)
    phone = models.CharField(max_length=20, blank=True, null=True)
    email = models.EmailField(blank=True, null=True)
    
    # Branding
    logo = models.ImageField(upload_to='school_logos/', null=True, blank=True)
    favicon = models.ImageField(upload_to='school_favicons/', null=True, blank=True)
    primary_color = models.CharField(max_length=7, default='#3B82F6')
    secondary_color = models.CharField(max_length=7, default='#1E40AF')
    
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