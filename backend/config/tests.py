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

    def test_editing_a_student_with_an_existing_photo_shows_a_preview_of_it(self):
        from django.core.files.uploadedfile import SimpleUploadedFile

        profile = self._make_student()
        profile.user.profile_picture = SimpleUploadedFile("student.jpg", b"student-photo-bytes", content_type="image/jpeg")
        profile.user.save(update_fields=["profile_picture"])

        response = self.client.get(f"{self.url}?role=student&edit_id={profile.id}")

        self.assertContains(response, "cp-current-photo")
        self.assertContains(response, profile.user.profile_picture.url)

    def test_adding_a_new_student_shows_no_photo_preview(self):
        # "cp-current-photo" alone also matches the page's own <style> block
        # (the CSS selector renders unconditionally) - check for the actual
        # conditional HTML element instead.
        response = self.client.get(f"{self.url}?role=student")
        self.assertNotContains(response, '<span class="cp-current-photo">')

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


class LoginAsLinkFromControlPanelTests(TestCase):
    """Generating a "login as" link is the Control Panel half of
    impersonation - see users.tests.ExchangeImpersonationCodeTests for the
    other half (trading that link's code for a real session). This half
    only ever stashes a one-time code in the cache and redirects to the
    frontend; it never hands out a real JWT itself."""

    def setUp(self):
        from django.core.cache import cache
        cache.clear()

        self.school = SchoolTenant.objects.create(
            name="Login As School", schema_name="login_as_school", is_active=True,
        )
        self.student_user = User.objects.create_user(
            email="login.as.student@login-as-school.edu", password="StudentPass123", first_name="Stu", last_name="Dent",
            role="student", tenant=self.school, is_active=True, is_verified=True,
        )
        self.student_profile = StudentProfile.objects.create(
            user=self.student_user, student_id="STU-LOGIN-1", admission_number="ADM-LOGIN-1", admission_date="2024-01-01",
            guardian_name="Guardian", guardian_phone="08010000001",
        )
        self.superuser = User.objects.create_user(
            email="platform2@schooldom.test", password="SuperPass123", first_name="Platform", last_name="Super",
            role="super_admin", is_active=True, is_staff=True, is_superuser=True,
        )
        self.client.force_login(self.superuser)
        self.url = f"/control-panel/core/schooltenant/{self.school.id}/login-as/"

    def test_generating_a_link_redirects_to_the_frontend_with_a_code_and_stashes_it_in_the_cache(self):
        from django.conf import settings
        from django.core.cache import cache

        response = self.client.get(f"{self.url}?role=student&person_id={self.student_profile.id}")

        self.assertEqual(response.status_code, 302)
        self.assertTrue(response.url.startswith(f"{settings.FRONTEND_BASE_URL}/app/?login_as="))
        code = response.url.split("login_as=")[1]
        entry = cache.get(f"impersonation_code:{code}")
        self.assertIsNotNone(entry)
        self.assertEqual(entry["user_id"], str(self.student_user.id))
        self.assertEqual(entry["actor_id"], str(self.superuser.id))

    def test_an_unknown_person_id_is_rejected_without_generating_a_code(self):
        response = self.client.get(f"{self.url}?role=student&person_id=00000000-0000-0000-0000-000000000000")

        self.assertEqual(response.status_code, 302)
        self.assertIn("/add-person/", response.url)

    def test_generating_a_link_for_a_school_admin(self):
        school_admin = User.objects.create_user(
            email="head.admin@login-as-school.edu", password="AdminPass123", first_name="Head", last_name="Admin",
            role="school_admin", tenant=self.school, is_active=True, is_verified=True,
        )

        response = self.client.get(f"{self.url}?role=admin&person_id={school_admin.id}")

        self.assertEqual(response.status_code, 302)
        code = response.url.split("login_as=")[1]
        from django.core.cache import cache
        entry = cache.get(f"impersonation_code:{code}")
        self.assertIsNotNone(entry)
        self.assertEqual(entry["user_id"], str(school_admin.id))

    def test_an_inactive_admin_is_rejected(self):
        inactive_admin = User.objects.create_user(
            email="inactive.admin@login-as-school.edu", password="AdminPass123", first_name="Inactive", last_name="Admin",
            role="school_admin", tenant=self.school, is_active=False, is_verified=True,
        )

        response = self.client.get(f"{self.url}?role=admin&person_id={inactive_admin.id}")

        self.assertEqual(response.status_code, 302)
        self.assertIn("/add-person/", response.url)

    def test_a_teacher_cannot_be_impersonated_via_the_admin_role(self):
        """role=admin only ever resolves school_admin/principal - a student,
        teacher or staff id passed under role=admin must not also work, or
        the role param would just be decoration."""
        teacher_user = User.objects.create_user(
            email="not.an.admin@login-as-school.edu", password="TeacherPass123", first_name="Not", last_name="Admin",
            role="teacher", tenant=self.school, is_active=True, is_verified=True,
        )

        response = self.client.get(f"{self.url}?role=admin&person_id={teacher_user.id}")

        self.assertEqual(response.status_code, 302)
        self.assertIn("/add-person/", response.url)

    def test_cannot_generate_a_link_for_a_student_at_a_different_school(self):
        other_school = SchoolTenant.objects.create(name="Other Login As School", schema_name="other_login_as_school", is_active=True)
        url = f"/control-panel/core/schooltenant/{other_school.id}/login-as/"

        response = self.client.get(f"{url}?role=student&person_id={self.student_profile.id}")

        self.assertEqual(response.status_code, 302)
        self.assertIn("/add-person/", response.url)

    def test_a_non_superuser_without_permission_is_forbidden(self):
        plain_user = User.objects.create_user(
            email="plain2@schooldom.test", password="StaffPass123", first_name="Plain", last_name="Two",
            role="staff", is_active=True, is_staff=True, is_superuser=False,
        )
        self.client.force_login(plain_user)

        response = self.client.get(f"{self.url}?role=student&person_id={self.student_profile.id}")
        self.assertEqual(response.status_code, 403)


class AdminTabFromControlPanelTests(TestCase):
    """The Add Person page's "Admin" tab (control_panel.py's add_person_view/
    _existing_people, role == "admin") is browse-and-login-as only - there's
    no account-creation flow for admins here, unlike student/teacher/staff."""

    def setUp(self):
        self.school = SchoolTenant.objects.create(
            name="Admin Tab School", schema_name="admin_tab_school", is_active=True,
        )
        self.school_admin = User.objects.create_user(
            email="principal@admin-tab-school.edu", password="AdminPass123", first_name="Pat", last_name="Principal",
            role="principal", tenant=self.school, is_active=True, is_verified=True,
        )
        self.teacher = User.objects.create_user(
            email="teacher@admin-tab-school.edu", password="TeacherPass123", first_name="Terry", last_name="Teacher",
            role="teacher", tenant=self.school, is_active=True, is_verified=True,
        )
        self.superuser = User.objects.create_user(
            email="platform3@schooldom.test", password="SuperPass123", first_name="Platform", last_name="Three",
            role="super_admin", is_active=True, is_staff=True, is_superuser=True,
        )
        self.client.force_login(self.superuser)
        self.url = f"/control-panel/core/schooltenant/{self.school.id}/add-person/"

    def test_the_admin_tab_lists_the_schools_admins_and_principals(self):
        response = self.client.get(f"{self.url}?role=admin")

        self.assertContains(response, self.school_admin.get_full_name())
        self.assertNotContains(response, self.teacher.get_full_name())

    def test_posting_to_the_admin_tab_is_rejected(self):
        response = self.client.post(self.url, data={"account_type": "admin", "first_name": "Should", "last_name": "Not Save"}, follow=True)

        self.assertContains(response, "Login as to sign in as an existing one")
        self.assertFalse(User.objects.filter(first_name="Should").exists())
