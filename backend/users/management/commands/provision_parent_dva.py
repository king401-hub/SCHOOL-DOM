"""Management command to backfill Paystack DVAs for existing parents who don't have one."""
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Provision a Paystack virtual account for every parent without one."

    def add_arguments(self, parser):
        parser.add_argument(
            "--school",
            default="",
            help="Limit to a specific school schema_name",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Print counts without provisioning anything",
        )

    def handle(self, *args, **options):
        from users.models import User
        from finance.models import ParentVirtualAccount
        from finance.services import provision_parent_dva

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

        # Done here and now, one parent at a time, rather than queued through
        # Celery: a backfill run by hand should report what actually happened,
        # and must not depend on a broker and worker being up.
        created = skipped = failed = 0
        for u in pending:
            try:
                result = provision_parent_dva(str(u.id))
            except Exception as exc:
                failed += 1
                self.stderr.write(self.style.ERROR(f"  {u.email}: {exc}"))
                continue
            if result.get("status") == "ok":
                created += 1
            else:
                skipped += 1
                self.stdout.write(f"  skipped {u.email}: {result.get('reason', result.get('status'))}")

        self.stdout.write(self.style.SUCCESS(
            f"Provisioned {created}, skipped {skipped}, failed {failed}."
        ))
