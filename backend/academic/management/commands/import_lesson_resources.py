import json
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from academic.bulk_import import import_lesson_resource


class Command(BaseCommand):
    help = (
        "Import lesson plan / scheme-of-work templates into the central resource bank "
        "teachers can pick from as a starting point. Source shape: "
        '{"subject": "Mathematics", "resources": [{"title", "grade_level"?, "description"?, '
        '"objectives"?, "activities"?, "resources"?, "assessment"?, "attachment"?}, ...]}. '
        "\"attachment\", if given, is a filename resolved relative to the manifest's own "
        "folder (or --attachments-dir). Safe to re-run: a resource matching an existing "
        "one by subject+title is updated in place, not duplicated."
    )

    def add_arguments(self, parser):
        parser.add_argument("source", help="Path to the subject-organized JSON manifest.")
        parser.add_argument(
            "--attachments-dir",
            default=None,
            help="Folder to resolve each resource's \"attachment\" filename against. Defaults to the manifest's own folder.",
        )
        parser.add_argument("--dry-run", action="store_true", help="Parse and validate without saving.")

    def handle(self, *args, **options):
        source = Path(options["source"]).resolve()
        if not source.exists():
            raise CommandError(f"Source not found: {source}")

        attachments_dir = Path(options["attachments_dir"]).resolve() if options["attachments_dir"] else source.parent

        with open(source, encoding="utf-8") as handle:
            data = json.load(handle)

        subject_name = str(data.get("subject") or "").strip()
        records = data.get("resources") or []
        if not subject_name:
            raise CommandError("subject is required.")
        if not isinstance(records, list) or not records:
            raise CommandError('"resources" must be a non-empty list.')

        cleaned = []
        for index, record in enumerate(records, start=1):
            title = str(record.get("title") or "").strip()
            if not title:
                raise CommandError(f"Resource #{index} is missing a title.")
            attachment_path = None
            attachment_name = str(record.get("attachment") or "").strip()
            if attachment_name:
                attachment_path = attachments_dir / attachment_name
                if not attachment_path.exists():
                    raise CommandError(f'Resource "{title}": attachment not found at {attachment_path}.')
            cleaned.append(
                {
                    "title": title,
                    "grade_level": str(record.get("grade_level") or "").strip(),
                    "description": str(record.get("description") or "").strip(),
                    "objectives": str(record.get("objectives") or "").strip(),
                    "activities": str(record.get("activities") or "").strip(),
                    "resources": str(record.get("resources") or "").strip(),
                    "assessment": str(record.get("assessment") or "").strip(),
                    "attachment_path": attachment_path,
                }
            )

        self.stdout.write(f"{source.name}: {subject_name} - {len(cleaned)} resource(s).")

        if options["dry_run"]:
            self.stdout.write(self.style.SUCCESS("Dry run complete. No database changes were made."))
            return

        created_count = 0
        updated_count = 0
        for record in cleaned:
            _resource, created = import_lesson_resource(subject_name=subject_name, **record)
            if created:
                created_count += 1
            else:
                updated_count += 1

        self.stdout.write(
            self.style.SUCCESS(f"Done: {created_count} new resource(s) created, {updated_count} updated.")
        )
