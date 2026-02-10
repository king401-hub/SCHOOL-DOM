from django.db import models
from core.models import TenantAwareModel, TimeStampedModel

class Subject(TenantAwareModel, TimeStampedModel):
    name = models.CharField(max_length=100)
    code = models.CharField(max_length=20)
    
    def __str__(self):
        return self.name

class Class(TenantAwareModel, TimeStampedModel):
    name = models.CharField(max_length=100)
    section = models.CharField(max_length=50, null=True, blank=True)
    
    def __str__(self):
        return f"{self.name} - {self.section}"