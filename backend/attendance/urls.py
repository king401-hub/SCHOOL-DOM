"""URL configuration for attendance app."""
from django.urls import path
from . import views

app_name = 'attendance'

urlpatterns = [
    # QR Code Management (Admin)
    path('qr-code/generate/', views.generate_qr_code, name='generate_qr_code'),
    path('qr-code/get/', views.get_qr_code, name='get_qr_code'),
    path('qr-code/download/', views.download_qr_code, name='download_qr_code'),
    
    # Staff Attendance Marking
    path('scan/<str:token>/', views.scan_qr_code, name='scan_qr_code'),
    path('check-status/', views.check_attendance_status, name='check_attendance_status'),
    path('clock-out/', views.clock_out, name='clock_out'),
    
    # Admin Dashboard
    path('today/', views.today_attendance_list, name='today_attendance_list'),
    path('by-date/<str:date_str>/', views.attendance_by_date, name='attendance_by_date'),
    path('teacher/<str:teacher_id>/', views.teacher_attendance_history, name='teacher_attendance_history'),
    path('summary/', views.attendance_summary, name='attendance_summary'),
]
