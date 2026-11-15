from django.urls import path

from . import views

urlpatterns = [
    # Device-facing (vendor-fixed paths, see the "Cloud Attendance and
    # Access Control (HTTP)" protocol doc - the device calls these exact
    # paths, they are not ours to rename).
    path('device/updateStateDevice', views.device_update_state, name='facegate-device-update-state'),
    path('devicePass/selectPassInfo', views.device_select_pass_info, name='facegate-select-pass-info'),
    path('devicePass/selectDeleteInfo', views.device_select_delete_info, name='facegate-select-delete-info'),
    path('devicePass/setPassResult', views.device_set_pass_result, name='facegate-set-pass-result'),
    path('note/insertNoteFace', views.note_insert_note_face, name='facegate-insert-note-face'),
    path('device/selectRestart', views.device_select_restart, name='facegate-select-restart'),

    # Admin-facing (SchoolDom's own convention, authenticated).
    path('admin/devices', views.admin_list_devices, name='facegate-admin-list-devices'),
    path('admin/devices/register', views.admin_register_device, name='facegate-admin-register-device'),
    path('admin/devices/<uuid:device_pk>/enroll', views.admin_bulk_enroll, name='facegate-admin-bulk-enroll'),
    path('admin/devices/<uuid:device_pk>/unenroll', views.admin_bulk_unenroll, name='facegate-admin-bulk-unenroll'),
    path('admin/devices/<uuid:device_pk>/opendoor', views.admin_queue_opendoor, name='facegate-admin-opendoor'),
    path('admin/devices/<uuid:device_pk>/restart', views.admin_queue_restart, name='facegate-admin-restart'),
]
