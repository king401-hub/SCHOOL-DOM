from django.urls import path

from . import views

urlpatterns = [
    # Device-facing - one URL, commands multiplexed by the JSON body's
    # `cmd`/`ret` field (the "cloud solution" protocol's actual wire shape -
    # see views.device_api).
    path('device_api/', views.device_api, name='facegate-device-api'),

    # Admin-facing (SchoolDom's own convention, authenticated).
    path('admin/devices', views.admin_list_devices, name='facegate-admin-list-devices'),
    path('admin/devices/register', views.admin_register_device, name='facegate-admin-register-device'),
    path('admin/devices/<uuid:device_pk>/enroll', views.admin_bulk_enroll, name='facegate-admin-bulk-enroll'),
    path('admin/devices/<uuid:device_pk>/unenroll', views.admin_bulk_unenroll, name='facegate-admin-bulk-unenroll'),
    path('admin/devices/<uuid:device_pk>/opendoor', views.admin_queue_opendoor, name='facegate-admin-opendoor'),
    path('admin/devices/<uuid:device_pk>/restart', views.admin_queue_restart, name='facegate-admin-restart'),
]
