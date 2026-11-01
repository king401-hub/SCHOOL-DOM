"""Mark every student a school's RFID gate terminal never saw today as
absent, once that school's own clock-out window has closed - without
needing Celery, and without the terminal having to be online at all (see
[[project-no-celery-in-production]] and
rfid_attendance.services.mark_schoolgate_absentees's own docstring for why).

    python manage.py mark_absentees
        Dry run across every school with an RFID gate configured: prints who
        would be marked absent (and in which school) without writing
        anything or sending any SMS.

    python manage.py mark_absentees --commit
        Does it for real. Meant to run often via a real OS cron entry on the
        VPS rather than relying on Celery beat, e.g. every 15 minutes:
            */15 * * * * cd /root/SCHOOL-DOM && ./venv/bin/python manage.py mark_absentees --commit
        Each school is only acted on once its own clock-out window has
        actually closed (in its own local time), so running this often is
        exactly the point - it's what lets the marking happen close to that
        moment for every school regardless of timezone, without having to
        schedule one cron entry per school.

    python manage.py mark_absentees --school cherished_child_school --commit
        Limit to one school's code (its schema_name).
"""
from django.core.management.base import BaseCommand

from rfid_attendance.services import mark_schoolgate_absentees


class Command(BaseCommand):
    help = "Mark students absent once their school's RFID gate clock-out window has closed (dry run unless --commit is given)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--school", default="",
            help="Limit to one school's code (its schema_name). Every school with an RFID gate configured if omitted.",
        )
        parser.add_argument(
            "--commit", action="store_true",
            help="Actually mark students absent and send the parent SMS. Without this it only prints what would happen.",
        )

    def handle(self, *args, **options):
        school_code = options["school"].strip()
        results = mark_schoolgate_absentees(school_code=school_code, dry_run=not options["commit"])

        if not results:
            self.stdout.write(
                f'No school matches "{school_code}" with an RFID gate configured.' if school_code
                else "No school has an RFID gate configured yet."
            )
            return

        for schema_name, result in results.items():
            if not result["ran"]:
                self.stdout.write(f"{schema_name}: skipped ({result['reason']})")
                continue
            rows = result["rows"]
            if not rows:
                self.stdout.write(f"{schema_name}: nobody left to mark absent")
                continue
            self.stdout.write(f"\n{schema_name}: {len(rows)} student(s)")
            for row in rows:
                name = row["profile"].user.get_full_name() or row["profile"].user.email
                if row["outcome"] == "marked_absent":
                    self.stdout.write(self.style.WARNING(f"  {name}: marked absent"))
                elif row["outcome"] == "dry_run":
                    self.stdout.write(f"  {name}: would be marked absent")
                else:
                    self.stdout.write(self.style.ERROR(f"  {name}: {row['outcome']}"))

        if not options["commit"]:
            self.stdout.write(self.style.WARNING("\nDry run - nothing was marked, no SMS sent. Add --commit to run for real."))
