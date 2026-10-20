from django.urls import path

from apps.auth.views import GoogleLoginView, MicrosoftLoginView
from . import app_views, views

urlpatterns = [
    path("login/", views.login_view, name="api_login"),
    path("exchange-impersonation/", views.exchange_impersonation_code, name="api_exchange_impersonation"),
    path("register/", views.register, name="api_register"),
    path("create-school/", views.create_school, name="api_create_school"),
    path("logout/", views.logout_view, name="api_logout"),
    path("me/", views.me, name="api_me"),
    path("refresh/", views.refresh_token, name="api_refresh"),
    path("check-email/", views.check_email, name="check_email"),
    path("send-verification/", views.resend_verification, name="send_verification"),
    path("verify-email/", views.verify_email, name="verify_email"),
    path("admin/verify-otp/", views.admin_verify_otp, name="admin_verify_otp"),
    path("admin/resend-otp/", views.admin_resend_otp, name="admin_resend_otp"),
    path("admin/set-phone/", views.set_phone_and_send_otp, name="set_phone_and_send_otp"),
    path("admin/verify-phone-otp/", views.phone_verify_otp, name="phone_verify_otp"),
    path("admin/resend-phone-otp/", views.phone_resend_otp, name="phone_resend_otp"),
    path("password-reset/", views.password_reset_request, name="password_reset_request"),
    path("password-reset/resend/", views.password_reset_resend_otp, name="password_reset_resend_otp"),
    path("password-reset/confirm/", views.password_reset_confirm, name="password_reset_confirm"),
    path("contact/", app_views.public_contact_email, name="public_contact_email"),
    path("change-password/", views.change_password, name="api_change_password"),
    path("google/login/", GoogleLoginView.as_view(), name="google_login"),
    path("microsoft/login/", MicrosoftLoginView.as_view(), name="microsoft_login"),
]
