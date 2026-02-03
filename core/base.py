# backend/core/models/base.py
from django.db import models
from django.contrib.auth import get_user_model

User = get_user_model()

class TimeStampedModel(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(
        User, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        related_name='created_%(class)ss'
    )
    
    class Meta:
        abstract = True

class TenantAwareModel(models.Model):
    tenant = models.ForeignKey('core.SchoolTenant', on_delete=models.CASCADE)
    
    class Meta:
        abstract = True