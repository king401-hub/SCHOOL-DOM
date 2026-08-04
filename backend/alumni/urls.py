from django.urls import path

from alumni import views

urlpatterns = [
    path("overview/", views.alumni_overview, name="alumni_overview"),
    path("students/", views.alumni_students, name="alumni_students"),
    path("students/<str:student_key>/", views.alumni_student_detail, name="alumni_student_detail"),
]
