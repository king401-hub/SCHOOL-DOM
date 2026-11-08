"""Send (or preview) the daily WhatsApp attendance report to each school's
admin(s), without needing Celery.

    python manage.py send_daily_attendance_report
        Dry run: prints who would be messaged, and with what, for every
        active school. Sends nothing.

    python manage.py send_daily_attendance_report --commit
        Sends it for real, to every active school. Meant to be wired to a
        real OS cron entry on the VPS (crontab -e: 0 17 * * * cd
        /root/SCHOOL-DOM && ./venv/bin/python manage.py
        send_daily_attendance_report --commit) rather than relying on
        Celery beat - see [[project-no-celery-in-production]].

--school limits either mode to one school's code (its schema_name).
--date overrides which day's attendance to report (default: today) - useful
for testing against, or re-sending, a day that already has real data.
"""
from django.core.management.base import BaseCommand, CommandError
from django.utils.dateparse import parse_date

from core.tasks import send_daily_attendance_report


class Command(BaseCommand):
    help = "Preview or send the daily WhatsApp attendance report to each school's admin(s) (dry run unless --commit is given)."

    def add_arguments(self, parser):
        parser.add_argument("--school", default="", help="Limit to one school's code (its schema_name). Every active school if omitted.")
        parser.add_argument("--date", default="", help="YYYY-MM-DD to report on. Defaults to today.")
        parser.add_argument("--commit", action="store_true", help="Actually send the WhatsApp message. Without this it only prints what would be sent.")

    def handle(self, *args, **options):
        report_date = None
        if options["date"]:
            report_date = parse_date(options["date"])
            if not report_date:
                raise CommandError(f"--date {options['date']!r} is not a valid YYYY-MM-DD date.")

        results = send_daily_attendance_report(
            school_code=options["school"].strip(), today=report_date, dry_run=not options["commit"],
        )
        if not results:
            self.stdout.write(
                f'No active school matches "{options["school"]}", or it has no students or staff.' if options["school"]
                else "No active schools with any students or staff."
            )
            return

        for schema_name, result in results.items():
            s, st = result["students"], result["staff"]
            self.stdout.write(
                f"\n{schema_name}: students present={s['present']} absent={s['absent']} late={s['late']} "
                f"(of {s['total']}) | staff present={st['present']} absent={st['absent']} late={st['late']} (of {st['total']})"
            )
            for row in result["rows"]:
                name = row["admin"].get_full_name() or row["admin"].email
                if row["outcome"] == "dry_run":
                    self.stdout.write(f"  {name} ({row['phone']}): would send")
                elif row["outcome"] == "sent":
                    self.stdout.write(f"  {name}: sent to {row['phone']}")
                elif row["outcome"] == "skipped_no_phone":
                    self.stdout.write(self.style.WARNING(f"  {name}: no phone number on file"))
                else:
                    self.stderr.write(self.style.ERROR(f"  {name}: {row['outcome']}"))

        if not options["commit"]:
            self.stdout.write(self.style.WARNING("\nDry run - nothing was sent. Add --commit to send for real."))
