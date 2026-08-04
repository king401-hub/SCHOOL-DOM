from datetime import timedelta
from decimal import Decimal

from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from academic.models import AcademicYear, AttendanceRecord, Class, StudentClassPromotion, StudentSubjectScore, Subject, Term
from alumni.models import ArchivedStudentRecord, ArchiveProtectedError
from alumni.services import build_student_archive_payload, snapshot_student
from core.models import SchoolTenant
from finance.models import SchoolFee
from tenants.models import Tenant
from users.models import StudentProfile, User


class AlumniTestBase(TestCase):
    def setUp(self):
        self.school = SchoolTenant.objects.create(name="Archive Academy", schema_name="archive_academy", is_active=True)
        self.legacy_tenant = Tenant.objects.create(name="Archive Academy Legacy", slug="archive_academy")

        self.admin = User.objects.create_user(
            email="admin@archive.edu", password="AdminPass123", first_name="Ada", last_name="Admin",
            role="school_admin", tenant=self.school, is_active=True,
        )
        self.student_user = User.objects.create_user(
            email="sam@archive.edu", password="StudentPass123", first_name="Sam", last_name="Scholar",
            role="student", tenant=self.school, is_active=True,
        )

        self.academic_year = AcademicYear.objects.create(
            name="2024/2025", start_date=timezone.now().date() - timedelta(days=300),
            end_date=timezone.now().date() + timedelta(days=65), tenant=self.legacy_tenant,
        )
        self.term = Term.objects.create(
            name="First Term", start_date=self.academic_year.start_date,
            end_date=self.academic_year.start_date + timedelta(days=90),
            academic_year=self.academic_year, tenant=self.legacy_tenant,
        )
        self.classroom = Class.objects.create(name="SSS 3", section="A", tenant=self.legacy_tenant)

        self.student = StudentProfile.objects.create(
            user=self.student_user, student_id="STAR001", admission_number="ADM-AR-001",
            admission_date=timezone.now().date() - timedelta(days=400),
            guardian_name="Grace Scholar", guardian_phone="+2348010000001", guardian_relation="Mother",
            guardian_email="grace@archive.edu", blood_group="O+", medical_conditions="Asthma",
            current_class=self.classroom, current_term=self.term,
        )

        self.subject = Subject.objects.create(name="Mathematics", code="MTH", tenant=self.legacy_tenant)

    def _client(self, user=None):
        client = APIClient()
        client.force_authenticate(user=user or self.admin)
        return client

    def _add_history(self):
        """Give the student one of every kind of record the archive reports on."""
        StudentSubjectScore.objects.create(
            student=self.student, subject=self.subject, class_group=self.classroom, term=self.term,
            score=Decimal("82.00"), max_score=Decimal("100.00"), grade="A", remarks="Excellent work",
            approval_status="published", tenant=self.legacy_tenant,
        )
        AttendanceRecord.objects.create(
            student=self.student_user, class_group=self.classroom,
            date=timezone.now().date() - timedelta(days=1), status="present", tenant=self.legacy_tenant,
        )
        SchoolFee.objects.create(
            student=self.student, title="Third Term Tuition", amount=Decimal("50000.00"),
            amount_paid=Decimal("20000.00"), due_date=timezone.now().date(), status="partial",
        )
        StudentClassPromotion.objects.create(
            student=self.student, from_class=self.classroom, to_class=self.classroom,
            to_academic_year=self.academic_year, batch_reference="BATCH-1", tenant=self.legacy_tenant,
        )


class ArchivePayloadTests(AlumniTestBase):
    def test_payload_contains_every_record_section(self):
        self._add_history()
        payload = build_student_archive_payload(self.student)

        for section in (
            "profile", "admission", "guardians", "medical", "attendance", "academics",
            "exams", "finance", "documents", "awards", "activities", "discipline",
            "correspondence", "transcript", "testimonial",
        ):
            self.assertIn(section, payload, f"missing section: {section}")

        self.assertEqual(payload["profile"]["student_id"], "STAR001")
        self.assertEqual(payload["medical"]["blood_group"], "O+")
        self.assertEqual(payload["guardians"]["guardians"][0]["name"], "Grace Scholar")
        self.assertEqual(payload["attendance"]["summary"]["present"], 1)
        self.assertEqual(len(payload["academics"]["report_cards"]), 1)
        self.assertEqual(len(payload["academics"]["promotions"]), 1)
        self.assertEqual(payload["finance"]["summary"]["total_billed"], 50000.0)
        self.assertEqual(payload["finance"]["summary"]["outstanding"], 30000.0)

    def test_payload_is_json_serializable(self):
        """The snapshot goes into a JSONField, so no Decimals or dates may survive."""
        import json

        self._add_history()
        payload = build_student_archive_payload(self.student)
        json.dumps(payload)  # raises if anything was left un-coerced


class ArchivePermanenceTests(AlumniTestBase):
    def test_deleting_a_student_seals_a_permanent_archive(self):
        self._add_history()
        self.student.delete()

        record = ArchivedStudentRecord.objects.get(student_id="STAR001")
        self.assertTrue(record.is_sealed)
        self.assertIsNone(record.source_student_id)
        self.assertEqual(record.archive_reason, ArchivedStudentRecord.REASON_DELETED)
        # The history itself survived the cascade that removed the source rows.
        self.assertEqual(len(record.snapshot["academics"]["report_cards"]), 1)
        self.assertEqual(record.snapshot["finance"]["summary"]["total_billed"], 50000.0)
        self.assertFalse(StudentSubjectScore.objects.filter(student_id=self.student.id).exists())

    def test_deleting_the_student_user_also_seals_the_archive(self):
        self._add_history()
        self.student_user.delete()

        record = ArchivedStudentRecord.objects.get(student_id="STAR001")
        self.assertTrue(record.is_sealed)
        self.assertEqual(record.full_name, "Sam Scholar")
        self.assertEqual(record.last_class_name, "SSS 3 - A")

    def test_sealed_records_cannot_be_edited_or_deleted(self):
        snapshot_student(self.student, seal=True)
        record = ArchivedStudentRecord.objects.get(student_id="STAR001")

        record.full_name = "Tampered Name"
        with self.assertRaises(ArchiveProtectedError):
            record.save()
        with self.assertRaises(ArchiveProtectedError):
            record.delete()

    def test_resnapshotting_an_unsealed_record_updates_in_place(self):
        first = snapshot_student(self.student)
        self._add_history()
        second = snapshot_student(self.student)

        self.assertEqual(first.id, second.id)
        self.assertEqual(ArchivedStudentRecord.objects.count(), 1)
        self.assertEqual(len(second.snapshot["academics"]["report_cards"]), 1)


class AlumniApiTests(AlumniTestBase):
    def test_non_admin_cannot_read_the_archive(self):
        response = self._client(self.student_user).get("/api/alumni/students/")
        self.assertEqual(response.status_code, 403)

    def test_overview_lists_filter_options(self):
        response = self._client().get("/api/alumni/overview/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["summary"]["active_students"], 1)
        self.assertIn("2024/2025", [year["name"] for year in response.data["academic_years"]])
        self.assertIn("SSS 3 - A", [item["name"] for item in response.data["classes"]])

    def test_active_student_appears_in_the_list(self):
        response = self._client().get("/api/alumni/students/")
        self.assertEqual(response.status_code, 200)
        rows = response.data["students"]
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["student_id"], "STAR001")
        self.assertTrue(rows[0]["is_active_student"])

    def test_search_matches_name_and_student_id(self):
        client = self._client()
        self.assertEqual(len(client.get("/api/alumni/students/?search=Scholar").data["students"]), 1)
        self.assertEqual(len(client.get("/api/alumni/students/?search=STAR001").data["students"]), 1)
        self.assertEqual(len(client.get("/api/alumni/students/?search=nobody").data["students"]), 0)

    def test_class_and_year_filters_narrow_the_list(self):
        client = self._client()
        self.assertEqual(len(client.get("/api/alumni/students/?class_name=SSS 3 - A").data["students"]), 1)
        self.assertEqual(len(client.get("/api/alumni/students/?class_name=JSS 1 A").data["students"]), 0)
        self.assertEqual(len(client.get("/api/alumni/students/?academic_year=2024/2025").data["students"]), 1)
        self.assertEqual(len(client.get("/api/alumni/students/?academic_year=1999/2000").data["students"]), 0)

    def test_detail_returns_the_full_history_for_an_active_student(self):
        self._add_history()
        response = self._client().get(f"/api/alumni/students/active:{self.student.id}/")
        self.assertEqual(response.status_code, 200)
        student = response.data["student"]
        self.assertTrue(student["is_live"])
        self.assertEqual(student["profile"]["name"], "Sam Scholar")
        self.assertEqual(len(student["academics"]["report_cards"]), 1)

    def test_detail_serves_a_deleted_student_from_the_sealed_snapshot(self):
        self._add_history()
        self.student.delete()
        record = ArchivedStudentRecord.objects.get(student_id="STAR001")

        response = self._client().get(f"/api/alumni/students/archived:{record.id}/")
        self.assertEqual(response.status_code, 200)
        student = response.data["student"]
        self.assertFalse(student["is_live"])
        self.assertEqual(student["profile"]["name"], "Sam Scholar")
        self.assertEqual(len(student["academics"]["report_cards"]), 1)
        self.assertEqual(student["archive"]["status"], "Archived")

    def test_archived_student_stays_searchable_after_deletion(self):
        self.student.delete()
        response = self._client().get("/api/alumni/students/?search=STAR001")
        rows = response.data["students"]
        self.assertEqual(len(rows), 1)
        self.assertFalse(rows[0]["is_active_student"])
        self.assertTrue(rows[0]["is_sealed"])

    def test_detail_accepts_a_bare_student_id(self):
        response = self._client().get("/api/alumni/students/STAR001/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["student"]["profile"]["student_id"], "STAR001")

    def test_archive_is_scoped_to_the_viewers_school(self):
        other_school = SchoolTenant.objects.create(name="Rival School", schema_name="rival_school", is_active=True)
        other_admin = User.objects.create_user(
            email="admin@rival.edu", password="AdminPass123", first_name="Rio", last_name="Rival",
            role="school_admin", tenant=other_school, is_active=True,
        )
        response = self._client(other_admin).get("/api/alumni/students/")
        self.assertEqual(len(response.data["students"]), 0)

        detail = self._client(other_admin).get(f"/api/alumni/students/active:{self.student.id}/")
        self.assertEqual(detail.status_code, 404)

    def test_the_api_is_read_only(self):
        """Every archive endpoint rejects anything that could change a record."""
        client = self._client()
        for method, url in (
            ("post", "/api/alumni/students/"),
            ("patch", f"/api/alumni/students/active:{self.student.id}/"),
            ("delete", f"/api/alumni/students/active:{self.student.id}/"),
            ("put", "/api/alumni/overview/"),
        ):
            response = getattr(client, method)(url, {}, format="json")
            self.assertEqual(response.status_code, 405, f"{method.upper()} {url} should not be allowed")
