from django.db.models.signals import post_save
from django.dispatch import receiver

from .models import Notification
from .push import send_web_push_to_user


@receiver(post_save, sender=Notification)
def push_new_notification(sender, instance, created, **kwargs):
    # bulk_create() bypasses this signal entirely - those call sites push
    # explicitly via push_for_notifications() right after the bulk_create call.
    if not created:
        return
    send_web_push_to_user(instance.user, instance.title, instance.message, url=instance.deep_link)
