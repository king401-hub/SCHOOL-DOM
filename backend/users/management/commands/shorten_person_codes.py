from django.core.management.base import BaseCommand
from django.db import transaction

from finance.models import StudentPaymentReference
from hr.models import StaffProfile
from users.models import StudentProfile, TeacherProfile, random_code_digits, school_code_letters


def random_school_code(prefix, school, used):
    school_letters = school_code_letters(school)
    while True:
        candidate = f"{prefix}{school_letters}{random_code_digits()}"
        if candidate not in used:
            used.add(candidate)
            return candidate


class Command(BaseCommand):
    help = "Rewrite existing student, teacher, and staff identifiers to the short code format."

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true", help="Show how many records would change without saving.")

    def handle(self, *args, **options):
        dry_run = options["dry_run"]
        counts = {
            "students": StudentProfile.objects.count(),
            "teachers": TeacherProfile.objects.count(),
            "staff": StaffProfile.objects.count(),
            "payment_references": StudentPaymentReference.objects.count(),
        }

        if dry_run:
            self.stdout.write(self.style.WARNING(f"Dry run only. Records found: {counts}"))
            return

        with transaction.atomic():
            self._temporary_codes()

            student_map = self._update_students()
            teacher_map = self._update_teachers()
            staff_map = self._update_staff(teacher_map)
            reference_map = self._update_payment_references(student_map)

        self.stdout.write(
            self.style.SUCCESS(
                "Shortened codes: "
                f"{len(student_map)} students, "
                f"{len(teacher_map)} teachers, "
                f"{len(staff_map)} staff, "
                f"{len(reference_map)} fee references."
            )
        )

    def _temporary_codes(self):
        for index, student in enumerate(StudentProfile.objects.order_by("created_at", "id"), start=1):
            student.student_id = f"TMPST{index:06d}"
            student.save(update_fields=["student_id"])

        for index, teacher in enumerate(TeacherProfile.objects.order_by("created_at", "id"), start=1):
            teacher.employee_id = f"TMPTC{index:06d}"
            teacher.save(update_fields=["employee_id"])

        for index, staff in enumerate(StaffProfile.objects.order_by("tenant_id", "created_at", "id"), start=1):
            staff.staff_code = f"TMPSF{index:06d}"
            staff.save(update_fields=["staff_code"])

        for index, reference in enumerate(StudentPaymentReference.objects.order_by("created_at", "id"), start=1):
            reference.code = f"TMPRF{index:06d}"
            reference.save(update_fields=["code"])

    def _update_students(self):
        code_map = {}
        used = set()
        for student in StudentProfile.objects.select_related("user", "user__tenant").order_by("created_at", "id"):
            old_code = student.student_id
            student.student_id = random_school_code("ST", student.user.tenant, used)
            student.save(update_fields=["student_id", "updated_at"])
            code_map[str(student.id)] = (old_code, student.student_id)
        return code_map

    def _update_teachers(self):
        code_map = {}
        used = set()
        for teacher in TeacherProfile.objects.select_related("user", "user__tenant").order_by("created_at", "id"):
            old_code = teacher.employee_id
            teacher.employee_id = random_school_code("TC", teacher.user.tenant, used)
            teacher.save(update_fields=["employee_id", "updated_at"])
            code_map[str(teacher.user_id)] = (old_code, teacher.employee_id)
        return code_map

    def _update_staff(self, teacher_map):
        code_map = {}
        used_by_tenant = {}
        staff_records = StaffProfile.objects.select_related("user", "tenant").order_by("tenant_id", "created_at", "id")

        for staff in staff_records:
            tenant_key = str(staff.tenant_id or "")
            used = used_by_tenant.setdefault(tenant_key, set())
            old_code = staff.staff_code

            teacher_codes = teacher_map.get(str(staff.user_id))
            if staff.staff_type == StaffProfile.TEACHING and teacher_codes and teacher_codes[1] not in used:
                next_code = teacher_codes[1]
            else:
                prefix = "NS" if staff.staff_type == StaffProfile.NON_TEACHING else "TC"
                next_code = random_school_code(prefix, staff.tenant, used)

            staff.staff_code = next_code
            staff.save(update_fields=["staff_code", "updated_at"])
            used.add(next_code)
            code_map[str(staff.id)] = (old_code, staff.staff_code)
        return code_map

    def _update_payment_references(self, student_map):
        code_map = {}
        references = StudentPaymentReference.objects.select_related("student").order_by("created_at", "id")
        for reference in references:
            old_code = reference.code
            student_codes = student_map.get(str(reference.student_id))
            reference.code = student_codes[1] if student_codes else StudentProfile.objects.get(id=reference.student_id).student_id
            reference.save(update_fields=["code", "updated_at"])
            code_map[str(reference.id)] = (old_code, reference.code)
        return code_map
