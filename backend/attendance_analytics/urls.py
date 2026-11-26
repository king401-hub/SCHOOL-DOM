from django.urls import path

from . import views

app_name = 'attendance_analytics'

urlpatterns = [
    path('overview/', views.overview, name='overview'),
    path('dashboard/', views.dashboard_overview, name='dashboard_overview'),
    path('daily/', views.daily_summary, name='daily_summary'),
    path('daily/register/', views.daily_register, name='daily_register'),
    path('staff/<str:person_id>/', views.staff_profile, name='staff_profile'),
    path('staff/<str:person_id>/history/', views.staff_history, name='staff_history'),
    path('students/<uuid:student_id>/', views.student_profile, name='student_profile'),
    path('students/<uuid:student_id>/history/', views.student_history, name='student_history'),
    path('filters/', views.filters_lookup, name='filters_lookup'),
    path('term/', views.term_overview, name='term_overview'),
    path('term/trends/', views.term_trends, name='term_trends'),
    path('term/rankings/', views.term_rankings, name='term_rankings'),
    path('class-department/', views.class_department, name='class_department'),
    path('correct/', views.correct_attendance, name='correct_attendance'),
    path('reports/daily.pdf', views.daily_report_pdf, name='daily_report_pdf'),
    path('reports/daily.csv', views.daily_report_csv, name='daily_report_csv'),
    path('reports/staff/<str:person_id>.pdf', views.staff_report_pdf, name='staff_report_pdf'),
    path('reports/staff/<str:person_id>.csv', views.staff_report_csv, name='staff_report_csv'),
    path('reports/students/<uuid:student_id>.pdf', views.student_report_pdf, name='student_report_pdf'),
    path('reports/students/<uuid:student_id>.csv', views.student_report_csv, name='student_report_csv'),
    path('reports/class-department.pdf', views.class_department_report_pdf, name='class_department_report_pdf'),
    path('reports/class-department.csv', views.class_department_report_csv, name='class_department_report_csv'),
    path('reports/termly.pdf', views.termly_report_pdf, name='termly_report_pdf'),
]
