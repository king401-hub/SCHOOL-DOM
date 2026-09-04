from django.urls import path

from . import views

app_name = 'device_fleet'

urlpatterns = [
    path('schools/', views.schools_list, name='schools_list'),
    path('devices/', views.devices_list, name='devices_list'),
    path('devices/<uuid:device_pk>/', views.device_detail, name='device_detail'),
    path('devices/<uuid:device_pk>/assign-school/', views.assign_school, name='assign_school'),
    path('devices/<uuid:device_pk>/unassign-school/', views.unassign_school, name='unassign_school'),
    path('devices/<uuid:device_pk>/suspend/', views.suspend_device, name='suspend_device'),
    path('devices/<uuid:device_pk>/reactivate/', views.reactivate_device, name='reactivate_device'),
    path('devices/<uuid:device_pk>/revoke/', views.revoke_device, name='revoke_device'),
    path('devices/<uuid:device_pk>/delete/', views.delete_device, name='delete_device'),
    path('provisioning-keys/', views.generate_provisioning_key, name='generate_provisioning_key'),
    path('audit-logs/', views.audit_logs_list, name='audit_logs_list'),

    # Device-facing (AllowAny + own credential, not a user JWT)
    path('device/provision/', views.device_provision, name='device_provision'),
    path('device/heartbeat/', views.device_heartbeat, name='device_heartbeat'),
]
