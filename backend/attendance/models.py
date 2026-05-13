"""Teacher attendance tracking with QR code support."""
import uuid
from django.db import models
from django.utils import timezone
from django.db.models import Q
from django.contrib.auth import get_user_model

User = get_user_model()


class AttendanceQRCode(models.Model):
    """
    Single, static QR code for teacher attendance.
    Shared by all teachers in a school tenant.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.OneToOneField(
        'core.SchoolTenant',
        on_delete=models.CASCADE,
        related_name='attendance_qr_code',
        help_text="School tenant this QR code belongs to"
    )
    token = models.CharField(
        max_length=64,
        unique=True,
        help_text="Secure token embedded in QR code"
    )
    
    # Status
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    # Metadata
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name='created_qr_codes'
    )
    notes = models.TextField(blank=True, default="")
    
    class Meta:
        verbose_name = "Attendance QR Code"
        verbose_name_plural = "Attendance QR Codes"
        ordering = ['-created_at']
    
    def __str__(self):
        return f"QR Code for {self.tenant.name}"
    
    @classmethod
    def get_or_create_for_tenant(cls, tenant):
        """Get existing or create new QR code for tenant."""
        qr_code, created = cls.objects.get_or_create(
            tenant=tenant,
            defaults={'token': cls.static_token_for_tenant(tenant)}
        )
        static_token = cls.static_token_for_tenant(tenant)
        if not created and qr_code.token != static_token:
            qr_code.token = static_token
            qr_code.save(update_fields=['token', 'updated_at'])
        return qr_code, created

    @staticmethod
    def static_token_for_tenant(tenant):
        """Return the stable token used in the shared attendance QR code."""
        return f"schooldom-attendance-{tenant.id}"
    
    @classmethod
    def verify_token(cls, token):
        """Verify QR token and return QR code if valid."""
        try:
            qr_code = cls.objects.get(token=token, is_active=True)
            return qr_code
        except cls.DoesNotExist:
            return None


class TeacherAttendance(models.Model):
    """
    Daily attendance record for teachers.
    Each teacher can mark attendance only once per day.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    teacher = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='teacher_attendances',
        limit_choices_to={'role': 'teacher'}
    )
    tenant = models.ForeignKey(
        'core.SchoolTenant',
        on_delete=models.CASCADE,
        related_name='teacher_attendance'
    )
    qr_code = models.ForeignKey(
        AttendanceQRCode,
        on_delete=models.SET_NULL,
        null=True,
        related_name='attendance_records'
    )
    
    # Attendance details
    attendance_date = models.DateField(auto_now_add=True)
    check_in_time = models.DateTimeField(auto_now_add=True)
    check_out_time = models.DateTimeField(null=True, blank=True)
    
    # Status
    STATUS_CHOICES = [
        ('checked_in', 'Checked In'),
        ('present', 'Present'),
        ('absent', 'Absent'),
        ('late', 'Late'),
    ]
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='present'
    )
    
    # Additional info
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    device_info = models.CharField(max_length=255, blank=True, default="")
    notes = models.TextField(blank=True, default="")
    
    class Meta:
        verbose_name = "Teacher Attendance"
        verbose_name_plural = "Teacher Attendances"
        ordering = ['-attendance_date', '-check_in_time']
        # Ensure one attendance per teacher per day
        unique_together = ('teacher', 'attendance_date')
        indexes = [
            models.Index(fields=['teacher', 'attendance_date']),
            models.Index(fields=['tenant', 'attendance_date']),
            models.Index(fields=['check_in_time']),
        ]
    
    def __str__(self):
        return f"{self.teacher.email} - {self.attendance_date} - {self.status}"
    
    @classmethod
    def has_checked_in_today(cls, teacher, date=None):
        """Check if teacher has already marked attendance today."""
        if date is None:
            date = timezone.localdate()
        return cls.objects.filter(
            teacher=teacher,
            attendance_date=date
        ).exists()
    
    @classmethod
    def get_today_attendance(cls, tenant, date=None):
        """Get all attendance records for today."""
        if date is None:
            date = timezone.localdate()
        return cls.objects.filter(
            tenant=tenant,
            attendance_date=date
        ).select_related('teacher').order_by('-check_in_time')
    
    @classmethod
    def get_attendance_count_today(cls, tenant, date=None):
        """Get count of teachers checked in today."""
        if date is None:
            date = timezone.localdate()
        return cls.objects.filter(
            tenant=tenant,
            attendance_date=date
        ).count()


class AttendanceReport(models.Model):
    """
    Monthly or custom period attendance report for a teacher.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    teacher = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='attendance_reports'
    )
    tenant = models.ForeignKey(
        'core.SchoolTenant',
        on_delete=models.CASCADE,
        related_name='attendance_reports'
    )
    
    period_start = models.DateField()
    period_end = models.DateField()
    
    total_days = models.IntegerField(default=0)
    present_days = models.IntegerField(default=0)
    absent_days = models.IntegerField(default=0)
    late_days = models.IntegerField(default=0)
    
    attendance_percentage = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=0.00
    )
    
    generated_at = models.DateTimeField(auto_now_add=True)
    generated_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name='generated_reports'
    )
    
    class Meta:
        verbose_name = "Attendance Report"
        verbose_name_plural = "Attendance Reports"
        ordering = ['-period_start']
        unique_together = ('teacher', 'period_start', 'period_end')
    
    def __str__(self):
        return f"{self.teacher.email} - {self.period_start} to {self.period_end}"
