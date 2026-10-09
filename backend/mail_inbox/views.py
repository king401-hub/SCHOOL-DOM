from django.conf import settings
from django.core.mail import send_mail
from django.shortcuts import get_object_or_404
from rest_framework.generics import ListAPIView, RetrieveAPIView
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import InboundMessage
from .permissions import IsSupportMailStaff
from .serializers import (
    InboundMessageDetailSerializer,
    InboundMessageListSerializer,
    ReplySerializer,
)


def _from_address_for(account_label):
    for account in settings.MAIL_INBOX_ACCOUNTS:
        if account["label"] == account_label:
            return account["address"]
    return settings.DEFAULT_FROM_EMAIL


class InboundMessageListView(ListAPIView):
    permission_classes = [IsSupportMailStaff]
    serializer_class = InboundMessageListSerializer

    def get_queryset(self):
        qs = InboundMessage.objects.all()
        account = self.request.query_params.get("account")
        if account:
            qs = qs.filter(account_label=account)
        if self.request.query_params.get("unread_only") == "true":
            qs = qs.filter(is_read=False)
        return qs


class InboundMessageDetailView(RetrieveAPIView):
    permission_classes = [IsSupportMailStaff]
    serializer_class = InboundMessageDetailSerializer
    queryset = InboundMessage.objects.all()


class MarkReadView(APIView):
    permission_classes = [IsSupportMailStaff]

    def post(self, request, pk):
        message = get_object_or_404(InboundMessage, pk=pk)
        message.is_read = request.data.get("is_read", True)
        message.save(update_fields=["is_read"])
        return Response({"id": message.id, "is_read": message.is_read})


class ReplyView(APIView):
    permission_classes = [IsSupportMailStaff]

    def post(self, request, pk):
        message = get_object_or_404(InboundMessage, pk=pk)
        serializer = ReplySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        send_mail(
            subject=f"Re: {message.subject}",
            message=serializer.validated_data["body"],
            from_email=_from_address_for(message.account_label),
            recipient_list=[message.from_address],
        )
        return Response({"sent": True})
