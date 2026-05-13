from django.urls import path

from . import views


urlpatterns = [
    path("overview/", views.hr_snapshot, name="hr_snapshot"),
    path("activity/", views.activity_snapshot, name="hr_activity"),
    path("me/", views.staff_self_service_snapshot, name="hr_staff_self_service"),
    path("staff/download/", views.download_staff_csv, name="hr_download_staff"),
    path("staff/create/", views.create_staff, name="hr_create_staff"),
    path("staff/<uuid:staff_id>/qr/download/", views.download_staff_qr, name="hr_staff_qr_download"),
    path("staff/<uuid:staff_id>/", views.staff_detail, name="hr_staff_detail"),
    path("attendance/mark/", views.mark_attendance, name="hr_mark_attendance"),
    path("attendance/scan/<str:token>/", views.scan_staff_attendance, name="hr_scan_staff_attendance"),
    path("leave/create/", views.create_leave_request, name="hr_create_leave"),
    path("leave/<uuid:leave_id>/review/", views.review_leave_request, name="hr_review_leave"),
    path("advances/create/", views.create_advance_request, name="hr_create_advance"),
    path("advances/<uuid:advance_id>/review/", views.review_advance_request, name="hr_review_advance"),
    path("payroll/create/", views.create_payroll_record, name="hr_create_payroll"),
]
