"""Serializers for attendance app."""
from rest_framework import serializers
from django.utils import timezone
from users.models import User
from .models import AttendanceQRCode, TeacherAttendance, AttendanceReport
from .utils import build_teacher_scan_url


class AttendanceQRCodeSerializer(serializers.ModelSerializer):
    """Serializer for QR code management."""
    qr_url = serializers.SerializerMethodField()
    created_by_name = serializers.CharField(source='created_by.get_full_name', read_only=True)
    
    class Meta:
        model = AttendanceQRCode
        fields = [
            'id', 'is_active', 'created_at', 'updated_at',
            'created_by', 'created_by_name', 'notes', 'qr_url'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at', 'qr_url']
    
    def get_qr_url(self, obj):
        """Return the URL where QR code can be scanned."""
        request = self.context.get('request')
        return build_teacher_scan_url(request, obj)


class TeacherSimpleSerializer(serializers.ModelSerializer):
    """Simple teacher serializer for attendance records."""
    full_name = serializers.CharField(source='get_full_name', read_only=True)
    
    class Meta:
        model = User
        fields = ['id', 'email', 'first_name', 'last_name', 'full_name', 'phone', 'role']


class TeacherAttendanceSerializer(serializers.ModelSerializer):
    """Serializer for teacher attendance records."""
    teacher_details = TeacherSimpleSerializer(source='teacher', read_only=True)
    check_in_time_formatted = serializers.SerializerMethodField()
    check_out_time_formatted = serializers.SerializerMethodField()
    
    class Meta:
        model = TeacherAttendance
        fields = [
            'id', 'teacher', 'teacher_details', 'attendance_date',
            'check_in_time', 'check_in_time_formatted', 'check_out_time',
            'check_out_time_formatted', 'status', 'ip_address', 'device_info', 'notes'
        ]
        read_only_fields = [
            'id', 'attendance_date', 'check_in_time', 'check_out_time', 'ip_address'
        ]
    
    def get_check_in_time_formatted(self, obj):
        """Return formatted check-in time."""
        return timezone.localtime(obj.check_in_time).strftime('%H:%M:%S') if obj.check_in_time else None

    def get_check_out_time_formatted(self, obj):
        """Return formatted check-out time."""
        return timezone.localtime(obj.check_out_time).strftime('%H:%M:%S') if obj.check_out_time else None


class AttendanceListSerializer(serializers.ModelSerializer):
    """Serializer for attendance list view (optimized for display)."""
    teacher_name = serializers.CharField(source='teacher.get_full_name', read_only=True)
    teacher_email = serializers.CharField(source='teacher.email', read_only=True)
    teacher_role = serializers.CharField(source='teacher.role', read_only=True)
    check_in_time_formatted = serializers.SerializerMethodField()
    check_out_time_formatted = serializers.SerializerMethodField()
    device_info = serializers.CharField(read_only=True)
    ip_address = serializers.IPAddressField(read_only=True)
    
    class Meta:
        model = TeacherAttendance
        fields = [
            'id', 'teacher_name', 'teacher_email', 'attendance_date',
            'teacher_role', 'check_in_time', 'check_in_time_formatted',
            'check_out_time', 'check_out_time_formatted', 'status',
            'device_info', 'ip_address',
        ]
        read_only_fields = [
            'id', 'teacher_name', 'teacher_email', 'attendance_date',
            'check_in_time', 'check_in_time_formatted', 'status'
        ]
    
    def get_check_in_time_formatted(self, obj):
        """Return formatted check-in time HH:MM:SS."""
        return timezone.localtime(obj.check_in_time).strftime('%H:%M:%S') if obj.check_in_time else None

    def get_check_out_time_formatted(self, obj):
        """Return formatted check-out time HH:MM:SS."""
        return timezone.localtime(obj.check_out_time).strftime('%H:%M:%S') if obj.check_out_time else None


class AttendanceReportSerializer(serializers.ModelSerializer):
    """Serializer for attendance reports."""
    teacher_name = serializers.CharField(source='teacher.get_full_name', read_only=True)
    teacher_email = serializers.CharField(source='teacher.email', read_only=True)
    
    class Meta:
        model = AttendanceReport
        fields = [
            'id', 'teacher', 'teacher_name', 'teacher_email',
            'period_start', 'period_end', 'total_days', 'present_days',
            'absent_days', 'late_days', 'attendance_percentage', 'generated_at'
        ]
        read_only_fields = [
            'id', 'attendance_percentage', 'generated_at'
        ]


class QRCodeDetailSerializer(serializers.ModelSerializer):
    """Serializer for QR code details with attendance summary."""
    tenant_name = serializers.CharField(source='tenant.name', read_only=True)
    created_by_email = serializers.CharField(source='created_by.email', read_only=True)
    today_attendance_count = serializers.SerializerMethodField()
    qr_url = serializers.SerializerMethodField()
    
    class Meta:
        model = AttendanceQRCode
        fields = [
            'id', 'tenant', 'tenant_name', 'is_active',
            'created_at', 'updated_at', 'created_by', 'created_by_email',
            'notes', 'today_attendance_count', 'qr_url'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']
    
    def get_today_attendance_count(self, obj):
        """Get count of teachers who checked in today."""
        return TeacherAttendance.get_attendance_count_today(obj.tenant)

    def get_qr_url(self, obj):
        """Return the teacher-facing route embedded in the QR code."""
        request = self.context.get('request')
        return build_teacher_scan_url(request, obj)
