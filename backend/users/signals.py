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
        # Try Celery first (production path — non-blocking).
        try:
            from finance.tasks import provision_parent_dva_task
            provision_parent_dva_task.delay(user_id)
            return
        except Exception:
            pass  # Broker not available — fall through to synchronous path.

        # Synchronous fallback (development without a Celery worker).
        try:
            from finance.models import ParentVirtualAccount
            from finance.services import provision_parent_virtual_account
            from users.models import User as UserModel

            parent = UserModel.objects.select_related("tenant").get(id=user_id, role="parent")
            if not ParentVirtualAccount.objects.filter(parent=parent, is_active=True).exists():
                provision_parent_virtual_account(parent, actor=None)
        except Exception:
            # School subaccount not configured yet, or Paystack error —
            # admin can provision manually from the Finance page.
            pass

    # Run after the current DB transaction commits so the user row is
    # visible to the Celery worker and Paystack calls don't block the save.
    transaction.on_commit(_provision)
