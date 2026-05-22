from django.db import models
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator, MaxValueValidator
from django.utils import timezone
from core.models import TimeStampedModel
from core.tenant import SchoolTenant
from users.models import User
import uuid
import json


class UUIDModel(models.Model):
    """
    Abstract base model that provides UUID as primary key.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    
    class Meta:
        abstract = True

class NotificationTemplate(TimeStampedModel, UUIDModel):
    """
    Reusable notification templates for different events.
    """
    tenant = models.ForeignKey(SchoolTenant, on_delete=models.CASCADE, null=True, blank=True)
    name = models.CharField(max_length=200)
    code = models.CharField(max_length=50, unique=True)
    
    EVENT_TYPES = [
        ('exam_published', 'Exam Published'),
        ('exam_graded', 'Exam Graded'),
        ('assignment_posted', 'Assignment Posted'),
        ('assignment_graded', 'Assignment Graded'),
        ('fee_due', 'Fee Due'),
        ('payment_received', 'Payment Received'),
        ('receipt_generated', 'Receipt Generated'),
        ('result_published', 'Result Published'),
        ('attendance_marked', 'Attendance Marked'),
        ('announcement', 'Announcement'),
        ('message_received', 'Message Received'),
        ('account_created', 'Account Created'),
        ('password_reset', 'Password Reset'),
        ('email_verification', 'Email Verification'),
        ('class_schedule', 'Class Schedule'),
        ('holiday', 'Holiday'),
        ('event', 'Event'),
        ('alert', 'Alert'),
        ('reminder', 'Reminder'),
        ('system', 'System Notification'),
    ]
    event_type = models.CharField(max_length=50, choices=EVENT_TYPES)
    
    # Content templates with placeholders
    subject_template = models.CharField(max_length=200)
    email_body_template = models.TextField()
    sms_template = models.TextField(blank=True, null=True)
    push_title_template = models.CharField(max_length=100)
    push_body_template = models.TextField()
    in_app_template = models.TextField()
    
    # Available channels
    can_email = models.BooleanField(default=True)
    can_sms = models.BooleanField(default=False)
    can_push = models.BooleanField(default=True)
    can_in_app = models.BooleanField(default=True)
    
    # Priority
    PRIORITY_CHOICES = [
        (1, 'Low'),
        (2, 'Normal'),
        (3, 'High'),
        (4, 'Urgent'),
    ]
    default_priority = models.IntegerField(choices=PRIORITY_CHOICES, default=2)
    
    # Expiry
    expiry_hours = models.IntegerField(default=48, help_text="Notification expires after X hours")
    
    is_active = models.BooleanField(default=True)
    
    class Meta:
        verbose_name = "Notification Template"
        verbose_name_plural = "Notification Templates"
        unique_together = [['tenant', 'code']]
    
    def __str__(self):
        return f"{self.name} ({self.code})"

class Notification(TimeStampedModel, UUIDModel):
    """
    Individual notifications sent to users.
    """
    tenant = models.ForeignKey(SchoolTenant, on_delete=models.CASCADE)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='notifications')
    template = models.ForeignKey(NotificationTemplate, on_delete=models.SET_NULL, null=True, blank=True)
    
    # Notification content
    title = models.CharField(max_length=200)
    message = models.TextField()
    
    NOTIFICATION_TYPES = [
        ('info', 'Information'),
        ('success', 'Success'),
        ('warning', 'Warning'),
        ('error', 'Error'),
        ('alert', 'Alert'),
        ('reminder', 'Reminder'),
        ('achievement', 'Achievement'),
        ('update', 'Update'),
    ]
    notification_type = models.CharField(max_length=20, choices=NOTIFICATION_TYPES, default='info')
    
    PRIORITY_CHOICES = [
        (1, 'Low'),
        (2, 'Normal'),
        (3, 'High'),
        (4, 'Urgent'),
    ]
    priority = models.IntegerField(choices=PRIORITY_CHOICES, default=2)
    
    # Action
    action_url = models.URLField(null=True, blank=True)
    action_text = models.CharField(max_length=50, null=True, blank=True)
    deep_link = models.CharField(max_length=255, null=True, blank=True)
    
    # Metadata
    event_type = models.CharField(max_length=50, blank=True, null=True)
    reference_id = models.UUIDField(null=True, blank=True)
    reference_model = models.CharField(max_length=100, blank=True, null=True)
    
    # Delivery status
    CHANNEL_CHOICES = [
        ('email', 'Email'),
        ('sms', 'SMS'),
        ('push', 'Push'),
        ('in_app', 'In-App'),
    ]
    channel = models.CharField(max_length=20, choices=CHANNEL_CHOICES)
    
    # Read status
    is_read = models.BooleanField(default=False)
    read_at = models.DateTimeField(null=True, blank=True)
    
    # Delivery status
    is_delivered = models.BooleanField(default=False)
    delivered_at = models.DateTimeField(null=True, blank=True)
    delivery_error = models.TextField(blank=True, null=True)
    
    # User interaction
    is_archived = models.BooleanField(default=False)
    is_dismissed = models.BooleanField(default=False)
    dismissed_at = models.DateTimeField(null=True, blank=True)
    
    # Expiry
    expires_at = models.DateTimeField(null=True, blank=True)
    
    # Image/Icon
    icon = models.CharField(max_length=100, blank=True, null=True)
    image = models.ImageField(upload_to='notifications/', null=True, blank=True)
    
    class Meta:
        verbose_name = "Notification"
        verbose_name_plural = "Notifications"
        ordering = ['-priority', '-created_at']
        indexes = [
            models.Index(fields=['user', '-created_at']),
            models.Index(fields=['is_read', '-created_at']),
            models.Index(fields=['notification_type', '-created_at']),
        ]
    
    def __str__(self):
        return f"{self.user.get_full_name()} - {self.title[:50]}"

    def clean(self):
        super().clean()
        if self.user_id and self.tenant_id and self.user.tenant_id != self.tenant_id:
            raise ValidationError("Notification tenant must match the recipient user's tenant.")

    def save(self, *args, **kwargs):
        self.clean()
        super().save(*args, **kwargs)
    
    def mark_as_read(self):
        self.is_read = True
        self.read_at = timezone.now()
        self.save(update_fields=['is_read', 'read_at'])
    
    def mark_as_delivered(self):
        self.is_delivered = True
        self.delivered_at = timezone.now()
        self.save(update_fields=['is_delivered', 'delivered_at'])

class NotificationPreference(TimeStampedModel, UUIDModel):
    """
    User preferences for receiving notifications.
    """
    tenant = models.ForeignKey(SchoolTenant, on_delete=models.CASCADE)
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='notification_preferences')
    
    # Global opt-out
    disable_all = models.BooleanField(default=False)
    
    # Channel preferences
    allow_email = models.BooleanField(default=True)
    allow_sms = models.BooleanField(default=False)
    allow_push = models.BooleanField(default=True)
    allow_in_app = models.BooleanField(default=True)
    
    # Quiet hours
    enable_quiet_hours = models.BooleanField(default=False)
    quiet_hours_start = models.TimeField(null=True, blank=True)
    quiet_hours_end = models.TimeField(null=True, blank=True)
    quiet_hours_timezone = models.CharField(max_length=50, default='UTC')
    
    # Frequency
    FREQUENCY_CHOICES = [
        ('immediate', 'Immediate'),
        ('hourly', 'Hourly Digest'),
        ('daily', 'Daily Digest'),
        ('weekly', 'Weekly Digest'),
        ('never', 'Never'),
    ]
    email_frequency = models.CharField(max_length=20, choices=FREQUENCY_CHOICES, default='immediate')
    push_frequency = models.CharField(max_length=20, choices=FREQUENCY_CHOICES, default='immediate')
    
    # Per-event type preferences (JSON)
    event_preferences = models.JSONField(default=dict, help_text="Fine-grained control per event type")
    
    # Device tokens for push notifications
    device_tokens = models.JSONField(default=list, blank=True)
    
    class Meta:
        verbose_name = "Notification Preference"
        verbose_name_plural = "Notification Preferences"
    
    def __str__(self):
        return f"Notification Preferences - {self.user.get_full_name()}"

class NotificationDigest(TimeStampedModel, UUIDModel):
    """
    Digest of notifications sent at scheduled intervals.
    """
    tenant = models.ForeignKey(SchoolTenant, on_delete=models.CASCADE)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='notification_digests')
    
    DIGEST_TYPE_CHOICES = [
        ('hourly', 'Hourly'),
        ('daily', 'Daily'),
        ('weekly', 'Weekly'),
    ]
    digest_type = models.CharField(max_length=20, choices=DIGEST_TYPE_CHOICES)
    
    # Period covered
    period_start = models.DateTimeField()
    period_end = models.DateTimeField()
    
    # Summary
    total_notifications = models.IntegerField(default=0)
    summary_data = models.JSONField(default=dict)
    
    # Content
    email_sent = models.BooleanField(default=False)
    email_sent_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        verbose_name = "Notification Digest"
        verbose_name_plural = "Notification Digests"
        ordering = ['-period_end']
    
    def __str__(self):
        return f"{self.user.get_full_name()} - {self.digest_type} Digest ({self.period_start.date()})"

class Announcement(TimeStampedModel, UUIDModel):
    """
    School-wide announcements with targeting.
    """
    tenant = models.ForeignKey(SchoolTenant, on_delete=models.CASCADE, related_name='announcements')
    title = models.CharField(max_length=200)
    slug = models.SlugField(max_length=250, unique=True)
    summary = models.TextField(max_length=500, blank=True, null=True)
    content = models.TextField()
    
    # Author
    author = models.ForeignKey(User, on_delete=models.CASCADE, related_name='authored_announcements')
    
    # Targeting
    AUDIENCE_CHOICES = [
        ('all', 'Everyone'),
        ('students', 'All Students'),
        ('teachers', 'All Teachers'),
        ('parents', 'All Parents'),
        ('staff', 'All Staff'),
        ('class', 'Specific Class(es)'),
        ('student', 'Specific Student(s)'),
        ('department', 'Specific Department'),
        ('role', 'Specific Role'),
    ]
    audience_type = models.CharField(max_length=20, choices=AUDIENCE_CHOICES, default='all')
    
    # TODO: Uncomment when ClassArm and StudentProfile models are created
    # target_classes = models.ManyToManyField('academic.ClassArm', blank=True)
    # target_students = models.ManyToManyField('users.StudentProfile', blank=True)
    target_roles = models.JSONField(default=list, blank=True)
    target_departments = models.JSONField(default=list, blank=True)
    
    # Media
    featured_image = models.ImageField(upload_to='announcements/featured/', null=True, blank=True)
    attachments = models.JSONField(default=list, blank=True)
    
    # Schedule
    publish_from = models.DateTimeField(default=timezone.now)
    publish_until = models.DateTimeField(null=True, blank=True)
    is_published = models.BooleanField(default=True)
    is_pinned = models.BooleanField(default=False)
    
    # Priority
    PRIORITY_CHOICES = [
        (1, 'Low'),
        (2, 'Normal'),
        (3, 'High'),
        (4, 'Urgent'),
    ]
    priority = models.IntegerField(choices=PRIORITY_CHOICES, default=2)
    
    # Tracking
    view_count = models.IntegerField(default=0)
    unique_views = models.IntegerField(default=0)
    click_count = models.IntegerField(default=0)
    
    # Notifications
    send_notification = models.BooleanField(default=True)
    notification_sent = models.BooleanField(default=False)
    notification_sent_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        verbose_name = "Announcement"
        verbose_name_plural = "Announcements"
        ordering = ['-is_pinned', '-priority', '-publish_from']
        indexes = [
            models.Index(fields=['-publish_from', 'is_published']),
            models.Index(fields=['author', '-publish_from']),
        ]
    
    def __str__(self):
        return f"{self.title} - {self.publish_from.date()}"

    def clean(self):
        super().clean()
        if self.author_id and self.tenant_id and self.author.tenant_id != self.tenant_id:
            raise ValidationError("Announcement tenant must match the author's tenant.")

    def save(self, *args, **kwargs):
        self.clean()
        super().save(*args, **kwargs)
    
    def increment_views(self, unique=False):
        self.view_count += 1
        if unique:
            self.unique_views += 1
        self.save(update_fields=['view_count', 'unique_views'])

class AnnouncementRead(TimeStampedModel, UUIDModel):
    """
    Track which users have read which announcements.
    """
    tenant = models.ForeignKey(SchoolTenant, on_delete=models.CASCADE)
    announcement = models.ForeignKey(Announcement, on_delete=models.CASCADE, related_name='reads')
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='read_announcements')
    read_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        verbose_name = "Announcement Read"
        verbose_name_plural = "Announcement Reads"
        unique_together = ['announcement', 'user']
    
    def __str__(self):
        return f"{self.user.get_full_name()} read {self.announcement.title}"

class BroadcastMessage(TimeStampedModel, UUIDModel):
    """
    Mass messaging system for administrators.
    """
    tenant = models.ForeignKey(SchoolTenant, on_delete=models.CASCADE)
    sender = models.ForeignKey(User, on_delete=models.CASCADE, related_name='broadcasts')
    
    subject = models.CharField(max_length=200)
    message = models.TextField()
    
    # Targeting
    target_all = models.BooleanField(default=False)
    target_roles = models.JSONField(default=list)
    # TODO: Uncomment when ClassArm model is created
    # target_classes = models.ManyToManyField('academic.ClassArm', blank=True)
    
    # Channels
    send_email = models.BooleanField(default=True)
    send_sms = models.BooleanField(default=False)
    send_push = models.BooleanField(default=False)
    send_in_app = models.BooleanField(default=True)
    
    # Status
    STATUS_CHOICES = [
        ('draft', 'Draft'),
        ('scheduled', 'Scheduled'),
        ('sending', 'Sending'),
        ('sent', 'Sent'),
        ('cancelled', 'Cancelled'),
        ('failed', 'Failed'),
    ]
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='draft')
    
    scheduled_for = models.DateTimeField(null=True, blank=True)
    sent_at = models.DateTimeField(null=True, blank=True)
    
    # Statistics
    total_recipients = models.IntegerField(default=0)
    successful_deliveries = models.IntegerField(default=0)
    failed_deliveries = models.IntegerField(default=0)
    
    class Meta:
        verbose_name = "Broadcast Message"
        verbose_name_plural = "Broadcast Messages"
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.subject} - {self.get_status_display()}"

class InAppMessage(TimeStampedModel, UUIDModel):
    """
    Real-time messaging between users.
    """
    tenant = models.ForeignKey(SchoolTenant, on_delete=models.CASCADE)
    sender = models.ForeignKey(User, on_delete=models.CASCADE, related_name='sent_messages')
    recipient = models.ForeignKey(User, on_delete=models.CASCADE, related_name='received_messages')
    
    subject = models.CharField(max_length=200, blank=True, null=True)
    body = models.TextField()
    
    # Read status
    is_read = models.BooleanField(default=False)
    read_at = models.DateTimeField(null=True, blank=True)
    
    # Reply
    parent_message = models.ForeignKey('self', on_delete=models.CASCADE, null=True, blank=True)
    
    # Attachments
    attachments = models.JSONField(default=list, blank=True)
    
    # Thread
    thread_id = models.UUIDField(default=uuid.uuid4, db_index=True)
    
    # Deleted status
    deleted_by_sender = models.BooleanField(default=False)
    deleted_by_recipient = models.BooleanField(default=False)
    
    class Meta:
        verbose_name = "In-App Message"
        verbose_name_plural = "In-App Messages"
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['thread_id', '-created_at']),
            models.Index(fields=['sender', '-created_at']),
            models.Index(fields=['recipient', '-created_at', 'is_read']),
        ]
    
    def __str__(self):
        return f"From: {self.sender.get_full_name()} To: {self.recipient.get_full_name()}"

    def clean(self):
        super().clean()
        if self.sender_id and self.tenant_id and self.sender.tenant_id != self.tenant_id:
            raise ValidationError("Message tenant must match the sender's tenant.")
        if self.recipient_id and self.tenant_id and self.recipient.tenant_id != self.tenant_id:
            raise ValidationError("Message tenant must match the recipient's tenant.")

    def save(self, *args, **kwargs):
        self.clean()
        super().save(*args, **kwargs)
    
    def mark_as_read(self):
        self.is_read = True
        self.read_at = timezone.now()
        self.save(update_fields=['is_read', 'read_at'])


class EmailConfiguration(TimeStampedModel):
    """Email configuration for a school tenant"""
    school_tenant = models.OneToOneField(
        'core.SchoolTenant',
        on_delete=models.CASCADE,
        related_name='email_config',
        null=True,
        blank=True
    )
    smtp_host = models.CharField(max_length=255, blank=True)
    smtp_port = models.IntegerField(default=587)
    smtp_username = models.CharField(max_length=255, blank=True)
    smtp_password = models.CharField(max_length=255, blank=True)
    from_email = models.EmailField(blank=True)
    use_tls = models.BooleanField(default=True)
    is_active = models.BooleanField(default=False)
    
    class Meta:
        verbose_name = "Email Configuration"
        verbose_name_plural = "Email Configurations"
    
    def __str__(self):
        return f"Email Config - {self.school_tenant}"


class SMSConfiguration(TimeStampedModel):
    """SMS configuration for a school tenant"""
    school_tenant = models.OneToOneField(
        'core.SchoolTenant',
        on_delete=models.CASCADE,
        related_name='sms_config',
        null=True,
        blank=True
    )
    provider = models.CharField(
        max_length=50,
        choices=[
            ('twilio', 'Twilio'),
            ('aws_sns', 'AWS SNS'),
            ('custom', 'Custom Provider'),
        ],
        blank=True
    )
    api_key = models.CharField(max_length=255, blank=True)
    api_secret = models.CharField(max_length=255, blank=True)
    sender_id = models.CharField(max_length=20, blank=True)
    is_active = models.BooleanField(default=False)
    
    class Meta:
        verbose_name = "SMS Configuration"
        verbose_name_plural = "SMS Configurations"
    
    def __str__(self):
        return f"SMS Config - {self.school_tenant}"


class PaymentGatewayConfiguration(TimeStampedModel):
    """Payment gateway configuration for a school tenant"""
    school_tenant = models.OneToOneField(
        'core.SchoolTenant',
        on_delete=models.CASCADE,
        related_name='payment_config',
        null=True,
        blank=True
    )
    provider = models.CharField(
        max_length=50,
        choices=[
            ('stripe', 'Stripe'),
            ('paypal', 'PayPal'),
            ('razorpay', 'Razorpay'),
            ('custom', 'Custom Provider'),
        ],
        blank=True
    )
    api_key = models.CharField(max_length=255, blank=True)
    api_secret = models.CharField(max_length=255, blank=True)
    is_active = models.BooleanField(default=False)
    test_mode = models.BooleanField(default=True)
    
    class Meta:
        verbose_name = "Payment Gateway Configuration"
        verbose_name_plural = "Payment Gateway Configurations"
    
    def __str__(self):
        return f"Payment Config - {self.school_tenant}"
