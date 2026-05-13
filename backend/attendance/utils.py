"""Utilities for teacher attendance QR links."""
import socket
from urllib.parse import urlsplit, urlunsplit

from django.conf import settings


LOCAL_HOSTNAMES = {"localhost", "127.0.0.1", "0.0.0.0", "::1"}


def get_network_ip():
    """Best-effort LAN IP lookup for QR codes scanned from other devices."""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as probe:
            probe.connect(("8.8.8.8", 80))
            ip_address = probe.getsockname()[0]
            if ip_address and not ip_address.startswith("127."):
                return ip_address
    except OSError:
        pass

    try:
        for ip_address in socket.gethostbyname_ex(socket.gethostname())[2]:
            if ip_address and not ip_address.startswith("127."):
                return ip_address
    except OSError:
        pass

    return ""


def networkize_local_url(base_url):
    """Replace localhost URLs with a LAN host so phones can open QR links."""
    parsed = urlsplit(base_url.strip().rstrip("/"))
    if parsed.hostname not in LOCAL_HOSTNAMES:
        return base_url.strip().rstrip("/")

    network_ip = get_network_ip()
    if not network_ip:
        return base_url.strip().rstrip("/")

    port = parsed.port
    if port in (None, 8000):
        dev_port = getattr(settings, "FRONTEND_DEV_PORT", "5173")
        port = int(dev_port) if str(dev_port).isdigit() else None

    netloc = f"{network_ip}:{port}" if port else network_ip
    return urlunsplit((parsed.scheme or "http", netloc, parsed.path, parsed.query, parsed.fragment)).rstrip("/")


def get_frontend_base_url(request=None):
    """Return the teacher-facing frontend origin for attendance scan links."""
    ngrok_url = getattr(settings, "NGROK_PUBLIC_URL", "").strip().rstrip("/")
    if ngrok_url:
        return ngrok_url

    configured_url = getattr(settings, "FRONTEND_BASE_URL", "").strip().rstrip("/")
    if configured_url:
        return networkize_local_url(configured_url)

    if request:
        origin = request.headers.get("Origin", "").strip().rstrip("/")
        if origin:
            return networkize_local_url(origin)

        return networkize_local_url(request.build_absolute_uri("/").rstrip("/"))

    return ""


def build_teacher_scan_url(request, qr_code_obj):
    base_url = get_frontend_base_url(request)
    if base_url:
        return f"{base_url}/attendance/scan/{qr_code_obj.token}"
    return f"/attendance/scan/{qr_code_obj.token}"
