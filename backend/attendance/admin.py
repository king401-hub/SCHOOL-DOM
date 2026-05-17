"""Django admin configuration for attendance app."""
from django.contrib import admin
from django.utils.html import format_html
from .models import AttendanceQRCode, TeacherAttendance, AttendanceReport


@admin.register(AttendanceQRCode)
class AttendanceQRCodeAdmin(admin.ModelAdmin):
    """Admin interface for QR codes."""
    list_display = ['id', 'tenant', 'is_active', 'created_by', 'created_at']
    list_filter = ['is_active', 'created_at', 'tenant']
    search_fields = ['token', 'tenant__name', 'created_by__email']
    readonly_fields = ['id', 'token', 'created_at', 'updated_at']
    fieldsets = (
        ('QR Code Information', {
            'fields': ('id', 'token', 'tenant', 'is_active')
        }),
        ('Metadata', {
            'fields': ('created_by', 'notes', 'created_at', 'updated_at')
        }),
    )
    
    def has_delete_permission(self, request):
        # Prevent accidental deletion
        return request.user.is_superuser


@admin.register(TeacherAttendance)
class TeacherAttendanceAdmin(admin.ModelAdmin):
    """Admin interface for teacher attendance records."""
    list_display = ['teacher_email', 'attendance_date', 'check_in_time_formatted', 'status', 'check_in_map', 'tenant']
    list_filter = ['status', 'attendance_date', 'tenant', 'check_in_time']
    search_fields = ['teacher__email', 'teacher__first_name', 'teacher__last_name', 'tenant__name', 'check_in_address', 'check_out_address']
    readonly_fields = [
        'id', 'check_in_time', 'attendance_date', 'ip_address',
        'check_in_map', 'check_out_map',
    ]
    fieldsets = (
        ('Attendance Record', {
            'fields': ('id', 'teacher', 'attendance_date', 'check_in_time', 'check_out_time', 'status')
        }),
        ('Device Information', {
            'fields': ('ip_address', 'device_info', 'client_device_info')
        }),
        ('Geo Tracking', {
            'fields': (
                'check_in_latitude', 'check_in_longitude', 'check_in_accuracy_meters', 'check_in_address', 'check_in_map',
                'check_out_latitude', 'check_out_longitude', 'check_out_accuracy_meters', 'check_out_address', 'check_out_map',
            )
        }),
        ('Additional Info', {
            'fields': ('tenant', 'qr_code', 'notes')
        }),
    )
    date_hierarchy = 'attendance_date'
    
    def teacher_email(self, obj):
        return obj.teacher.email
    teacher_email.short_description = 'Teacher'
    
    def check_in_time_formatted(self, obj):
        return obj.check_in_time.strftime('%H:%M:%S') if obj.check_in_time else '-'
    check_in_time_formatted.short_description = 'Check-in Time'

    def check_in_map(self, obj):
        return self._map_link(obj.check_in_latitude, obj.check_in_longitude)
    check_in_map.short_description = 'Check-in Map'

    def check_out_map(self, obj):
        return self._map_link(obj.check_out_latitude, obj.check_out_longitude)
    check_out_map.short_description = 'Check-out Map'

    def _map_link(self, latitude, longitude):
        if latitude is None or longitude is None:
            return '-'
        url = f'https://www.google.com/maps?q={latitude},{longitude}'
        return format_html('<a href="{}" target="_blank" rel="noopener">View map</a>', url)
    
    def has_add_permission(self, request):
        # Attendance should only be created via QR code scanning
        return request.user.is_superuser
    
    def has_delete_permission(self, request):
        # Restrict deletion
        return request.user.is_superuser


@admin.register(AttendanceReport)
class AttendanceReportAdmin(admin.ModelAdmin):
    """Admin interface for attendance reports."""
    list_display = ['teacher_email', 'period_start', 'period_end', 'attendance_percentage', 'generated_at']
    list_filter = ['period_start', 'period_end', 'generated_at', 'tenant']
    search_fields = ['teacher__email', 'teacher__first_name', 'teacher__last_name']
    readonly_fields = ['id', 'generated_at', 'attendance_percentage']
    fieldsets = (
        ('Report Information', {
            'fields': ('id', 'teacher', 'period_start', 'period_end', 'tenant')
        }),
        ('Attendance Statistics', {
            'fields': ('total_days', 'present_days', 'absent_days', 'late_days', 'attendance_percentage')
        }),
        ('Metadata', {
            'fields': ('generated_by', 'generated_at')
        }),
    )
    date_hierarchy = 'period_start'
    
    def teacher_email(self, obj):
        return obj.teacher.email
    teacher_email.short_description = 'Teacher'
