from django.urls import path

from request_queue import views

urlpatterns = [
    path("", views.request_queue_list, name="request_queue_list"),
    path("<uuid:request_id>/retry/", views.request_queue_retry, name="request_queue_retry"),
    path("<uuid:request_id>/cancel/", views.request_queue_cancel, name="request_queue_cancel"),
]
