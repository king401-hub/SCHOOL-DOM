"""Give every existing teacher an HR record (StaffProfile), one-off.

    python manage.py backfill_teacher_staff_profiles
    python manage.py backfill_teacher_staff_profiles --school cherished_child_school --commit

A teacher created by an admin never got a StaffProfile at all until they
happened to visit their own staff self-service page themselves (most never
do) - so every teacher created before this was fixed simply never showed up
in HR (Admin > HR / Payroll), only non-teaching staff did. New teachers are
fixed automatically going forward; this is the one-off catch-up for everyone
already in the system. Dry run unless --commit is given.
"""
from django.core.management.base import BaseCommand, CommandError

from hr.models import StaffProfile
from users.app_views import _sync_teacher_hr_salary
from users.models import TeacherProfile


class Command(BaseCommand):
    help = "Give every teacher without one an HR StaffProfile (dry run unless --commit is given)."

    def add_arguments(self, parser):
        parser.add_argument("--school", default="", help="Limit to one school's code (its schema_name). Every school if omitted.")
        parser.add_argument("--commit", action="store_true", help="Actually create the missing HR records. Without this it only reports.")

    def handle(self, *args, **options):
        from core.models import SchoolTenant

        school_code = options["school"].strip()
        teachers = TeacherProfile.objects.select_related("user", "user__tenant").filter(user__role="teacher")
        if school_code:
            school = SchoolTenant.objects.filter(schema_name__iexact=school_code).first()
            if not school:
                raise CommandError(f'No school with the code "{school_code}".')
            teachers = teachers.filter(user__tenant=school)

        existing_staff_user_ids = set(StaffProfile.objects.values_list("user_id", flat=True))
        missing = [t for t in teachers if t.user_id not in existing_staff_user_ids]

        self.stdout.write(f"{len(missing)} teacher(s) without an HR record, out of {teachers.count()} checked.")
        for teacher in missing:
            school_name = getattr(teacher.user.tenant, "name", "") or teacher.user.tenant_id
            self.stdout.write(f"  {teacher.user.get_full_name() or teacher.user.email} ({school_name})")

        if not options["commit"]:
            self.stdout.write(self.style.WARNING("\nDry run - nothing was created. Add --commit to create these HR records."))
            return
        if not missing:
            self.stdout.write("Nobody to fix.")
            return

        created = 0
        for teacher in missing:
            _sync_teacher_hr_salary(teacher)
            created += 1
        self.stdout.write(self.style.SUCCESS(f"\nCreated {created} HR record(s). They now show up in Admin > HR."))
