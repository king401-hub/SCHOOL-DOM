from django.urls import path

from ai_chat import views

urlpatterns = [
    path("chat/", views.chat, name="ai_chat"),
    path("status/", views.status_check, name="ai_chat_status"),
]
