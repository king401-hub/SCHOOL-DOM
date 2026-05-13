import ipaddress

from django.conf import settings
from django.http import HttpResponseForbidden


class IPWhitelistMiddleware:
    """Restrict requests to configured IP addresses or CIDR networks."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if not getattr(settings, "IP_WHITELIST_ENABLED", False):
            return self.get_response(request)

        allowed_ranges = getattr(settings, "IP_WHITELIST_RANGES", [])
        if not allowed_ranges:
            return HttpResponseForbidden("IP whitelist is enabled, but no allowed IPs are configured.")

        client_ip = self._client_ip(request)
        if client_ip and self._is_allowed(client_ip, allowed_ranges):
            return self.get_response(request)

        return HttpResponseForbidden("Access denied: your IP address is not whitelisted.")

    def _client_ip(self, request):
        trusted_proxy_header = getattr(settings, "IP_WHITELIST_USE_X_FORWARDED_FOR", True)
        if trusted_proxy_header:
            forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR", "")
            if forwarded_for:
                return forwarded_for.split(",")[0].strip()
        return request.META.get("REMOTE_ADDR", "")

    def _is_allowed(self, client_ip, allowed_ranges):
        try:
            ip = ipaddress.ip_address(client_ip)
        except ValueError:
            return False

        for allowed in allowed_ranges:
            try:
                if ip in ipaddress.ip_network(allowed, strict=False):
                    return True
            except ValueError:
                continue
        return False
