from django import forms
from django.contrib import admin

from finance.models import (
    ActivationCreditPool,
    ActivationCreditTransaction,
    AdminWallet,
    BankLink,
    ClassFee,
    ExpenseRecord,
    FinanceLedgerLog,
    SchoolFee,
    StudentActivationCredit,
    Transaction,
    Wallet,
)
from finance.services import adjust_activation_credit_pool, record_finance_activity


class ActivationCreditPoolAdminForm(forms.ModelForm):
    balance_adjustment = forms.IntegerField(
        required=False,
        initial=0,
        help_text="Optional manual adjustment. Use a positive number to add tokens or a negative number to deduct tokens.",
    )

    class Meta:
        model = ActivationCreditPool
        fields = "__all__"

    def clean_price_per_credit(self):
        price = self.cleaned_data["price_per_credit"]
        if price <= 0:
            raise forms.ValidationError("Token price must be greater than zero.")
        return price


@admin.register(Wallet)
class WalletAdmin(admin.ModelAdmin):
    list_display = ("user", "balance", "currency", "updated_at")
    readonly_fields = ("user", "created_at", "updated_at")

    def has_add_permission(self, request):
        # Wallets are created only when students register.
        return False


@admin.register(Transaction)
class TransactionAdmin(admin.ModelAdmin):
    list_display = ("reference", "tx_type", "status", "amount", "currency", "created_at")
    list_filter = ("tx_type", "status", "currency")
    search_fields = ("reference", "narration")
    readonly_fields = ("wallet", "admin_wallet", "created_at", "updated_at")

    def has_add_permission(self, request):
        return False


@admin.register(SchoolFee)
class SchoolFeeAdmin(admin.ModelAdmin):
    list_display = ("title", "student", "amount", "status", "due_date", "class_fee", "is_customized")
    list_filter = ("status", "class_fee", "is_customized")
    search_fields = ("title", "student__user__email")


@admin.register(ClassFee)
class ClassFeeAdmin(admin.ModelAdmin):
    list_display = ("title", "school_class", "amount", "currency", "due_date", "is_active")
    list_filter = ("is_active", "currency")
    search_fields = ("title", "school_class__name", "school_class__section")


@admin.register(ExpenseRecord)
class ExpenseRecordAdmin(admin.ModelAdmin):
    list_display = ("title", "tenant", "vendor", "phone_number", "record_type", "amount", "status", "record_date", "created_by")
    list_filter = ("record_type", "status", "tenant", "record_date")
    search_fields = ("title", "vendor", "phone_number", "category", "receipt_number", "note")
    readonly_fields = ("created_at", "updated_at")


@admin.register(AdminWallet)
class AdminWalletAdmin(admin.ModelAdmin):
    list_display = ("tenant", "balance", "currency", "updated_at")


@admin.register(BankLink)
class BankLinkAdmin(admin.ModelAdmin):
    list_display = ("bank_name", "is_active", "updated_at")
    list_filter = ("is_active",)
    search_fields = ("bank_name", "deep_link_template")


@admin.register(FinanceLedgerLog)
class FinanceLedgerLogAdmin(admin.ModelAdmin):
    list_display = ("created_at", "tenant", "action", "amount", "currency", "reference", "actor")
    list_filter = ("action", "currency", "created_at")
    search_fields = ("action", "description", "reference", "actor__email")
    readonly_fields = ("tenant", "actor", "action", "description", "amount", "currency", "reference", "metadata", "created_at")

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(ActivationCreditPool)
class ActivationCreditPoolAdmin(admin.ModelAdmin):
    form = ActivationCreditPoolAdminForm
    list_display = ("tenant", "balance", "price_per_credit", "auto_assign_enabled", "auto_assign_scope", "updated_at")
    list_filter = ("auto_assign_enabled", "auto_assign_scope")
    search_fields = ("tenant__name", "tenant__schema_name")
    fields = (
        "tenant",
        "balance",
        "balance_adjustment",
        "price_per_credit",
        "currency",
        "auto_assign_enabled",
        "auto_assign_scope",
        "last_auto_assigned_month",
        "last_reminder_month",
        "created_at",
        "updated_at",
    )
    readonly_fields = ("created_at", "updated_at")

    def save_model(self, request, obj, form, change):
        old_balance = 0
        old_price = None
        requested_balance = int(obj.balance or 0)
        if change and obj.pk:
            old = ActivationCreditPool.objects.get(pk=obj.pk)
            old_balance = int(old.balance or 0)
            old_price = old.price_per_credit
            obj.balance = old_balance
        else:
            obj.balance = 0

        super().save_model(request, obj, form, change)

        balance_delta = requested_balance - old_balance
        manual_delta = int(form.cleaned_data.get("balance_adjustment") or 0)
        total_delta = balance_delta + manual_delta
        if total_delta:
            adjust_activation_credit_pool(
                obj.tenant,
                total_delta,
                actor=request.user,
                narration="Super admin activation token adjustment",
            )
            obj.refresh_from_db()

        if old_price is not None and old_price != obj.price_per_credit:
            record_finance_activity(
                obj.tenant,
                request.user,
                "token_price_updated",
                "Updated activation token price from Django admin.",
                amount=obj.price_per_credit,
                currency=obj.currency,
                reference=str(obj.id),
                metadata={"old_price": str(old_price), "new_price": str(obj.price_per_credit)},
            )


@admin.register(StudentActivationCredit)
class StudentActivationCreditAdmin(admin.ModelAdmin):
    list_display = ("student", "credits_assigned", "active_until", "inactive_since", "is_excluded_from_auto_deductions")
    list_filter = ("is_excluded_from_auto_deductions", "active_until")
    search_fields = ("student__user__email", "student__student_id", "student__admission_number")


@admin.register(ActivationCreditTransaction)
class ActivationCreditTransactionAdmin(admin.ModelAdmin):
    list_display = ("reference", "pool", "student_credit", "tx_type", "credits", "amount", "created_at")
    list_filter = ("tx_type", "created_at")
    search_fields = ("reference", "narration", "student_credit__student__user__email")
    readonly_fields = ("created_at",)
