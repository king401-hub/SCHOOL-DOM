# backend/core/apps.py
from django.apps import AppConfig

class CoreConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'core'
    verbose_name = 'Core System'

    def ready(self):
        # Registers OpenAPI security schemes for this project's custom DRF
        # authentication classes (drf_spectacular) - see
        # config/openapi_extensions.py for why this needs AppConfig.ready()
        # rather than a plain settings.py import.
        import config.openapi_extensions  # noqa: F401