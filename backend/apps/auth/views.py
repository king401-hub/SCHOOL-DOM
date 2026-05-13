from django.contrib.auth import views as auth_views
from django.http import JsonResponse
from django.views import View
from django.views.generic import TemplateView


class LoginView(auth_views.LoginView):
    template_name = "auth/login.html"
    redirect_authenticated_user = True


class LogoutView(auth_views.LogoutView):
    next_page = "login"


class RegisterView(TemplateView):
    template_name = "auth/register.html"


class APILoginView(View):
    def post(self, request, *args, **kwargs):
        return JsonResponse({"detail": "Not implemented yet."}, status=501)


class APIRegisterView(View):
    def post(self, request, *args, **kwargs):
        return JsonResponse({"detail": "Not implemented yet."}, status=501)


class CheckEmailView(View):
    def get(self, request, *args, **kwargs):
        return JsonResponse({"detail": "Not implemented yet."}, status=501)


class SendVerificationView(View):
    def post(self, request, *args, **kwargs):
        return JsonResponse({"detail": "Not implemented yet."}, status=501)


class GoogleLoginView(View):
    def post(self, request, *args, **kwargs):
        return JsonResponse({"detail": "Not implemented yet."}, status=501)


class MicrosoftLoginView(View):
    def post(self, request, *args, **kwargs):
        return JsonResponse({"detail": "Not implemented yet."}, status=501)
