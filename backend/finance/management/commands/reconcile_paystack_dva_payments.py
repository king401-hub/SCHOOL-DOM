"""
Recovers fee payments that Paystack charged successfully but SchoolDom never
recorded, because the webhook that should have credited them was crashing
(two separate bugs fixed alongside this command: a null-metadata
AttributeError, and a "FOR UPDATE on the nullable side of an outer join"
Postgres error - see finance/services.py process_paystack_webhook's
dedicated_nuban branch and process_virtual_account_payment). Paystack retries
a failed webhook delivery for a while and then gives up, so any transfer
older than that retry window needs this one-off backfill.

Walks Paystack's own transaction list for a date range, finds successful
dedicated_nuban (virtual account bank transfer) charges that either have no
Transaction row here at all, OR have one stuck at allocation_status=pending
(process_virtual_account_payment creates the Transaction row before running
the fee-allocation query that was crashing, so a failed call still leaves a
row behind - checking existence alone misses these entirely), and replays
each one through the normal webhook processing path so it gets allocated
exactly as if the webhook had worked. Safe to re-run: anything already
allocated is skipped.
"""
from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

from finance.services import _paystack_base_url, _paystack_headers, _paystack_json, process_paystack_webhook
from finance.models import Transaction


class Command(BaseCommand):
    help = (
        "Replay successful Paystack dedicated_nuban (DVA bank transfer) charges that "
        "have no matching Transaction row here, to recover payments lost to the "
        "webhook crash. Use --dry-run first to see what would be recovered."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--since-days", type=int, default=60,
            help="How many days back to scan Paystack's transaction history (default 60).",
        )
        parser.add_argument(
            "--dry-run", action="store_true",
            help="List what would be recovered without writing anything.",
        )

    def handle(self, *args, **options):
        import requests

        since_days = options["since_days"]
        dry_run = options["dry_run"]
        date_from = (timezone.now() - timedelta(days=since_days)).strftime("%Y-%m-%dT%H:%M:%S")
        date_to = timezone.now().strftime("%Y-%m-%dT%H:%M:%S")

        candidates = []
        page = 1
        while True:
            resp = requests.get(
                f"{_paystack_base_url()}/transaction",
                headers=_paystack_headers(),
                params={
                    "perPage": 50,
                    "page": page,
                    "status": "success",
                    "from": date_from,
                    "to": date_to,
                },
                timeout=30,
            )
            body = _paystack_json(resp)
            if not body.get("status"):
                self.stderr.write(self.style.ERROR(f"Paystack list failed: {body.get('message')}"))
                return
            rows = body.get("data") or []
            for row in rows:
                if row.get("channel") == "dedicated_nuban":
                    candidates.append(row)
            meta = body.get("meta") or {}
            if page >= int(meta.get("pageCount") or 1):
                break
            page += 1

        self.stdout.write(f"Found {len(candidates)} successful dedicated_nuban charge(s) in the last {since_days} day(s).")

        # A row that exists but is still ALLOCATION_PENDING means a prior call
        # created the Transaction and then crashed before allocating it to any
        # fee - that needs replaying exactly like a genuinely missing one.
        done_refs = set(
            Transaction.objects.filter(
                paystack_ref__in=[c.get("reference") for c in candidates]
            ).exclude(allocation_status=Transaction.ALLOCATION_PENDING).values_list("paystack_ref", flat=True)
        )

        missing = [c for c in candidates if c.get("reference") not in done_refs]
        self.stdout.write(f"{len(missing)} of those are missing or stuck pending and would be recovered.")

        for row in missing:
            reference = row.get("reference")
            amount_naira = (row.get("amount") or 0) / 100
            self.stdout.write(f"  - {reference}: NGN {amount_naira:,.2f} (customer={row.get('customer', {}).get('email')})")

        if dry_run:
            self.stdout.write(self.style.WARNING("Dry run - nothing was written."))
            return

        recovered, failed = 0, 0
        for row in missing:
            reference = row.get("reference")
            try:
                result = process_paystack_webhook({"event": "charge.success", "data": row})
                self.stdout.write(f"  recovered {reference}: {result}")
                recovered += 1
            except Exception as exc:
                self.stderr.write(self.style.ERROR(f"  FAILED {reference}: {exc}"))
                failed += 1

        self.stdout.write(self.style.SUCCESS(f"Recovered {recovered} payment(s), {failed} failed."))
