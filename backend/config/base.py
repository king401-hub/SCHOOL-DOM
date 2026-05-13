TENANT_MODEL = "core.SchoolTenant"
TENANT_DOMAIN_MODEL = "core.Domain"

# Temporary debug: surface key settings when running the dev server
import sys

if "runserver" in sys.argv:
    def _g(name, default="(undefined)"):
        return globals().get(name, default)

    print("\n" + "=" * 50)
    print("DEBUG SETTINGS:")
    print(f"CSRF_TRUSTED_ORIGINS: {_g('CSRF_TRUSTED_ORIGINS')}")
    print(f"CORS_ALLOWED_ORIGINS: {_g('CORS_ALLOWED_ORIGINS')}")
    print(f"CORS_ALLOW_ALL_ORIGINS: {_g('CORS_ALLOW_ALL_ORIGINS')}")
    print(f"CORS_ALLOW_CREDENTIALS: {_g('CORS_ALLOW_CREDENTIALS')}")
    print("=" * 50 + "\n")
