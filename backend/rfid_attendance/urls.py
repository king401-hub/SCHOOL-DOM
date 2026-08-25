from django.urls import path

from . import views

app_name = 'rfid_attendance'

urlpatterns = [
    path('card-assignments/', views.card_assignments_pull, name='card_assignments_pull'),
    path('card-assignments/assign/', views.card_assignment_create, name='card_assignment_create'),
    path('card-assignments/revoke/', views.card_assignment_revoke, name='card_assignment_revoke'),
    path('attendance/scan/', views.attendance_scan_create, name='attendance_scan_create'),
    path('classes/', views.classes_lookup, name='classes_lookup'),
    path('students/', views.students_lookup, name='students_lookup'),
]
