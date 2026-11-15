from django.contrib import admin

from .models import FaceGateDevice, FaceGateEnrollment


@admin.register(FaceGateDevice)
class FaceGateDeviceAdmin(admin.ModelAdmin):
    list_display = ['device_id', 'label', 'tenant', 'is_active', 'last_seen_at', 'next_employee_number']
    list_filter = ['is_active', 'tenant']
    search_fields = ['device_id', 'label']
    readonly_fields = ['id', 'next_employee_number', 'created_at', 'updated_at']


@admin.register(FaceGateEnrollment)
class FaceGateEnrollmentAdmin(admin.ModelAdmin):
    list_display = ['user', 'device', 'device_employee_number', 'status', 'last_note_time']
    list_filter = ['status', 'device']
    search_fields = ['user__email', 'user__first_name', 'user__last_name']
    readonly_fields = ['id', 'device_employee_number', 'created_at', 'updated_at']
    raw_id_fields = ['user']
