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
    list_display = ("tenant", "balance", "price_per_credit", "auto_assign_enabled", "auto_assign_scope", "updated_at")
    list_filter = ("auto_assign_enabled", "auto_assign_scope")


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
