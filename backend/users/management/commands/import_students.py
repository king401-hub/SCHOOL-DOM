"""Import a CSV of students into one school from the command line.

    python manage.py import_students --school cherished_child_school --file students.csv
    python manage.py import_students --school cherished_child_school --file students.csv --commit

Without --commit nothing is saved: it prints what an import would do, which is
the same check the Students > "Import from spreadsheet" screen shows. With
--commit it creates the students exactly as that screen does (users.student_import),
then writes each student's first password to a login sheet, because passwords
are stored hashed and cannot be read back later.
"""
import csv
import os
import time

from django.core.management.base import BaseCommand, CommandError

from users import student_import as si


class Command(BaseCommand):
    help = "Import a CSV of students into a school (dry run unless --commit is given)."

    def add_arguments(self, parser):
        parser.add_argument("--school", required=True, help="The school's code (its schema_name), e.g. cherished_child_school.")
        parser.add_argument("--file", required=True, help="Path to the CSV file.")
        parser.add_argument("--commit", action="store_true", help="Actually create the students. Without this it only reports.")
        parser.add_argument("--email-domain", default=si.DEFAULT_EMAIL_DOMAIN, help="Domain for logins made from a student's name (default %(default)s).")
        parser.add_argument("--assign-tokens", action="store_true", help="Give each new student an activation token (uses the school's token pool).")
        parser.add_argument(
            "--class-map",
            action="append",
            default=[],
            metavar='"TEXT IN FILE=CLASS"',
            help='Send a class name from the file to one of the school\'s classes, e.g. --class-map "SS2/ART DEPARTMENT=SS 2 - Art". Repeatable.',
        )
        parser.add_argument("--default-class", default="", help="Class for rows that have no class in the file.")
        parser.add_argument("--admin-email", default="", help="Run as this school admin (default: the school's first active admin).")
        parser.add_argument("--skip-errors", action="store_true", help="Import the good rows even if some rows have problems.")
        parser.add_argument("--login-sheet", default="", help="Where to write the passwords (default: student-logins-<school>-<time>.csv here).")

    def handle(self, *args, **options):
        from core.models import SchoolTenant
        from users.models import User

        code = options["school"].strip()
        school = SchoolTenant.objects.filter(schema_name__iexact=code).first()
        if not school:
            raise CommandError(f'No school with the code "{code}".')

        admin = None
        if options["admin_email"]:
            admin = User.objects.filter(tenant=school, email__iexact=options["admin_email"].strip()).first()
        else:
            for role in ("school_admin", "principal"):
                admin = User.objects.filter(tenant=school, role=role, is_active=True).order_by("email").first()
                if admin:
                    break
        if not admin:
            raise CommandError(f"{school.name} has no admin to run the import as. Pass --admin-email.")

        try:
            with open(options["file"], "rb") as handle:
                rows = si.read_upload(handle)
        except OSError as exc:
            raise CommandError(f"Cannot read {options['file']}: {exc}")
        except si.ImportFileError as exc:
            raise CommandError(str(exc))

        ctx = si.ImportContext(admin, email_domain=options["email_domain"])
        class_map = {}
        for item in options["class_map"]:
            source, separator, target = item.rpartition("=")
            if not separator or not source.strip() or not target.strip():
                raise CommandError(f'--class-map wants "TEXT IN FILE=CLASS", got "{item}".')
            class_map[source.strip()] = str(self._find_class(ctx, target).id)
        default_class_id = str(self._find_class(ctx, options["default_class"]).id) if options["default_class"] else ""
        common = {"default_class_id": default_class_id, "class_map": class_map, "email_domain": options["email_domain"]}

        preview = si.build_preview(admin, rows, **common)
        self._report(school, admin, preview)

        counts = preview["counts"]
        if not options["commit"]:
            self.stdout.write(self.style.WARNING("\nDry run - nothing was saved. Add --commit to import."))
            return
        if counts["error"] and not options["skip_errors"]:
            raise CommandError(
                f"{counts['error']} row(s) have problems (listed above). Fix them, map the classes with --class-map, "
                "or add --skip-errors to import the rest. Nothing was saved."
            )
        if not counts["create"]:
            self.stdout.write("Nobody new to add.")
            return

        self._commit(school, admin, rows, preview, options, common)

    # -- helpers ---------------------------------------------------------

    def _find_class(self, ctx, text):
        text = str(text).strip()
        if text in ctx.classes_by_id:
            return ctx.classes_by_id[text]
        wanted = text.casefold()
        matches = [item for item in ctx.classes if ctx.class_label(item).casefold() == wanted]
        if not matches:
            key = si.class_key(text)
            matches = ctx.class_index.get(key) or ctx.name_index.get(key) or []
        if len(matches) != 1:
            labels = ", ".join(ctx.class_label(item) for item in ctx.classes) or "(none yet)"
            raise CommandError(f'"{text}" is not one of this school\'s classes. Classes: {labels}')
        return matches[0]

    def _report(self, school, admin, preview):
        counts = preview["counts"]
        self.stdout.write(f"School: {school.name} ({school.schema_name}) - importing as {admin.email}")
        self.stdout.write(
            f"{counts['create']} to add, {counts['skip']} already there, {counts['error']} with problems"
            f" (emails will end @{preview['email_domain']})"
        )
        self.stdout.write("\nClasses in the file:")
        for item in preview["classes"]:
            target = item["class_label"] or "NOT MATCHED  <- use --class-map"
            self.stdout.write(f"  {item['source'] or '(none)':<32} {item['count']:>3}  ->  {target}")
        self.stdout.write("\nThe school's classes: " + (", ".join(item["label"] for item in preview["available_classes"]) or "(none yet)"))
        problems = [row for row in preview["rows"] if row["status"] == "error"]
        if problems:
            self.stdout.write("\nProblems:")
            for row in problems:
                name = f"{row.get('first_name', '')} {row.get('last_name', '')}".strip() or "(no name)"
                self.stdout.write(f"  line {row['line']}: {name} - {row['message']}")
        warned = [row for row in preview["rows"] if row["status"] == "create" and row["warnings"]]
        if warned:
            self.stdout.write("\nWarnings (the student is still added):")
            for row in warned:
                self.stdout.write(f"  line {row['line']}: {row['first_name']} {row['last_name']} - {' '.join(row['warnings'])}")

    def _commit(self, school, admin, rows, preview, options, common):
        creating = {row["line"] for row in preview["rows"] if row["status"] == "create"}
        queue = [row for row in rows if row["line"] in creating]
        created, skipped, failed, warnings = [], [], [], []
        tokens = 0
        token_message = ""
        for start in range(0, len(queue), si.MAX_COMMIT_BATCH):
            result = si.commit_rows(
                admin, queue[start:start + si.MAX_COMMIT_BATCH], assign_tokens=options["assign_tokens"], **common
            )
            created += result["created"]
            skipped += result["skipped"]
            failed += result["failed"]
            warnings += result["warnings"]
            tokens += result["tokens_assigned"]
            token_message = token_message or result["token_message"]
            self.stdout.write(f"  {min(start + si.MAX_COMMIT_BATCH, len(queue))} of {len(queue)} done")

        sheet = options["login_sheet"] or f"student-logins-{school.schema_name}-{time.strftime('%Y%m%d-%H%M%S')}.csv"
        if created:
            self._write_sheet(sheet, created)

        self.stdout.write(self.style.SUCCESS(f"\nAdded {len(created)} student(s)."))
        if skipped:
            self.stdout.write(f"{len(skipped)} skipped (already in the class).")
        for item in failed:
            self.stderr.write(self.style.ERROR(f"  not added - line {item['line']}, {item['name']}: {item['message']}"))
        for text in warnings:
            self.stdout.write(self.style.WARNING(f"  {text}"))
        if options["assign_tokens"]:
            self.stdout.write(f"{tokens} activation token(s) assigned.")
            if token_message:
                self.stdout.write(self.style.WARNING(f"  Tokens: {token_message}"))
        if created:
            self.stdout.write(self.style.WARNING(
                f"\nPasswords are in {os.path.abspath(sheet)} - this is the only copy, they cannot be looked up later. "
                "Copy it off the server and delete it."
            ))
            self.stdout.write(
                "Parent virtual accounts are being created in the background. If any were missed, run:\n"
                f"  python manage.py provision_parent_dva --school {school.schema_name}"
            )

    def _write_sheet(self, path, created):
        # Created private from the start: the file holds every new student's password.
        descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(descriptor, "w", newline="", encoding="utf-8-sig") as handle:
            writer = csv.writer(handle)
            writer.writerow(["Student ID", "Name", "Class", "Login email", "Password", "Guardian", "Guardian phone"])
            for item in created:
                writer.writerow([
                    item["student_id"], item["name"], item["class_label"], item["email"],
                    item["password"], item["guardian_name"], item["guardian_phone"],
                ])
