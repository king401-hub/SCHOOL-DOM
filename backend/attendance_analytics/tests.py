import datetime

from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from academic.models import AttendanceRecord, Class, SchoolActivityCalendar
from attendance.models import TeacherAttendance
from core.models import SchoolTenant
from hr.models import StaffAttendance, StaffProfile
from rfid_attendance.models import GateSettings
from rfid_attendance.services import _legacy_tenant_for_attendance
from users.models import StudentProfile, User

from . import services


def _make_school(name, schema):
    return SchoolTenant.objects.create(name=name, schema_name=schema, is_active=True)


def _make_gate_settings(school, **overrides):
    defaults = dict(
        early_start=datetime.time(7, 30), early_end=datetime.time(8, 30),
        clockout_start=datetime.time(13, 0), clockout_end=datetime.time(16, 0),
    )
    defaults.update(overrides)
    return GateSettings.objects.create(tenant=school, **defaults)


class ExpectedWorkingDaysTests(TestCase):
    def setUp(self):
        self.school = _make_school("EWD School", "aa_ewd_school")

    def test_excludes_weekends(self):
        # 2026-01-05 (Mon) .. 2026-01-11 (Sun) - a full week
        days = services.expected_working_days(self.school, datetime.date(2026, 1, 5), datetime.date(2026, 1, 11))
        self.assertEqual(days, [datetime.date(2026, 1, d) for d in (5, 6, 7, 8, 9)])

    def test_excludes_flagged_holiday_but_not_an_unflagged_entry(self):
        legacy_tenant = _legacy_tenant_for_attendance(self.school)
        SchoolActivityCalendar.objects.create(
            tenant=legacy_tenant, month=1, year=2026, title="Public Holiday",
            activity_date=datetime.date(2026, 1, 6), is_non_school_day=True,
        )
        SchoolActivityCalendar.objects.create(
            tenant=legacy_tenant, month=1, year=2026, title="Sports Day",
            activity_date=datetime.date(2026, 1, 7), is_non_school_day=False,
        )
        days = services.expected_working_days(self.school, datetime.date(2026, 1, 5), datetime.date(2026, 1, 9))
        self.assertNotIn(datetime.date(2026, 1, 6), days)
        self.assertIn(datetime.date(2026, 1, 7), days)

    def test_is_a_pure_calendar_function_independent_of_now(self):
        # Including a future date in the range does not exclude it - that's
        # handled separately by day_status, not by this denominator function.
        days = services.expected_working_days(self.school, datetime.date(2026, 1, 5), datetime.date(2026, 1, 9))
        self.assertEqual(len(days), 5)


class DayStatusTests(TestCase):
    def setUp(self):
        self.school = _make_school("Day Status School", "aa_daystatus_school")
        self.gate_settings = _make_gate_settings(self.school)

    def test_no_record_past_cutoff_is_absent(self):
        past_day = datetime.date(2026, 1, 5)
        now = timezone.make_aware(datetime.datetime(2026, 1, 10, 9, 0))
        result = services.day_status(self.school, past_day, None, None, gate_settings=self.gate_settings, now=now)
        self.assertEqual(result["status"], "absent")

    def test_no_record_today_before_cutoff_is_in_progress_never_absent(self):
        today = datetime.date(2026, 1, 10)
        now = timezone.make_aware(datetime.datetime(2026, 1, 10, 9, 0))  # before clockout_end (16:00)
        result = services.day_status(self.school, today, None, None, gate_settings=self.gate_settings, now=now)
        self.assertEqual(result["status"], "in_progress")
        self.assertNotEqual(result["status"], "absent")

    def test_no_record_today_after_cutoff_is_absent(self):
        today = datetime.date(2026, 1, 10)
        now = timezone.make_aware(datetime.datetime(2026, 1, 10, 17, 0))  # after clockout_end
        result = services.day_status(self.school, today, None, None, gate_settings=self.gate_settings, now=now)
        self.assertEqual(result["status"], "absent")

    def test_clock_in_in_early_window_is_not_late(self):
        day = datetime.date(2026, 1, 5)
        clock_in = timezone.make_aware(datetime.datetime(2026, 1, 5, 8, 0))
        result = services.day_status(self.school, day, clock_in, None, gate_settings=self.gate_settings)
        self.assertFalse(result["is_late"])

    def test_clock_in_in_late_bucket_is_late(self):
        day = datetime.date(2026, 1, 5)
        clock_in = timezone.make_aware(datetime.datetime(2026, 1, 5, 10, 0))  # between early_end and clockout_start
        result = services.day_status(self.school, day, clock_in, None, gate_settings=self.gate_settings)
        self.assertTrue(result["is_late"])

    def test_clocked_out_before_window_opens_is_early_departure(self):
        day = datetime.date(2026, 1, 5)
        clock_in = timezone.make_aware(datetime.datetime(2026, 1, 5, 8, 0))
        clock_out = timezone.make_aware(datetime.datetime(2026, 1, 5, 11, 0))  # before clockout_start (13:00)
        result = services.day_status(self.school, day, clock_in, clock_out, gate_settings=self.gate_settings)
        self.assertTrue(result["is_early_departure"])

    def test_present_with_no_clock_out_has_hours_none_and_not_clocked_out(self):
        day = datetime.date(2026, 1, 5)
        clock_in = timezone.make_aware(datetime.datetime(2026, 1, 5, 8, 0))
        result = services.day_status(self.school, day, clock_in, None, gate_settings=self.gate_settings)
        self.assertIsNone(result["hours"])
        self.assertFalse(result["clocked_out"])

    def test_hours_computed_for_a_completed_session(self):
        day = datetime.date(2026, 1, 5)
        clock_in = timezone.make_aware(datetime.datetime(2026, 1, 5, 8, 0))
        clock_out = timezone.make_aware(datetime.datetime(2026, 1, 5, 15, 30))
        result = services.day_status(self.school, day, clock_in, clock_out, gate_settings=self.gate_settings)
        self.assertEqual(result["hours"], 7.5)


class ManualStatusDayTests(TestCase):
    """The non-teaching-staff path - hr.StaffAttendance has no clock
    timestamps, so this never derives late/early/hours, only present/absent/
    excused from the stored status."""

    def test_present_late_and_half_day_all_count_as_present(self):
        for value in (StaffAttendance.PRESENT, StaffAttendance.LATE, StaffAttendance.HALF_DAY):
            result = services.day_status_from_manual_status(value, datetime.date(2026, 1, 5), True)
            self.assertEqual(result["status"], "present")
            self.assertIsNone(result["is_late"])

    def test_excused_is_excluded_not_counted_absent(self):
        result = services.day_status_from_manual_status(StaffAttendance.EXCUSED, datetime.date(2026, 1, 5), True)
        self.assertEqual(result["status"], "excused")

    def test_absent_status_only_resolves_once_cutoff_passed(self):
        result_pending = services.day_status_from_manual_status(StaffAttendance.ABSENT, datetime.date(2026, 1, 5), False)
        self.assertEqual(result_pending["status"], "in_progress")
        result_resolved = services.day_status_from_manual_status(StaffAttendance.ABSENT, datetime.date(2026, 1, 5), True)
        self.assertEqual(result_resolved["status"], "absent")

    def test_no_row_at_all_behaves_like_explicit_absent(self):
        result = services.day_status_from_manual_status(None, datetime.date(2026, 1, 5), True)
        self.assertEqual(result["status"], "absent")


class AttendancePercentTests(TestCase):
    def test_zero_expected_days_returns_zero_not_divide_by_zero(self):
        self.assertEqual(services.attendance_percent(0, 0), 0.0)

    def test_normal_calculation(self):
        self.assertEqual(services.attendance_percent(60, 65), 92.3)

    def test_person_with_zero_records_in_range_shows_zero_percent(self):
        school = _make_school("Zero Records School", "aa_zero_school")
        _make_gate_settings(school)
        stats = services.compute_person_period_stats(
            school, datetime.date(2026, 1, 5), datetime.date(2026, 1, 9), {},
        )
        self.assertEqual(stats["attendance_percent"], 0.0)
        self.assertEqual(stats["days_present"], 0)


class LateNeverDoubleCountedTests(TestCase):
    def setUp(self):
        self.school = _make_school("Donut School", "aa_donut_school")
        self.gate_settings = _make_gate_settings(self.school)

    def test_present_count_includes_late_days(self):
        day = datetime.date(2026, 1, 5)
        clock_in = timezone.make_aware(datetime.datetime(2026, 1, 5, 10, 0))  # late bucket
        stats = services.compute_person_period_stats(
            self.school, day, day, {day: {"clock_in_at": clock_in, "clock_out_at": None}},
            gate_settings=self.gate_settings,
        )
        self.assertEqual(stats["days_present"], 1)
        self.assertEqual(stats["late_arrivals"], 1)

    def test_bulk_day_stats_segments_sum_exactly_to_total_registered(self):
        day = datetime.date(2026, 1, 5)
        on_time = timezone.make_aware(datetime.datetime(2026, 1, 5, 8, 0))
        late = timezone.make_aware(datetime.datetime(2026, 1, 5, 10, 0))
        now = timezone.make_aware(datetime.datetime(2026, 1, 5, 17, 0))  # past cutoff
        records = {
            "on_time_person": {"clock_in_at": on_time, "clock_out_at": None},
            "late_person": {"clock_in_at": late, "clock_out_at": None},
            "absent_person": {"clock_in_at": None, "clock_out_at": None},
        }
        stats = services.compute_bulk_day_stats(self.school, day, records, gate_settings=self.gate_settings, now=now)
        self.assertEqual(
            stats["present_on_time"] + stats["present_late"] + stats["total_absent"] + stats["unresolved"],
            stats["total_registered"],
        )
        self.assertEqual(stats["present_on_time"], 1)
        self.assertEqual(stats["present_late"], 1)
        self.assertEqual(stats["total_absent"], 1)

    def test_bulk_day_stats_counts_early_departures(self):
        day = datetime.date(2026, 1, 5)
        clock_in = timezone.make_aware(datetime.datetime(2026, 1, 5, 8, 0))
        early_clock_out = timezone.make_aware(datetime.datetime(2026, 1, 5, 11, 0))  # before clockout_start (13:00)
        records = {"early_leaver": {"clock_in_at": clock_in, "clock_out_at": early_clock_out}}
        stats = services.compute_bulk_day_stats(self.school, day, records, gate_settings=self.gate_settings)
        self.assertEqual(stats["early_departures"], 1)
        self.assertEqual(stats["not_yet_clocked_out"], 0)


class OverviewAndDailyViewTests(TestCase):
    def setUp(self):
        self.school = _make_school("View School", "aa_view_school")
        _make_gate_settings(self.school)
        self.admin = User.objects.create_user(
            email="admin@viewschool.test", password="testpass123", role="school_admin", tenant=self.school,
        )
        self.client = APIClient()
        self.client.force_authenticate(user=self.admin)

    def test_non_admin_cannot_view_overview(self):
        teacher = User.objects.create_user(
            email="teacher@viewschool.test", password="testpass123", role="teacher", tenant=self.school,
        )
        client = APIClient()
        client.force_authenticate(user=teacher)
        resp = client.get("/api/attendance-analytics/overview/")
        self.assertEqual(resp.status_code, 403)

    def test_admin_can_view_overview_with_both_scope_by_default(self):
        resp = self.client.get("/api/attendance-analytics/overview/")
        self.assertEqual(resp.status_code, 200)
        self.assertIn("staff", resp.data)
        self.assertIn("students", resp.data)

    def test_staff_only_scope_omits_students_key_and_403s_student_daily(self):
        self.school.attendance_analytics_scope = SchoolTenant.SCOPE_STAFF_ONLY
        self.school.save(update_fields=["attendance_analytics_scope"])

        overview_resp = self.client.get("/api/attendance-analytics/overview/")
        self.assertEqual(overview_resp.status_code, 200)
        self.assertNotIn("students", overview_resp.data)
        self.assertIn("staff", overview_resp.data)

        daily_resp = self.client.get("/api/attendance-analytics/daily/?population=student")
        self.assertEqual(daily_resp.status_code, 403)

    def test_student_only_scope_omits_staff_key_and_403s_staff_daily(self):
        self.school.attendance_analytics_scope = SchoolTenant.SCOPE_STUDENT_ONLY
        self.school.save(update_fields=["attendance_analytics_scope"])

        overview_resp = self.client.get("/api/attendance-analytics/overview/")
        self.assertNotIn("staff", overview_resp.data)
        self.assertIn("students", overview_resp.data)

        daily_resp = self.client.get("/api/attendance-analytics/daily/?population=staff")
        self.assertEqual(daily_resp.status_code, 403)


class DailyRegisterIntegrationTests(TestCase):
    """End-to-end through the real models, confirming the fetch adapters and
    register row-building work against actual AttendanceRecord/
    TeacherAttendance/StaffAttendance rows, not just hand-built dicts."""

    def setUp(self):
        self.school = _make_school("Register School", "aa_register_school")
        _make_gate_settings(self.school)
        self.admin = User.objects.create_user(
            email="admin@registerschool.test", password="testpass123", role="school_admin", tenant=self.school,
        )
        self.school_class = Class.objects.create(tenant=_legacy_tenant_for_attendance(self.school), name="JSS1", section="A")
        self.client = APIClient()
        self.client.force_authenticate(user=self.admin)

    def test_student_register_reflects_a_real_attendance_record(self):
        student_user = User.objects.create_user(
            email="student@registerschool.test", password="testpass123", role="student", tenant=self.school,
            first_name="Reg", last_name="Student",
        )
        StudentProfile.objects.create(
            user=student_user, student_id="REG001", admission_number="ADM-REG-001",
            admission_date=datetime.date(2024, 9, 1), guardian_name="Guardian",
            guardian_phone="08010000000", guardian_relation="Parent", current_class=self.school_class,
        )
        today = timezone.localdate()
        AttendanceRecord.objects.create(
            student=student_user, class_group=self.school_class, date=today,
            clock_in_at=timezone.now(), status="present",
        )

        resp = self.client.get(f"/api/attendance-analytics/daily/register/?population=student&date={today.isoformat()}")
        self.assertEqual(resp.status_code, 200)
        names = [row["name"] for row in resp.data["results"]]
        self.assertIn(student_user.get_full_name(), names)

    def test_staff_register_includes_both_teachers_and_nonteaching_staff(self):
        teacher = User.objects.create_user(
            email="teacher@registerschool.test", password="testpass123", role="teacher", tenant=self.school,
            first_name="Teach", last_name="Er",
        )
        TeacherAttendance.objects.create(tenant=self.school, teacher=teacher)

        nonteaching = StaffProfile.objects.create(
            tenant=self.school, staff_code="NT001", first_name="Guard", last_name="Ian",
            staff_type=StaffProfile.NON_TEACHING, role="Security", department="Security",
        )
        StaffAttendance.objects.create(staff=nonteaching, date=timezone.localdate(), status=StaffAttendance.PRESENT)

        resp = self.client.get("/api/attendance-analytics/daily/register/?population=staff")
        self.assertEqual(resp.status_code, 200)
        names = [row["name"] for row in resp.data["results"]]
        self.assertIn(teacher.get_full_name(), names)
        self.assertIn(nonteaching.full_name, names)
