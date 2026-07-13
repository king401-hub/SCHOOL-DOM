# users/models.py
from django.db import models
from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
from django.utils import timezone
from django.core.exceptions import ObjectDoesNotExist, ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator, RegexValidator
from django.utils.translation import gettext_lazy as _
import uuid
import secrets
import string
import jwt
from datetime import datetime, timedelta
from django.conf import settings

class UserManager(BaseUserManager):
    """
    Custom user manager where email is the unique identifier
    """
    def create_user(self, email, password=None, **extra_fields):
        if not email:
            raise ValueError(_('The Email must be set'))
        email = self.normalize_email(email)
        extra_fields.setdefault('admin_otp_purpose', '')
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user
    
    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        extra_fields.setdefault('is_active', True)
        extra_fields.setdefault('is_verified', True)
        extra_fields.setdefault('role', 'super_admin')
        
        if extra_fields.get('is_staff') is not True:
            raise ValueError(_('Superuser must have is_staff=True.'))
        if extra_fields.get('is_superuser') is not True:
            raise ValueError(_('Superuser must have is_superuser=True.'))
        
        return self.create_user(email, password, **extra_fields)

class User(AbstractBaseUser, PermissionsMixin):
    """
    Custom User Model for SchoolDom
    """
    # UUID as primary key for better security and scalability
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    
    # Basic Information
    email = models.EmailField(_('email address'), unique=True, db_index=True)
    first_name = models.CharField(_('first name'), max_length=150, blank=True)
    last_name = models.CharField(_('last name'), max_length=150, blank=True)
    
    # Phone with validation
    phone_regex = RegexValidator(
        regex=r'^\+?1?\d{9,15}$',
        message="Phone number must be entered in format: '+999999999'. Up to 15 digits allowed."
    )
    phone = models.CharField(validators=[phone_regex], max_length=17, blank=True)
    
    # Role based access
    ROLE_CHOICES = [
        ('super_admin', 'Super Administrator'),
        ('school_superadmin', 'School Superadmin'),
        ('school_admin', 'School Administrator'),
        ('principal', 'Principal'),
        ('accountant', 'Accountant'),
        ('teacher', 'Teacher'),
        ('staff', 'Staff'),
        ('student', 'Student'),
        ('parent', 'Parent'),
    ]
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='student')
    admin_title = models.CharField(max_length=80, blank=True)
    
    # Multi-tenancy
    tenant = models.ForeignKey('core.SchoolTenant', on_delete=models.CASCADE, 
                               null=True, blank=True, related_name='users')
    school_group = models.ForeignKey(
        'core.SchoolGroup',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='users',
    )
    
    # Profile
    profile_picture = models.ImageField(upload_to='profiles/', null=True, blank=True)
    date_of_birth = models.DateField(null=True, blank=True)
    
    GENDER_CHOICES = [
        ('M', 'Male'),
        ('F', 'Female'),
        ('O', 'Other'),
        ('N', 'Prefer not to say')
    ]
    gender = models.CharField(max_length=1, choices=GENDER_CHOICES, null=True, blank=True)

    # Director/proprietor KYC (collected during school onboarding)
    DIRECTOR_ID_TYPE_CHOICES = [
        ('drivers_license', "Driver's License"),
        ('nin', 'National ID (NIN)'),
        ('voters_card', "Voter's Card"),
        ('passport', 'International Passport'),
    ]
    director_address = models.TextField(blank=True, default="")
    director_proof_of_address = models.FileField(upload_to='directors/proof_of_address/%Y/%m/', null=True, blank=True)
    director_id_type = models.CharField(max_length=20, choices=DIRECTOR_ID_TYPE_CHOICES, blank=True, default="")
    director_id_document = models.FileField(upload_to='directors/id_documents/%Y/%m/', null=True, blank=True)

    # Account status
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)
    is_verified = models.BooleanField(default=False)
    is_locked = models.BooleanField(default=False)
    
    # Security
    last_login_ip = models.GenericIPAddressField(null=True, blank=True)
    login_attempts = models.IntegerField(default=0)
    last_password_change = models.DateTimeField(null=True, blank=True)
    
    # Verification
    email_verification_token = models.CharField(max_length=255, blank=True, null=True)
    email_verification_sent_at = models.DateTimeField(null=True, blank=True)
    email_verified_at = models.DateTimeField(null=True, blank=True)
    
    # Password reset (OTP-based: password_reset_token stores a hashed 6-digit code)
    password_reset_token = models.CharField(max_length=255, blank=True, null=True)
    password_reset_sent_at = models.DateTimeField(null=True, blank=True)
    password_reset_challenge = models.CharField(max_length=64, blank=True, null=True)
    password_reset_otp_attempts = models.PositiveIntegerField(default=0)
    
    # Admin OTP
    admin_otp_hash = models.CharField(max_length=128, blank=True, null=True)
    admin_otp_sent_at = models.DateTimeField(null=True, blank=True)
    admin_otp_purpose = models.CharField(max_length=32, default='')
    admin_otp_attempts = models.PositiveIntegerField(default=0)
    admin_otp_challenge = models.CharField(max_length=64, blank=True, null=True)
    admin_otp_verified_at = models.DateTimeField(null=True, blank=True)

    # Account deletion grace period
    account_deletion_requested_at = models.DateTimeField(null=True, blank=True)
    account_deletion_scheduled_for = models.DateTimeField(null=True, blank=True)
    
    # Device info for push notifications
    device_tokens = models.JSONField(default=list, blank=True)
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    objects = UserManager()
    
    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['first_name', 'last_name']
    
    class Meta:
        verbose_name = _('user')
        verbose_name_plural = _('users')
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['email', 'tenant']),
            models.Index(fields=['role', 'tenant']),
            models.Index(fields=['is_active', 'tenant']),
        ]
    
    def __str__(self):
        return self.get_full_name() or self.email
    
    def get_full_name(self):
        """Return the full name of the user"""
        full_name = f"{self.first_name} {self.last_name}".strip()
        return full_name if full_name else self.email
    
    def get_short_name(self):
        """Return the short name of the user"""
        return self.first_name or self.email.split('@')[0]
    
    def generate_jwt_token(self):
        """Generate JWT token for the user"""
        payload = {
            'user_id': str(self.id),
            'email': self.email,
            'role': self.role,
            'tenant': str(self.tenant.id) if self.tenant else None,
            'exp': datetime.utcnow() + timedelta(hours=24),
            'iat': datetime.utcnow()
        }
        return jwt.encode(payload, settings.SECRET_KEY, algorithm='HS256')
    
    @staticmethod
    def decode_jwt_token(token):
        """Decode JWT token"""
        try:
            payload = jwt.decode(token, settings.SECRET_KEY, algorithms=['HS256'])
            return payload
        except jwt.ExpiredSignatureError:
            return None
        except jwt.InvalidTokenError:
            return None
    
    def generate_email_verification_token(self):
        """Generate email verification token"""
        self.email_verification_token = str(uuid.uuid4())
        self.email_verification_sent_at = timezone.now()
        self.save(update_fields=['email_verification_token', 'email_verification_sent_at'])
        return self.email_verification_token
    
    def verify_email(self, token):
        """Verify user's email"""
        if self.email_verification_token == token:
            self.is_verified = True
            self.email_verified_at = timezone.now()
            self.email_verification_token = None
            self.save(update_fields=['is_verified', 'email_verified_at', 'email_verification_token'])
            return True
        return False
    
    def increment_login_attempts(self):
        """Increment failed login attempts"""
        self.login_attempts += 1
        if self.login_attempts >= 5:
            self.is_locked = True
        self.save(update_fields=['login_attempts', 'is_locked'])
    
    def reset_login_attempts(self):
        """Reset failed login attempts"""
        self.login_attempts = 0
        self.is_locked = False
        self.save(update_fields=['login_attempts', 'is_locked'])
    
    def update_last_login_ip(self, ip):
        """Update last login IP"""
        self.last_login_ip = ip
        self.save(update_fields=['last_login_ip'])

class StudentActivityTitle(models.Model):
    """
    Tenant-controlled student activity or leadership titles for admissions.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(
        'core.SchoolTenant',
        on_delete=models.CASCADE,
        related_name='student_activity_titles',
    )
    name = models.CharField(max_length=120)
    star_rating = models.DecimalField(
        max_digits=2,
        decimal_places=1,
        default=1,
        validators=[MinValueValidator(0.5), MaxValueValidator(5)],
    )
    is_active = models.BooleanField(default=True)
    sort_order = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _('student activity title')
        verbose_name_plural = _('student activity titles')
        ordering = ['sort_order', 'name']
        constraints = [
            models.UniqueConstraint(fields=['tenant', 'name'], name='unique_student_activity_title_per_school'),
        ]

    def __str__(self):
        return self.name


class StudentProfile(models.Model):
    """
    Extended profile for students
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='student_profile')
    
    # Student specific fields
    student_id = models.CharField(max_length=50, unique=True)
    admission_number = models.CharField(max_length=50, unique=True)
    admission_date = models.DateField()
    
    # Academic
    current_class = models.ForeignKey('academic.Class', on_delete=models.SET_NULL, 
                                       null=True, blank=True)
    current_term = models.ForeignKey('academic.Term', on_delete=models.SET_NULL, 
                                      null=True, blank=True)
    
    # Guardian information
    state_of_origin = models.CharField(max_length=120, blank=True)
    local_government = models.CharField(max_length=120, blank=True)
    guardian_name = models.CharField(max_length=255)
    guardian_phone = models.CharField(max_length=17)
    guardian_email = models.EmailField(blank=True)
    guardian_relation = models.CharField(max_length=100)
    second_guardian_name = models.CharField(max_length=255, blank=True)
    second_guardian_phone = models.CharField(max_length=17, blank=True)
    second_guardian_email = models.EmailField(blank=True)
    second_guardian_relation = models.CharField(max_length=100, blank=True)
    
    # Medical
    blood_group = models.CharField(max_length=5, blank=True)
    disability = models.CharField(max_length=20, blank=True, default="no")
    student_type = models.CharField(max_length=120, blank=True)
    extra_curricular_activity_title = models.ForeignKey(
        StudentActivityTitle,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='students',
    )
    home_address = models.TextField(blank=True)
    allergies = models.TextField(blank=True)
    medical_conditions = models.TextField(blank=True)
    
    # Documents
    birth_certificate = models.FileField(upload_to='students/documents/', null=True, blank=True)
    previous_school_report = models.FileField(upload_to='students/documents/', null=True, blank=True)
    id_card_generated_at = models.DateTimeField(null=True, blank=True)
    id_card_viewed_at = models.DateTimeField(null=True, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = _('student profile')
        verbose_name_plural = _('student profiles')
    
    def __str__(self):
        return f"{self.user.get_full_name()} - {self.student_id}"


def school_code_letters(school):
    name = str(getattr(school, "name", "") or getattr(school, "schema_name", "") or "").strip()
    words = ["".join(ch for ch in word if ch.isalpha()).upper() for word in name.replace("_", " ").split()]
    words = [word for word in words if word]
    if len(words) >= 2:
        return f"{words[0][0]}{words[1][0]}"
    letters = "".join(words)
    return (letters[:2] or "XX").ljust(2, "X")


def random_code_digits(size=3):
    return "".join(secrets.choice(string.digits) for _ in range(size))


def generate_short_student_id(seed="", school=None):
    school_letters = school_code_letters(school)
    candidate = f"ST{school_letters}{random_code_digits()}"
    while StudentProfile.objects.filter(student_id__iexact=candidate).exists():
        candidate = f"ST{school_letters}{random_code_digits()}"
    return candidate

class TeacherProfile(models.Model):
    """
    Extended profile for teachers
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='teacher_profile')
    
    # Teacher specific fields
    employee_id = models.CharField(max_length=50, unique=True)
    qualification = models.TextField()
    specialization = models.CharField(max_length=255)
    subjects_text = models.TextField(blank=True, default="")
    years_of_experience = models.IntegerField(default=0)
    hire_date = models.DateField()
    monthly_salary = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    
    EMPLOYMENT_TYPES = [
        ('full_time', 'Full Time'),
        ('part_time', 'Part Time'),
        ('contract', 'Contract'),
        ('visiting', 'Visiting'),
    ]
    employment_type = models.CharField(max_length=20, choices=EMPLOYMENT_TYPES, default='full_time')
    
    # Documents
    resume = models.FileField(upload_to='teachers/documents/', null=True, blank=True)
    certificates = models.FileField(upload_to='teachers/documents/', null=True, blank=True)
    
    # Emergency contact
    emergency_contact_name = models.CharField(max_length=255)
    emergency_contact_phone = models.CharField(max_length=17)
    emergency_contact_relation = models.CharField(max_length=100)
    subjects = models.ManyToManyField('academic.Subject', related_name='assigned_teachers', blank=True)
    assigned_classes = models.ManyToManyField('academic.Class', related_name='assigned_teachers', blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = _('teacher profile')
        verbose_name_plural = _('teacher profiles')
    
    def __str__(self):
        return f"{self.user.get_full_name()} - {self.employee_id}"

    def save(self, *args, **kwargs):
        if not getattr(self, 'employee_id', None) or not str(self.employee_id).strip():
            self.employee_id = generate_short_teacher_id(
                getattr(self.user, 'id', None).hex if getattr(self.user, 'id', None) else '',
                getattr(self.user, 'tenant', None)
            )
        super().save(*args, **kwargs)


def generate_short_teacher_id(seed="", school=None):
    school_letters = school_code_letters(school)
    candidate = f"TC{school_letters}{random_code_digits()}"
    while TeacherProfile.objects.filter(employee_id__iexact=candidate).exists():
        candidate = f"TC{school_letters}{random_code_digits()}"
    return candidate

class ParentProfile(models.Model):
    """
    Extended profile for parents
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='parent_profile')
    
    # Parent specific fields
    occupation = models.CharField(max_length=255, blank=True)
    company = models.CharField(max_length=255, blank=True)
    
    # Children (students)
    children = models.ManyToManyField(StudentProfile, related_name='parents', blank=True)
    
    # Communication preferences
    PREFERENCE_CHOICES = [
        ('email', 'Email'),
        ('sms', 'SMS'),
        ('push', 'Push Notification'),
        ('whatsapp', 'WhatsApp'),
    ]
    preferred_contact = models.CharField(max_length=20, choices=PREFERENCE_CHOICES, default='email')
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = _('parent profile')
        verbose_name_plural = _('parent profiles')
    
    def __str__(self):
        return f"{self.user.get_full_name()} - Parent"


def resolve_legacy_tenant_for_school(school):
    """
    Map core.SchoolTenant to the legacy tenants.Tenant relation used by academic/exams.
    """
    if not school:
        return None

    from tenants.models import Tenant

    return Tenant.objects.filter(slug__iexact=school.schema_name).first()


class StudentEnrollment(models.Model):
    """
    Admin-driven enrollment record that links a student to class, exams, and message onboarding.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    school = models.ForeignKey('core.SchoolTenant', on_delete=models.CASCADE, related_name='student_enrollments')
    student = models.ForeignKey(StudentProfile, on_delete=models.CASCADE, related_name='enrollments')
    assigned_class = models.ForeignKey(
        'academic.Class',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='student_enrollments',
    )
    exams = models.ManyToManyField('exams.Exam', blank=True, related_name='student_enrollments')

    welcome_subject = models.CharField(max_length=200, default='Enrollment update')
    welcome_message = models.TextField(blank=True)
    enrollment_message = models.ForeignKey(
        'notifications.InAppMessage',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='enrollment_records',
    )

    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='created_enrollments',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _('student enrollment')
        verbose_name_plural = _('student enrollments')
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['school', 'student']),
            models.Index(fields=['created_at']),
        ]

    def __str__(self):
        student = self._get_related_or_none('student')
        school = self._get_related_or_none('school')
        student_label = student.user.get_full_name() if student else str(self.student_id or 'unknown student')
        school_label = school.name if school else str(self.school_id or 'unknown school')
        return f"{student_label} enrollment @ {school_label}"

    def _get_related_or_none(self, relation_name):
        relation_id = getattr(self, f'{relation_name}_id', None)
        if not relation_id:
            return None
        try:
            return getattr(self, relation_name)
        except ObjectDoesNotExist:
            return None

    def clean(self):
        errors = {}
        student = self._get_related_or_none('student')
        school = self._get_related_or_none('school')

        if student and student.user.role != 'student':
            errors['student'] = _('Selected user profile is not a student.')

        if student and not self.school_id:
            self.school = student.user.tenant
            school = self.school

        if student and not student.user.tenant:
            errors['student'] = _('Student must be linked to a school tenant before enrollment.')

        if student and school and student.user.tenant_id != self.school_id:
            errors['school'] = _('School does not match the selected student account.')

        legacy_tenant = resolve_legacy_tenant_for_school(school)
        if self.assigned_class and not legacy_tenant:
            errors['assigned_class'] = _('Could not map this school to legacy class tenant.')
        if self.assigned_class and legacy_tenant and self.assigned_class.tenant_id != legacy_tenant.id:
            errors['assigned_class'] = _('Selected class does not belong to this school.')

        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        student = self._get_related_or_none('student')
        if student and not self.school_id:
            self.school = student.user.tenant
        self.full_clean()
        return super().save(*args, **kwargs)

    def apply_links(self):
        """
        Apply post-save links:
        1) set student current_class
        2) create exam attempts for selected exams
        3) send onboarding message if provided
        """
        student_user = self.student.user

        if self.assigned_class and self.student.current_class_id != self.assigned_class_id:
            self.student.current_class = self.assigned_class
            self.student.save(update_fields=['current_class'])

        from exams.models import ExamAttempt

        for exam in self.exams.select_related('tenant').all():
            defaults = {}
            if exam.tenant_id:
                defaults['tenant'] = exam.tenant
            ExamAttempt.objects.get_or_create(
                exam=exam,
                student=student_user,
                defaults=defaults,
            )

        if self.welcome_message and not self.enrollment_message_id:
            from notifications.models import InAppMessage

            sender = self._resolve_sender()
            if sender:
                message = InAppMessage.objects.create(
                    tenant=self.school,
                    sender=sender,
                    recipient=student_user,
                    subject=self.welcome_subject or 'Enrollment update',
                    body=self.welcome_message,
                )
                self.__class__.objects.filter(pk=self.pk).update(enrollment_message=message)
                self.enrollment_message = message

    def _resolve_sender(self):
        if self.created_by_id:
            return self.created_by

        return User.objects.filter(
            tenant=self.school,
            role__in=['school_admin', 'principal', 'super_admin'],
            is_active=True,
        ).order_by('created_at').first()


class StudentTestimonial(models.Model):
    """
    Editable official testimonial details for terminal junior/senior students.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    school = models.ForeignKey('core.SchoolTenant', on_delete=models.CASCADE, related_name='student_testimonials')
    student = models.OneToOneField(StudentProfile, on_delete=models.CASCADE, related_name='testimonial')

    class_of_admission = models.CharField(max_length=120, blank=True)
    date_of_leaving = models.DateField(null=True, blank=True)
    class_of_leaving = models.CharField(max_length=120, blank=True)
    reason_for_leaving = models.CharField(max_length=255, blank=True)
    educational_attainment = models.CharField(max_length=255, blank=True)
    subjects_offered = models.TextField(blank=True)
    co_curricular_activities = models.TextField(blank=True)
    prizes_and_honors = models.TextField(blank=True)
    office_held = models.CharField(max_length=255, blank=True)
    administrator_remarks = models.TextField(blank=True)
    issue_date = models.DateField(null=True, blank=True)
    principal_name = models.CharField(max_length=255, blank=True)

    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='created_testimonials',
    )
    updated_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='updated_testimonials',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _('student testimonial')
        verbose_name_plural = _('student testimonials')
        indexes = [
            models.Index(fields=['school', 'student']),
            models.Index(fields=['updated_at']),
        ]

    def __str__(self):
        return f"Testimonial - {self.student.student_id}"


class LoginHistory(models.Model):
    """
    Track user login history for security
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='login_history')
    
    login_time = models.DateTimeField(auto_now_add=True)
    logout_time = models.DateTimeField(null=True, blank=True)
    ip_address = models.GenericIPAddressField()
    user_agent = models.TextField(blank=True)
    device_type = models.CharField(max_length=50, blank=True)
    browser = models.CharField(max_length=100, blank=True)
    os = models.CharField(max_length=100, blank=True)
    location = models.CharField(max_length=255, blank=True)
    
    STATUS_CHOICES = [
        ('success', 'Success'),
        ('failed', 'Failed'),
        ('locked', 'Account Locked'),
    ]
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='success')
    
    class Meta:
        verbose_name = _('login history')
        verbose_name_plural = _('login histories')
        ordering = ['-login_time']
    
    def __str__(self):
        return f"{self.user.email} - {self.login_time}"


class DatabaseImportJob(models.Model):
    """Admin-only school migration upload and validation record."""

    IMPORT_TYPES = [
        ("students", "Student records"),
        ("teachers", "Teacher profiles"),
        ("classes_subjects", "Classes and subjects"),
        ("cbt_results", "CBT results"),
        ("attendance", "Attendance records"),
        ("payments", "Payment history"),
        ("timetables", "Timetables"),
        ("assignments", "Assignments"),
        ("documents", "Uploaded documents"),
        ("academic_records", "Academic records"),
        ("full_school", "Full school database"),
    ]
    STATUS_CHOICES = [
        ("uploaded", "Uploaded"),
        ("validated", "Validated"),
        ("needs_review", "Needs review"),
        ("failed", "Failed"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey("core.SchoolTenant", on_delete=models.CASCADE, related_name="database_import_jobs")
    uploaded_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="database_import_jobs")
    import_type = models.CharField(max_length=40, choices=IMPORT_TYPES)
    source_platform = models.CharField(max_length=120, blank=True)
    link_key = models.CharField(max_length=80, blank=True)
    notes = models.TextField(blank=True)
    upload = models.FileField(upload_to="database_imports/%Y/%m/")
    original_filename = models.CharField(max_length=255)
    file_size = models.PositiveBigIntegerField(default=0)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="uploaded")
    summary = models.JSONField(default=dict, blank=True)
    errors = models.JSONField(default=list, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["tenant", "status"]),
            models.Index(fields=["tenant", "import_type"]),
        ]

    def __str__(self):
        return f"{self.get_import_type_display()} - {self.original_filename}"


class SupportTicket(models.Model):
    """School support request submitted from the admin settings page."""

    CATEGORY_CHOICES = [
        ("technical_issue", "Technical Issue"),
        ("account_issue", "Account Issue"),
        ("billing_issue", "Billing Issue"),
        ("feature_request", "Feature Request"),
        ("general_inquiry", "General Inquiry"),
    ]
    STATUS_CHOICES = [
        ("open", "Open"),
        ("in_progress", "In Progress"),
        ("awaiting_response", "Awaiting Response"),
        ("resolved", "Resolved"),
        ("closed", "Closed"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    school = models.ForeignKey("core.SchoolTenant", on_delete=models.CASCADE, related_name="support_tickets")
    submitted_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="support_tickets")
    category = models.CharField(max_length=40, choices=CATEGORY_CHOICES)
    subject = models.CharField(max_length=180)
    description = models.TextField()
    attachment = models.FileField(upload_to="support_tickets/%Y/%m/", null=True, blank=True)
    status = models.CharField(max_length=24, choices=STATUS_CHOICES, default="open")
    requester_email = models.EmailField(blank=True)
    support_notified_at = models.DateTimeField(null=True, blank=True)
    requester_notified_at = models.DateTimeField(null=True, blank=True)
    last_status_email_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["school", "status"]),
            models.Index(fields=["school", "created_at"]),
        ]

    def __str__(self):
        return f"{self.get_category_display()} - {self.subject}"


class LoanApplication(models.Model):
    """A school's request for financing from SchoolDom, reviewed manually by the SchoolDom team."""

    STATUS_CHOICES = [
        ("pending", "Pending Review"),
        ("under_review", "Under Review"),
        ("approved", "Approved"),
        ("rejected", "Rejected"),
        ("disbursed", "Disbursed"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    school = models.ForeignKey("core.SchoolTenant", on_delete=models.CASCADE, related_name="loan_applications")
    submitted_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="loan_applications")
    amount_requested = models.DecimalField(max_digits=14, decimal_places=2)
    purpose = models.CharField(max_length=255)
    repayment_period_months = models.PositiveIntegerField()
    additional_notes = models.TextField(blank=True)
    supporting_document = models.FileField(upload_to="loan_applications/%Y/%m/", null=True, blank=True)
    status = models.CharField(max_length=24, choices=STATUS_CHOICES, default="pending")
    requester_email = models.EmailField(blank=True)
    requester_phone = models.CharField(max_length=32, blank=True)
    support_notified_at = models.DateTimeField(null=True, blank=True)
    requester_notified_at = models.DateTimeField(null=True, blank=True)
    last_status_email_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["school", "status"]),
            models.Index(fields=["school", "created_at"]),
        ]

    def __str__(self):
        return f"{self.school.name} loan - {self.amount_requested} ({self.status})"


class KidsMonitorSubscription(models.Model):
    """Paid subscription enabling SMS alerts to a parent when their child's attendance is marked."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    parent = models.OneToOneField(
        'ParentProfile',
        on_delete=models.CASCADE,
        related_name='kids_monitor',
    )
    school = models.ForeignKey(
        'core.SchoolTenant',
        on_delete=models.CASCADE,
        related_name='kids_monitor_subscriptions',
    )
    is_active = models.BooleanField(default=False)
    paystack_ref = models.CharField(max_length=100, blank=True)
    activated_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(fields=['school', 'is_active']),
        ]

    def __str__(self):
        return f"KidsMonitor({self.parent.user.email}, active={self.is_active})"
