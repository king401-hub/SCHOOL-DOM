from pathlib import Path
from urllib.parse import urlsplit
import subprocess

from django.conf import settings
from django.http import FileResponse, Http404, JsonResponse
from django.shortcuts import redirect
from django.urls import reverse
from django.views.generic import TemplateView


APK_FILENAME = "schooldom-app.apk"
ADMIN_APP_FILENAME = "SchoolDomAdmin.exe"
STUDENT_CBT_FILENAME = "SchoolDomCBT.exe"
LEGACY_STUDENT_CBT_FILENAME = "SchoolDom-Student-CBT.exe"
MIN_DESKTOP_INSTALLER_SIZE = 5 * 1024 * 1024


def app_apk_path():
    return Path(settings.MEDIA_ROOT) / "app" / APK_FILENAME


def frontend_dir():
    return Path(settings.BASE_DIR) / "backend" / "frontend"


def safe_server_slug(server_url):
    host = urlsplit(server_url).netloc or "local-server"
    return "".join(char if char.isalnum() else "-" for char in host).strip("-").lower() or "local-server"


def student_cbt_app_path(server_url):
    return Path(settings.MEDIA_ROOT) / "app" / "student-cbt" / safe_server_slug(server_url) / LEGACY_STUDENT_CBT_FILENAME


def offline_cbt_installer_candidates():
    release_dir = Path(settings.BASE_DIR) / "schooldom-cbt-client" / "release"
    media_dir = Path(settings.MEDIA_ROOT) / "app" / "student-cbt"
    candidates = [
        media_dir / STUDENT_CBT_FILENAME,
        media_dir / "SchoolDom-CBT-Client-Setup.exe",
    ]
    if release_dir.exists():
        candidates.extend(sorted(release_dir.glob("SchoolDom-CBT-Client-*-Setup.exe"), reverse=True))
        candidates.extend(sorted(release_dir.glob("*.exe"), reverse=True))
    return candidates


def offline_cbt_installer_path():
    for candidate in offline_cbt_installer_candidates():
        if candidate.exists() and candidate.is_file() and candidate.stat().st_size >= MIN_DESKTOP_INSTALLER_SIZE:
            return candidate
    return None


def admin_app_installer_candidates():
    release_dir = Path(settings.BASE_DIR) / "schooldom-admin-app" / "release"
    media_dir = Path(settings.MEDIA_ROOT) / "app" / "admin"
    candidates = [
        media_dir / ADMIN_APP_FILENAME,
        media_dir / "SchoolDom-Admin-Setup.exe",
    ]
    if release_dir.exists():
        candidates.extend(sorted(release_dir.glob("SchoolDom-Admin-*-Setup.exe"), reverse=True))
        candidates.extend(sorted(release_dir.glob("*.exe"), reverse=True))
    return candidates


def admin_app_installer_path():
    for candidate in admin_app_installer_candidates():
        if candidate.exists() and candidate.is_file() and candidate.stat().st_size >= MIN_DESKTOP_INSTALLER_SIZE:
            return candidate
    return None


def offline_cbt_client_version():
    package_path = Path(settings.BASE_DIR) / "schooldom-cbt-client" / "package.json"
    try:
        import json

        return json.loads(package_path.read_text(encoding="utf-8")).get("version") or "0.1.0"
    except (OSError, ValueError, TypeError):
        return "0.1.0"


def admin_app_version():
    package_path = Path(settings.BASE_DIR) / "schooldom-admin-app" / "package.json"
    try:
        import json

        return json.loads(package_path.read_text(encoding="utf-8")).get("version") or "0.1.0"
    except (OSError, ValueError, TypeError):
        return "0.1.0"


def request_origin(request):
    raw = request.headers.get("Origin") or request.headers.get("Referer") or ""
    parsed = urlsplit(raw)
    if parsed.scheme and parsed.netloc:
        return f"{parsed.scheme}://{parsed.netloc}".rstrip("/")
    return ""


def frontend_server_url(request):
    configured = str(getattr(settings, "FRONTEND_BASE_URL", "") or "").rstrip("/")
    if configured:
        return configured

    origin = request_origin(request)
    if origin:
        return origin

    scheme = request.scheme
    host = request.get_host()
    split = urlsplit(f"{scheme}://{host}")
    frontend_port = str(getattr(settings, "FRONTEND_DEV_PORT", "5173") or "5173")
    hostname = split.hostname or "localhost"
    port = split.port

    django_dev_ports = {"8000", "8001"}
    if port and str(port) != frontend_port and (getattr(settings, "DEBUG", False) or str(port) in django_dev_ports):
        return f"{scheme}://{hostname}:{frontend_port}"
    return f"{scheme}://{host}".rstrip("/")


def build_student_cbt_app(server_url):
    app_path = student_cbt_app_path(server_url)
    if app_path.exists():
        return app_path

    icon_path = frontend_dir() / "electron" / "icon.ico"
    if not icon_path.exists():
        raise Http404("Student CBT desktop app icon is missing.")

    app_path.parent.mkdir(parents=True, exist_ok=True)
    source_path = app_path.parent / "SchoolDomStudentCbtLauncher.cs"
    cbt_url = f"{server_url}/student-cbt"
    source_path.write_text(
        f'''
using System;
using System.Diagnostics;
using System.IO;
using System.Windows.Forms;

namespace SchoolDomStudentCbt
{{
    static class Program
    {{
        private const string CbtUrl = @"{cbt_url}";

        [STAThread]
        static void Main()
        {{
            Application.EnableVisualStyles();
            Application.SetCompatibleTextRenderingDefault(false);
            string browser = FindBrowser();
            if (String.IsNullOrEmpty(browser))
            {{
                MessageBox.Show(
                    "Microsoft Edge or Google Chrome is required to run SchoolDom Student CBT.",
                    "SchoolDom Student CBT",
                    MessageBoxButtons.OK,
                    MessageBoxIcon.Error
                );
                return;
            }}

            ProcessStartInfo info = new ProcessStartInfo();
            info.FileName = browser;
            info.Arguments = "--app=\\"" + CbtUrl + "\\" --start-fullscreen --disable-pinch --overscroll-history-navigation=0";
            info.UseShellExecute = false;
            Process.Start(info);
        }}

        private static string FindBrowser()
        {{
            string[] candidates = new string[]
            {{
                Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.ProgramFilesX86), "Microsoft", "Edge", "Application", "msedge.exe"),
                Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.ProgramFiles), "Microsoft", "Edge", "Application", "msedge.exe"),
                Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData), "Microsoft", "Edge", "Application", "msedge.exe"),
                Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.ProgramFiles), "Google", "Chrome", "Application", "chrome.exe"),
                Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.ProgramFilesX86), "Google", "Chrome", "Application", "chrome.exe"),
                Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData), "Google", "Chrome", "Application", "chrome.exe")
            }};

            foreach (string candidate in candidates)
            {{
                if (File.Exists(candidate))
                {{
                    return candidate;
                }}
            }}
            return "";
        }}
    }}
}}
'''.strip(),
        encoding="utf-8",
    )

    csc_path = Path("C:/Windows/Microsoft.NET/Framework64/v4.0.30319/csc.exe")
    if not csc_path.exists():
        csc_path = Path("C:/Windows/Microsoft.NET/Framework/v4.0.30319/csc.exe")
    if not csc_path.exists():
        raise Http404("Windows C# compiler is not available on this admin computer.")

    command = [
        str(csc_path),
        "/nologo",
        "/target:winexe",
        f"/win32icon:{icon_path}",
        f"/out:{app_path}",
        "/reference:System.Windows.Forms.dll",
        str(source_path),
    ]
    try:
        subprocess.run(command, check=True, timeout=60)
    except subprocess.TimeoutExpired as exc:
        raise Http404("Student CBT app build timed out. Try the download again.") from exc
    except (OSError, subprocess.CalledProcessError) as exc:
        raise Http404("Student CBT app build failed on this admin computer.") from exc

    if not app_path.exists():
        raise Http404("Student CBT app build finished but the executable was not created.")
    return app_path


class AppDownloadView(TemplateView):
    template_name = "app/download.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        apk_path = app_apk_path()
        context["apk_available"] = apk_path.exists()
        context["apk_size_mb"] = round(apk_path.stat().st_size / (1024 * 1024), 1) if apk_path.exists() else None
        context["apk_download_url"] = reverse("app_apk_download")
        context["student_cbt_download_url"] = reverse("student_cbt_app_download")
        context["admin_app_download_url"] = reverse("admin_app_download")
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


def download_student_cbt_app(request):
    app_path = offline_cbt_installer_path()
    if not app_path:
        raise Http404(
            "SchoolDom CBT Client installer is not available yet. Build it with `cd schooldom-cbt-client && npm run dist`, "
            "then copy the setup exe to media/app/student-cbt/SchoolDomCBT.exe."
        )
    response = FileResponse(
        app_path.open("rb"),
        as_attachment=True,
        filename=STUDENT_CBT_FILENAME,
        content_type="application/vnd.microsoft.portable-executable",
    )
    response["Cache-Control"] = "no-store"
    response["Content-Length"] = app_path.stat().st_size
    response["X-Accel-Buffering"] = "no"
    return response


def download_admin_app(request):
    app_path = admin_app_installer_path()
    if not app_path:
        raise Http404(
            "SchoolDom Admin installer is not available yet. Build it with `cd schooldom-admin-app && npm run dist`, "
            "then copy the setup exe to media/app/admin/SchoolDomAdmin.exe."
        )
    response = FileResponse(
        app_path.open("rb"),
        as_attachment=True,
        filename=ADMIN_APP_FILENAME,
        content_type="application/vnd.microsoft.portable-executable",
    )
    response["Cache-Control"] = "no-store"
    response["Content-Length"] = app_path.stat().st_size
    response["X-Accel-Buffering"] = "no"
    return response


def admin_app_download_version(request):
    app_path = admin_app_installer_path()
    return JsonResponse(
        {
            "version": admin_app_version(),
            "available": bool(app_path),
            "download_url": request.build_absolute_uri(reverse("admin_app_download")),
            "filename": ADMIN_APP_FILENAME,
            "size_bytes": app_path.stat().st_size if app_path else 0,
        }
    )


def student_cbt_app_version(request):
    app_path = offline_cbt_installer_path()
    download_url = request.build_absolute_uri(reverse("student_cbt_app_download"))
    payload = {
        "version": offline_cbt_client_version(),
        "available": bool(app_path),
        "download_url": download_url,
        "filename": STUDENT_CBT_FILENAME,
        "size_bytes": app_path.stat().st_size if app_path else 0,
    }
    return JsonResponse(payload)


def redirect_student_cbt(request):
    return redirect(f"{frontend_server_url(request)}/student-cbt")
