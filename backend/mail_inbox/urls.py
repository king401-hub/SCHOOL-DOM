from django.urls import path

from .views import InboundMessageDetailView, InboundMessageListView, MarkReadView, ReplyView

urlpatterns = [
    path("messages/", InboundMessageListView.as_view(), name="mail_inbox_list"),
    path("messages/<int:pk>/", InboundMessageDetailView.as_view(), name="mail_inbox_detail"),
    path("messages/<int:pk>/read/", MarkReadView.as_view(), name="mail_inbox_mark_read"),
    path("messages/<int:pk>/reply/", ReplyView.as_view(), name="mail_inbox_reply"),
]
