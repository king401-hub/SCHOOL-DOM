__all__ = [
    'SchoolTenant',
    'Domain',
    'TimeStampedModel', 
    'TenantAwareModel',
    'AuditLog'
]

def __getattr__(name):
    """Lazy load models to avoid AppRegistryNotReady errors"""
    if name == 'SchoolTenant':
        from .tenant import SchoolTenant
        return SchoolTenant
    elif name == 'Domain':
        from .tenant import Domain
        return Domain
    elif name == 'TimeStampedModel':
        from .base import TimeStampedModel
        return TimeStampedModel
    elif name == 'TenantAwareModel':
        from .base import TenantAwareModel
        return TenantAwareModel
    elif name == 'AuditLog':
        from .audit import AuditLog
        return AuditLog
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")