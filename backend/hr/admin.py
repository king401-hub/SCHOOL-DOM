from django.contrib import admin

from .models import (
    LeaveRequest,
    PayrollRecord,
    SalaryAdvanceRequest,
    StaffActivity,
    StaffAttendance,
    StaffProfile,
)


@admin.register(StaffProfile)
class StaffProfileAdmin(admin.ModelAdmin):
    list_display = ("staff_code", "full_name", "staff_type", "role", "department", "base_salary", "employment_status")
    list_filter = ("staff_type", "department", "employment_status")
    search_fields = ("staff_code", "first_name", "last_name", "email", "role", "department", "emergency_contact_name")


@admin.register(StaffAttendance)
class StaffAttendanceAdmin(admin.ModelAdmin):
    list_display = ("staff", "date", "status", "check_in", "check_out")
    list_filter = ("status", "date")
    search_fields = ("staff__first_name", "staff__last_name", "staff__staff_code")


@admin.register(LeaveRequest)
class LeaveRequestAdmin(admin.ModelAdmin):
    list_display = ("staff", "leave_type", "start_date", "end_date", "status")
    list_filter = ("status", "leave_type")
    search_fields = ("staff__first_name", "staff__last_name", "staff__staff_code")


@admin.register(SalaryAdvanceRequest)
class SalaryAdvanceRequestAdmin(admin.ModelAdmin):
    list_display = ("staff", "amount", "status", "request_date")
    list_filter = ("status", "request_date")
    search_fields = ("staff__first_name", "staff__last_name", "staff__staff_code")


@admin.register(PayrollRecord)
class PayrollRecordAdmin(admin.ModelAdmin):
    list_display = ("staff", "period_label", "net_salary", "amount_paid", "balance_after_payment", "status")
    list_filter = ("status", "year", "month")
    search_fields = ("staff__first_name", "staff__last_name", "staff__staff_code")


@admin.register(StaffActivity)
class StaffActivityAdmin(admin.ModelAdmin):
    list_display = ("action", "staff", "actor", "created_at")
    list_filter = ("action", "created_at")
    search_fields = ("staff__first_name", "staff__last_name", "details")
