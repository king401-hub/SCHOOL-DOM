"""Guarantees a student's history survives their deletion.

Deleting a student runs `student_user.delete()`, and StudentProfile - along with
every score, fee, and attendance row that points at it - is removed by CASCADE.
By the time post_delete fires there is nothing left to read, so the snapshot has
to be taken in pre_delete, while the rows are still there.

Both the User and the StudentProfile receivers are registered because a student
can be removed from either end (deleting the account cascades to the profile;
deleting the profile alone leaves the account). Whichever fires first seals the
archive, and the second one finds a sealed record and leaves it alone.
"""
import logging

from django.db.models.signals import pre_delete
from django.dispatch import receiver

from users.models import StudentProfile, User

from .models import ArchivedStudentRecord
from .services import seal_archive_for_student

logger = logging.getLogger(__name__)


def _seal(student_profile, reason):
    if student_profile is None:
        return
    try:
        seal_archive_for_student(student_profile, reason=reason)
    except Exception:
        # A snapshot failure must never block the delete the admin asked for,
        # but it does need to be visible in the logs.
        logger.exception(
            "Failed to archive student %s before deletion", getattr(student_profile, "student_id", "?")
        )


@receiver(pre_delete, sender=StudentProfile, dispatch_uid="alumni_seal_on_student_profile_delete")
def seal_on_student_profile_delete(sender, instance, **kwargs):
    _seal(instance, ArchivedStudentRecord.REASON_DELETED)


@receiver(pre_delete, sender=User, dispatch_uid="alumni_seal_on_student_user_delete")
def seal_on_student_user_delete(sender, instance, **kwargs):
    if getattr(instance, "role", "") != "student":
        return
    profile = StudentProfile.objects.filter(user=instance).select_related("user", "current_class").first()
    _seal(profile, ArchivedStudentRecord.REASON_DELETED)
