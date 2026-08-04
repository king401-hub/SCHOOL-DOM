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


class DocumentTheme(TimeStampedModel):
    """School-wide styling applied to every generated document (report cards,
    transcripts, testimonials, invoices, receipts, bills, payslips, ID cards,
    broadsheets, service agreements) across print, PDF, and PNG output."""

    ORIENTATION_CHOICES = [("portrait", "Portrait"), ("landscape", "Landscape")]

    school_tenant = models.OneToOneField(
        'core.SchoolTenant',
        on_delete=models.CASCADE,
        related_name='document_theme',
    )
    orientation = models.CharField(max_length=10, choices=ORIENTATION_CHOICES, default="portrait")
    id_card_orientation = models.CharField(max_length=10, choices=ORIENTATION_CHOICES, default="landscape")
    page_size = models.CharField(max_length=10, choices=[("A4", "A4"), ("letter", "Letter")], default="A4")
    margin_mm = models.PositiveSmallIntegerField(default=15)
    font_family = models.CharField(max_length=100, default="Segoe UI")
    font_size_body = models.PositiveSmallIntegerField(default=13)
    font_size_heading = models.PositiveSmallIntegerField(default=20)
    primary_color = models.CharField(max_length=7, default="#0f766e")
    secondary_color = models.CharField(max_length=7, default="#0f172a")
    accent_color = models.CharField(max_length=7, default="#0f766e")
    table_style = models.CharField(
        max_length=10,
        choices=[("bordered", "Bordered"), ("striped", "Striped"), ("minimal", "Minimal")],
        default="bordered",
    )
    border_style = models.CharField(
        max_length=10,
        choices=[("solid", "Solid"), ("double", "Double"), ("dashed", "Dashed"), ("none", "None")],
        default="solid",
    )
    border_width = models.PositiveSmallIntegerField(default=1)
    header_note = models.CharField(max_length=255, blank=True, default="")
    footer_text = models.TextField(blank=True, default="")
    show_logo = models.BooleanField(default=True)
    show_signature = models.BooleanField(default=True)
    watermark_enabled = models.BooleanField(default=False)
    watermark_source = models.CharField(
        max_length=10, choices=[("text", "Text"), ("logo", "School logo")], default="text"
    )
    watermark_text = models.CharField(max_length=60, blank=True, default="")
    watermark_opacity = models.PositiveSmallIntegerField(default=8)

    class Meta:
        verbose_name = "Document Theme"
        verbose_name_plural = "Document Themes"

    def __str__(self):
        return f"Document Theme - {self.school_tenant}"


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
