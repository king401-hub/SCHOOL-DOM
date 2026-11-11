"""Scanner-kiosk authentication for the device's own work-calls (recording a
scan, reading gate settings, sending a fee reminder) - everything the kiosk
does once provisioned, besides heartbeat/provisioning/switch-school, which
already authenticate off Device.auth_token directly (see
device_fleet.views._device_from_token).

Those work-calls used to go through the device's scanner_user JWT session
instead, reusing SIMPLE_JWT's generic REFRESH_TOKEN_LIFETIME (7 days) - a
setting sized for a human staff login, not an unattended terminal. A missed
renewal (the device offline longer than that, a flaky connection during the
refresh call) silently expired that session while Device.authorized/status
in the Control Panel stayed completely untouched, forcing a needless
"re-enter license key" even though nothing was actually revoked.

This authenticator makes the Control Panel the only source of truth for a
terminal's access: Device.auth_token has no timer of its own and is only
ever invalidated by an admin actually suspending/revoking the device.
"""
from rest_framework.authentication import BaseAuthentication
from rest_framework.exceptions import AuthenticationFailed

from .models import Device


class DeviceTokenAuthentication(BaseAuthentication):
    def authenticate(self, request):
        token = request.headers.get("X-Device-Token", "").strip()
        if not token:
            return None

        device = Device.objects.select_related("scanner_user").filter(auth_token=token).first()
        if device is None:
            raise AuthenticationFailed("Unknown or revoked device token.")
        # Same gate device_heartbeat already reports as "authorized" (see
        # device_fleet.views.device_heartbeat) - deliberately not blocking on
        # status="expired"/"maintenance", only an explicit suspend/revoke.
        if not (device.authorized and device.status not in ("suspended", "revoked")) or device.scanner_user_id is None:
            raise AuthenticationFailed("This terminal has been suspended or revoked.")

        return (device.scanner_user, device)
