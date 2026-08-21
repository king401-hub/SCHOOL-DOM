from django.contrib.auth import get_user_model
from django.conf import settings
from django.core.mail import send_mail
from django.core.management.base import BaseCommand

# School-level roles that can touch the CBT license / Admin Sync desktop app -
# same set licensing/views.py's LICENSE_ROLES uses, minus the platform-level
# super_admin role (they don't run a school's own CBT app).
CBT_ADMIN_ROLES = ["school_admin", "principal", "school_superadmin", "accountant"]

SUBJECT = 'Admin Sync App: Fix for "Update Available" Loop'

BODY = """Hello,

If your SchoolDom Admin Sync (Windows 7) app keeps showing "Update Available" and clicking Update Now doesn't fix it, this is a known issue - some antivirus software briefly locks the app file during the update, causing it to fail silently and repeat the prompt.

To fix it:
1. Fully close the app - check Task Manager for "SchoolDom.Cbt.Win7.exe" and End Task it if it's still listed.
2. Go to https://schooldom.academy/app/download/admin/ in your browser, download the installer, and run it directly (instead of using the in-app "Update Now" button).
3. Once installed, the title bar should read "v0.2.11.0".

If it still won't update after that, please contact support.

- SchoolDom
"""


class Command(BaseCommand):
    help = (
        "One-off broadcast: emails every school's CBT-eligible admin about the "
        "Admin Sync Win7 app's update-loop fix. Defaults to a dry run (lists "
        "recipients without sending) - pass --send to actually email them."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--send",
            action="store_true",
            help="Actually send the emails. Without this flag, only lists recipients.",
        )

    def handle(self, *args, **options):
        User = get_user_model()
        recipients = sorted(set(
            User.objects.filter(role__in=CBT_ADMIN_ROLES, is_active=True)
            .exclude(email="")
            .exclude(email__isnull=True)
            .values_list("email", flat=True)
        ))

        if not options["send"]:
            self.stdout.write(f"DRY RUN - would email {len(recipients)} recipient(s):")
            for email in recipients:
                self.stdout.write(f"  {email}")
            self.stdout.write(self.style.WARNING("Re-run with --send to actually email them."))
            return

        sent, failed = 0, []
        for email in recipients:
            try:
                send_mail(SUBJECT, BODY, settings.DEFAULT_FROM_EMAIL, [email], fail_silently=False)
                sent += 1
            except Exception as exc:
                failed.append((email, str(exc)))

        self.stdout.write(self.style.SUCCESS(f"Sent {sent}/{len(recipients)} emails."))
        if failed:
            self.stdout.write(self.style.ERROR(f"{len(failed)} failed:"))
            for email, error in failed:
                self.stdout.write(f"  {email}: {error}")
