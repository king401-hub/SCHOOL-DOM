"""Give the students of an imported CSV fresh passwords and a new login sheet.

    python manage.py reset_student_passwords --school cherished_child_school --file students.csv
    python manage.py reset_student_passwords --school cherished_child_school --file students.csv --commit

For when the login sheet written by import_students was lost: passwords are
stored hashed and cannot be read back, so the only way to hand a family a
working password is to set a new one.

Only the students listed in the CSV are considered (matched by first name,
surname and class, the same way the importer spots someone already there), so
nobody else in the school is touched. A student who has already signed in is
skipped unless --include-signed-in is given, because somebody already holds
that password and a reset would lock them out. Without --commit it only
reports.
"""
from django.core.management.base import CommandError

from users import student_import as si
from users.management.commands.import_students import Command as ImportStudentsCommand


class Command(ImportStudentsCommand):
    help = "Set new passwords for the students listed in a CSV and write a login sheet (dry run unless --commit)."

    def add_arguments(self, parser):
        parser.add_argument("--school", required=True, help="The school's code (its schema_name).")
        parser.add_argument("--file", required=True, help="The CSV the students were imported from.")
        parser.add_argument("--commit", action="store_true", help="Actually change the passwords. Without this it only reports.")
        parser.add_argument("--include-signed-in", action="store_true", help="Also reset students who have already signed in (locks out whoever has their password).")
        parser.add_argument("--class-map", action="append", default=[], metavar='"TEXT IN FILE=CLASS"', help="As for import_students.")
        parser.add_argument("--default-class", default="", help="As for import_students.")
        parser.add_argument("--admin-email", default="", help="Resolve classes as this school admin (default: the school's first active admin).")
        parser.add_argument("--login-sheet", default="", help="Where to write the new passwords (default: student-logins-reset-<school>-<time>.csv here).")

    def handle(self, *args, **options):
        import time

        from core.models import SchoolTenant
        from users.models import StudentProfile, User

        school = SchoolTenant.objects.filter(schema_name__iexact=options["school"].strip()).first()
        if not school:
            raise CommandError(f'No school with the code "{options["school"].strip()}".')

        admin = None
        if options["admin_email"]:
            admin = User.objects.filter(tenant=school, email__iexact=options["admin_email"].strip()).first()
        else:
            for role in ("school_admin", "principal"):
                admin = User.objects.filter(tenant=school, role=role, is_active=True).order_by("email").first()
                if admin:
                    break
        if not admin:
            raise CommandError(f"{school.name} has no admin to run this as. Pass --admin-email.")

        try:
            with open(options["file"], "rb") as handle:
                rows = si.read_upload(handle)
        except OSError as exc:
            raise CommandError(f"Cannot read {options['file']}: {exc}")
        except si.ImportFileError as exc:
            raise CommandError(str(exc))

        ctx = si.ImportContext(admin, email_domain=si.DEFAULT_EMAIL_DOMAIN)
        for item in options["class_map"]:
            source, separator, target = item.rpartition("=")
            if not separator or not source.strip() or not target.strip():
                raise CommandError(f'--class-map wants "TEXT IN FILE=CLASS", got "{item}".')
            ctx.class_map[si.source_key(source)] = str(self._find_class(ctx, target).id)
        if options["default_class"]:
            ctx.default_class = self._find_class(ctx, options["default_class"])

        to_reset, signed_in, not_found, bad_class = [], [], [], []
        for row in rows:
            first, last = si.tidy_name(row.get("first_name")), si.tidy_name(row.get("last_name"))
            label = f"line {row['line']}: {first} {last}".strip()
            class_obj, message = ctx.resolve_class(row.get("class"))
            if not class_obj:
                bad_class.append(f"{label} - {message}")
                continue
            profile = (
                StudentProfile.objects.select_related("user", "current_class")
                .filter(user__tenant=school, user__first_name__iexact=first, user__last_name__iexact=last, current_class=class_obj)
                .first()
            )
            if not profile:
                not_found.append(f"{label} - not in {ctx.class_label(class_obj)}")
            elif not options["include_signed_in"] and profile.user.login_history.filter(status="success").exists():
                signed_in.append(label)
            else:
                to_reset.append((label, profile))

        self.stdout.write(f"School: {school.name} ({school.schema_name})")
        self.stdout.write(
            f"{len(to_reset)} to reset, {len(signed_in)} already signed in (left alone), "
            f"{len(not_found)} not found, {len(bad_class)} with an unknown class"
        )
        for title, items in (("Already signed in - skipped:", signed_in), ("Not found:", not_found), ("Class not recognised:", bad_class)):
            if items:
                self.stdout.write(f"\n{title}")
                for text in items:
                    self.stdout.write(f"  {text}")

        if not options["commit"]:
            self.stdout.write(self.style.WARNING("\nDry run - nothing was changed. Add --commit to reset these passwords."))
            return
        if not to_reset:
            self.stdout.write("Nobody to reset.")
            return

        sheet = options["login_sheet"] or f"student-logins-reset-{school.schema_name}-{time.strftime('%Y%m%d-%H%M%S')}.csv"
        entries = []
        for _label, profile in to_reset:
            password = si.generate_password()
            profile.user.set_password(password)
            profile.user.save(update_fields=["password"])
            entries.append({
                "student_id": profile.student_id,
                "name": profile.user.get_full_name(),
                "class_label": ctx.class_label(profile.current_class),
                "email": profile.user.email,
                "password": password,
                "guardian_name": profile.guardian_name,
                "guardian_phone": profile.guardian_phone,
            })
        self._write_sheet(sheet, entries)

        import os

        self.stdout.write(self.style.SUCCESS(f"\nNew passwords set for {len(entries)} student(s)."))
        self.stdout.write(self.style.WARNING(
            f"They are in {os.path.abspath(sheet)} - the only copy, they cannot be looked up later. "
            "Copy it off the server BEFORE deleting anything."
        ))
