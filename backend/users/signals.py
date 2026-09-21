"""User model signals — auto-provision parent virtual accounts on creation."""
from django.db import transaction
from django.db.models.signals import post_save
from django.dispatch import receiver


@receiver(post_save, sender="users.User")
def on_user_created(sender, instance, created, **kwargs):
    if not created or instance.role != "parent":
        return

    user_id = str(instance.id)

    def _provision():
        # A background thread, not Celery. This used to call
        # provision_parent_dva_task.delay() first; with no broker that blocked
        # ~110 seconds before raising (so creating a parent - or importing a
        # class of them - hung), and with a broker but no worker it queued the
        # task forever and no account was ever made. The pool is small and
        # dedicated, so a bulk import queues instead of hitting Paystack with
        # hundreds of calls at once, and a slow Paystack cannot delay receipts.
        from core.background import run_in_background
        from finance.services import provision_parent_dva_with_retries

        run_in_background(
            lambda: provision_parent_dva_with_retries(user_id),
            name=f"parent-dva-{user_id}",
            pool="provisioning",
            workers=2,
        )

    # Run after the current DB transaction commits so the user row is visible
    # to the worker thread and the Paystack calls never delay the save.
    transaction.on_commit(_provision)
