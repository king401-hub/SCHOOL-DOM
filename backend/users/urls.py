from django.urls import path

from apps.auth.views import GoogleLoginView, MicrosoftLoginView
from . import views

urlpatterns = [
    path("login/", views.login_view, name="api_login"),
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
    path("password-reset/", views.password_reset_request, name="password_reset_request"),
    path("password-reset/confirm/", views.password_reset_confirm, name="password_reset_confirm"),
    path("change-password/", views.change_password, name="api_change_password"),
    path("google/login/", GoogleLoginView.as_view(), name="google_login"),
    path("microsoft/login/", MicrosoftLoginView.as_view(), name="microsoft_login"),
]
