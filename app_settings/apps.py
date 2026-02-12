from django.apps import AppConfig


class AppSettingsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'app_settings'
    verbose_name = 'Application Settings'
    
    def ready(self):
        # Import models when app is ready
        import app_settings.models
