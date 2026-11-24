import json
import logging

from django.conf import settings
from django.core.mail import send_mail
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from rest_framework.generics import ListAPIView, RetrieveAPIView
from rest_framework.response import Response
from rest_framework.views import APIView

from .forwarding import ForwardError, forward_received_email, signature_valid
from .models import InboundMessage
from .permissions import IsSupportMailStaff
from .serializers import (
    InboundMessageDetailSerializer,
    InboundMessageListSerializer,
    ReplySerializer,
)


logger = logging.getLogger(__name__)


@csrf_exempt
@require_POST
def resend_inbound_webhook(request):
    """Resend `email.received` webhook: forward the message to MAIL_FORWARD_TO.

    Authenticated by Resend's Svix signature, not a login. 5xx on a failure so
    Resend retries; 2xx for anything that should not be retried.
    """
    if not signature_valid(request.body, request.headers):
        return HttpResponse(status=403)
    try:
        event = json.loads(request.body)
    except ValueError:
        return HttpResponse(status=400)
    if event.get("type") != "email.received":
        return JsonResponse({"status": "ignored"})
    email_id = (event.get("data") or {}).get("email_id")
    if not email_id:
        return JsonResponse({"status": "no-email-id"})
    try:
        outcome = forward_received_email(email_id)
    except ForwardError as exc:
        logger.error("Resend forward failed: %s", exc)
        return JsonResponse({"status": "error"}, status=502)
    except Exception:
        logger.exception("Resend forward crashed for %s", email_id)
        return JsonResponse({"status": "error"}, status=500)
    return JsonResponse({"status": outcome})


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
