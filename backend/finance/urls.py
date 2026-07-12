from django.urls import path

from finance import views

urlpatterns = [
    # ============================================================
    # EXISTING WEBHOOKS
    # ============================================================
    path("flutterwave/webhook/", views.flutterwave_webhook, name="flutterwave_webhook"),
    path("kuda/webhook/", views.kuda_webhook, name="kuda_webhook"),
    path("whatsapp/webhook/", views.whatsapp_business_webhook, name="whatsapp_business_webhook"),
    path("whatsapp/balance-preview/", views.whatsapp_balance_preview, name="whatsapp_balance_preview"),
    path("whatsapp/reminders/run/", views.admin_whatsapp_fee_reminders, name="admin_whatsapp_fee_reminders"),
    path("bank-credit/webhook/", views.bank_credit_webhook, name="bank_credit_webhook"),
    
    # ============================================================
    # EXISTING PAYMENT ENDPOINTS
    # ============================================================
    path("pay/<str:student_ref>/", views.payment_fallback_page, name="payment_fallback_page"),
    path("receipt/<uuid:token>/", views.receipt_page, name="receipt_page"),
    path("wallet/", views.wallet_summary, name="wallet_summary"),
    path("wallet/fund/", views.wallet_fund, name="wallet_fund"),
    path("wallet/verify/", views.wallet_verify, name="wallet_verify"),
    
    # ============================================================
    # NEW: PAYSTACK SPLIT PAYMENT ENDPOINTS
    # ============================================================
    # Webhook for Paystack (must be public, no auth)
    path("paystack/webhook/", views.paystack_webhook, name="paystack_webhook"),
    
    # Initialize split payment for school fees
    path("paystack/initialize/", views.paystack_initialize_payment, name="paystack_initialize_payment"),
    
    # Verify payment after callback
    path("paystack/verify/", views.paystack_verify_payment, name="paystack_verify_payment"),
    
    # Get payment breakdown for fees
    path("paystack/breakdown/", views.paystack_payment_breakdown, name="paystack_payment_breakdown"),
    
    # Test SMS sending (admin only — returns raw Sendchamp response)
    path("admin/test-sms/", views.admin_test_sms, name="admin_test_sms"),

    # Test email receipt (admin only — sends a sample receipt to the given email)
    path("admin/test-email/", views.admin_test_email, name="admin_test_email"),

    # List Nigerian banks for the subaccount setup form (admin only)
    path("admin/paystack/banks/", views.admin_paystack_banks, name="admin_paystack_banks"),
    # Resolve account number to account name via Paystack (admin only)
    path("admin/paystack/resolve-account/", views.admin_paystack_resolve_account, name="admin_paystack_resolve_account"),

    # Setup split code for school (admin only)
    path("admin/paystack/split/setup/", views.admin_paystack_split_setup, name="admin_paystack_split_setup"),
    
    # Get split status for school
    path("admin/paystack/split/status/", views.admin_paystack_split_status, name="admin_paystack_split_status"),
    
    # Transaction history for parent
    path("transactions/", views.parent_transaction_history, name="parent_transaction_history"),

    # Transaction details
    path("transactions/<str:reference>/", views.transaction_detail, name="transaction_detail"),

    # Parent full dashboard (virtual account + fees per child + recent payments)
    path("parent/dashboard/", views.parent_dashboard, name="parent_dashboard"),

    # Admin: list all virtual account assignments for this school
    path("admin/virtual-accounts/", views.admin_list_virtual_accounts, name="admin_list_virtual_accounts"),

    # Admin: assign/update/deactivate virtual account per parent
    path("admin/virtual-accounts/<uuid:parent_id>/", views.admin_manage_virtual_account, name="admin_manage_virtual_account"),

    # Admin: send WhatsApp/SMS fee reminder to a parent
    path("admin/virtual-accounts/<uuid:parent_id>/remind/", views.admin_send_fee_reminder, name="admin_send_fee_reminder"),

    # Admin: auto-provision a real Paystack dedicated virtual account for a parent
    path("admin/virtual-accounts/<uuid:parent_id>/provision/", views.admin_provision_paystack_virtual_account, name="admin_provision_paystack_virtual_account"),

    # Admin: bulk SMS/WhatsApp/Email to selected parents
    path("admin/parents/bulk-message/", views.admin_bulk_message_parents, name="admin_bulk_message_parents"),

    # Admin: SMS wallet (balance, bundle purchase via Paystack, transaction history)
    path("admin/sms-wallet/", views.sms_wallet_overview, name="sms_wallet_overview"),
    path("admin/sms-wallet/purchase/", views.sms_wallet_purchase, name="sms_wallet_purchase"),
    path("admin/sms-wallet/verify/<str:reference>/", views.sms_wallet_verify, name="sms_wallet_verify"),

    # ============================================================
    # EXISTING ADMIN ENDPOINTS
    # ============================================================
    path("admin/overview/", views.admin_overview, name="admin_overview"),
    path("admin/payment-account/", views.admin_payment_account, name="admin_payment_account"),
    path("admin/kuda-virtual-account/", views.admin_kuda_virtual_account, name="admin_kuda_virtual_account"),
    path("admin/class-fees/", views.admin_class_fee_create, name="admin_class_fee_create"),
    path("admin/class-fees/<uuid:fee_id>/", views.admin_class_fee_detail, name="admin_class_fee_detail"),
    path("admin/fees/<uuid:fee_id>/", views.admin_school_fee_detail, name="admin_school_fee_detail"),
    path("admin/activation-credits/purchase/", views.admin_activation_credit_purchase, name="admin_activation_credit_purchase"),
    path("admin/activation-credits/verify/", views.admin_activation_credit_verify, name="admin_activation_credit_verify"),
    path("admin/activation-credits/assign/", views.admin_activation_credit_assign, name="admin_activation_credit_assign"),
    path("admin/activation-credits/price/", views.admin_activation_credit_price, name="admin_activation_credit_price"),
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
