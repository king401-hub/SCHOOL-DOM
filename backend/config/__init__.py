try:
    from .celery import app as celery_app
except ModuleNotFoundError:  # Celery is installed from requirements in production.
    celery_app = None

__all__ = ("celery_app",)
