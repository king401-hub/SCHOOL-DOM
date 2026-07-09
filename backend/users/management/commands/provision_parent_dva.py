"""Management command to backfill Paystack DVAs for existing parents who don't have one."""
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Queue Paystack DVA provisioning for all parents without a virtual account."

    def add_arguments(self, parser):
        parser.add_argument(
            "--school",
            default="",
            help="Limit to a specific school schema_name",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Print counts without queuing tasks",
        )

    def handle(self, *args, **options):
        from users.models import User
        from finance.models import ParentVirtualAccount
        from finance.tasks import provision_parent_dva_task

        already_provisioned = set(
            ParentVirtualAccount.objects.filter(is_active=True).values_list("parent_id", flat=True)
        )
        qs = User.objects.filter(role="parent", is_active=True).select_related("tenant")
        if options["school"]:
            qs = qs.filter(tenant__schema_name=options["school"])

        pending = [u for u in qs if u.id not in already_provisioned]
        self.stdout.write(f"Found {len(pending)} parent(s) without a DVA.")

        if options["dry_run"]:
            for u in pending:
                self.stdout.write(f"  [dry-run] {u.email} (tenant: {getattr(u.tenant, 'schema_name', '?')})")
            return

        queued = 0
        for u in pending:
            provision_parent_dva_task.delay(str(u.id))
            queued += 1

        self.stdout.write(self.style.SUCCESS(f"Queued {queued} provisioning task(s)."))
