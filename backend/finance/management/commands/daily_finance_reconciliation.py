"""
Daily automated check for the two classes of "money received but not
correctly reflected" issue found while investigating a parent's stuck
NGN11,500 overpayment on 2026-10-30 (Emmanuel Udeze Bonaventure):

1. A Paystack DVA (bank transfer) charge Paystack marked successful that
   never got a matching, fully-allocated Transaction row here - reuses the
   existing reconcile_paystack_dva_payments --dry-run scan, so there is one
   source of truth for "what counts as stuck."
2. A student wallet sitting on a credit balance while that same student has
   an outstanding fee - the exact shape of the Emmanuel Udeze case, which
   the DVA scan above cannot see once the payment itself was already
   correctly recorded (the gap was downstream, in applying it to a fee that
   didn't exist yet when the payment landed).

Both are read-only (the DVA scan runs with --dry-run; nothing here writes
anything else). Meant to run once a day from cron - this project runs no
Celery in production - e.g.:
    0 6 * * * cd /root/SCHOOL-DOM && ./venv/bin/python manage.py daily_finance_reconciliation
Only sends an email (to FINANCE_ALERT_EMAIL, if set) when something is
actually found; a clean run prints a one-line "nothing found" and exits.
"""
import io
import os

from django.conf import settings
from django.core.mail import send_mail
from django.core.management import call_command
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = (
        "Daily read-only scan for stuck Paystack DVA payments and student wallet "
        "credit sitting next to an outstanding fee; emails a summary (to "
        "FINANCE_ALERT_EMAIL) only when something is found."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--since-days", type=int, default=3,
            help="DVA scan window in days (default 3, to overlap successive daily runs).",
        )

    def handle(self, *args, **options):
        since_days = options["since_days"]
        findings = []

        stuck_dva = self._scan_stuck_dva(since_days)
        if stuck_dva:
            findings.append(("Stuck DVA payments", stuck_dva))

        unswept_credit = self._scan_unswept_wallet_credit()
        if unswept_credit:
            findings.append(("Students with wallet credit sitting next to an outstanding fee", unswept_credit))

        if not findings:
            self.stdout.write(self.style.SUCCESS("Daily finance reconciliation: nothing found."))
            return

        report = self._format_report(findings)
        self.stdout.write(report)
        self._send_alert(report)

    def _scan_stuck_dva(self, since_days):
        buffer = io.StringIO()
        try:
            call_command(
                "reconcile_paystack_dva_payments", "--dry-run", f"--since-days={since_days}",
                stdout=buffer, stderr=buffer,
            )
        except Exception as exc:
            return [f"- DVA scan itself raised an exception: {exc}"]

        output = buffer.getvalue()
        rows = [line.strip() for line in output.splitlines() if line.strip().startswith("- ")]
        if not rows and "ERROR" in output:
            last_line = output.strip().splitlines()[-1] if output.strip() else "no output"
            rows.append(f"- DVA scan reported an error: {last_line}")
        return rows

    def _scan_unswept_wallet_credit(self):
        from finance.models import SchoolFee, Wallet

        outstanding_user_ids = set(
            SchoolFee.objects.filter(
                status__in=[SchoolFee.STATUS_PENDING, SchoolFee.STATUS_OVERDUE, SchoolFee.STATUS_PARTIAL],
            ).values_list("student__user_id", flat=True)
        )
        if not outstanding_user_ids:
            return []

        wallets = (
            Wallet.objects.filter(balance__gt=0, user_id__in=outstanding_user_ids)
            .select_related("user", "user__tenant")
        )
        return [
            f"- {wallet.user.get_full_name() or wallet.user.email}: NGN {wallet.balance:,.2f} credit "
            f"(school: {getattr(wallet.user.tenant, 'name', 'unknown')})"
            for wallet in wallets
        ]

    def _format_report(self, findings):
        lines = ["Daily finance reconciliation found something that needs a look:", ""]
        for title, rows in findings:
            lines.append(f"{title} ({len(rows)}):")
            lines.extend(rows[:25])
            if len(rows) > 25:
                lines.append(f"  ... and {len(rows) - 25} more")
            lines.append("")
        return "\n".join(lines)

    def _send_alert(self, report):
        recipient = os.getenv("FINANCE_ALERT_EMAIL", "")
        if not recipient:
            self.stdout.write(self.style.WARNING(
                "FINANCE_ALERT_EMAIL is not set - skipping the email, see the findings printed above."
            ))
            return
        from_email = getattr(settings, "DEFAULT_FROM_EMAIL", "noreply@schooldom.academy")
        send_mail(
            subject="SchoolDom: daily finance reconciliation found something",
            message=report,
            from_email=from_email,
            recipient_list=[recipient],
            fail_silently=True,
        )
