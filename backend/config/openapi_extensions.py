"""OpenAPI security scheme registrations for this project's custom DRF
authentication classes.

drf_spectacular only documents a security scheme for a class it has an
OpenApiAuthenticationExtension registered for; without these, every
endpoint authenticated by either class below - which, via
REST_FRAMEWORK['DEFAULT_AUTHENTICATION_CLASSES'] in config/settings.py, is
effectively every endpoint in the project - showed up in the generated
schema with no security requirement listed at all, even though the real
API enforces one.

Imported from core.apps.CoreConfig.ready() (see core/apps.py): extension
classes self-register on import via drf_spectacular's own metaclass, so
this module just needs to be imported once before schema generation runs.
Not imported directly from settings.py, since DeviceTokenAuthentication
imports its model at module level - safe only once Django's app registry
is fully loaded, which AppConfig.ready() guarantees and settings.py does
not.
"""
from drf_spectacular.extensions import OpenApiAuthenticationExtension


class BranchAwareJWTAuthenticationScheme(OpenApiAuthenticationExtension):
    target_class = "users.authentication.BranchAwareJWTAuthentication"
    name = "jwtAuth"

    def get_security_definition(self, auto_schema):
        return {
            "type": "http",
            "scheme": "bearer",
            "bearerFormat": "JWT",
            "description": (
                "Access token from /api/token/ or /api/auth/login/ "
                '("Authorization: Bearer <token>"). Branch-aware: a token '
                "carrying an active_tenant claim scopes the request to that "
                "branch instead of the user's home tenant (see "
                "users.authentication.BranchAwareJWTAuthentication)."
            ),
        }


class DeviceTokenAuthenticationScheme(OpenApiAuthenticationExtension):
    target_class = "device_fleet.authentication.DeviceTokenAuthentication"
    name = "deviceTokenAuth"

    def get_security_definition(self, auto_schema):
        return {
            "type": "apiKey",
            "in": "header",
            "name": "X-Device-Token",
            "description": (
                "Permanent, non-expiring per-device token issued at kiosk/"
                "scanner provisioning (see device_fleet.views.device_provision "
                "and device_fleet.views.device_heartbeat). Used for a device's "
                "own work-calls instead of a human JWT session - see "
                "device_fleet.authentication.DeviceTokenAuthentication."
            ),
        }
