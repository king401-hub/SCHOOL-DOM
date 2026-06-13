"""
URL configuration for config project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/4.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.conf import settings
from django.conf.urls.static import static as static_urlpatterns
from django.contrib import admin
from django.contrib.auth import views as auth_views
from django.http import FileResponse, Http404
from django.templatetags.static import static
from django.urls import include, path, re_path
from django.views.static import serve
from django.views.generic import RedirectView
from django.views.generic import TemplateView
from django.views.decorators.csrf import csrf_exempt
from apps.auth.views import LoginView, LogoutView, RegisterView, school_superadmin_dashboard
from apps.app.views import AppDownloadView, admin_app_download_version, download_admin_app, download_android_apk, download_student_cbt_app, download_student_cbt_win7_app, download_student_cbt_win7_student_app, redirect_student_cbt, student_cbt_app_version, student_cbt_win7_app_version, student_cbt_win7_student_app_version
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView


LANDING_DIST_DIR = settings.BASE_DIR / 'backend' / 'landing-page' / 'dist'


def landing_page(request):
    index_file = LANDING_DIST_DIR / 'index.html'
    if not index_file.exists():
        raise Http404('Landing page build not found. Run `npm run build` in backend/landing-page.')
    return FileResponse(index_file.open('rb'), content_type='text/html')


urlpatterns = [
    path('', landing_page, name='landing_page'),
    path('favicon.ico', RedirectView.as_view(url=static('img/schooldom-favicon.jpeg'), permanent=True)),
    path('admin/', admin.site.urls),
    path('api/auth/', include('users.urls')),
    path('api/finance/', include('finance.urls')),
    path('api/collections/', include('fee_collections.urls')),
    path('api/hr/', include('hr.urls')),
    path('api/attendance/', include('attendance.urls')),
    path('api/app/', include('users.app_urls')),
    path('api/quizzes/', include('quizzes.urls')),
    path('api/exams/', include('exams.urls')),
    path('login/', csrf_exempt(LoginView.as_view()), name='login'),
    path('api/login/', LoginView.as_view(), name='api_login'),
    path('api/token/', TokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('api/token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    path('register/', RegisterView.as_view(), name='register'),
    path('logout/', LogoutView.as_view(), name='logout'),
    path('school-superadmin/', school_superadmin_dashboard, name='school_superadmin_dashboard'),
    path(
        'password-reset/',
        auth_views.PasswordResetView.as_view(
            template_name='registration/password_reset_form.html',
            email_template_name='registration/password_reset_email.html',
            subject_template_name='registration/password_reset_subject.txt',
            success_url='/password-reset/done/',
        ),
        name='password_reset',
    ),
    path(
        'password-reset/done/',
        auth_views.PasswordResetDoneView.as_view(template_name='registration/password_reset_done.html'),
        name='password_reset_done',
    ),
    path(
        'reset/<uidb64>/<token>/',
        auth_views.PasswordResetConfirmView.as_view(
            template_name='registration/password_reset_confirm.html',
            success_url='/reset/done/',
        ),
        name='password_reset_confirm',
    ),
    path(
        'reset/done/',
        auth_views.PasswordResetCompleteView.as_view(template_name='registration/password_reset_complete.html'),
        name='password_reset_complete',
    ),
    path('school/settings/', TemplateView.as_view(template_name='school/settings.html'), name='school_settings'),
    path('app/download/', AppDownloadView.as_view(), name='app_download'),
    path('app/download/admin/', download_admin_app, name='admin_app_download'),
    path('app/download/admin/version/', admin_app_download_version, name='admin_app_download_version'),
    path('app/download/apk/', download_android_apk, name='app_apk_download'),
    path('app/download/student-cbt/', download_student_cbt_app, name='student_cbt_app_download'),
    path('app/download/student-cbt/version/', student_cbt_app_version, name='student_cbt_app_version'),
    path('app/download/student-cbt/win7/', download_student_cbt_win7_app, name='student_cbt_win7_app_download'),
    path('app/download/student-cbt/win7/version/', student_cbt_win7_app_version, name='student_cbt_win7_app_version'),
    path('app/download/student-cbt/win7/student/', download_student_cbt_win7_student_app, name='student_cbt_win7_student_app_download'),
    path('app/download/student-cbt/win7/student/version/', student_cbt_win7_student_app_version, name='student_cbt_win7_student_app_version'),
    path('student-cbt/', redirect_student_cbt, name='student_cbt_redirect'),
    path("super-admin/", include("superadmin_dashboard.urls")),
    re_path(r'^assets/(?P<path>.*)$', serve, {'document_root': LANDING_DIST_DIR / 'assets'}),
    re_path(r'^icons/(?P<path>.*)$', serve, {'document_root': LANDING_DIST_DIR / 'icons'}),
    path('manifest.webmanifest', serve, {'path': 'manifest.webmanifest', 'document_root': LANDING_DIST_DIR}),
    path('service-worker.js', serve, {'path': 'service-worker.js', 'document_root': LANDING_DIST_DIR}),
    path('favicon.svg', serve, {'path': 'favicon.svg', 'document_root': LANDING_DIST_DIR}),
    path('schooldom-favicon.jpeg', serve, {'path': 'schooldom-favicon.jpeg', 'document_root': LANDING_DIST_DIR}),
    path('school-favicon.svg', serve, {'path': 'school-favicon.svg', 'document_root': LANDING_DIST_DIR}),
    re_path(r'^(?!api/|admin/|app/download/|school-superadmin/|student-cbt/|assets/|icons/|favicon\.ico$|favicon\.svg$|schooldom-favicon\.jpeg$|school-favicon\.svg$|manifest\.webmanifest$|service-worker\.js$).*$', landing_page),
]

# Serve uploaded media files in development.
if settings.DEBUG:
    urlpatterns += static_urlpatterns(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
