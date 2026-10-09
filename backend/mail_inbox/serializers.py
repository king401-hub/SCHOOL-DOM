from rest_framework import serializers

from .models import InboundMessage, MailAttachment


class MailAttachmentSerializer(serializers.ModelSerializer):
    class Meta:
        model = MailAttachment
        fields = ["id", "filename", "file", "content_type"]


class InboundMessageListSerializer(serializers.ModelSerializer):
    has_attachments = serializers.SerializerMethodField()

    class Meta:
        model = InboundMessage
        fields = [
            "id", "account_label", "from_address", "to_address", "subject",
            "received_at", "is_read", "has_attachments",
        ]

    def get_has_attachments(self, obj):
        return obj.attachments.exists()


class InboundMessageDetailSerializer(serializers.ModelSerializer):
    attachments = MailAttachmentSerializer(many=True, read_only=True)

    class Meta:
        model = InboundMessage
        fields = [
            "id", "account_label", "from_address", "to_address", "subject",
            "body_text", "body_html", "received_at", "is_read", "attachments",
        ]


class ReplySerializer(serializers.Serializer):
    body = serializers.CharField()
