from django.urls import path

from . import views

app_name = "licensing"

urlpatterns = [
    path("status/", views.license_status, name="license_status"),
    path("activate/", views.license_activate, name="license_activate"),
    path("purchase/", views.license_purchase, name="license_purchase"),
    path("purchase/verify/<str:reference>/", views.license_purchase_verify, name="license_purchase_verify"),
]
