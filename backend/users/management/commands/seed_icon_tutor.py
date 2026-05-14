import re

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from core.models import Domain, SchoolTenant
from tenants.models import Tenant
from users.models import StudentProfile, TeacherProfile, User


SCHOOL_DEFAULTS = {
    "name": "Icon Tutor",
    "schema_name": "icon_tutor_8",
    "email": "icon01@gmail.com",
    "phone": "07071651847",
}

USERS = [
    {
        "email": "icon01@gmail.com",
        "first_name": "Icon",
        "last_name": "Tutor",
        "role": "school_admin",
        "phone": "07071651847",
        "is_verified": False,
    },
    {
        "email": "solomonenoch63@gmail.com",
        "first_name": "Solomon",
        "last_name": "Enoch",
        "role": "staff",
        "phone": "07071651847",
        "is_verified": True,
        "staff_code": "STITSTAFF001",
        "staff_role": "Staff",
    },
    {
        "email": "ade01@gmail.com",
        "first_name": "ADEKUNLE",
        "last_name": "MARIAM AJOKE",
        "role": "student",
        "is_verified": True,
        "student_id": "STIT372",
        "admission_number": "ADM2026032310294727BC",
        "guardian_name": "Mr ADEKUNLE",
        "guardian_phone": "08102804802",
    },
    {
        "email": "arleyhrp123@gmail.com",
        "first_name": "Solomon",
        "last_name": "Enoch",
        "role": "student",
        "is_verified": True,
        "student_id": "STIT176",
        "admission_number": "ADM20260504090904F92C",
        "guardian_name": "Mr Solomon",
        "guardian_phone": "07071651847",
    },
    {
        "email": "attah02@gmail.com",
        "first_name": "ATTAH",
        "last_name": "DANIELA",
        "role": "student",
        "is_verified": True,
        "student_id": "STIT217",
        "admission_number": "ADM2026031205541715E1",
        "guardian_name": "Mrs Attah",
        "guardian_phone": "07071651847",
    },
    {
        "email": "david03@gmail.com",
        "first_name": "DAVID",
        "last_name": "EFIONGB HONESTY",
        "role": "student",
        "is_verified": True,
        "student_id": "STIT326",
        "admission_number": "ADM20260312055724F12D",
        "guardian_name": "Mr David",
        "guardian_phone": "07071651847",
    },
    {
        "email": "ebe01@gmail.com",
        "first_name": "EBE",
        "last_name": "EMMANUEL",
        "role": "student",
        "is_verified": True,
        "student_id": "STIT041",
        "admission_number": "ADM202603101822067699",
        "guardian_name": "Mr Ebeh",
        "guardian_phone": "09069796407",
    },
    {
        "email": "favour04@gmail.com",
        "first_name": "IBIKUNLE",
        "last_name": "FAVOUR ENIOLA",
        "role": "student",
        "is_verified": True,
        "student_id": "STIT117",
        "admission_number": "ADM202603120600285863",
        "guardian_name": "Mr Ibikunle",
        "guardian_phone": "07071651847",
    },
    {
        "email": "icon1@gmail.com",
        "first_name": "Aman",
        "last_name": "Sophie",
        "role": "student",
        "is_verified": True,
        "student_id": "STIT467",
        "admission_number": "ADM202605041706335A0A",
        "guardian_name": "Mr Amani",
        "guardian_phone": "08119984774",
    },
    {
        "email": "solomon3@gmail.com",
        "first_name": "Amana",
        "last_name": "Sophie",
        "role": "student",
        "is_verified": True,
        "student_id": "STIT414",
        "admission_number": "ADM2026051009010088F5",
        "guardian_name": "Mr Amani",
        "guardian_phone": "08119984774",
    },
    {
        "email": "somto05@gmail.com",
        "first_name": "JIDEONWOR",
        "last_name": "SOMTOCHUKWU",
        "role": "student",
        "phone": "07071651847",
        "is_verified": True,
        "student_id": "STIT835",
        "admission_number": "ADM20260312060226ED40",
        "guardian_name": "Mr Jideonwor",
        "guardian_phone": "07071651847",
    },
    {
        "email": "harleyhrp123@gmail.com",
        "first_name": "Adekunle",
        "last_name": "Chidera",
        "role": "teacher",
        "phone": "08119984774",
        "is_verified": True,
        "employee_id": "TCIT334",
        "specialization": "English and  Mathematics",
    },
    {
        "email": "solomonen3@gmail.com",
        "first_name": "Solomon",
        "last_name": "Enoch",
        "role": "teacher",
        "phone": "09069796407",
        "is_verified": True,
        "employee_id": "TCIT1002",
        "specialization": "Not specified",
    },
    {
        "email": "solomonenoch653@gmail.com",
        "first_name": "Solomon",
        "last_name": "Enoch",
        "role": "teacher",
        "phone": "07071651847",
        "is_verified": True,
        "employee_id": "TCIT245",
        "specialization": "Not specified",
    },
    {
        "email": "thomas@gmail.com",
        "first_name": "Thomas",
        "last_name": "Bankole",
        "role": "teacher",
        "phone": "0916854390",
        "is_verified": True,
        "employee_id": "TCIT766",
        "specialization": "Not specified",
    },
]


def password_env_name(email):
    safe_email = re.sub(r"[^A-Za-z0-9]+", "_", email).strip("_").upper()
    return f"ICON_TUTOR_PASSWORD_{safe_email}"


class Command(BaseCommand):
    help = "Seed the Icon Tutor school and known login accounts without storing passwords in git."

    def add_arguments(self, parser):
        parser.add_argument("--school-code", default=SCHOOL_DEFAULTS["schema_name"])
        parser.add_argument("--reset-passwords", action="store_true")

    @transaction.atomic
    def handle(self, *args, **options):
        import os

        school_code = options["school_code"].strip() or SCHOOL_DEFAULTS["schema_name"]
        school, _ = SchoolTenant.objects.update_or_create(
            schema_name=school_code,
            defaults={
                "name": SCHOOL_DEFAULTS["name"],
                "email": SCHOOL_DEFAULTS["email"],
                "phone": SCHOOL_DEFAULTS["phone"],
                "is_active": True,
            },
        )
        Domain.objects.get_or_create(
            tenant=school,
            domain=f"{school.schema_name}.school.local",
            defaults={"is_primary": True},
        )
        Tenant.objects.update_or_create(
            slug=school.schema_name,
            defaults={"name": school.name},
        )

        created = 0
        updated = 0
        unusable_passwords = []

        for item in USERS:
            user, was_created = User.objects.get_or_create(
                email=item["email"].lower(),
                defaults={
                    "first_name": item["first_name"],
                    "last_name": item["last_name"],
                    "role": item["role"],
                    "phone": item.get("phone", ""),
                    "tenant": school,
                    "is_active": True,
                    "is_verified": item.get("is_verified", True),
                },
            )
            user.first_name = item["first_name"]
            user.last_name = item["last_name"]
            user.role = item["role"]
            user.phone = item.get("phone", "")
            user.tenant = school
            user.is_active = True
            user.is_verified = item.get("is_verified", True)

            env_name = password_env_name(item["email"])
            password = os.environ.get(env_name) or os.environ.get("ICON_TUTOR_DEFAULT_PASSWORD")
            if password and (was_created or options["reset_passwords"]):
                user.set_password(password)
            elif was_created:
                user.set_unusable_password()
                unusable_passwords.append((item["email"], env_name))

            user.save()
            self._sync_profile(user, item, school)

            created += int(was_created)
            updated += int(not was_created)

        self.stdout.write(self.style.SUCCESS(f"Seeded {school.name} ({school.schema_name})."))
        self.stdout.write(f"Users created: {created}; users updated: {updated}.")
        if unusable_passwords:
            self.stdout.write(self.style.WARNING("Created users without passwords:"))
            for email, env_name in unusable_passwords:
                self.stdout.write(f"  {email}: set {env_name} or ICON_TUTOR_DEFAULT_PASSWORD and rerun with --reset-passwords")

    def _sync_profile(self, user, item, school):
        today = timezone.localdate()

        if user.role == "student":
            StudentProfile.objects.update_or_create(
                user=user,
                defaults={
                    "student_id": item["student_id"],
                    "admission_number": item["admission_number"],
                    "admission_date": today,
                    "guardian_name": item["guardian_name"],
                    "guardian_phone": item["guardian_phone"],
                    "guardian_relation": "Guardian",
                },
            )
            try:
                from finance.services import ensure_student_wallet

                ensure_student_wallet(user)
            except Exception:
                pass

        if user.role == "teacher":
            TeacherProfile.objects.update_or_create(
                user=user,
                defaults={
                    "employee_id": item["employee_id"],
                    "qualification": "Not specified",
                    "specialization": item.get("specialization") or "Not specified",
                    "hire_date": today,
                    "emergency_contact_name": "Not provided",
                    "emergency_contact_phone": "Not provided",
                    "emergency_contact_relation": "Not provided",
                },
            )

        if user.role == "staff":
            try:
                from hr.models import StaffProfile

                StaffProfile.objects.update_or_create(
                    tenant=school,
                    staff_code=item["staff_code"],
                    defaults={
                        "user": user,
                        "first_name": user.first_name,
                        "last_name": user.last_name,
                        "email": user.email,
                        "phone": user.phone,
                        "role": item.get("staff_role", "Staff"),
                        "staff_type": StaffProfile.NON_TEACHING,
                    },
                )
            except Exception:
                pass
