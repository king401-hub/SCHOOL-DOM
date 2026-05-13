from django.urls import path

from finance import views

urlpatterns = [
    path("flutterwave/webhook/", views.flutterwave_webhook, name="flutterwave_webhook"),
    path("wallet/", views.wallet_summary, name="wallet_summary"),
    path("wallet/fund/", views.wallet_fund, name="wallet_fund"),
    path("wallet/verify/", views.wallet_verify, name="wallet_verify"),
    path("admin/overview/", views.admin_overview, name="admin_overview"),
    path("admin/payment-account/", views.admin_payment_account, name="admin_payment_account"),
    path("admin/class-fees/", views.admin_class_fee_create, name="admin_class_fee_create"),
    path("admin/class-fees/<uuid:fee_id>/", views.admin_class_fee_detail, name="admin_class_fee_detail"),
    path("admin/activation-credits/purchase/", views.admin_activation_credit_purchase, name="admin_activation_credit_purchase"),
    path("admin/activation-credits/verify/", views.admin_activation_credit_verify, name="admin_activation_credit_verify"),
    path("admin/activation-credits/assign/", views.admin_activation_credit_assign, name="admin_activation_credit_assign"),
    path("admin/activation-credits/settings/", views.admin_activation_credit_settings, name="admin_activation_credit_settings"),
    path("admin/activation-credits/run-auto/", views.admin_activation_credit_run_auto, name="admin_activation_credit_run_auto"),
    path("admin/bank-payments/ingest/", views.admin_bank_payment_ingest, name="admin_bank_payment_ingest"),
    path("admin/bank-payments/<uuid:payment_id>/recover/", views.admin_bank_payment_recover, name="admin_bank_payment_recover"),
    path("admin/expenses/", views.admin_expense_records, name="admin_expense_records"),
    path("admin/expenses/<uuid:record_id>/", views.admin_expense_record_detail, name="admin_expense_record_detail"),
    path("bank-payments/<uuid:payment_id>/receipt/", views.bank_payment_receipt, name="bank_payment_receipt"),
    path("admin/adjust/", views.admin_adjust_wallet, name="admin_adjust_wallet"),
    path("admin/fee/", views.admin_assign_fee, name="admin_assign_fee"),
    path("admin/withdraw/", views.admin_withdraw, name="admin_withdraw"),
]
