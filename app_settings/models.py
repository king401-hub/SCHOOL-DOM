from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator, RegexValidator
from django.utils import timezone
from core.models import TimeStampedModel
import uuid
import json


class UUIDModel(models.Model):
    """
    Abstract base model that provides UUID as primary key.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    
    class Meta:
        abstract = True


class SystemSetting(TimeStampedModel, UUIDModel):
    """
    Global system settings that apply across all tenants.
    """
    key = models.CharField(max_length=100, unique=True, db_index=True)
    value = models.JSONField()
    
    SETTING_TYPE_CHOICES = [
        ('string', 'String'),
        ('integer', 'Integer'),
        ('float', 'Float'),
        ('boolean', 'Boolean'),
        ('json', 'JSON'),
        ('email', 'Email'),
        ('url', 'URL'),
        ('color', 'Color'),
        ('file', 'File'),
    ]
    setting_type = models.CharField(max_length=20, choices=SETTING_TYPE_CHOICES, default='string')
    
    label = models.CharField(max_length=200)
    description = models.TextField(blank=True, null=True)
    
    # Category
    CATEGORY_CHOICES = [
        ('system', 'System'),
        ('security', 'Security'),
        ('email', 'Email'),
        ('sms', 'SMS'),
        ('payment', 'Payment'),
        ('storage', 'Storage'),
        ('api', 'API'),
        ('features', 'Features'),
        ('maintenance', 'Maintenance'),
    ]
    category = models.CharField(max_length=20, choices=CATEGORY_CHOICES, default='system')
    
    # Validation
    validation_rules = models.JSONField(default=dict, blank=True)
    
    # Is encrypted
    is_encrypted = models.BooleanField(default=False)
    
    # Is public
    is_public = models.BooleanField(default=False)
    
    class Meta:
        verbose_name = "System Setting"
        verbose_name_plural = "System Settings"
        ordering = ['category', 'key']
        indexes = [
            models.Index(fields=['category']),
            models.Index(fields=['key']),
        ]
    
    def __str__(self):
        return f"{self.key} ({self.get_category_display()})"


class FeatureFlag(TimeStampedModel, UUIDModel):
    """
    Global feature flags for enabling/disabling features system-wide.
    """
    code = models.CharField(max_length=100, unique=True, db_index=True)
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True, null=True)
    is_enabled = models.BooleanField(default=False, db_index=True)
    
    class Meta:
        verbose_name = "Feature Flag"
        verbose_name_plural = "Feature Flags"
        ordering = ['code']
    
    def __str__(self):
        return f"{self.name} ({'Enabled' if self.is_enabled else 'Disabled'})"
