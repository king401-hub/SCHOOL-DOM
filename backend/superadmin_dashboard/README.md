# SchoolDom Super Admin Dashboard

This app is a standalone Django dashboard that is separate from Django Admin.

## Install

Add the app to `INSTALLED_APPS`:

```python
"superadmin_dashboard",
```

Add the URL route outside Django Admin:

```python
from django.urls import include, path

urlpatterns = [
    path("super-admin/", include("superadmin_dashboard.urls")),
]
```

## Access Control

Only authenticated Super Admin users can access the dashboard. A user is allowed when one of these is true:

- `user.is_superuser` is true.
- `user.role` is `super_admin`, `superadmin`, or `platform_admin`.
- `user.profile.role` is `super_admin`, `superadmin`, or `platform_admin`.
- The user belongs to `Super Admin`, `SuperAdmin`, or `Platform Admin`.

## Model Connections

The dashboard auto-detects common app/model names in `services.py`. If your project uses different names, update `platform_models()` to point to the existing models for:

- Schools
- Subscriptions
- Payments and transactions
- Virtual accounts
- Support tickets
- Announcements
- Audit logs

The pages degrade gracefully when a module is not connected yet.

## Delegated Super Admins

The dashboard can create other Super Admin users from `Users & Roles -> Create Super Admin`.

Created users are:

- Staff users.
- Added to the `Platform Admin` group.
- Added to function-specific groups such as `Super Admin: Schools`, `Super Admin: Billing`, and `Super Admin: Tokens`.

Function groups control which areas the delegated admin can open. Full Django superusers can access every dashboard function.

## School Token Payments

Use `Schools -> Tokens` to edit token payment settings for a school:

- Price per token payment.
- Tokens granted per payment.
- Minimum token balance.
- Whether payment is required.
- Whether the token setting is active.

These settings are stored in `SchoolTokenPaymentSetting` and keyed by the school model plus school primary key, so the dashboard can work with different existing School model implementations.
