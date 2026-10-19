"""Control Panel admin views that don't belong to any one app's own test
file - see control_panel.py's ControlPanelSchoolTenantAdmin.add_person_view.
"""
from django.contrib.auth import get_user_model
from django.test import TestCase

from academic.models import Class
from core.models import SchoolTenant
from hr.models import StaffProfile
from tenants.models import Tenant
from users.models import StudentProfile, TeacherProfile

User = get_user_model()


class AddPersonFromControlPanelTests(TestCase):
    """A platform superadmin can create a student/teacher/staff account
    directly into any school from the Control Panel, without signing in as
    that school's own admin - this dispatches into the exact same validated
    create_student/create_teacher/create_staff views that school's own Add
    Student/Teacher/Staff screens use, so it must behave identically to
    using those screens as that school's admin would."""

    def setUp(self):
        self.school = SchoolTenant.objects.create(
            name="Control Panel School", schema_name="control_panel_school", is_active=True,
        )
        self.legacy_tenant = Tenant.objects.create(name=self.school.name, slug=self.school.schema_name)
        self.school_admin = User.objects.create_user(
            email="admin@control-panel-school.edu", password="AdminPass123", first_name="Head", last_name="Admin",
            role="school_admin", tenant=self.school, is_active=True, is_verified=True,
        )
        self.superuser = User.objects.create_user(
            email="platform@schooldom.test", password="SuperPass123", first_name="Platform", last_name="Super",
            role="super_admin", is_active=True, is_staff=True, is_superuser=True,
        )
        self.client.force_login(self.superuser)
        self.url = f"/control-panel/core/schooltenant/{self.school.id}/add-person/"

    def test_a_student_can_be_created_into_the_school(self):
        response = self.client.post(self.url, data={
            "account_type": "student",
            "student_email": "new.student@control-panel-school.edu",
            "first_name": "New", "last_name": "Student",
            "guardian_name": "Guardian Person", "guardian_phone": "08010000001",
            "student_password": "StudentPass123", "confirm_student_password": "StudentPass123",
        })
        self.assertEqual(response.status_code, 302)
        student = User.objects.get(email="new.student@control-panel-school.edu")
        self.assertEqual(student.tenant_id, self.school.id)
        self.assertEqual(student.role, "student")

    def test_a_teacher_can_be_created_with_multiple_subjects_selected(self):
        from academic.models import Subject

        math = Subject.objects.create(tenant=self.legacy_tenant, name="Mathematics", code="MATH")
        english = Subject.objects.create(tenant=self.legacy_tenant, name="English", code="ENG")

        response = self.client.post(self.url, data={
            "account_type": "teacher",
            "teacher_email": "new.teacher@control-panel-school.edu",
            "first_name": "New", "last_name": "Teacher",
            "teacher_password": "TeacherPass123", "confirm_teacher_password": "TeacherPass123",
            "subject_ids": [str(math.id), str(english.id)],
        })
        self.assertEqual(response.status_code, 302)
        profile = TeacherProfile.objects.get(user__email="new.teacher@control-panel-school.edu")
        self.assertEqual(profile.user.tenant_id, self.school.id)
        self.assertEqual(set(profile.subjects.values_list("id", flat=True)), {math.id, english.id})

    def test_a_non_teaching_staff_member_can_be_created(self):
        response = self.client.post(self.url, data={
            "account_type": "staff",
            "first_name": "New", "last_name": "Accountant",
            "role": "Accountant",
            "base_salary": "150000",
        })
        self.assertEqual(response.status_code, 302)
        staff = StaffProfile.objects.get(tenant=self.school, role="Accountant")
        self.assertEqual(staff.first_name, "New")

    def test_a_school_with_no_admin_yet_is_rejected_with_a_clear_message(self):
        empty_school = SchoolTenant.objects.create(name="Empty School", schema_name="empty_school_cp", is_active=True)
        url = f"/control-panel/core/schooltenant/{empty_school.id}/add-person/"

        response = self.client.post(url, data={
            "account_type": "student",
            "student_email": "orphan@empty-school.edu",
            "first_name": "Orphan", "last_name": "Student",
            "guardian_name": "Guardian", "guardian_phone": "08010000001",
            "student_password": "StudentPass123", "confirm_student_password": "StudentPass123",
        }, follow=True)
        self.assertContains(response, "no active admin account yet")
        self.assertFalse(User.objects.filter(email="orphan@empty-school.edu").exists())

    def test_a_non_superuser_without_the_students_staff_data_permission_is_forbidden(self):
        plain_staff_user = User.objects.create_user(
            email="plain.staff@schooldom.test", password="StaffPass123", first_name="Plain", last_name="Staff",
            role="staff", is_active=True, is_staff=True, is_superuser=False,
        )
        self.client.force_login(plain_staff_user)

        response = self.client.post(self.url, data={
            "account_type": "student",
            "student_email": "blocked@control-panel-school.edu",
            "first_name": "Blocked", "last_name": "Student",
            "guardian_name": "Guardian", "guardian_phone": "08010000001",
            "student_password": "StudentPass123", "confirm_student_password": "StudentPass123",
        })
        self.assertEqual(response.status_code, 403)
        self.assertFalse(User.objects.filter(email="blocked@control-panel-school.edu").exists())


class EditPersonFromControlPanelTests(TestCase):
    """The same Control Panel page also edits an existing student/teacher/
    staff record, through the exact same validated PATCH views (student_
    detail/teacher_detail/staff_detail) their own school's admin would hit
    on the real Edit screen - and can reset a lost password, since there is
    no way to recover/view the real one (it's a one-way hash)."""

    def setUp(self):
        self.school = SchoolTenant.objects.create(
            name="Edit Control Panel School", schema_name="edit_control_panel_school", is_active=True,
        )
        self.legacy_tenant = Tenant.objects.create(name=self.school.name, slug=self.school.schema_name)
        self.school_admin = User.objects.create_user(
            email="admin@edit-cp-school.edu", password="AdminPass123", first_name="Head", last_name="Admin",
            role="school_admin", tenant=self.school, is_active=True, is_verified=True,
        )
        self.superuser = User.objects.create_user(
            email="platform@schooldom.test", password="SuperPass123", first_name="Platform", last_name="Super",
            role="super_admin", is_active=True, is_staff=True, is_superuser=True,
        )
        self.client.force_login(self.superuser)
        self.url = f"/control-panel/core/schooltenant/{self.school.id}/add-person/"

    def _make_student(self):
        student_user = User.objects.create_user(
            email="edit.student@edit-cp-school.edu", password="OldPass123", first_name="Old", last_name="Name",
            role="student", tenant=self.school, is_active=True, is_verified=True,
        )
        return StudentProfile.objects.create(
            user=student_user, student_id="STU-EDIT-1", admission_number="ADM-EDIT-1",
            admission_date="2024-01-01", guardian_name="Old Guardian", guardian_phone="08010000001",
        )

    def test_editing_a_student_updates_their_record_and_shows_up_in_the_list(self):
        profile = self._make_student()

        listing = self.client.get(f"{self.url}?role=student&q=Old")
        self.assertContains(listing, profile.user.get_full_name())

        response = self.client.post(self.url, data={
            "account_type": "student", "edit_id": str(profile.id),
            "first_name": "New", "last_name": "Name",
            "guardian_name": "New Guardian", "guardian_phone": "08029999999",
            "student_password": "", "confirm_student_password": "",
        })
        self.assertEqual(response.status_code, 302)
        profile.refresh_from_db()
        profile.user.refresh_from_db()
        self.assertEqual(profile.user.first_name, "New")
        self.assertEqual(profile.guardian_name, "New Guardian")

    def test_leaving_the_password_blank_while_editing_does_not_error_or_change_it(self):
        profile = self._make_student()
        old_password_hash = profile.user.password

        response = self.client.post(self.url, data={
            "account_type": "student", "edit_id": str(profile.id),
            "first_name": "Old", "last_name": "Name",
            "guardian_name": "Old Guardian", "guardian_phone": "08010000001",
            "student_password": "", "confirm_student_password": "",
        }, follow=True)
        self.assertNotContains(response, "is required when updating a password")
        profile.user.refresh_from_db()
        self.assertEqual(profile.user.password, old_password_hash)

    def test_setting_a_new_password_while_editing_actually_changes_it(self):
        profile = self._make_student()
        old_password_hash = profile.user.password

        response = self.client.post(self.url, data={
            "account_type": "student", "edit_id": str(profile.id),
            "first_name": "Old", "last_name": "Name",
            "guardian_name": "Old Guardian", "guardian_phone": "08010000001",
            "student_password": "BrandNewPass123", "confirm_student_password": "BrandNewPass123",
        })
        self.assertEqual(response.status_code, 302)
        profile.user.refresh_from_db()
        self.assertNotEqual(profile.user.password, old_password_hash)
        self.assertTrue(profile.user.check_password("BrandNewPass123"))

    def test_editing_a_teacher_preserves_their_existing_subjects_when_untouched(self):
        from academic.models import Subject

        math = Subject.objects.create(tenant=self.legacy_tenant, name="Mathematics", code="MATH")
        teacher_user = User.objects.create_user(
            email="edit.teacher@edit-cp-school.edu", password="OldPass123", first_name="Old", last_name="Teacher",
            role="teacher", tenant=self.school, is_active=True, is_verified=True,
        )
        profile = TeacherProfile.objects.create(
            user=teacher_user, employee_id="TCH-EDIT-1", hire_date="2024-01-01", employment_type="full_time",
        )
        profile.subjects.set([math])

        # Pre-fill (GET) must already carry the current subject as selected -
        # this is what the template reads to keep it checked without the
        # admin having to re-pick it.
        prefill = self.client.get(f"{self.url}?role=teacher&edit_id={profile.id}")
        self.assertContains(prefill, f'value="{math.id}" selected')

        response = self.client.post(self.url, data={
            "account_type": "teacher", "edit_id": str(profile.id),
            "first_name": "Updated", "last_name": "Teacher",
            "subject_ids": [str(math.id)],
            "teacher_password": "", "confirm_teacher_password": "",
        })
        self.assertEqual(response.status_code, 302)
        profile.refresh_from_db()
        profile.user.refresh_from_db()
        self.assertEqual(profile.user.first_name, "Updated")
        self.assertEqual(set(profile.subjects.values_list("id", flat=True)), {math.id})

    def test_editing_a_staff_member_updates_their_record(self):
        staff = StaffProfile.objects.create(
            tenant=self.school, staff_code="NS-EDIT-1", first_name="Old", last_name="Accountant",
            role="Accountant", base_salary="100000",
        )

        response = self.client.post(self.url, data={
            "account_type": "staff", "edit_id": str(staff.id),
            "first_name": "New", "last_name": "Accountant",
            "role": "Senior Accountant", "base_salary": "200000",
        })
        self.assertEqual(response.status_code, 302)
        staff.refresh_from_db()
        self.assertEqual(staff.first_name, "New")
        self.assertEqual(staff.role, "Senior Accountant")
        self.assertEqual(str(staff.base_salary), "200000.00")
