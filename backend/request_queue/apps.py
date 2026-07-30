from django.apps import AppConfig


class RequestQueueConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "request_queue"
    verbose_name = "Request Queue"
