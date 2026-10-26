"""Tests for the dual-school kiosk pairing/switching feature."""
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import TestCase
from rest_framework.test import APIClient

from core.tenant import SchoolGroup, SchoolTenant

from .models import Device, ProvisioningKey

User = get_user_model()


class DevicePairingTestCase(TestCase):
    def setUp(self):
        # IdempotencyMiddleware replays a byte-identical POST from an earlier
        # test (same ids in every fresh DB) as a JsonResponse with no .data.
        cache.clear()
        owner = User.objects.create_user(email="owner@test.com", password="testpass123", role="school_superadmin")
        self.group = SchoolGroup.objects.create(name="Test Group", owner=owner)
        self.other_group = SchoolGroup.objects.create(name="Other Group", owner=owner)

        self.school_a = SchoolTenant.objects.create(name="School A", schema_name="school_a", school_group=self.group)
        self.school_b = SchoolTenant.objects.create(name="School B", schema_name="school_b", school_group=self.group)
        self.school_c = SchoolTenant.objects.create(name="School C", schema_name="school_c", school_group=self.other_group)
        self.school_standalone = SchoolTenant.objects.create(name="Standalone School", schema_name="standalone_school")

        self.scanner_user = User.objects.create_user(
            email="scanner@test.com", password="testpass123", role="staff", tenant=self.school_a,
        )
        self.device = Device.objects.create(
            tenant=self.school_a,
            scanner_user=self.scanner_user,
            authorized=True,
            status="active",
            auth_token="devicetoken123",
        )
        self.client = APIClient()

    def test_switch_to_paired_school_swaps_fields(self):
        self.device.paired_tenant = self.school_b
        self.device.save(update_fields=["paired_tenant"])

        resp = self.client.post(
            "/api/device-fleet/device/switch-active-school/",
            {"auth_token": "devicetoken123", "school_id": str(self.school_b.id)},
            format="json",
        )
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.data["success"])
        self.assertEqual(resp.data["school_id"], str(self.school_b.id))
        self.assertEqual(resp.data["paired_school_id"], str(self.school_a.id))

        self.device.refresh_from_db()
        self.assertEqual(self.device.tenant_id, self.school_b.id)
        self.assertEqual(self.device.paired_tenant_id, self.school_a.id)

        self.scanner_user.refresh_from_db()
        self.assertEqual(self.scanner_user.tenant_id, self.school_b.id)

    def test_switch_to_already_active_school_is_a_noop(self):
        self.device.paired_tenant = self.school_b
        self.device.save(update_fields=["paired_tenant"])

        resp = self.client.post(
            "/api/device-fleet/device/switch-active-school/",
            {"auth_token": "devicetoken123", "school_id": str(self.school_a.id)},
            format="json",
        )
        self.assertEqual(resp.status_code, 200)
        self.device.refresh_from_db()
        self.assertEqual(self.device.tenant_id, self.school_a.id)
        self.assertEqual(self.device.paired_tenant_id, self.school_b.id)

    def test_switch_to_unpaired_school_is_rejected(self):
        resp = self.client.post(
            "/api/device-fleet/device/switch-active-school/",
            {"auth_token": "devicetoken123", "school_id": str(self.school_c.id)},
            format="json",
        )
        self.assertEqual(resp.status_code, 400)
        self.device.refresh_from_db()
        self.assertEqual(self.device.tenant_id, self.school_a.id)

    def test_switch_with_bad_token_is_unauthorized(self):
        resp = self.client.post(
            "/api/device-fleet/device/switch-active-school/",
            {"auth_token": "wrong-token", "school_id": str(self.school_a.id)},
            format="json",
        )
        self.assertEqual(resp.status_code, 401)

    def test_suspended_device_cannot_switch(self):
        self.device.paired_tenant = self.school_b
        self.device.status = "suspended"
        self.device.save(update_fields=["paired_tenant", "status"])

        resp = self.client.post(
            "/api/device-fleet/device/switch-active-school/",
            {"auth_token": "devicetoken123", "school_id": str(self.school_b.id)},
            format="json",
        )
        self.assertEqual(resp.status_code, 403)

    def test_heartbeat_reports_paired_school_when_set(self):
        self.device.paired_tenant = self.school_b
        self.device.save(update_fields=["paired_tenant"])

        resp = self.client.post(
            "/api/device-fleet/device/heartbeat/",
            {"auth_token": "devicetoken123", "app_version": "1.1.0"},
            format="json",
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data["paired_school_id"], str(self.school_b.id))
        self.assertEqual(resp.data["paired_school_name"], "School B")

    def test_heartbeat_omits_paired_school_when_unset(self):
        resp = self.client.post(
            "/api/device-fleet/device/heartbeat/",
            {"auth_token": "devicetoken123", "app_version": "1.1.0"},
            format="json",
        )
        self.assertEqual(resp.status_code, 200)
        self.assertNotIn("paired_school_id", resp.data)

    def test_assign_school_clears_stale_pairing(self):
        self.device.paired_tenant = self.school_b
        self.device.save(update_fields=["paired_tenant"])

        self.admin = User.objects.create_user(
            email="admin@test.com", password="testpass123", role="super_admin", is_superuser=True,
        )
        self.client.force_authenticate(user=self.admin)
        resp = self.client.post(f"/api/device-fleet/devices/{self.device.pk}/assign-school/", {"school_id": str(self.school_standalone.id)})
        self.assertEqual(resp.status_code, 200)

        self.device.refresh_from_db()
        self.assertEqual(self.device.tenant_id, self.school_standalone.id)
        self.assertIsNone(self.device.paired_tenant_id)


class DeviceProvisioningIdGenerationTests(TestCase):
    """Regression test for a live production incident (2026-10-26): with
    ATOMIC_REQUESTS=True, a device_fleet_device row never actually commits
    when a LATER statement in the same request raises - so the Device table
    alone understates which device_ids have truly been issued. A device's
    scanner_user (created from that same device_id) can still exist from an
    earlier device that was later deleted (on_delete=SET_NULL only clears
    the FK, it never deletes the User). _next_device_id() kept recomputing
    that same stale number forever, and every single provisioning attempt
    failed on the same users_user_email_key UniqueViolation (confirmed live:
    device-scn-025@scanner.schooldom.internal)."""

    def setUp(self):
        cache.clear()
        self.key = ProvisioningKey.objects.create()

    def test_next_device_id_skips_a_number_whose_scanner_email_is_already_taken(self):
        # No Device row for SCN-001 exists (its creation never committed, or
        # it was later deleted) - only the orphaned scanner_user survives.
        User.objects.create_user(email="device-scn-001@scanner.schooldom.internal", password=None, role="staff")
        self.assertEqual(Device._next_device_id(), "SCN-002")

    def test_provisioning_still_succeeds_when_the_next_ids_email_is_stale(self):
        User.objects.create_user(email="device-scn-001@scanner.schooldom.internal", password=None, role="staff")
        client = APIClient()
        resp = client.post(
            "/api/device-fleet/device/provision/",
            {"provisioning_key": self.key.key, "device_name": "Test Scanner"},
            format="json",
        )
        self.assertEqual(resp.status_code, 201)
        self.assertEqual(resp.data["data"]["device_id"], "SCN-002")
