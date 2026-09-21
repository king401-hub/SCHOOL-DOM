import json

from django.contrib.auth.models import AnonymousUser
from django.core.cache import cache
from django.core.files.uploadedfile import SimpleUploadedFile
from django.http import HttpResponse, JsonResponse
from django.test import RequestFactory, SimpleTestCase, override_settings

from middleware.idempotency import MAX_FINGERPRINT_BODY, IdempotencyMiddleware


class IdempotencyMiddlewareBodyTests(SimpleTestCase):
    def setUp(self):
        cache.clear()
        self.factory = RequestFactory()

    def test_a_large_upload_passes_through_without_being_read_into_memory(self):
        # Regression: fingerprinting called request.body, which loads the whole
        # upload and raises RequestDataTooBig (a bare "Bad Request (400)") when
        # it is over DATA_UPLOAD_MAX_MEMORY_SIZE - an APK could not be uploaded.
        upload = SimpleUploadedFile("release.apk", b"x" * (3 * MAX_FINGERPRINT_BODY))
        request = self.factory.post("/control-panel/device_fleet/apprelease/add/", {"apk_file": upload})
        request.user = AnonymousUser()
        seen = {}

        def view(req):
            seen["file"] = req.FILES["apk_file"]  # the stream must still be intact and parseable
            return HttpResponse("saved")

        with override_settings(DATA_UPLOAD_MAX_MEMORY_SIZE=MAX_FINGERPRINT_BODY):
            response = IdempotencyMiddleware(view)(request)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(seen["file"].name, "release.apk")
        self.assertEqual(seen["file"].size, 3 * MAX_FINGERPRINT_BODY)
        self.assertFalse(hasattr(request, "_body"), "the whole upload was read into memory")

    def test_identical_small_posts_are_still_deduplicated(self):
        calls = []

        def view(req):
            calls.append(1)
            return JsonResponse({"created": True}, status=201)

        def submit():
            request = self.factory.post(
                "/api/things/", data=json.dumps({"name": "same"}), content_type="application/json"
            )
            request.user = AnonymousUser()
            return IdempotencyMiddleware(view)(request)

        first, second = submit(), submit()

        self.assertEqual(len(calls), 1, "the second identical POST should have been replayed from cache")
        self.assertEqual(json.loads(second.content), {"created": True})
        self.assertEqual(second.status_code, first.status_code)
