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
from django.http import HttpResponse
from django.templatetags.static import static
from django.urls import include, path
from django.views.generic import RedirectView
from django.views.generic import TemplateView
from django.views.decorators.csrf import csrf_exempt
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
import json
from apps.auth.views import LoginView, LogoutView, RegisterView
from apps.app.views import AppDownloadView, download_android_apk
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView


def placeholder_view(request):
    return HttpResponse("Page not implemented yet.", status=501)


@csrf_exempt
@require_http_methods(["POST", "OPTIONS"])
def test_login_endpoint(request):
    print("\n" + "=" * 50)
    print("TEST ENDPOINT HIT!")
    print(f"Method: {request.method}")
    print(f"Headers: {dict(request.headers)}")
    print(f"Body: {request.body}")
    print("=" * 50 + "\n")

    if request.method == "OPTIONS":
        response = JsonResponse({})
        response["Access-Control-Allow-Origin"] = "*"
        response["Access-Control-Allow-Methods"] = "POST, OPTIONS"
        response["Access-Control-Allow-Headers"] = "Content-Type, X-CSRFToken"
        return response

    try:
        data = json.loads(request.body)
        return JsonResponse(
            {
                "status": "success",
                "message": "Test endpoint working!",
                "received_data": data,
            }
        )
    except Exception:
        return JsonResponse({"status": "error", "message": "Invalid JSON"}, status=400)

print(f"csrf_exempt type: {type(csrf_exempt)}")
print(f"LoginView type: {type(LoginView)}")
print(f"Wrapped view: {csrf_exempt(LoginView.as_view())}")

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
    path('test-login/', test_login_endpoint, name='test_login'),
    path('register/', RegisterView.as_view(), name='register'),
    path('logout/', LogoutView.as_view(), name='logout'),
    path('school/settings/', TemplateView.as_view(template_name='school/settings.html'), name='school_settings'),
    path('app/download/', AppDownloadView.as_view(), name='app_download'),
    path('app/download/apk/', download_android_apk, name='app_apk_download'),
    path('dashboard/', placeholder_view, name='dashboard'),
    path('exams/', placeholder_view, name='exam_list'),
    path('exams/upload-results/', placeholder_view, name='upload_results'),
    path('exams/my-exams/', placeholder_view, name='my_exams'),
    path('exams/my-results/', placeholder_view, name='my_results'),
    path('notifications/', placeholder_view, name='notifications'),
    path('notifications/list/', placeholder_view, name='notification_list'),
    path('profile/', placeholder_view, name='profile'),
    path('change-password/', placeholder_view, name='change_password'),
    path('auth/base_auth/', placeholder_view, name='base_auth'),
]

# Serve uploaded media files in development.
if settings.DEBUG:
    urlpatterns += static_urlpatterns(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
