from django.db import models

class TimeStampedModel(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        abstract = True

class TenantAwareModel(TimeStampedModel):
    tenant = models.ForeignKey(
        'tenants.Tenant',
        on_delete=models.CASCADE,
        null=True,
        blank=True
    )
    
    class Meta:
        abstract = True

# Ensure core models defined in other modules are registered.
from .tenant import Domain, SchoolGroup, SchoolTenant  # noqa: E402,F401
from .audit import AuditLog  # noqa: E402,F401

