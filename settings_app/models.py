from django.db import models
from core.models import TimeStampedModel


class ThemeConfiguration(TimeStampedModel):
    """Theme configuration for a school tenant"""
    school_tenant = models.OneToOneField(
        'core.SchoolTenant',
        on_delete=models.CASCADE,
        related_name='theme',
        null=True,
        blank=True
    )
    primary_color = models.CharField(max_length=7, default='#3B82F6')
    secondary_color = models.CharField(max_length=7, default='#1E40AF')
    logo = models.ImageField(upload_to='logos/', null=True, blank=True)
    favicon = models.ImageField(upload_to='favicons/', null=True, blank=True)
    font_family = models.CharField(max_length=100, default='Segoe UI')
    is_dark_mode_enabled = models.BooleanField(default=False)
    
    class Meta:
        verbose_name = "Theme Configuration"
        verbose_name_plural = "Theme Configurations"
    
    def __str__(self):
        return f"Theme - {self.school_tenant}"


class FeatureFlag(TimeStampedModel):
    """Feature flags to enable/disable features per school"""
    FEATURE_CHOICES = [
        ('offline_exams', 'Offline Exams'),
        ('analytics', 'Analytics'),
        ('assignments', 'Assignments'),
        ('discussion_forum', 'Discussion Forum'),
        ('video_conferencing', 'Video Conferencing'),
        ('advance_payments', 'Advance Payments'),
    ]
    
    school_tenant = models.ForeignKey(
        'core.SchoolTenant',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='features'
    )
    code = models.CharField(max_length=50, choices=FEATURE_CHOICES)
    is_enabled = models.BooleanField(default=False)
    description = models.TextField(blank=True)
    
    class Meta:
        verbose_name = "Feature Flag"
        verbose_name_plural = "Feature Flags"
        unique_together = ('school_tenant', 'code')
    
    def __str__(self):
        tenant = self.school_tenant.name if self.school_tenant else "Global"
        return f"{self.get_code_display()} - {tenant}"
