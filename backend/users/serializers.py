# users/serializers.py
from rest_framework import serializers
from django.contrib.auth import authenticate
from django.utils.translation import gettext_lazy as _
from django.utils import timezone
from .models import User, StudentProfile, TeacherProfile, ParentProfile, LoginHistory, generate_short_student_id, generate_short_teacher_id
from core.models import SchoolGroup, SchoolTenant
from finance.services import student_has_login_credit, update_student_activation_alerts
import re

SCHOOL_SCOPED_ROLES = {"student", "teacher", "staff", "accountant", "parent", "school_admin", "principal"}
STRICT_SCHOOL_CODE_LOGIN_ROLES = {"student", "teacher", "staff", "accountant"}


class UserSerializer(serializers.ModelSerializer):
    full_name = serializers.SerializerMethodField()
    display_role = serializers.SerializerMethodField()
    
    class Meta:
        model = User
        fields = [
            'id', 'email', 'first_name', 'last_name', 'full_name',
            'role', 'admin_title', 'display_role', 'phone', 'profile_picture', 'date_of_birth',
            'gender', 'is_verified', 'is_active', 'created_at',
            'account_deletion_requested_at', 'account_deletion_scheduled_for',
        ]
        read_only_fields = [
            'id', 'is_verified', 'is_active', 'created_at',
            'account_deletion_requested_at', 'account_deletion_scheduled_for',
        ]
    
    def get_full_name(self, obj):
        return obj.get_full_name()

    def get_display_role(self, obj):
        return obj.admin_title or obj.get_role_display()

class RegisterSerializer(serializers.Serializer):
    """
    Serializer for user registration
    """
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True, min_length=8)
    confirm_password = serializers.CharField(write_only=True, min_length=8)
    first_name = serializers.CharField(max_length=150)
    last_name = serializers.CharField(max_length=150)
    phone = serializers.CharField(max_length=17, required=False, allow_blank=True)
    role = serializers.ChoiceField(choices=User.ROLE_CHOICES)
    admin_title = serializers.CharField(max_length=80, required=False, allow_blank=True)
    school_code = serializers.CharField(max_length=50, required=False, allow_blank=True)
    school_group_name = serializers.CharField(max_length=255, required=False, allow_blank=True)
    terms_accepted = serializers.BooleanField(write_only=True, required=True)
    
    # Role specific fields
    student_id = serializers.CharField(max_length=50, required=False, allow_blank=True)
    teacher_id = serializers.CharField(max_length=50, required=False, allow_blank=True)
    guardian_name = serializers.CharField(max_length=255, required=False, allow_blank=True)
    guardian_phone = serializers.CharField(max_length=17, required=False, allow_blank=True)
    gender = serializers.ChoiceField(choices=User.GENDER_CHOICES, required=False, allow_blank=True)
    state_of_origin = serializers.CharField(max_length=120, required=False, allow_blank=True)
    local_government = serializers.CharField(max_length=120, required=False, allow_blank=True)
    
    def validate_email(self, value):
        """Check if email already exists"""
        if User.objects.filter(email__iexact=value).exists():
            raise serializers.ValidationError("A user with this email already exists.")
        return value.lower()
    
    def validate_password(self, value):
        """Validate password strength"""
        if len(value) < 8:
            raise serializers.ValidationError("Password must be at least 8 characters long.")
        
        if not re.search(r'[A-Z]', value):
            raise serializers.ValidationError("Password must contain at least one uppercase letter.")
        
        if not re.search(r'[a-z]', value):
            raise serializers.ValidationError("Password must contain at least one lowercase letter.")
        
        if not re.search(r'[0-9]', value):
            raise serializers.ValidationError("Password must contain at least one number.")
        
        return value
    
    def validate(self, data):
        """Validate the entire data"""
        if data['password'] != data['confirm_password']:
            raise serializers.ValidationError({"confirm_password": "Passwords do not match."})

        if not data.get('terms_accepted'):
            raise serializers.ValidationError(
                {"terms_accepted": "You must accept the terms and conditions to sign up."}
            )

        if data['role'] in SCHOOL_SCOPED_ROLES and not data.get('school_code'):
            raise serializers.ValidationError(
                {"school_code": "School code is required for school-scoped accounts."}
            )

        if data['role'] == 'school_superadmin' and not str(data.get('school_group_name') or '').strip():
            raise serializers.ValidationError(
                {"school_group_name": "School group name is required for owner/proprietor accounts."}
            )
        
        # Validate role-specific fields
        if data['role'] == 'student' and not data.get('guardian_name'):
            raise serializers.ValidationError({"guardian_name": "Guardian name is required for students."})
        
        return data
    
    def validate_school_code(self, value):
        """Validate school code if provided"""
        if value:
            try:
                # Use schema_name as the tenant code identifier.
                tenant = SchoolTenant.objects.get(schema_name__iexact=value, is_active=True)
                return tenant
            except SchoolTenant.DoesNotExist:
                raise serializers.ValidationError("Invalid school code.")
        return None
    
    def create(self, validated_data):
        """Create user and profile"""
        # Remove confirmation and extra fields
        validated_data.pop('confirm_password')
        validated_data.pop('terms_accepted', None)
        school_code = validated_data.pop('school_code', None)
        school_group_name = str(validated_data.pop('school_group_name', '') or '').strip()
        
        # Get role specific fields
        student_id = validated_data.pop('student_id', None)
        teacher_id = validated_data.pop('teacher_id', None)
        guardian_name = validated_data.pop('guardian_name', None)
        guardian_phone = validated_data.pop('guardian_phone', None)
        state_of_origin = validated_data.pop('state_of_origin', None)
        local_government = validated_data.pop('local_government', None)
        
        # Create user
        password = validated_data.pop('password')
        user = User(**validated_data)
        user.set_password(password)
        
        # Assign tenant if school code provided
        if school_code:
            user.tenant = school_code
        
        user.save()

        if user.role == 'school_superadmin':
            group = SchoolGroup.objects.create(name=school_group_name, owner=user)
            user.school_group = group
            user.save(update_fields=['school_group'])
        
        # Create role-specific profile
        if user.role == 'student':
            StudentProfile.objects.create(
                user=user,
                student_id=student_id or generate_short_student_id(user.id.hex, user.tenant),
                admission_number=f"ADM{timezone.now().strftime('%Y%m%d')}{user.id.hex[:4].upper()}",
                admission_date=timezone.now().date(),
                guardian_name=guardian_name,
                guardian_phone=guardian_phone or "",
                state_of_origin=state_of_origin or "",
                local_government=local_government or "",
                guardian_relation="Guardian"
            )
            try:
                from finance.services import ensure_student_wallet
                ensure_student_wallet(user)
            except Exception:
                pass
        elif user.role == 'teacher':
            TeacherProfile.objects.create(
                user=user,
                employee_id=teacher_id or generate_short_teacher_id(user.id.hex, user.tenant),
                qualification="Not specified",
                specialization="Not specified",
                hire_date=timezone.now().date(),
                emergency_contact_name="Not provided",
                emergency_contact_phone="Not provided",
                emergency_contact_relation="Not provided"
            )
        elif user.role == 'parent':
            ParentProfile.objects.create(user=user)
        
        # Generate verification token
        user.generate_email_verification_token()
        
        # TODO: Send verification email
        
        return user


class CreateSchoolSerializer(serializers.Serializer):
    """
    Serializer for school (tenant) creation from auth flow
    """

    school_name = serializers.CharField(max_length=255)
    school_code = serializers.CharField(max_length=63, required=False, allow_blank=True)
    email = serializers.EmailField(required=False, allow_blank=True)
    phone = serializers.CharField(max_length=20, required=False, allow_blank=True)
    address = serializers.CharField(required=False, allow_blank=True)
    school_type = serializers.ChoiceField(
        choices=(("k12", "K-12 school"), ("non_k12", "Non K-12 school")),
        required=False,
        default="k12",
    )

    def validate_school_name(self, value):
        cleaned = value.strip()
        if len(cleaned) < 3:
            raise serializers.ValidationError("School name must be at least 3 characters.")
        return cleaned

    def validate_school_code(self, value):
        if not value:
            return ""

        normalized = value.strip().lower().replace("-", "_")
        normalized = re.sub(r"[^a-z0-9_]", "_", normalized)
        normalized = re.sub(r"_+", "_", normalized).strip("_")

        if not normalized:
            raise serializers.ValidationError("School code can only contain letters, numbers, and underscores.")

        if normalized[0].isdigit():
            normalized = f"sch_{normalized}"

        if len(normalized) < 3:
            raise serializers.ValidationError("School code must be at least 3 characters.")

        return normalized[:63]

class LoginSerializer(serializers.Serializer):
    """
    Serializer for user login
    """
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True)
    school_code = serializers.CharField(max_length=50, required=False, allow_blank=True)
    device_token = serializers.CharField(max_length=255, required=False, allow_blank=True)
    
    def validate(self, data):
        email = data.get('email')
        password = data.get('password')
        school_code = (data.get('school_code') or '').strip().lower()
        
        if email and password:
            try:
                user = User.objects.get(email__iexact=email)
                
                # Check if account is locked
                if user.is_locked:
                    raise serializers.ValidationError({
                        'error': 'Account is locked due to too many failed attempts. Please reset your password or contact support.'
                    })
                
                # Check if account is active
                if not user.is_active:
                    raise serializers.ValidationError({
                        'error': 'Account is disabled. Please contact support.'
                    })
                
                # Verify password
                if not user.check_password(password):
                    user.increment_login_attempts()
                    raise serializers.ValidationError({
                        'error': 'Invalid credentials.'
                    })
                
                requires_school_scope = user.role in SCHOOL_SCOPED_ROLES
                requires_school_code = user.role in STRICT_SCHOOL_CODE_LOGIN_ROLES

                if requires_school_code and not school_code:
                    raise serializers.ValidationError({
                    'error': 'School code is required for student, teacher, staff, and accountant login.'
                    })

                if requires_school_scope and not user.tenant and not school_code:
                    raise serializers.ValidationError({
                        'error': 'School code is required because your account is not linked to a school.'
                    })

                # Verify school code when required or provided.
                tenant = None
                if requires_school_scope or school_code:
                    if not school_code and user.tenant:
                        tenant = user.tenant
                    else:
                        try:
                            tenant = SchoolTenant.objects.get(schema_name__iexact=school_code, is_active=True)
                        except SchoolTenant.DoesNotExist:
                            raise serializers.ValidationError({
                                'error': 'Invalid school code.'
                            })

                if tenant and user.tenant and user.tenant != tenant:
                    raise serializers.ValidationError({
                        'error': 'User does not belong to this school.'
                    })

                # Backfill missing tenant links for existing school-scoped accounts.
                if requires_school_scope and tenant and not user.tenant:
                    user.tenant = tenant
                    user.save(update_fields=['tenant'])

                if user.role == "student":
                    if user.tenant:
                        update_student_activation_alerts(user.tenant)
                    if not student_has_login_credit(user):
                        raise serializers.ValidationError({
                            'error': 'Account inactive. Contact admin.'
                        })
                
                # Reset login attempts on successful login
                user.reset_login_attempts()
                
                # Update last login IP (will be set in view)
                
                data['user'] = user
                
            except User.DoesNotExist:
                raise serializers.ValidationError({
                    'error': 'Invalid credentials.'
                })
        else:
            raise serializers.ValidationError({
                'error': 'Must include "email" and "password".'
            })
        
        return data

class VerifyEmailSerializer(serializers.Serializer):
    """
    Serializer for email verification
    """
    email = serializers.EmailField()
    code = serializers.CharField(max_length=6)

class ResendVerificationSerializer(serializers.Serializer):
    """
    Serializer for resending verification email
    """
    email = serializers.EmailField()

class PasswordResetRequestSerializer(serializers.Serializer):
    """
    Serializer for requesting password reset
    """
    email = serializers.EmailField()

class PasswordResetConfirmSerializer(serializers.Serializer):
    """
    Serializer for confirming password reset
    """
    token = serializers.CharField()
    password = serializers.CharField(min_length=8, write_only=True)
    confirm_password = serializers.CharField(min_length=8, write_only=True)
    
    def validate(self, data):
        if data['password'] != data['confirm_password']:
            raise serializers.ValidationError({
                'confirm_password': 'Passwords do not match.'
            })
        return data

class ChangePasswordSerializer(serializers.Serializer):
    """
    Serializer for changing password (authenticated)
    """
    old_password = serializers.CharField(write_only=True)
    new_password = serializers.CharField(min_length=8, write_only=True)
    confirm_password = serializers.CharField(min_length=8, write_only=True)
    
    def validate(self, data):
        if data['new_password'] != data['confirm_password']:
            raise serializers.ValidationError({
                'confirm_password': 'Passwords do not match.'
            })
        return data

class CheckEmailSerializer(serializers.Serializer):
    """
    Serializer for checking email availability
    """
    email = serializers.EmailField()
    
    def validate_email(self, value):
        exists = User.objects.filter(email__iexact=value).exists()
        return {'email': value, 'exists': exists}

class SocialAuthSerializer(serializers.Serializer):
    """
    Serializer for social authentication
    """
    provider = serializers.ChoiceField(choices=['google', 'microsoft', 'facebook'])
    access_token = serializers.CharField()
    id_token = serializers.CharField(required=False)
