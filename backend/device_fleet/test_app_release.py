"""Publishing a kiosk build: AppRelease rows are created from the Control Panel."""
import tempfile

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse

from .models import AppRelease, DeviceAuditLog

User = get_user_model()


class AppReleaseStrTests(TestCase):
    def test_a_release_is_named_by_its_app_and_version(self):
        # Regression: AppRelease carried a second __str__ that belonged to
        # DeviceAuditLog (self.actor / self.action), so str(release) raised
        # AttributeError - and the admin str()s a row right after saving it, so
        # uploading a release ended in "Server Error (500)".
        self.assertEqual(str(AppRelease(version_code=8, version_name="1.4.3")), "Scanner Kiosk 1.4.3 (8)")

    def test_an_audit_log_entry_is_named_by_its_action_and_actor(self):
        self.assertEqual(str(DeviceAuditLog(action="suspend")), "suspend - System")

        staff = User.objects.create_user(
            email="ops@test.com", password="testpass123", first_name="Ada", last_name="Ops", role="staff",
        )
        self.assertEqual(str(DeviceAuditLog(action="revoke", actor=staff)), "revoke - Ops Ada")  # surname first


class AppReleaseControlPanelTests(TestCase):
    def test_a_release_can_be_uploaded_through_the_control_panel(self):
        admin = User.objects.create_superuser(
            email="root@test.com", password="testpass123", first_name="Root", last_name="User",
        )
        self.client.force_login(admin)
        apk = SimpleUploadedFile(
            "kiosk.apk", b"PK\x03\x04" + b"0" * 4096, content_type="application/vnd.android.package-archive",
        )

        with tempfile.TemporaryDirectory() as media, override_settings(MEDIA_ROOT=media):
            response = self.client.post(
                reverse("control_panel:device_fleet_apprelease_add"),
                {
                    "app": AppRelease.APP_SCANNER_KIOSK,
                    "version_code": 8,
                    "version_name": "1.4.3",
                    "apk_file": apk,
                    "release_notes": "What's new",
                    "is_active": "on",
                },
            )

            self.assertEqual(response.status_code, 302, "saving a release should redirect to the list")
            release = AppRelease.objects.get()
            self.assertEqual((release.version_code, release.version_name, release.is_active), (8, "1.4.3", True))
            self.assertTrue(release.apk_file.name.startswith("app_releases/"))
            self.assertTrue(release.apk_file.name.endswith(".apk"))
            self.assertEqual(release.apk_file.size, 4 + 4096)
