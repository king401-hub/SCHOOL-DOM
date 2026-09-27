"""Send (or preview) SchoolGate's weekly attendance SMS digest, without needing
Celery. Two uses:

    python manage.py send_weekly_reports --school cherished_child_school
        Dry run: prints exactly what each parent would be sent, sends nothing.
        This is the way to test the weekly report - run it any day of the
        week to see this week's attendance-to-date summarised the same way
        Friday's real digest would word it.

    python manage.py send_weekly_reports --school cherished_child_school --commit
        Sends it for real. Meant to be wired to a real OS cron entry on the
        VPS (crontab -e: 0 17 * * 5 cd /root/SCHOOL-DOM && ./venv/bin/python
        manage.py send_weekly_reports --commit) rather than relying on Celery
        beat - see [[project-no-celery-in-production]].

Without --school, every active SchoolGate school gets it (only with --commit;
the dry run without --school lists them so a slip of the finger can't
preview-then-accidentally-message every school's parents in one command).
"""
from django.core.management.base import BaseCommand, CommandError

from rfid_attendance.services import send_weekly_reports


class Command(BaseCommand):
    help = "Preview or send SchoolGate's weekly attendance SMS digest (dry run unless --commit is given)."

    def add_arguments(self, parser):
        parser.add_argument("--school", default="", help="Limit to one school's code (its schema_name). Every active SchoolGate school if omitted.")
        parser.add_argument("--commit", action="store_true", help="Actually send the SMS. Without this it only prints what would be sent.")

    def handle(self, *args, **options):
        school_code = options["school"].strip()
        if options["commit"] and not school_code:
            raise CommandError("Pass --school to send for real. Run without --commit first to see who this would reach.")

        results = send_weekly_reports(school_code=school_code, dry_run=not options["commit"])
        if not results:
            self.stdout.write(
                f'No active SchoolGate school matches "{school_code}".' if school_code
                else "No active SchoolGate schools."
            )
            return

        for schema_name, result in results.items():
            self.stdout.write(f"\n{schema_name}: {result['sent']} to send, {result['skipped']} skipped, {result['failed']} failed")
            for row in result["rows"]:
                name = row["profile"].user.get_full_name() or row["profile"].user.email
                if row["outcome"] == "dry_run":
                    self.stdout.write(f"  {name}: {row['message']}")
                elif row["outcome"] == "sent":
                    self.stdout.write(f"  {name}: sent to {row['phone']}")
                elif row["outcome"].startswith("skipped"):
                    self.stdout.write(self.style.WARNING(f"  {name}: {row['outcome']}"))
                else:
                    self.stderr.write(self.style.ERROR(f"  {name}: {row['outcome']}"))

        if not options["commit"]:
            self.stdout.write(self.style.WARNING("\nDry run - nothing was sent. Add --commit (and --school) to send for real."))
