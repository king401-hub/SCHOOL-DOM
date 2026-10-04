from django.urls import path
from . import views

urlpatterns = [
    path("chat/", views.secretary_chat, name="secretary-chat"),
    path("status/", views.secretary_status, name="secretary-status"),
    path("briefing/", views.secretary_briefing, name="secretary-briefing"),
]
