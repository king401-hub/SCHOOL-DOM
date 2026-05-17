from pathlib import Path

from django.conf import settings
from django.http import FileResponse, Http404
from django.urls import reverse
from django.views.generic import TemplateView


APK_FILENAME = "schooldom-app.apk"


def app_apk_path():
    return Path(settings.MEDIA_ROOT) / "app" / APK_FILENAME


class AppDownloadView(TemplateView):
    template_name = "app/download.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        apk_path = app_apk_path()
        context["apk_available"] = apk_path.exists()
        context["apk_size_mb"] = round(apk_path.stat().st_size / (1024 * 1024), 1) if apk_path.exists() else None
        context["apk_download_url"] = reverse("app_apk_download")
        context["app_version"] = "0.1.0"
        return context


def download_android_apk(request):
    apk_path = app_apk_path()
    if not apk_path.exists():
        raise Http404("SchoolDom Android APK is not available yet.")

    response = FileResponse(
        apk_path.open("rb"),
        as_attachment=True,
        filename=APK_FILENAME,
        content_type="application/vnd.android.package-archive",
    )
    response["Cache-Control"] = "no-store"
    return response
