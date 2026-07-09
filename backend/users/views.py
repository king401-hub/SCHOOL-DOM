# users/views.py
import logging
import re
from rest_framework import status
from rest_framework.decorators import APIView, api_view, authentication_classes, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework_simplejwt.tokens import RefreshToken
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.hashers import check_password, make_password
from django.utils import timezone
from django.core.mail import get_connection, send_mail
from django.template.loader import render_to_string
from django.conf import settings
from django.db import IntegrityError, transaction
from django.utils.text import slugify
import random
import secrets
import string
import jwt
from datetime import datetime, timedelta
from urllib.parse import urlencode
from core.models import SchoolTenant, Domain
from tenants.models import Tenant
from .models import User, LoginHistory
from .serializers import (
    RegisterSerializer, LoginSerializer, UserSerializer,
    VerifyEmailSerializer, PasswordResetRequestSerializer,
    PasswordResetConfirmSerializer, ChangePasswordSerializer,
    CheckEmailSerializer, CreateSchoolSerializer
)
from .serializers import ResendVerificationSerializer
from finance.services import grant_school_registration_credits, student_has_login_credit, update_student_activation_alerts

ADMIN_OTP_ROLES = {"school_admin", "principal", "super_admin", "school_superadmin"}
ADMIN_OTP_ENABLED = getattr(settings, "ADMIN_OTP_ENABLED", False)
ADMIN_OTP_EXPIRY_MINUTES = 10
logger = logging.getLogger(__name__)

class ResendVerificationView(APIView):
    def post(self, request, *args, **kwargs):
        serializer = ResendVerificationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        ...


def normalize_school_code(raw_value):
    """
    Normalize school code to a schema-safe identifier:
    lowercase + underscores, leading alpha, max 63 chars.
    """
    normalized = slugify(str(raw_value or "")).replace("-", "_")
    normalized = re.sub(r"[^a-z0-9_]", "_", normalized)
    normalized = re.sub(r"_+", "_", normalized).strip("_")

    if not normalized:
        normalized = "school"

    if normalized[0].isdigit():
        normalized = f"sch_{normalized}"

    return normalized[:63]


def generate_unique_schema_name(preferred_code):
    """
    Generate a unique SchoolTenant.schema_name from preferred code.
    """
    reserved = {"public", "information_schema", "pg_catalog"}
    base = normalize_school_code(preferred_code)

    if base in reserved:
        base = f"{base}_school"

    if len(base) < 3:
        base = f"{base}_sch"

    candidate = base[:63]
    counter = 1

    while SchoolTenant.objects.filter(schema_name__iexact=candidate).exists():
        counter += 1
        suffix = f"_{counter}"
        candidate = f"{base[:63 - len(suffix)]}{suffix}"

    return candidate


def generate_unique_domain(schema_name):
    """
    Generate a unique primary domain for the school tenant.
    """
    base_domain = f"{schema_name}.school.local"
    candidate = base_domain
    counter = 1

    while Domain.objects.filter(domain__iexact=candidate).exists():
        counter += 1
        candidate = f"{schema_name}-{counter}.school.local"

    return candidate
def get_client_ip(request):
    """Get client IP address from request"""
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0]
    else:
        ip = request.META.get('REMOTE_ADDR')
    return ip

def get_device_info(request):
    """Parse user agent to get device info"""
    user_agent = request.META.get('HTTP_USER_AGENT', '')
    
    # Simple parsing - can be enhanced with a proper library
    device_type = 'desktop'
    browser = 'unknown'
    os = 'unknown'
    
    if 'Mobile' in user_agent:
        device_type = 'mobile'
    elif 'Tablet' in user_agent:
        device_type = 'tablet'
    
    if 'Chrome' in user_agent:
        browser = 'Chrome'
    elif 'Firefox' in user_agent:
        browser = 'Firefox'
    elif 'Safari' in user_agent:
        browser = 'Safari'
    
    if 'Windows' in user_agent:
        os = 'Windows'
    elif 'Mac' in user_agent:
        os = 'macOS'
    elif 'Linux' in user_agent:
        os = 'Linux'
    elif 'Android' in user_agent:
        os = 'Android'
    elif 'iOS' in user_agent or 'iPhone' in user_agent:
        os = 'iOS'
    
    return {
        'user_agent': user_agent,
        'device_type': device_type,
        'browser': browser,
        'os': os
    }

def create_login_history(user, request, status='success'):
    """Create login history entry"""
    ip = get_client_ip(request)
    device_info = get_device_info(request)
    
    LoginHistory.objects.create(
        user=user,
        ip_address=ip,
        status=status,
        **device_info
    )

def is_admin_otp_user(user):
    return ADMIN_OTP_ENABLED and getattr(user, "role", "") in ADMIN_OTP_ROLES


def get_admin_email_device(user, challenge=None):
    if not challenge or user.admin_otp_challenge != challenge:
        return None
    if not user.admin_otp_sent_at:
        return None
    expires_at = user.admin_otp_sent_at + timedelta(minutes=ADMIN_OTP_EXPIRY_MINUTES)
    if timezone.now() > expires_at:
        return None
    return user


def admin_otp_challenge_matches(user, challenge=None):
    return bool(challenge and user.admin_otp_challenge == challenge)


def send_admin_otp(user, purpose="login"):
    code = "".join(secrets.choice(string.digits) for _ in range(6))
    challenge = secrets.token_urlsafe(32)
    user._admin_otp_debug_code = code
    user.admin_otp_hash = make_password(code)
    user.admin_otp_sent_at = timezone.now()
    user.admin_otp_purpose = purpose
    user.admin_otp_attempts = 0
    user.admin_otp_challenge = challenge
    user.save(update_fields=[
        "admin_otp_hash",
        "admin_otp_sent_at",
        "admin_otp_purpose",
        "admin_otp_attempts",
        "admin_otp_challenge",
    ])

    message = render_to_string("emails/admin_otp.html", {
        "user": user,
        "code": code,
        "purpose": purpose,
        "expires_minutes": ADMIN_OTP_EXPIRY_MINUTES,
    })
    try:
        connection = get_connection(timeout=getattr(settings, "EMAIL_TIMEOUT", 10))
        send_mail(
            "Your SchoolDom admin verification code",
            f"Your SchoolDom verification code is {code}. It expires in {ADMIN_OTP_EXPIRY_MINUTES} minutes.",
            settings.DEFAULT_FROM_EMAIL,
            [user.email],
            connection=connection,
            html_message=message,
            fail_silently=False,
        )
    except Exception:
        if not getattr(settings, "ADMIN_OTP_EMAIL_FAILURE_CONSOLE_FALLBACK", False):
            raise
        logger.warning(
            "Admin OTP email delivery failed for %s. Using local console fallback. "
            "SchoolDom admin OTP code: %s",
            user.email,
            code,
        )
    return challenge


def admin_otp_debug_payload(user):
    if not getattr(settings, "ADMIN_OTP_DEBUG_CODE_ENABLED", False):
        return {}
    code = getattr(user, "_admin_otp_debug_code", "")
    return {"debug_otp": code} if code else {}


def clear_admin_otp(user):
    user.admin_otp_hash = None
    user.admin_otp_sent_at = None
    user.admin_otp_purpose = ''
    user.admin_otp_attempts = 0
    user.admin_otp_challenge = None
    user.admin_otp_verified_at = timezone.now()
    user.save(update_fields=[
        "admin_otp_hash",
        "admin_otp_sent_at",
        "admin_otp_purpose",
        "admin_otp_attempts",
        "admin_otp_challenge",
        "admin_otp_verified_at",
    ])


def admin_redirect_url(user):
    return {
        'super_admin': '/admin/dashboard/',
        'school_superadmin': '/school-superadmin/',
        'school_admin': '/school/dashboard/',
        'principal': '/dashboard/',
        'teacher': '/teacher/dashboard/',
        'student': '/student/dashboard/',
        'parent': '/parent/dashboard/',
        'staff': '/staff/dashboard/',
    }.get(user.role, '/dashboard/')


def auth_school_payload(user):
    school = getattr(user, "tenant", None)
    if not school:
        return {}
    return {
        "id": school.id,
        "name": school.name,
        "school_code": school.schema_name,
        "school_type": getattr(school, "school_type", "k12") or "k12",
        "email": school.email or "",
        "phone": school.phone or "",
        "address": school.address or "",
        "motto": getattr(school, "motto", "") or "",
        "tagline": getattr(school, "motto", "") or "",
        "student_rules": getattr(school, "student_rules", "") or "",
        "staff_rules": getattr(school, "staff_rules", "") or "",
    }


def build_frontend_url(request, path, query=None):
    base_url = (getattr(settings, "FRONTEND_BASE_URL", "") or "").strip().rstrip("/")
    if not base_url:
        scheme = request.headers.get("X-Forwarded-Proto", request.scheme)
        host = request.get_host()
        port = str(getattr(settings, "FRONTEND_DEV_PORT", "") or "").strip()
        hostname = host.split(":", 1)[0]
        if port and hostname in {"localhost", "127.0.0.1"}:
            host = f"{hostname}:{port}"
        base_url = f"{scheme}://{host}"

    normalized_path = f"/{str(path or '').lstrip('/')}"
    url = f"{base_url}{normalized_path}"
    if query:
        url = f"{url}?{urlencode(query)}"
    return url


def get_tokens_for_user(user):
    """Generate JWT tokens for user"""
    refresh = RefreshToken.for_user(user)
    
    # Add custom claims
    refresh['role'] = user.role
    refresh['tenant'] = str(user.tenant.id) if user.tenant else None
    
    return {
        'refresh': str(refresh),
        'access': str(refresh.access_token),
    }

@api_view(['POST'])
@authentication_classes([])
@permission_classes([AllowAny])
def register(request):
    """
    User registration endpoint
    """
    serializer = RegisterSerializer(data=request.data)
    
    if serializer.is_valid():
        user = serializer.save()

        if is_admin_otp_user(user):
            try:
                challenge = send_admin_otp(user, purpose="signup")
            except Exception as exc:
                logger.warning("Admin signup OTP email delivery failed for %s.", user.email, exc_info=True)
                return Response({
                    'success': False,
                    'message': 'Account created but the verification email could not be sent. Please configure the school email SMTP settings and try resend OTP.'
                }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
            return Response({
                'success': True,
                'requires_otp': True,
                'otp_purpose': 'signup',
                'otp_challenge': challenge,
                'otp_expires_in': ADMIN_OTP_EXPIRY_MINUTES * 60,
                'message': 'Account created. Enter the 6-digit OTP sent to your email to activate admin access.',
                'user': UserSerializer(user).data,
                **admin_otp_debug_payload(user),
            }, status=status.HTTP_201_CREATED)
        
        # Return response
        tokens = get_tokens_for_user(user)
        create_login_history(user, request, status='success')
        return Response({
            'success': True,
            'message': 'Registration successful. Please verify your email.',
            'user': UserSerializer(user).data,
            **tokens
        }, status=status.HTTP_201_CREATED)
    
    return Response({
        'success': False,
        'errors': serializer.errors
    }, status=status.HTTP_400_BAD_REQUEST)


@api_view(['POST'])
@authentication_classes([])
@permission_classes([AllowAny])
def create_school(request):
    """
    Create school tenant and allocate non-conflicting schema/domain.
    """
    serializer = CreateSchoolSerializer(data=request.data)

    if not serializer.is_valid():
        return Response({
            'success': False,
            'errors': serializer.errors
        }, status=status.HTTP_400_BAD_REQUEST)

    payload = serializer.validated_data
    preferred = payload.get('school_code') or payload['school_name']
    requested_code = normalize_school_code(preferred)

    # Retry loop for rare race conditions on unique constraints.
    for _ in range(5):
        schema_name = generate_unique_schema_name(preferred)
        domain_name = generate_unique_domain(schema_name)

        try:
            with transaction.atomic():
                tenant = SchoolTenant.objects.create(
                    name=payload['school_name'],
                    schema_name=schema_name,
                    school_type=payload.get('school_type') or SchoolTenant.K12,
                    email=payload.get('email') or None,
                    phone=payload.get('phone') or None,
                    address=payload.get('address') or None,
                    is_active=True,
                    compliance_deadline_reference_at=timezone.now(),
                )

                # Keep legacy tenant model in sync for modules still using tenants.Tenant.
                Tenant.objects.get_or_create(
                    slug=schema_name,
                    defaults={'name': payload['school_name']},
                )

                Domain.objects.create(
                    tenant=tenant,
                    domain=domain_name,
                    is_primary=True,
                )
                credit_pool = grant_school_registration_credits(tenant, credits=50)

            try:
                support_email = getattr(settings, "SCHOOLDOM_SUPPORT_EMAIL", None) or "support@schooldom.academy"
                send_mail(
                    f"New school signed up: {tenant.name}",
                    (
                        f"A new school has signed up on SchoolDom.\n\n"
                        f"School name: {tenant.name}\n"
                        f"School code: {tenant.schema_name}\n"
                        f"Sign-up date: {tenant.created_on.strftime('%Y-%m-%d')}\n"
                    ),
                    settings.DEFAULT_FROM_EMAIL,
                    [support_email],
                    fail_silently=False,
                )
                tenant.signup_notification_sent_at = timezone.now()
                tenant.save(update_fields=["signup_notification_sent_at"])
            except Exception:
                logger.warning("Signup notification email failed for school %s.", tenant.schema_name, exc_info=True)

            return Response({
                'success': True,
                'message': 'School created successfully with 50 free activation credits.',
                'school': {
                    'id': tenant.id,
                    'name': tenant.name,
                    'school_code': tenant.schema_name,
                    'domain': domain_name,
                    'free_credits': credit_pool.balance,
                    'school_type': tenant.school_type,
                },
                'requested_code': requested_code,
                'conflict_resolved': tenant.schema_name != requested_code,
            }, status=status.HTTP_201_CREATED)
        except IntegrityError:
            continue

    return Response({
        'success': False,
        'message': 'Could not allocate a unique school code. Please try again.'
    }, status=status.HTTP_409_CONFLICT)

@api_view(['POST'])
@authentication_classes([])
@permission_classes([AllowAny])
def login_view(request):
    """
    User login endpoint
    """
    serializer = LoginSerializer(data=request.data)
    
    if serializer.is_valid():
        user = serializer.validated_data['user']

        if user.tenant_id and not user.tenant.is_active:
            create_login_history(user, request, status='failed')
            return Response({
                'success': False,
                'message': "Your school's account is suspended pending compliance documents. Contact support@schooldom.academy for help."
            }, status=status.HTTP_403_FORBIDDEN)

        # Update last login
        user.last_login = timezone.now()
        user.update_last_login_ip(get_client_ip(request))
        
        # Save device token if provided
        device_token = request.data.get('device_token')
        if device_token and device_token not in user.device_tokens:
            user.device_tokens.append(device_token)
            user.save(update_fields=['device_tokens'])
        
        if is_admin_otp_user(user):
            purpose = "login" if user.is_verified else "signup"
            try:
                challenge = send_admin_otp(user, purpose=purpose)
            except Exception as exc:
                create_login_history(user, request, status='failed')
                logger.warning("Admin login OTP email delivery failed for %s.", user.email, exc_info=True)
                return Response({
                    'success': False,
                    'message': 'Could not send the admin verification code. Please configure the school email SMTP settings.'
                }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
            create_login_history(user, request, status='success')
            return Response({
                'success': True,
                'requires_otp': True,
                'otp_purpose': purpose,
                'otp_challenge': challenge,
                'otp_expires_in': ADMIN_OTP_EXPIRY_MINUTES * 60,
                'message': 'Enter the 6-digit OTP sent to your email to continue.',
                'user': UserSerializer(user).data,
                'school_code': user.tenant.schema_name if user.tenant else '',
                'school': auth_school_payload(user),
                **admin_otp_debug_payload(user),
            })

        tokens = get_tokens_for_user(user)
        create_login_history(user, request, status='success')
        if not user.is_verified:
            return Response({
                'success': True,
                'requires_verification': True,
                'message': 'Please verify your email address.',
                'user': UserSerializer(user).data,
                'school_code': user.tenant.schema_name if user.tenant else '',
                'school': auth_school_payload(user),
                **tokens
            })
        
        return Response({
            'success': True,
            'message': 'Login successful',
            'user': UserSerializer(user).data,
            'school_code': user.tenant.schema_name if user.tenant else '',
            'school': auth_school_payload(user),
            'redirect_url': admin_redirect_url(user),
            **tokens
        })
    
    return Response({
        'success': False,
        'errors': serializer.errors
    }, status=status.HTTP_400_BAD_REQUEST)

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def logout_view(request):
    """
    User logout endpoint
    """
    try:
        # Update last logout in login history
        last_login = LoginHistory.objects.filter(
            user=request.user
        ).order_by('-login_time').first()
        
        if last_login:
            last_login.logout_time = timezone.now()
            last_login.save()
        
        # Blacklist refresh token if provided
        refresh_token = request.data.get('refresh_token')
        if refresh_token:
            try:
                token = RefreshToken(refresh_token)
                token.blacklist()
            except Exception:
                pass
        
        logout(request)
        
        return Response({
            'success': True,
            'message': 'Logout successful'
        })
    except Exception as e:
        return Response({
            'success': False,
            'message': str(e)
        }, status=status.HTTP_400_BAD_REQUEST)

@api_view(['POST'])
@authentication_classes([])
@permission_classes([AllowAny])
def verify_email(request):
    """
    Verify email with verification code
    """
    serializer = VerifyEmailSerializer(data=request.data)
    
    if serializer.is_valid():
        email = serializer.validated_data['email']
        code = serializer.validated_data['code']
        
        try:
            user = User.objects.get(email=email)
            
            if user.verify_email(code):
                return Response({
                    'success': True,
                    'message': 'Email verified successfully'
                })
            else:
                return Response({
                    'success': False,
                    'message': 'Invalid verification code'
                }, status=status.HTTP_400_BAD_REQUEST)
                
        except User.DoesNotExist:
            return Response({
                'success': False,
                'message': 'User not found'
            }, status=status.HTTP_404_NOT_FOUND)
    
    return Response({
        'success': False,
        'errors': serializer.errors
    }, status=status.HTTP_400_BAD_REQUEST)

@api_view(['POST'])
@authentication_classes([])
@permission_classes([AllowAny])
def resend_verification(request):
    """
    Resend verification email
    """
    serializer = ResendVerificationSerializer(data=request.data)
    
    if serializer.is_valid():
        email = serializer.validated_data['email']
        
        try:
            user = User.objects.get(email=email)
            
            if user.is_verified:
                return Response({
                    'success': False,
                    'message': 'Email already verified'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            # Generate new token
            token = user.generate_email_verification_token()
            
            # Send email
            subject = 'Verify Your Email'
            message = render_to_string('emails/verify_email.html', {
                'user': user,
                'token': token
            })
            
            send_mail(
                subject,
                message,
                settings.DEFAULT_FROM_EMAIL,
                [user.email],
                html_message=message,
                fail_silently=False
            )
            
            return Response({
                'success': True,
                'message': 'Verification email sent'
            })
            
        except User.DoesNotExist:
            return Response({
                'success': False,
                'message': 'User not found'
            }, status=status.HTTP_404_NOT_FOUND)
    
    return Response({
        'success': False,
        'errors': serializer.errors
    }, status=status.HTTP_400_BAD_REQUEST)


@api_view(['POST'])
@authentication_classes([])
@permission_classes([AllowAny])
def admin_verify_otp(request):
    email = str(request.data.get('email') or '').strip().lower()
    code = str(request.data.get('code') or request.data.get('otp') or '').strip()
    challenge = str(request.data.get('challenge') or request.data.get('otp_challenge') or '').strip()
    if not email or not code or not challenge:
        return Response({
            'success': False,
            'message': 'Email, OTP code, and challenge are required.'
        }, status=status.HTTP_400_BAD_REQUEST)
    if not re.fullmatch(r"\d{6}", code):
        return Response({
            'success': False,
            'message': 'OTP must be a 6-digit code.'
        }, status=status.HTTP_400_BAD_REQUEST)
    try:
        user = User.objects.get(email__iexact=email)
    except User.DoesNotExist:
        return Response({'success': False, 'message': 'Invalid OTP challenge.'}, status=status.HTTP_404_NOT_FOUND)
    if not is_admin_otp_user(user):
        return Response({'success': False, 'message': 'OTP verification is only required for admin accounts.'}, status=status.HTTP_400_BAD_REQUEST)
    if user.is_locked:
        create_login_history(user, request, status='locked')
        return Response({'success': False, 'message': 'Account is locked. Contact support.'}, status=status.HTTP_423_LOCKED)
    otp_user = get_admin_email_device(user, challenge=challenge)
    if not otp_user:
        create_login_history(user, request, status='failed')
        return Response({'success': False, 'message': 'Invalid OTP challenge.'}, status=status.HTTP_400_BAD_REQUEST)

    if not user.admin_otp_hash or not check_password(code, user.admin_otp_hash):
        user.admin_otp_attempts += 1
        user.save(update_fields=['admin_otp_attempts'])
        if user.admin_otp_attempts >= 5:
            user.increment_login_attempts()
        create_login_history(user, request, status='failed')
        if user.is_locked or user.admin_otp_attempts >= 5:
            return Response({'success': False, 'message': 'Too many failed OTP attempts. Account locked.'}, status=status.HTTP_423_LOCKED)
        remaining = max(5 - user.admin_otp_attempts, 0)
        return Response({
            'success': False,
            'message': f'Invalid OTP code. {remaining} attempt{"s" if remaining != 1 else ""} remaining.'
        }, status=status.HTTP_400_BAD_REQUEST)

    if not user.is_verified:
        user.is_verified = True
        user.email_verified_at = timezone.now()
        user.save(update_fields=['is_verified', 'email_verified_at'])
    user.last_login = timezone.now()
    user.update_last_login_ip(get_client_ip(request))
    user.reset_login_attempts()
    clear_admin_otp(user)
    create_login_history(user, request, status='success')
    tokens = get_tokens_for_user(user)
    return Response({
        'success': True,
        'message': 'Admin verification successful.',
        'user': UserSerializer(user).data,
        'school_code': user.tenant.schema_name if user.tenant else '',
        'school': auth_school_payload(user),
        'redirect_url': admin_redirect_url(user),
        **tokens
    })


@api_view(['POST'])
@authentication_classes([])
@permission_classes([AllowAny])
def admin_resend_otp(request):
    email = str(request.data.get('email') or '').strip().lower()
    challenge = str(request.data.get('challenge') or request.data.get('otp_challenge') or '').strip()
    if not email:
        return Response({'success': False, 'message': 'Email is required.'}, status=status.HTTP_400_BAD_REQUEST)
    try:
        user = User.objects.get(email__iexact=email)
    except User.DoesNotExist:
        return Response({'success': False, 'message': 'User not found.'}, status=status.HTTP_404_NOT_FOUND)
    if not is_admin_otp_user(user):
        return Response({'success': False, 'message': 'OTP resend is only available for admin accounts.'}, status=status.HTTP_400_BAD_REQUEST)
    if challenge and not admin_otp_challenge_matches(user, challenge=challenge):
        return Response({'success': False, 'message': 'Invalid OTP challenge.'}, status=status.HTTP_400_BAD_REQUEST)
    purpose = 'login' if user.is_verified else 'signup'
    try:
        next_challenge = send_admin_otp(user, purpose=purpose)
    except Exception as exc:
        logger.warning("Admin OTP resend email delivery failed for %s.", user.email, exc_info=True)
        return Response({'success': False, 'message': 'Could not send OTP. Please configure the school email SMTP settings.'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    return Response({
        'success': True,
        'message': 'A new OTP code has been sent.',
        'requires_otp': True,
        'otp_purpose': purpose,
        'otp_challenge': next_challenge,
        'otp_expires_in': ADMIN_OTP_EXPIRY_MINUTES * 60,
        **admin_otp_debug_payload(user),
    })

@api_view(['POST'])
@authentication_classes([])
@permission_classes([AllowAny])
def password_reset_request(request):
    """
    Request password reset
    """
    serializer = PasswordResetRequestSerializer(data=request.data)
    
    if serializer.is_valid():
        email = serializer.validated_data['email']
        
        try:
            user = User.objects.get(email=email)
            
            # Generate reset token
            token = user.generate_password_reset_token()
            
            # Send email
            subject = 'Password Reset Request'
            reset_url = build_frontend_url(request, "/reset-password", {"token": token})
            message = render_to_string('emails/password_reset.html', {
                'user': user,
                'token': token,
                'reset_url': reset_url,
                'expires_hours': 24,
            })
            
            send_mail(
                subject,
                message,
                settings.DEFAULT_FROM_EMAIL,
                [user.email],
                html_message=message,
                fail_silently=False
            )
            
            return Response({
                'success': True,
                'message': 'Password reset email sent'
            })
            
        except User.DoesNotExist:
            # Don't reveal that user doesn't exist
            return Response({
                'success': True,
                'message': 'If an account exists with this email, a reset link will be sent.'
            })
    
    return Response({
        'success': False,
        'errors': serializer.errors
    }, status=status.HTTP_400_BAD_REQUEST)

@api_view(['POST'])
@authentication_classes([])
@permission_classes([AllowAny])
def password_reset_confirm(request):
    """
    Confirm password reset with token
    """
    serializer = PasswordResetConfirmSerializer(data=request.data)
    
    if serializer.is_valid():
        token = serializer.validated_data['token']
        new_password = serializer.validated_data['password']
        
        try:
            user = User.objects.get(password_reset_token=token)
            
            # Check if token is expired (24 hours)
            if user.password_reset_sent_at:
                time_diff = timezone.now() - user.password_reset_sent_at
                if time_diff.total_seconds() > 24 * 3600:
                    return Response({
                        'success': False,
                        'message': 'Reset token has expired'
                    }, status=status.HTTP_400_BAD_REQUEST)
            
            # Set new password
            user.set_password(new_password)
            user.password_reset_token = None
            user.password_reset_sent_at = None
            user.last_password_change = timezone.now()
            user.login_attempts = 0
            user.is_locked = False
            user.save(update_fields=[
                'password',
                'password_reset_token',
                'password_reset_sent_at',
                'last_password_change',
                'login_attempts',
                'is_locked',
            ])
            
            return Response({
                'success': True,
                'message': 'Password reset successful'
            })
            
        except User.DoesNotExist:
            return Response({
                'success': False,
                'message': 'Invalid reset token'
            }, status=status.HTTP_400_BAD_REQUEST)
    
    return Response({
        'success': False,
        'errors': serializer.errors
    }, status=status.HTTP_400_BAD_REQUEST)

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def change_password(request):
    """
    Change password for authenticated user
    """
    serializer = ChangePasswordSerializer(data=request.data)
    
    if serializer.is_valid():
        user = request.user
        
        # Check old password
        if not user.check_password(serializer.validated_data['old_password']):
            return Response({
                'success': False,
                'message': 'Current password is incorrect'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Set new password
        user.set_password(serializer.validated_data['new_password'])
        user.last_password_change = timezone.now()
        user.save()
        
        return Response({
            'success': True,
            'message': 'Password changed successfully'
        })
    
    return Response({
        'success': False,
        'errors': serializer.errors
    }, status=status.HTTP_400_BAD_REQUEST)

@api_view(['GET'])
@permission_classes([AllowAny])
def check_email(request):
    """
    Check if email exists (for registration)
    """
    serializer = CheckEmailSerializer(data=request.query_params)
    
    if serializer.is_valid():
        result = serializer.validate_email(serializer.validated_data['email'])
        return Response(result)
    
    return Response({
        'success': False,
        'errors': serializer.errors
    }, status=status.HTTP_400_BAD_REQUEST)

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def me(request):
    """
    Get current user information
    """
    user = request.user
    data = UserSerializer(user).data
    
    # Add role-specific profile data
    if user.role == 'student' and hasattr(user, 'student_profile'):
        data['profile'] = {
            'student_id': user.student_profile.student_id,
            'admission_number': user.student_profile.admission_number,
            'guardian_name': user.student_profile.guardian_name
        }
    elif user.role == 'teacher' and hasattr(user, 'teacher_profile'):
        data['profile'] = {
            'employee_id': user.teacher_profile.employee_id,
            'qualification': user.teacher_profile.qualification,
            'specialization': user.teacher_profile.specialization
        }
    elif user.role == 'parent' and hasattr(user, 'parent_profile'):
        data['profile'] = {
            'occupation': user.parent_profile.occupation,
            'children_count': user.parent_profile.children.count()
        }
    
    return Response(data)

@api_view(['POST'])
@permission_classes([AllowAny])
def refresh_token(request):
    """
    Refresh access token
    """
    refresh_token = request.data.get('refresh')
    
    if not refresh_token:
        return Response({
            'success': False,
            'message': 'Refresh token required'
        }, status=status.HTTP_401_UNAUTHORIZED)
    
    try:
        token = RefreshToken(refresh_token)
        user_id = token.get('user_id')
        if user_id:
            user = User.objects.filter(id=user_id).first()
            if user and user.role == 'student':
                if user.tenant:
                    update_student_activation_alerts(user.tenant)
                if not student_has_login_credit(user):
                    return Response({
                        'success': False,
                        'message': 'Account inactive. Contact admin.'
                    }, status=status.HTTP_401_UNAUTHORIZED)
        # Access access_token to trigger rotation if enabled
        access_token = str(token.access_token)
        data = {
            'access': access_token
        }
        # Include new refresh token if rotation occurred
        new_refresh = str(token)
        if new_refresh != refresh_token:
            data['refresh'] = new_refresh
        return Response(data)
    except Exception as e:
        import logging
        logger = logging.getLogger(__name__)
        logger.warning(f"Token refresh failed: {str(e)}")
        return Response({
            'success': False,
            'message': 'Invalid or expired refresh token'
        }, status=status.HTTP_401_UNAUTHORIZED)
