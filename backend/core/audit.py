# backend/core/models/audit.py
from django.db import models
from .base import TimeStampedModel

class AuditLog(TimeStampedModel):
    ACTION_CHOICES = [
        ('CREATE', 'Create'),
        ('READ', 'Read'),
        ('UPDATE', 'Update'),
        ('DELETE', 'Delete'),
        ('LOGIN', 'Login'),
        ('LOGOUT', 'Logout'),
        ('DOWNLOAD', 'Download'),
        ('UPLOAD', 'Upload'),
    ]
    
    # AuditLog is a shared app (one table in the public schema); User is
    # tenant-scoped (a separate table per school schema), so there is no
    # single users_user table this FK could reference at the database level -
    # db_constraint=False keeps the column without a real Postgres FK.
    user = models.ForeignKey('users.User', on_delete=models.SET_NULL, null=True, db_constraint=False)
    tenant = models.ForeignKey('core.SchoolTenant', on_delete=models.CASCADE)
    action = models.CharField(max_length=20, choices=ACTION_CHOICES)
    model_name = models.CharField(max_length=100)
    object_id = models.CharField(max_length=100, null=True, blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True, null=True)
    metadata = models.JSONField(default=dict)
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['tenant', 'created_at']),
            models.Index(fields=['user', 'created_at']),
            models.Index(fields=['action', 'created_at']),
        ]
    
    def __str__(self):
        return f"{self.user} - {self.action} - {self.model_name}"