"""Serializers for finance API responses."""
from decimal import Decimal

from rest_framework import serializers

from finance.models import (
    ActivationCreditPool,
    ActivationCreditTransaction,
    AdminWallet,
    ClassFee,
    BankPayment,
    ExpenseRecord,
    FinanceLedgerLog,
    SchoolFee,
    StudentPaymentReference,
    StudentActivationCredit,
    Transaction,
    Wallet,
)
from finance.services import fee_paid_amount


class TransactionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Transaction
        fields = [
            "id",
            "tx_type",
            "status",
            "amount",
            "currency",
            "reference",
            "narration",
            "created_at",
        ]


class FinanceLedgerLogSerializer(serializers.ModelSerializer):
    actor_name = serializers.SerializerMethodField()

    class Meta:
        model = FinanceLedgerLog
        fields = [
            "id",
            "action",
            "description",
            "amount",
            "currency",
            "reference",
            "actor_name",
            "created_at",
            "metadata",
        ]

    def get_actor_name(self, obj):
        if not obj.actor_id:
            return "System"
        return obj.actor.get_full_name() or obj.actor.email


class SchoolFeeSerializer(serializers.ModelSerializer):
    amount_paid = serializers.SerializerMethodField()
    remaining_balance = serializers.SerializerMethodField()
    payment_status = serializers.SerializerMethodField()
    student_name = serializers.SerializerMethodField()
    student_identifier = serializers.SerializerMethodField()
    class_label = serializers.SerializerMethodField()

    class Meta:
        model = SchoolFee
        fields = [
            "id",
            "student",
            "student_name",
            "student_identifier",
            "class_fee",
            "class_label",
            "title",
            "amount",
            "currency",
            "due_date",
            "status",
            "auto_deduct",
            "is_customized",
            "amount_paid",
            "remaining_balance",
            "payment_status",
        ]

    def get_amount_paid(self, obj):
        return fee_paid_amount(obj)

    def get_remaining_balance(self, obj):
        return max(obj.amount - fee_paid_amount(obj), Decimal("0.00"))

    def get_payment_status(self, obj):
        paid = fee_paid_amount(obj)
        if obj.amount <= 0 or paid >= obj.amount:
            return "paid"
        if paid > 0:
            return "partial"
        return obj.status

    def get_student_name(self, obj):
        return obj.student.user.get_full_name() or obj.student.user.email

    def get_student_identifier(self, obj):
        return obj.student.student_id or obj.student.admission_number

    def get_class_label(self, obj):
        school_class = obj.student.current_class
        if not school_class:
            return ""
        section = getattr(school_class, "section", "") or ""
        return f"{school_class.name} - {section}" if section else school_class.name


class StudentPaymentReferenceSerializer(serializers.ModelSerializer):
    student_name = serializers.SerializerMethodField()
    student_id = serializers.SerializerMethodField()

    class Meta:
        model = StudentPaymentReference
        fields = ["id", "code", "is_active", "student_name", "student_id", "created_at"]

    def get_student_name(self, obj):
        return obj.student.user.get_full_name() or obj.student.user.email

    def get_student_id(self, obj):
        return obj.student.student_id or obj.student.admission_number


class BankPaymentSerializer(serializers.ModelSerializer):
    student_name = serializers.SerializerMethodField()
    student_id = serializers.SerializerMethodField()
    reference_code = serializers.SerializerMethodField()
    payment_method = serializers.SerializerMethodField()
    note = serializers.SerializerMethodField()

    class Meta:
        model = BankPayment
        fields = [
            "id",
            "student",
            "student_name",
            "student_id",
            "reference_code",
            "amount",
            "currency",
            "narration",
            "bank_reference",
            "status",
            "applied_amount",
            "unapplied_amount",
            "matched_at",
            "receipt_number",
            "payment_method",
            "note",
            "created_at",
        ]

    def get_student_name(self, obj):
        if not obj.student_id:
            return ""
        return obj.student.user.get_full_name() or obj.student.user.email

    def get_student_id(self, obj):
        if not obj.student_id:
            return ""
        return obj.student.student_id or obj.student.admission_number

    def get_reference_code(self, obj):
        return obj.payment_reference.code if obj.payment_reference_id else ""

    def get_payment_method(self, obj):
        return (obj.metadata or {}).get("payment_method", "bank_transfer")

    def get_note(self, obj):
        return (obj.metadata or {}).get("note", "")


class ClassFeeSerializer(serializers.ModelSerializer):
    class_label = serializers.SerializerMethodField()
    student_count = serializers.IntegerField(read_only=True)
    expected_amount = serializers.DecimalField(max_digits=14, decimal_places=2, read_only=True)

    class Meta:
        model = ClassFee
        fields = [
            "id",
            "school_class",
            "class_label",
            "title",
            "amount",
            "currency",
            "due_date",
            "is_active",
            "student_count",
            "expected_amount",
        ]

    def get_class_label(self, obj):
        section = getattr(obj.school_class, "section", "") or ""
        return f"{obj.school_class.name} - {section}" if section else obj.school_class.name


class ExpenseRecordSerializer(serializers.ModelSerializer):
    type = serializers.CharField(source="record_type", required=False)
    date = serializers.DateField(source="record_date", required=False)
    receiptNumber = serializers.CharField(source="receipt_number", required=False, allow_blank=True)
    phoneNumber = serializers.CharField(source="phone_number", required=False, allow_blank=True)

    class Meta:
        model = ExpenseRecord
        fields = [
            "id",
            "title",
            "vendor",
            "phoneNumber",
            "amount",
            "currency",
            "type",
            "category",
            "color",
            "status",
            "date",
            "receiptNumber",
            "note",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "currency", "created_at", "updated_at"]

    def validate_type(self, value):
        if value not in {choice[0] for choice in ExpenseRecord.TYPE_CHOICES}:
            raise serializers.ValidationError("Type must be expense, bill, or receipt.")
        return value

    def validate_status(self, value):
        if value not in {choice[0] for choice in ExpenseRecord.STATUS_CHOICES}:
            raise serializers.ValidationError("Status must be pending, due, or paid.")
        return value


class WalletSerializer(serializers.ModelSerializer):
    transactions = TransactionSerializer(many=True, read_only=True)

    class Meta:
        model = Wallet
        fields = ["id", "balance", "currency", "is_locked", "transactions"]


class AdminWalletSerializer(serializers.ModelSerializer):
    transactions = TransactionSerializer(many=True, read_only=True)
    bank_name = serializers.CharField(source="bank_code", read_only=True)

    class Meta:
        model = AdminWallet
        fields = [
            "id",
            "balance",
            "currency",
            "bank_account_name",
            "bank_account_number",
            "bank_name",
            "bank_code",
            "subaccount_code",
            "kuda_virtual_account_number",
            "kuda_virtual_account_name",
            "kuda_virtual_account_bank_name",
            "kuda_virtual_account_reference",
            "kuda_virtual_account_status",
            "kuda_virtual_account_metadata",
            "transactions",
        ]


class ActivationCreditPoolSerializer(serializers.ModelSerializer):
    total_value = serializers.SerializerMethodField()

    class Meta:
        model = ActivationCreditPool
        fields = [
            "id",
            "balance",
            "price_per_credit",
            "currency",
            "total_value",
            "auto_assign_enabled",
            "auto_assign_scope",
            "last_auto_assigned_month",
            "last_reminder_month",
        ]

    def get_total_value(self, obj):
        return obj.balance * obj.price_per_credit


class StudentActivationCreditSerializer(serializers.ModelSerializer):
    student_name = serializers.SerializerMethodField()
    student_id = serializers.SerializerMethodField()

    class Meta:
        model = StudentActivationCredit
        fields = [
            "id",
            "student",
            "student_name",
            "student_id",
            "credits_assigned",
            "active_until",
            "inactive_since",
            "inactive_flagged_at",
            "is_excluded_from_auto_deductions",
        ]

    def get_student_name(self, obj):
        return obj.student.user.get_full_name() or obj.student.user.email

    def get_student_id(self, obj):
        return obj.student.student_id or obj.student.admission_number


class ActivationCreditTransactionSerializer(serializers.ModelSerializer):
    class Meta:
        model = ActivationCreditTransaction
        fields = [
            "id",
            "tx_type",
            "status",
            "credits",
            "price_per_credit",
            "amount",
            "reference",
            "narration",
            "provider",
            "created_at",
        ]
