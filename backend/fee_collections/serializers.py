from rest_framework import serializers

from fee_collections.models import (
    CollectionAuditLog,
    CollectionConfig,
    FeePayment,
    SchoolCollectionProfile,
    SchoolSettlement,
    SchoolVirtualAccount,
)


class CollectionConfigSerializer(serializers.ModelSerializer):
    class Meta:
        model = CollectionConfig
        fields = [
            "id",
            "commission_type",
            "commission_value",
            "minimum_commission",
            "maximum_commission",
            "settlement_frequency",
            "settlement_weekday",
            "auto_settlement_enabled",
            "updated_at",
        ]


class SchoolCollectionProfileSerializer(serializers.ModelSerializer):
    school_name = serializers.CharField(source="school.name", read_only=True)
    school_code = serializers.CharField(source="school.schema_name", read_only=True)

    class Meta:
        model = SchoolCollectionProfile
        fields = [
            "id",
            "school",
            "school_name",
            "school_code",
            "status",
            "bank_name",
            "bank_code",
            "account_number",
            "account_name",
            "flutterwave_customer_id",
            "flutterwave_customer_reference",
            "flutterwave_customer_metadata",
            "approved_at",
            "metadata",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["status", "approved_at", "metadata", "created_at", "updated_at"]


class SchoolVirtualAccountSerializer(serializers.ModelSerializer):
    school_name = serializers.CharField(source="school.name", read_only=True)

    class Meta:
        model = SchoolVirtualAccount
        fields = [
            "id",
            "school",
            "school_name",
            "provider",
            "account_number",
            "account_name",
            "bank_name",
            "provider_reference",
            "order_reference",
            "status",
            "created_at",
            "updated_at",
        ]


class FeePaymentSerializer(serializers.ModelSerializer):
    school_name = serializers.CharField(source="school.name", read_only=True)

    class Meta:
        model = FeePayment
        fields = [
            "id",
            "school",
            "school_name",
            "provider_reference",
            "session_id",
            "payer_name",
            "payer_account_number",
            "payer_bank_name",
            "narration",
            "currency",
            "gross_amount",
            "platform_fee",
            "net_amount",
            "status",
            "paid_at",
            "created_at",
        ]


class SchoolSettlementSerializer(serializers.ModelSerializer):
    school_name = serializers.CharField(source="school.name", read_only=True)
    payment_count = serializers.SerializerMethodField()

    class Meta:
        model = SchoolSettlement
        fields = [
            "id",
            "school",
            "school_name",
            "gross_amount",
            "platform_fee",
            "net_amount",
            "currency",
            "transfer_reference",
            "provider_transfer_id",
            "status",
            "scheduled_for",
            "settled_at",
            "failure_reason",
            "payment_count",
            "created_at",
            "updated_at",
        ]

    def get_payment_count(self, obj):
        return obj.payments.count()


class CollectionAuditLogSerializer(serializers.ModelSerializer):
    actor_name = serializers.SerializerMethodField()
    school_name = serializers.CharField(source="school.name", read_only=True)

    class Meta:
        model = CollectionAuditLog
        fields = [
            "id",
            "school",
            "school_name",
            "actor_name",
            "action",
            "reference",
            "message",
            "metadata",
            "created_at",
        ]

    def get_actor_name(self, obj):
        if not obj.actor_id:
            return "System"
        return obj.actor.get_full_name() or obj.actor.email
