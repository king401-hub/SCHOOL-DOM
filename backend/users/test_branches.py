"""Branch switching: one school_admin/principal login operating more than
one SchoolTenant branch (e.g. "Primary"/"Secondary") under one school name.

The central promise under test is isolation: nothing created or read on one
branch may ever be visible from another, even though both are reached with
the exact same login. See users.authentication.BranchAwareJWTAuthentication
and users.branch_views for the implementation these tests exercise through
real HTTP calls and real JWTs (never force_authenticate, which would bypass
the authentication class entirely and prove nothing about it).
"""
import uuid
from unittest.mock import patch

from django.core.cache import cache
from django.test import TestCase
from rest_framework.test import APIClient

from core.models import SchoolGroup, SchoolTenant
from tenants.models import Tenant
from users.models import User


@patch("users.views.ADMIN_OTP_ENABLED", False)
class BranchSwitchingTests(TestCase):
    def setUp(self):
        # IdempotencyMiddleware caches by (requester, method, path, body) for
        # 10s - every test here logs in with the exact same credentials, so
        # without clearing it a later test's login would silently replay an
        # earlier test's cached response.
        cache.clear()
        self.school = SchoolTenant.objects.create(
            name="Greenwood International School", schema_name="greenwood_branches", is_active=True,
        )
        self.legacy_tenant = Tenant.objects.create(name=self.school.name, slug=self.school.schema_name)
        self.admin = User.objects.create_user(
            email="admin@greenwood.edu", password="AdminPass123", first_name="Ada", last_name="Min",
            role="school_admin", tenant=self.school, is_active=True, is_verified=True,
        )
        self.client = APIClient()

    def _access_token(self, email="admin@greenwood.edu", password="AdminPass123", school_code=""):
        payload = {"email": email, "password": password}
        if school_code:
            payload["school_code"] = school_code
        response = self.client.post("/api/auth/login/", payload, format="json")
        self.assertEqual(response.status_code, 200, response.data)
        self.assertIn("access", response.data, response.data)
        return response.data["access"]

    def _auth(self, access):
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {access}")

    def _login(self, **kwargs):
        self._auth(self._access_token(**kwargs))

    def _create_student(self, email):
        response = self.client.post(
            "/api/app/students/create/",
            {
                "student_email": email, "first_name": "Stu", "last_name": "Dent",
                "guardian_name": "Guardian", "guardian_phone": "08010000001",
                "student_password": "StudentPass123", "confirm_student_password": "StudentPass123",
            },
        )
        self.assertEqual(response.status_code, 201, response.data)

    def _student_emails(self):
        response = self.client.get("/api/app/students/")
        self.assertEqual(response.status_code, 200, response.data)
        return {row["email"] for row in response.data["students"]}

    def _student_id(self, email):
        response = self.client.get("/api/app/students/")
        self.assertEqual(response.status_code, 200, response.data)
        for row in response.data["students"]:
            if row["email"] == email:
                return row["id"]
        self.fail(f"{email} not found in the current branch's student list")

    # -- creating a branch ---------------------------------------------------

    def test_creating_the_first_branch_auto_creates_a_group_and_labels_the_original_main(self):
        self._login()
        response = self.client.post("/api/app/branches/create/", {"branch_label": "Secondary"})
        self.assertEqual(response.status_code, 201, response.data)

        self.school.refresh_from_db()
        self.admin.refresh_from_db()
        self.assertEqual(self.school.branch_label, "Main")
        self.assertIsNotNone(self.school.school_group_id)
        self.assertEqual(self.admin.school_group_id, self.school.school_group_id)

        secondary = SchoolTenant.objects.get(branch_label="Secondary")
        self.assertEqual(secondary.school_group_id, self.school.school_group_id)
        self.assertEqual(secondary.name, self.school.name, "branches share one name/brand")
        self.assertNotEqual(secondary.id, self.school.id, "a branch is its own fully separate SchoolTenant")

    def test_a_duplicate_branch_label_is_rejected(self):
        self._login()
        self.client.post("/api/app/branches/create/", {"branch_label": "Secondary"})
        # Real duplicates happen well apart, not back-to-back identical
        # requests - clear the 10s idempotency cache so the second POST
        # below exercises the actual duplicate-label guard instead of just
        # replaying the first response.
        cache.clear()
        response = self.client.post("/api/app/branches/create/", {"branch_label": "Secondary"})
        self.assertEqual(response.status_code, 400, response.data)

    def test_only_school_admin_or_principal_can_manage_branches(self):
        User.objects.create_user(
            email="teacher@greenwood.edu", password="TeacherPass123", first_name="Tee", last_name="Cher",
            role="teacher", tenant=self.school, is_active=True, is_verified=True,
        )
        self._login(email="teacher@greenwood.edu", password="TeacherPass123", school_code=self.school.schema_name)
        for response in (
            self.client.get("/api/app/branches/"),
            self.client.post("/api/app/branches/create/", {"branch_label": "Secondary"}),
            self.client.post("/api/app/branches/switch/", {"tenant_id": str(self.school.id)}),
        ):
            self.assertEqual(response.status_code, 403, response.data)

    # -- switching --------------------------------------------------------

    def test_switching_to_a_branch_outside_your_own_group_is_rejected(self):
        other_school = SchoolTenant.objects.create(name="Unrelated School", schema_name="unrelated_school", is_active=True)
        self._login()
        self.client.post("/api/app/branches/create/", {"branch_label": "Secondary"})  # gives self.admin a school_group

        response = self.client.post("/api/app/branches/switch/", {"tenant_id": str(other_school.id)})
        self.assertEqual(response.status_code, 404, response.data)

    def test_switching_without_any_branches_is_rejected(self):
        self._login()
        response = self.client.post("/api/app/branches/switch/", {"tenant_id": str(self.school.id)})
        self.assertEqual(response.status_code, 400, response.data)

    def test_a_token_for_a_branch_removed_from_the_group_is_rejected_on_the_very_next_request(self):
        """The authorization check in BranchAwareJWTAuthentication re-verifies
        the live school_group relationship on EVERY request, not just at
        switch time - an already-issued token must stop working the moment
        its branch is no longer actually part of the group, not silently
        keep scoping to a different (the admin's home) tenant instead."""
        self._login()
        create = self.client.post("/api/app/branches/create/", {"branch_label": "Secondary"})
        secondary_id = create.data["branch"]["id"]

        switch = self.client.post("/api/app/branches/switch/", {"tenant_id": secondary_id})
        self.assertEqual(switch.status_code, 200, switch.data)
        self._auth(switch.data["access"])

        # Confirm the token works before the branch is removed.
        ok = self.client.get("/api/app/branches/")
        self.assertEqual(ok.status_code, 200, ok.data)

        secondary = SchoolTenant.objects.get(pk=secondary_id)
        secondary.school_group = None
        secondary.save(update_fields=["school_group"])

        rejected = self.client.get("/api/app/branches/")
        self.assertEqual(rejected.status_code, 401, rejected.data)

    # -- the actual isolation guarantee -------------------------------------

    def test_data_created_on_one_branch_is_never_visible_from_the_other(self):
        self._login()
        create = self.client.post("/api/app/branches/create/", {"branch_label": "Secondary"})
        self.assertEqual(create.status_code, 201, create.data)
        secondary_id = create.data["branch"]["id"]
        main_id = str(self.school.id)

        # Student created while the Main branch is active.
        self._create_student("main.student@greenwood.edu")
        self.assertEqual(self._student_emails(), {"main.student@greenwood.edu"})

        # Switch to Secondary - Main's student must not be visible here.
        switch = self.client.post("/api/app/branches/switch/", {"tenant_id": secondary_id})
        self.assertEqual(switch.status_code, 200, switch.data)
        self._auth(switch.data["access"])
        self.assertEqual(self._student_emails(), set(), "Main's student leaked into Secondary")

        self._create_student("secondary.student@greenwood.edu")
        self.assertEqual(self._student_emails(), {"secondary.student@greenwood.edu"})

        # Switch back to Main - only ever see Main's own student, never
        # Secondary's, proving isolation holds in both directions.
        switch_back = self.client.post("/api/app/branches/switch/", {"tenant_id": main_id})
        self.assertEqual(switch_back.status_code, 200, switch_back.data)
        self._auth(switch_back.data["access"])
        self.assertEqual(self._student_emails(), {"main.student@greenwood.edu"}, "Secondary's student leaked into Main")

    def test_a_plain_single_branch_school_is_completely_unaffected(self):
        """Regression safety net: the overwhelming majority of schools never
        create a branch at all - BranchAwareJWTAuthentication must be a
        no-op for them, identical to plain JWTAuthentication."""
        self._login()
        response = self.client.get("/api/app/branches/")
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data["branches"], [])

        self._create_student("only.student@greenwood.edu")
        self.assertEqual(self._student_emails(), {"only.student@greenwood.edu"})

    # -- transferring a student between branches -----------------------------

    def test_transferring_a_student_moves_them_to_the_target_branch(self):
        self._login()
        create = self.client.post("/api/app/branches/create/", {"branch_label": "Secondary"})
        secondary_id = create.data["branch"]["id"]
        main_id = str(self.school.id)

        self._create_student("mover@greenwood.edu")
        self.assertEqual(self._student_emails(), {"mover@greenwood.edu"})

        response = self.client.post(
            "/api/app/branches/transfer-student/",
            {"student_id": self._student_id("mover@greenwood.edu"), "target_tenant_id": secondary_id},
        )
        self.assertEqual(response.status_code, 200, response.data)

        # Gone from Main...
        self.assertEqual(self._student_emails(), set())

        # ...and now on Secondary.
        switch = self.client.post("/api/app/branches/switch/", {"tenant_id": secondary_id})
        self._auth(switch.data["access"])
        self.assertEqual(self._student_emails(), {"mover@greenwood.edu"})

        from users.models import StudentProfile
        moved = StudentProfile.objects.get(user__email="mover@greenwood.edu")
        self.assertEqual(str(moved.user.tenant_id), secondary_id)
        self.assertIsNone(moved.current_class_id, "a class from the old branch must not dangle across tenants")
        self.assertIsNone(moved.current_term_id)

    def test_transferring_a_students_payment_reference_moves_with_them(self):
        self._login()
        create = self.client.post("/api/app/branches/create/", {"branch_label": "Secondary"})
        secondary_id = create.data["branch"]["id"]
        self._create_student("payref@greenwood.edu")

        from finance.models import StudentPaymentReference
        from users.models import StudentProfile

        student = StudentProfile.objects.get(user__email="payref@greenwood.edu")
        payref = StudentPaymentReference.objects.create(student=student, tenant=self.school, code="PR-TEST-0001")

        response = self.client.post(
            "/api/app/branches/transfer-student/",
            {"student_id": str(student.id), "target_tenant_id": secondary_id},
        )
        self.assertEqual(response.status_code, 200, response.data)

        payref.refresh_from_db()
        self.assertEqual(str(payref.tenant_id), secondary_id)

    def test_transfer_rejects_a_student_who_is_not_on_your_current_branch(self):
        self._login()
        create = self.client.post("/api/app/branches/create/", {"branch_label": "Secondary"})
        secondary_id = create.data["branch"]["id"]

        switch = self.client.post("/api/app/branches/switch/", {"tenant_id": secondary_id})
        self._auth(switch.data["access"])
        self._create_student("on.secondary@greenwood.edu")
        secondary_student_id = self._student_id("on.secondary@greenwood.edu")

        switch_back = self.client.post("/api/app/branches/switch/", {"tenant_id": str(self.school.id)})
        self._auth(switch_back.data["access"])

        response = self.client.post(
            "/api/app/branches/transfer-student/",
            {"student_id": secondary_student_id, "target_tenant_id": secondary_id},
        )
        self.assertEqual(response.status_code, 404, response.data)

    def test_transfer_rejects_a_target_branch_outside_your_group(self):
        other_school = SchoolTenant.objects.create(name="Unrelated School", schema_name="unrelated_school_2", is_active=True)
        self._login()
        self.client.post("/api/app/branches/create/", {"branch_label": "Secondary"})
        self._create_student("stuck@greenwood.edu")

        response = self.client.post(
            "/api/app/branches/transfer-student/",
            {"student_id": self._student_id("stuck@greenwood.edu"), "target_tenant_id": str(other_school.id)},
        )
        self.assertEqual(response.status_code, 404, response.data)

    def test_transfer_rejects_the_same_branch_as_a_no_op(self):
        self._login()
        self.client.post("/api/app/branches/create/", {"branch_label": "Secondary"})
        self._create_student("same.branch@greenwood.edu")

        response = self.client.post(
            "/api/app/branches/transfer-student/",
            {"student_id": self._student_id("same.branch@greenwood.edu"), "target_tenant_id": str(self.school.id)},
        )
        self.assertEqual(response.status_code, 400, response.data)

    def test_only_school_admin_or_principal_can_transfer_students(self):
        User.objects.create_user(
            email="transfer.teacher@greenwood.edu", password="TeacherPass123", first_name="Tee", last_name="Cher",
            role="teacher", tenant=self.school, is_active=True, is_verified=True,
        )
        self._login()
        self.client.post("/api/app/branches/create/", {"branch_label": "Secondary"})
        self._create_student("guarded@greenwood.edu")
        student_id = self._student_id("guarded@greenwood.edu")

        self._login(email="transfer.teacher@greenwood.edu", password="TeacherPass123", school_code=self.school.schema_name)
        response = self.client.post(
            "/api/app/branches/transfer-student/",
            {"student_id": student_id, "target_tenant_id": str(self.school.id)},
        )
        self.assertEqual(response.status_code, 403, response.data)
