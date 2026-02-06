# backend/core/models/base.py
from django.db import models

class TimeStampedModel(models.Model):
    """Abstract base model with timestamp fields"""
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        abstract = True

class TenantAwareModel(models.Model):
    """Abstract base model for tenant-specific models"""
    tenant = models.ForeignKey('core.SchoolTenant', on_delete=models.CASCADE)
    
    class Meta:
        abstract = True