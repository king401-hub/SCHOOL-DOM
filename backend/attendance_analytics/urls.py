from django.urls import path

from . import views

app_name = 'attendance_analytics'

urlpatterns = [
    path('overview/', views.overview, name='overview'),
    path('daily/', views.daily_summary, name='daily_summary'),
    path('daily/register/', views.daily_register, name='daily_register'),
    path('staff/<str:person_id>/', views.staff_profile, name='staff_profile'),
    path('staff/<str:person_id>/history/', views.staff_history, name='staff_history'),
    path('students/<uuid:student_id>/', views.student_profile, name='student_profile'),
    path('students/<uuid:student_id>/history/', views.student_history, name='student_history'),
    path('filters/', views.filters_lookup, name='filters_lookup'),
]
