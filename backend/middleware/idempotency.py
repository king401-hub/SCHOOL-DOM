import hashlib
import json
import time

from django.core.cache import cache
from django.http import JsonResponse

IDEMPOTENCY_TTL = 10  # seconds — window in which identical requests are deduplicated
SKIP_METHODS = {"GET", "HEAD", "OPTIONS"}
SKIP_PREFIXES = ("/admin/", "/static/", "/media/")


def _fingerprint(request):
    user_id = request.user.pk if request.user and request.user.is_authenticated else "anon"
    body = request.body[:4096]  # cap at 4 KB to avoid hashing huge file uploads
    raw = f"{user_id}:{request.method}:{request.path}:{body!r}"
    return "idem:" + hashlib.sha256(raw.encode()).hexdigest()


class IdempotencyMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.method in SKIP_METHODS:
            return self.get_response(request)
        if any(request.path.startswith(p) for p in SKIP_PREFIXES):
            return self.get_response(request)

        key = _fingerprint(request)
        cached = cache.get(key)

        if cached is not None:
            return JsonResponse(cached["data"], status=cached["status"], safe=False)

        response = self.get_response(request)

        # Only cache successful mutation responses with JSON bodies
        if 200 <= response.status_code < 300:
            try:
                data = json.loads(response.content)
                cache.set(key, {"data": data, "status": response.status_code}, IDEMPOTENCY_TTL)
            except (ValueError, AttributeError):
                pass

        return response
