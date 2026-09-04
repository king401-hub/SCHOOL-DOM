from django.urls import path

from . import views

app_name = 'rfid_attendance'

urlpatterns = [
    path('card-assignments/', views.card_assignments_pull, name='card_assignments_pull'),
    path('card-assignments/assign/', views.card_assignment_create, name='card_assignment_create'),
    path('card-assignments/revoke/', views.card_assignment_revoke, name='card_assignment_revoke'),
    path('attendance/scan/', views.attendance_scan_create, name='attendance_scan_create'),
    path('attendance/history/', views.attendance_history, name='attendance_history'),
    path('classes/', views.classes_lookup, name='classes_lookup'),
    path('people/', views.people_lookup, name='people_lookup'),
    path('gate-settings/', views.gate_settings_get, name='gate_settings_get'),
    path('gate-settings/update/', views.gate_settings_update, name='gate_settings_update'),
    path('gate-settings/verify-pin/', views.gate_pin_verify, name='gate_pin_verify'),
    path('gate-settings/set-pin/', views.gate_pin_set, name='gate_pin_set'),
    path('fee-reminder/send/', views.fee_reminder_send, name='fee_reminder_send'),
]
