# Tenant models are defined in core.tenant module
# Import them here for backwards compatibility if needed
from core.tenant import SchoolTenant as School, Domain

__all__ = ['School', 'Domain']
