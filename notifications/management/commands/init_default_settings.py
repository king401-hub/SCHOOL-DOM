from django.core.management.base import BaseCommand
from app_settings.models import SystemSetting, FeatureFlag
from notifications.models import NotificationTemplate


class Command(BaseCommand):
    help = 'Initialize default system settings and notification templates'
    
    def handle(self, *args, **kwargs):
        
        # Default System Settings
        default_settings = [
            {
                'key': 'SYSTEM_NAME',
                'value': 'Virtual School Platform',
                'setting_type': 'string',
                'label': 'System Name',
                'category': 'system',
            },
            {
                'key': 'SUPPORT_EMAIL',
                'value': 'support@virtualschool.com',
                'setting_type': 'email',
                'label': 'Support Email',
                'category': 'system',
            },
            {
                'key': 'ENABLE_REGISTRATION',
                'value': True,
                'setting_type': 'boolean',
                'label': 'Enable Public Registration',
                'category': 'features',
            },
            {
                'key': 'MAX_FILE_SIZE_MB',
                'value': 50,
                'setting_type': 'integer',
                'label': 'Maximum File Size (MB)',
                'category': 'storage',
            },
            {
                'key': 'SESSION_TIMEOUT_MINUTES',
                'value': 120,
                'setting_type': 'integer',
                'label': 'Session Timeout (minutes)',
                'category': 'security',
            },
        ]
        
        for setting in default_settings:
            SystemSetting.objects.update_or_create(
                key=setting['key'],
                defaults=setting
            )
            self.stdout.write(f"Created setting: {setting['key']}")
        
        # Default Feature Flags
        default_features = [
            {
                'code': 'offline_exams',
                'name': 'Offline Exams',
                'description': 'Allow students to download and take exams offline',
                'is_enabled': True,
            },
            {
                'code': 'video_conferencing',
                'name': 'Video Conferencing',
                'description': 'Enable video conferencing for online classes',
                'is_enabled': False,
            },
            {
                'code': 'ai_grading',
                'name': 'AI-Powered Grading',
                'description': 'Use AI to assist in grading subjective answers',
                'is_enabled': False,
            },
            {
                'code': 'parent_portal',
                'name': 'Parent Portal',
                'description': 'Allow parents to access student information',
                'is_enabled': True,
            },
        ]
        
        for feature in default_features:
            FeatureFlag.objects.update_or_create(
                code=feature['code'],
                defaults=feature
            )
            self.stdout.write(f"Created feature flag: {feature['code']}")
        
        # Default Notification Templates
        default_templates = [
            {
                'code': 'welcome_email',
                'name': 'Welcome Email',
                'event_type': 'account_created',
                'subject_template': 'Welcome to {school_name}',
                'email_body_template': '''
                    Dear {full_name},
                    
                    Welcome to {school_name}! Your account has been successfully created.
                    
                    Email: {email}
                    Role: {role}
                    
                    Please login using the following link:
                    {login_url}
                    
                    Best regards,
                    {school_name} Administration
                ''',
                'push_title_template': 'Welcome to {school_name}!',
                'push_body_template': 'Your account has been created successfully.',
                'in_app_template': 'Welcome! Your account has been created.',
                'can_email': True,
                'can_sms': False,
                'can_push': True,
                'can_in_app': True,
            },
            {
                'code': 'exam_published',
                'name': 'Exam Published Notification',
                'event_type': 'exam_published',
                'subject_template': 'New Exam: {exam_title}',
                'email_body_template': '''
                    Dear {full_name},
                    
                    A new exam has been published for {class_name} - {subject_name}.
                    
                    Exam: {exam_title}
                    Date: {exam_date}
                    Duration: {duration} minutes
                    
                    Please login to access the exam.
                    
                    Best regards,
                    {school_name}
                ''',
                'push_title_template': 'New Exam: {exam_title}',
                'push_body_template': '{subject_name} exam is now available',
                'in_app_template': 'A new exam has been published: {exam_title}',
                'can_email': True,
                'can_sms': False,
                'can_push': True,
                'can_in_app': True,
            },
            {
                'code': 'fee_due_reminder',
                'name': 'Fee Due Reminder',
                'event_type': 'fee_due',
                'subject_template': 'Fee Payment Reminder',
                'email_body_template': '''
                    Dear {guardian_name},
                    
                    This is a reminder that fee payment for {student_name} is due.
                    
                    Amount: {currency} {amount}
                    Due Date: {due_date}
                    
                    Please make payment before the due date to avoid late fees.
                    
                    Best regards,
                    {school_name} Finance Department
                ''',
                'push_title_template': 'Fee Due Reminder',
                'push_body_template': 'Fee payment of {amount} is due on {due_date}',
                'in_app_template': 'Fee payment reminder: {amount} due on {due_date}',
                'can_email': True,
                'can_sms': True,
                'can_push': True,
                'can_in_app': True,
            },
            {
                'code': 'result_published',
                'name': 'Result Published',
                'event_type': 'result_published',
                'subject_template': 'Your Results for {exam_title}',
                'email_body_template': '''
                    Dear {full_name},
                    
                    Your results for {exam_title} have been published.
                    
                    Subject: {subject}
                    Score: {score}
                    Grade: {grade}
                    
                    You can view detailed results in the student portal.
                    
                    Best regards,
                    {school_name}
                ''',
                'push_title_template': 'Results Published',
                'push_body_template': 'Your results for {exam_title} are now available',
                'in_app_template': 'Your exam results have been published',
                'can_email': True,
                'can_sms': False,
                'can_push': True,
                'can_in_app': True,
            },
        ]
        
        for template in default_templates:
            NotificationTemplate.objects.update_or_create(
                code=template['code'],
                defaults=template
            )
            self.stdout.write(f"Created notification template: {template['code']}")
        
        self.stdout.write(self.style.SUCCESS('Successfully initialized default settings!'))
