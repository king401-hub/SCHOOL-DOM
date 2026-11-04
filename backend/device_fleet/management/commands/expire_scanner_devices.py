"""Suspend-by-expiry every scanner device whose licensed access has run out -
without needing Celery (see [[project-no-celery-in-production]] and
device_fleet.services.expire_scanner_devices's own docstring for why a cron
entry, not Celery beat, is what actually runs this).

    python manage.py expire_scanner_devices
        Dry run: prints which devices would be expired without touching
        anything.

    python manage.py expire_scanner_devices --commit
        Does it for real. Meant to run on a real OS cron entry on the VPS,
        e.g. once an hour:
            0 * * * * cd /root/SCHOOL-DOM && ./venv/bin/python manage.py expire_scanner_devices --commit
        An admin renews an expired device the same way it was first
        provisioned, by assigning it to a school again (assign_school
        recomputes a fresh access_expires_at and reactivates it).
"""
from django.core.management.base import BaseCommand

from device_fleet.services import expire_scanner_devices


class Command(BaseCommand):
    help = "Expire scanner devices whose access_expires_at has passed (dry run unless --commit is given)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--commit", action="store_true",
            help="Actually expire the devices. Without this it only prints what would happen.",
        )

    def handle(self, *args, **options):
        rows = expire_scanner_devices(dry_run=not options["commit"])

        if not rows:
            self.stdout.write("No device's access has expired.")
            return

        for row in rows:
            device = row["device"]
            school_name = device.tenant.name if device.tenant else "no school"
            if row["outcome"] == "dry_run":
                self.stdout.write(f"  {device.device_id} ({school_name}): would expire")
            else:
                self.stdout.write(self.style.WARNING(f"  {device.device_id} ({school_name}): expired"))

        if not options["commit"]:
            self.stdout.write(self.style.WARNING("\nDry run - nothing was changed. Add --commit to run for real."))
