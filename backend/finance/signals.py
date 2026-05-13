"""Finance sync hooks for live class fee updates."""

from django.db.models.signals import post_save
from django.dispatch import receiver

from finance.models import ClassFee
from finance.services import get_or_create_student_activation_credit, sync_class_fee_assignments, sync_student_class_fees
from users.models import StudentProfile


@receiver(post_save, sender=ClassFee)
def sync_students_after_class_fee_save(sender, instance, **kwargs):
    sync_class_fee_assignments(instance, actor=instance.created_by)


@receiver(post_save, sender=StudentProfile)
def sync_class_fees_after_student_save(sender, instance, **kwargs):
    get_or_create_student_activation_credit(instance)
    sync_student_class_fees(instance, actor=None)
