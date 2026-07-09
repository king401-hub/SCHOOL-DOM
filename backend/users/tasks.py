"""Periodic Celery tasks for the users module."""
from celery import shared_task
from celery.utils.log import get_task_logger
from django.utils import timezone
from datetime import timedelta

logger = get_task_logger(__name__)


@shared_task
def clear_old_database_imports():
    """Delete DatabaseImportJob records older than 7 days along with their uploaded files."""
    from users.models import DatabaseImportJob

    cutoff = timezone.now() - timedelta(days=7)
    old_jobs = DatabaseImportJob.objects.filter(created_at__lt=cutoff)
    count = old_jobs.count()
    for job in old_jobs.iterator():
        try:
            job.upload.delete(save=False)
        except Exception:
            pass
    old_jobs.delete()
    logger.info("clear_old_database_imports: deleted %d import job(s) older than 7 days", count)
    return {"deleted": count}
