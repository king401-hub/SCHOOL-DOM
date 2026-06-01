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
from django.templatetags.static import static
from django.urls import include, path
from django.views.generic import RedirectView
from django.views.generic import TemplateView
from django.views.decorators.csrf import csrf_exempt
from apps.auth.views import LoginView, LogoutView, RegisterView
from apps.app.views import AppDownloadView, admin_app_download_version, download_admin_app, download_android_apk, download_student_cbt_app, redirect_student_cbt, student_cbt_app_version
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView


urlpatterns = [
    path('', RedirectView.as_view(pattern_name='school_settings', permanent=False)),
    path('favicon.ico', RedirectView.as_view(url=static('img/schooldom-favicon.jpeg'), permanent=True)),
    path('admin/', admin.site.urls),
    path('api/auth/', include('users.urls')),
    path('api/finance/', include('finance.urls')),
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
    path('school/settings/', TemplateView.as_view(template_name='school/settings.html'), name='school_settings'),
    path('app/download/', AppDownloadView.as_view(), name='app_download'),
    path('app/download/admin/', download_admin_app, name='admin_app_download'),
    path('app/download/admin/version/', admin_app_download_version, name='admin_app_download_version'),
    path('app/download/apk/', download_android_apk, name='app_apk_download'),
    path('app/download/student-cbt/', download_student_cbt_app, name='student_cbt_app_download'),
    path('app/download/student-cbt/version/', student_cbt_app_version, name='student_cbt_app_version'),
    path('student-cbt/', redirect_student_cbt, name='student_cbt_redirect'),
]

# Serve uploaded media files in development.
if settings.DEBUG:
    urlpatterns += static_urlpatterns(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
