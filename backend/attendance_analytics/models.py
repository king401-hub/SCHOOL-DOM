# This app deliberately has no models for Phase 1 (see the "Attendance
# Analytics - Phase 1" plan). Every Phase 1 screen is either one-day x
# N-people or one-person x D-days - both cheap to compute per-request
# directly from academic.AttendanceRecord / attendance.TeacherAttendance /
# hr.StaffAttendance. The N-people x D-days access pattern (termly trends,
# rankings) that would actually justify a pre-aggregated snapshot table is
# Phase 2 scope. Add a DailyAttendanceSnapshot model here *when* Phase 2
# needs it - don't build it speculatively now.
