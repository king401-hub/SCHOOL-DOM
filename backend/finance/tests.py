from decimal import Decimal
from unittest.mock import patch

from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework.test import APIClient

from core.models import SchoolTenant
from academic.models import Class
from finance.models import (
    ActivationCreditTransaction,
    AdminWallet,
    ClassFee,
    DocumentGenerationCreditTransaction,
    FeeAllocation,
    FinanceLedgerLog,
    ParentVirtualAccount,
    SchoolFee,
    SmsWalletTransaction,
    StudentPaymentReference,
    Transaction,
)
from finance.services import (
    ACTIVATION_CREDIT_PRICE,
    SMS_CHAR_LIMIT,
    InsufficientSmsCreditsError,
    SmsWalletLockedError,
    _sms_message_with_receipt_link,
    activation_credit_bonus_for_purchase,
    adjust_sms_wallet,
    build_paystack_receipt_message,
    charge_sms_wallet,
    complete_wallet_funding,
    credit_sms_wallet_from_purchase,
    deduct_document_generation_credit,
    ensure_student_wallet,
    fee_paid_amount,
    get_or_create_activation_credit_pool,
    get_or_create_sms_wallet,
    get_or_create_student_payment_reference,
    initialize_sms_credit_purchase,
    process_virtual_account_payment,
    refund_sms_wallet,
    send_wallet_sms,
    sync_class_fee_assignments,
    verify_activation_credit_purchase,
)
from finance.models import SmsMessageLog
from notifications.models import Notification
from tenants.models import Tenant
from users.models import ParentProfile, StudentProfile, User, generate_short_student_id, generate_short_teacher_id


class StudentFeeReferenceTests(TestCase):
    def setUp(self):
        self.school = SchoolTenant.objects.create(name="Fee School", schema_name="fee_school", is_active=True)
        self.user = User.objects.create_user(
            email="student.fee@school.edu",
            password="StudentPass123",
            first_name="Fee",
            last_name="Student",
            role="student",
            tenant=self.school,
            is_active=True,
            is_verified=True,
        )
        self.student = StudentProfile.objects.create(
            user=self.user,
            student_id="STU12345",
            admission_number="ADM-FEE-001",
            admission_date=timezone.localdate(),
            guardian_name="Guardian",
            guardian_relation="Parent",
        )

    def test_generated_student_id_is_short(self):
        student_id = generate_short_student_id("abcdef123456", self.school)
        self.assertEqual(len(student_id), 7)
        self.assertRegex(student_id, r"^STFS\d{3}$")

    def test_generated_teacher_id_is_short(self):
        teacher_id = generate_short_teacher_id("abcdef123456", self.school)
        self.assertEqual(len(teacher_id), 7)
        self.assertRegex(teacher_id, r"^TCFS\d{3}$")

    def test_fee_payment_reference_matches_student_id(self):
        reference = get_or_create_student_payment_reference(self.student)
        self.assertEqual(reference.code, "STU12345")

    def test_existing_fee_payment_reference_updates_to_student_id(self):
        reference = StudentPaymentReference.objects.create(
            student=self.student,
            tenant=self.school,
            code="SDFEESCHOOL12345",
        )
        updated = get_or_create_student_payment_reference(self.student)
        self.assertEqual(updated.id, reference.id)
        self.assertEqual(updated.code, "STU12345")


class ActivationCreditBonusTests(TestCase):
    def setUp(self):
        self.school = SchoolTenant.objects.create(name="Bonus School", schema_name="bonus_school", is_active=True)
        self.admin = User.objects.create_user(
            email="admin@bonus.test",
            password="AdminPass123",
            first_name="Bonus",
            last_name="Admin",
            role="school_admin",
            tenant=self.school,
            is_active=True,
            is_verified=True,
        )

    def test_bonus_is_ten_for_every_hundred_tokens(self):
        self.assertEqual(activation_credit_bonus_for_purchase(99), 0)
        self.assertEqual(activation_credit_bonus_for_purchase(100), 10)
        self.assertEqual(activation_credit_bonus_for_purchase(250), 20)

    @patch("finance.services.verify_flutterwave_transaction")
    def test_verified_purchase_credits_paid_tokens_plus_bonus(self, mock_verify):
        pool = get_or_create_activation_credit_pool(self.school)
        tx = ActivationCreditTransaction.objects.create(
            pool=pool,
            tx_type=ActivationCreditTransaction.PURCHASE,
            status=ActivationCreditTransaction.STATUS_PENDING,
            credits=100,
            price_per_credit=ACTIVATION_CREDIT_PRICE,
            amount=ACTIVATION_CREDIT_PRICE * 100,
            reference="CRPBONUS100",
            narration="Activation token purchase via Flutterwave",
            created_by=self.admin,
        )
        mock_verify.return_value = {"status": "successful", "amount": "20000.00"}

        verified_pool = verify_activation_credit_purchase(tx.reference, actor=self.admin)
        tx.refresh_from_db()

        self.assertEqual(verified_pool.balance, 110)
        self.assertEqual(tx.credits, 100)
        self.assertEqual(tx.metadata["purchased_credits"], 100)
        self.assertEqual(tx.metadata["bonus_credits"], 10)
        self.assertEqual(tx.metadata["total_credits"], 110)


class FlutterwaveSchoolFeeSettlementTests(TestCase):
    def setUp(self):
        self.school = SchoolTenant.objects.create(name="Settlement School", schema_name="settlement_school", is_active=True)
        self.student_user = User.objects.create_user(
            email="student@settlement.test",
            password="StudentPass123",
            first_name="Settle",
            last_name="Student",
            role="student",
            tenant=self.school,
            is_active=True,
            is_verified=True,
        )
        self.student = StudentProfile.objects.create(
            user=self.student_user,
            student_id="STSET01",
            admission_number="ADM-SET-001",
            admission_date=timezone.localdate(),
            guardian_name="Guardian",
            guardian_relation="Parent",
        )
        self.admin_wallet = AdminWallet.objects.create(
            tenant=self.school,
            bank_account_name="Settlement School",
            bank_account_number="0123456789",
            bank_code="044",
        )

    @override_settings(FLUTTERWAVE_SECRET_KEY="flw-secret", FLUTTERWAVE_AUTO_SETTLE_SCHOOL_FEES=True)
    @patch("finance.services.requests.post")
    @patch("finance.services.verify_flutterwave_transaction")
    def test_verified_student_payment_transfers_to_admin_saved_account(self, mock_verify, mock_post):
        wallet = ensure_student_wallet(self.student_user)
        tx = Transaction.objects.create(
            wallet=wallet,
            amount=Decimal("1500.00"),
            tx_type=Transaction.FUNDING,
            status=Transaction.STATUS_PENDING,
            reference="PAYSETTLEMENT001",
            narration="School fee payment via Flutterwave",
            created_by=self.student_user,
        )
        mock_verify.return_value = {"status": "successful", "amount": "1500.00"}
        mock_post.return_value.json.return_value = {"status": "success", "data": {"id": 12345}}

        complete_wallet_funding(tx.reference, actor=self.student_user)

        tx.refresh_from_db()
        self.admin_wallet.refresh_from_db()
        withdrawal = Transaction.objects.get(
            admin_wallet=self.admin_wallet,
            tx_type=Transaction.WITHDRAWAL,
            metadata__bank__account_number="0123456789",
        )
        transfer_payload = mock_post.call_args.kwargs["json"]

        self.assertEqual(tx.status, Transaction.STATUS_SUCCESS)
        self.assertEqual(tx.metadata["admin_bank_settlement"]["status"], Transaction.STATUS_SUCCESS)
        self.assertEqual(withdrawal.amount, Decimal("1500.00"))
        self.assertEqual(withdrawal.status, Transaction.STATUS_SUCCESS)
        self.assertEqual(self.admin_wallet.balance, Decimal("0.00"))
        self.assertEqual(transfer_payload["account_bank"], "044")
        self.assertEqual(transfer_payload["account_number"], "0123456789")


class DocumentGenerationCreditTests(TestCase):
    def setUp(self):
        self.school = SchoolTenant.objects.create(name="Document School", schema_name="document_school", is_active=True)
        self.admin = User.objects.create_user(
            email="admin@documents.test",
            password="AdminPass123",
            first_name="Document",
            last_name="Admin",
            role="school_admin",
            tenant=self.school,
            is_active=True,
            is_verified=True,
        )
        self.student_user = User.objects.create_user(
            email="student@documents.test",
            password="StudentPass123",
            first_name="Document",
            last_name="Student",
            role="student",
            tenant=self.school,
            is_active=True,
            is_verified=True,
        )
        self.student = StudentProfile.objects.create(
            user=self.student_user,
            student_id="STDOC01",
            admission_number="ADM-DOC-001",
            admission_date=timezone.localdate(),
            guardian_name="Guardian",
            guardian_relation="Parent",
        )
        self.pool = get_or_create_activation_credit_pool(self.school)
        self.pool.balance = 3
        self.pool.save(update_fields=["balance", "updated_at"])

    def test_student_document_generation_charges_only_once_per_document_type(self):
        first_pool = deduct_document_generation_credit(
            self.school,
            document_type=DocumentGenerationCreditTransaction.TRANSCRIPT,
            student_profile=self.student,
            actor=self.admin,
        )
        second_pool = deduct_document_generation_credit(
            self.school,
            document_type=DocumentGenerationCreditTransaction.TRANSCRIPT,
            student_profile=self.student,
            actor=self.admin,
        )

        self.pool.refresh_from_db()
        self.assertTrue(first_pool.document_credit_charged)
        self.assertFalse(second_pool.document_credit_charged)
        self.assertEqual(self.pool.balance, 2)
        self.assertEqual(
            DocumentGenerationCreditTransaction.objects.filter(
                student=self.student,
                document_type=DocumentGenerationCreditTransaction.TRANSCRIPT,
            ).count(),
            1,
        )

    def test_different_student_document_type_still_charges_once(self):
        deduct_document_generation_credit(
            self.school,
            document_type=DocumentGenerationCreditTransaction.TRANSCRIPT,
            student_profile=self.student,
            actor=self.admin,
        )
        testimonial_pool = deduct_document_generation_credit(
            self.school,
            document_type=DocumentGenerationCreditTransaction.TESTIMONIAL,
            student_profile=self.student,
            actor=self.admin,
        )

        self.pool.refresh_from_db()
        self.assertTrue(testimonial_pool.document_credit_charged)
        self.assertEqual(self.pool.balance, 1)


class ManualFeeEditingTests(TestCase):
    def setUp(self):
        self.school = SchoolTenant.objects.create(name="Manual Fee School", schema_name="manual_fee", is_active=True)
        self.legacy_tenant = Tenant.objects.create(name=self.school.name, slug=self.school.schema_name)
        self.admin = User.objects.create_user(
            email="admin@manual.test",
            password="AdminPass123",
            first_name="Manual",
            last_name="Admin",
            role="school_admin",
            tenant=self.school,
            is_active=True,
            is_verified=True,
        )
        self.student_user = User.objects.create_user(
            email="student@manual.test",
            password="StudentPass123",
            first_name="Manual",
            last_name="Student",
            role="student",
            tenant=self.school,
            is_active=True,
            is_verified=True,
        )
        self.school_class = Class.objects.create(tenant=self.legacy_tenant, name="Basic 1", section="A")
        self.student = StudentProfile.objects.create(
            user=self.student_user,
            student_id="STMNL01",
            admission_number="ADM-MNL-001",
            admission_date=timezone.localdate(),
            guardian_name="Guardian",
            guardian_relation="Parent",
            current_class=self.school_class,
        )
        self.client = APIClient()
        self.client.force_authenticate(self.admin)

    def test_class_fee_edit_updates_existing_student_fee_without_duplicate(self):
        class_fee = ClassFee.objects.create(
            school_class=self.school_class,
            title="First Term",
            amount=Decimal("1000.00"),
            due_date=timezone.localdate(),
            created_by=self.admin,
        )
        sync_class_fee_assignments(class_fee, actor=self.admin)

        response = self.client.patch(
            f"/api/finance/admin/class-fees/{class_fee.id}/",
            {"amount": "1250.00", "title": "First Term Updated"},
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(SchoolFee.objects.filter(student=self.student, class_fee=class_fee).count(), 1)
        student_fee = SchoolFee.objects.get(student=self.student, class_fee=class_fee)
        self.assertEqual(student_fee.amount, Decimal("1250.00"))
        self.assertEqual(student_fee.title, "First Term Updated")
        self.assertEqual(Decimal(str(response.data["finance"]["expected_fee_amount"])), Decimal("1250.00"))

    def test_class_fee_create_sends_bill_to_every_student_in_class(self):
        second_user = User.objects.create_user(
            email="student2@manual.test",
            password="StudentPass123",
            first_name="Second",
            last_name="Student",
            role="student",
            tenant=self.school,
            is_active=True,
            is_verified=True,
        )
        second_student = StudentProfile.objects.create(
            user=second_user,
            student_id="STMNL02",
            admission_number="ADM-MNL-002",
            admission_date=timezone.localdate(),
            guardian_name="Guardian",
            guardian_relation="Parent",
            current_class=self.school_class,
        )

        response = self.client.post(
            "/api/finance/admin/class-fees/",
            {
                "school_class": str(self.school_class.id),
                "title": "Second Term",
                "amount": "2000.00",
                "due_date": timezone.localdate().isoformat(),
            },
            format="json",
        )

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data["assigned_count"], 2)
        self.assertEqual(
            SchoolFee.objects.filter(class_fee=response.data["class_fee"]["id"]).count(),
            2,
        )
        self.assertTrue(
            SchoolFee.objects.filter(student=self.student, title="Second Term", amount=Decimal("2000.00")).exists()
        )
        self.assertTrue(
            SchoolFee.objects.filter(student=second_student, title="Second Term", amount=Decimal("2000.00")).exists()
        )
        self.assertEqual(
            Notification.objects.filter(
                user__in=[self.student_user, second_user],
                event_type="fee_due",
                deep_link="/fees",
            ).count(),
            2,
        )

    def test_student_fee_amount_increase_reopens_status_against_recorded_payments(self):
        fee = SchoolFee.objects.create(
            student=self.student,
            title="Tuition",
            amount=Decimal("1000.00"),
            due_date=timezone.localdate(),
            status=SchoolFee.STATUS_PAID,
            created_by=self.admin,
        )
        admin_wallet = AdminWallet.objects.create(tenant=self.school, balance=Decimal("1000.00"))
        Transaction.objects.create(
            admin_wallet=admin_wallet,
            amount=Decimal("1000.00"),
            tx_type=Transaction.FEE_CREDIT,
            status=Transaction.STATUS_SUCCESS,
            reference="ADMMANUAL1000",
            narration="Recorded fee payment",
            metadata={"fee_id": str(fee.id), "bank_payment_id": "BANK001"},
            created_by=self.admin,
        )

        response = self.client.patch(
            f"/api/finance/admin/fees/{fee.id}/",
            {"amount": "1500.00"},
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        fee.refresh_from_db()
        self.assertNotEqual(fee.status, SchoolFee.STATUS_PAID)
        self.assertEqual(fee_paid_amount(fee), Decimal("1000.00"))
        self.assertEqual(Decimal(str(response.data["fee"]["remaining_balance"])), Decimal("500.00"))


class SmsWalletTests(TestCase):
    def setUp(self):
        self.school = SchoolTenant.objects.create(name="SMS School", schema_name="sms_school", is_active=True)
        self.admin = User.objects.create_user(
            email="admin@sms.test",
            password="AdminPass123",
            first_name="Sms",
            last_name="Admin",
            role="school_admin",
            tenant=self.school,
            is_active=True,
            is_verified=True,
        )

    def test_get_or_create_sms_wallet_grants_welcome_credit_once(self):
        wallet_a = get_or_create_sms_wallet(self.school)
        self.assertEqual(wallet_a.balance, 100)
        welcome_tx = SmsWalletTransaction.objects.get(wallet=wallet_a, tx_type=SmsWalletTransaction.ADMIN_CREDIT)
        self.assertEqual(welcome_tx.credits, 100)
        self.assertEqual(welcome_tx.balance_before, 0)
        self.assertEqual(welcome_tx.balance_after, 100)

        wallet_a.balance = 250
        wallet_a.save(update_fields=["balance", "updated_at"])
        wallet_b = get_or_create_sms_wallet(self.school)

        self.assertEqual(wallet_a.id, wallet_b.id)
        self.assertEqual(wallet_b.balance, 250)  # unchanged - welcome credit only applies once
        self.assertEqual(SmsWalletTransaction.objects.filter(wallet=wallet_a, tx_type=SmsWalletTransaction.ADMIN_CREDIT).count(), 1)

    def test_initialize_purchase_rejects_units_not_a_multiple_of_100(self):
        with self.assertRaises(ValueError):
            initialize_sms_credit_purchase(self.school, 150, self.admin)
        with self.assertRaises(ValueError):
            initialize_sms_credit_purchase(self.school, 50, self.admin)  # below minimum

    @patch("finance.services.requests.post")
    def test_initialize_purchase_creates_pending_transaction_at_100_per_1000(self, mock_post):
        mock_post.return_value.json.return_value = {
            "status": True,
            "data": {"authorization_url": "https://paystack.test/pay", "access_code": "abc123"},
        }

        result = initialize_sms_credit_purchase(self.school, 300, self.admin)

        tx = SmsWalletTransaction.objects.get(reference=result["reference"])
        self.assertEqual(tx.status, SmsWalletTransaction.STATUS_PENDING)
        self.assertEqual(tx.credits, 300)
        self.assertEqual(tx.amount, Decimal("3000.00"))
        self.assertEqual(result["authorization_url"], "https://paystack.test/pay")
        sent_amount_kobo = mock_post.call_args.kwargs["json"]["amount"]
        self.assertEqual(sent_amount_kobo, 300000)

    @patch("finance.services.verify_paystack_transaction")
    def test_credit_from_purchase_adds_units_on_top_of_welcome_credit(self, mock_verify):
        wallet = get_or_create_sms_wallet(self.school)  # starts at 100 (welcome credit)
        tx = SmsWalletTransaction.objects.create(
            wallet=wallet,
            tx_type=SmsWalletTransaction.PURCHASE,
            status=SmsWalletTransaction.STATUS_PENDING,
            credits=200,
            amount=Decimal("2000.00"),
            reference="SMSWTEST0001",
            created_by=self.admin,
        )
        mock_verify.return_value = {"status": "success", "amount": 200000}  # kobo

        credited_tx = credit_sms_wallet_from_purchase(tx.reference)
        wallet.refresh_from_db()

        self.assertEqual(wallet.balance, 300)
        self.assertEqual(credited_tx.status, SmsWalletTransaction.STATUS_SUCCESS)
        self.assertEqual(credited_tx.balance_before, 100)
        self.assertEqual(credited_tx.balance_after, 300)

    @patch("finance.services.verify_paystack_transaction")
    def test_credit_from_purchase_is_idempotent(self, mock_verify):
        wallet = get_or_create_sms_wallet(self.school)
        tx = SmsWalletTransaction.objects.create(
            wallet=wallet,
            tx_type=SmsWalletTransaction.PURCHASE,
            status=SmsWalletTransaction.STATUS_PENDING,
            credits=200,
            amount=Decimal("2000.00"),
            reference="SMSWTEST0002",
            created_by=self.admin,
        )
        mock_verify.return_value = {"status": "success", "amount": 200000}

        credit_sms_wallet_from_purchase(tx.reference)
        # Simulates the webhook and the client-side verify call both firing for the
        # same payment - balance must only be credited once.
        credit_sms_wallet_from_purchase(tx.reference)
        wallet.refresh_from_db()

        self.assertEqual(wallet.balance, 300)
        self.assertEqual(SmsWalletTransaction.objects.filter(reference=tx.reference).count(), 1)

    @patch("finance.services.verify_paystack_transaction")
    def test_credit_from_purchase_fails_on_amount_mismatch(self, mock_verify):
        wallet = get_or_create_sms_wallet(self.school)
        tx = SmsWalletTransaction.objects.create(
            wallet=wallet,
            tx_type=SmsWalletTransaction.PURCHASE,
            status=SmsWalletTransaction.STATUS_PENDING,
            credits=200,
            amount=Decimal("2000.00"),
            reference="SMSWTEST0003",
            created_by=self.admin,
        )
        mock_verify.return_value = {"status": "success", "amount": 100000}  # only NGN1000 paid, needed NGN2000

        with self.assertRaises(ValueError):
            credit_sms_wallet_from_purchase(tx.reference)

        wallet.refresh_from_db()
        tx.refresh_from_db()
        self.assertEqual(wallet.balance, 100)  # unchanged from welcome credit
        self.assertEqual(tx.status, SmsWalletTransaction.STATUS_FAILED)

    def test_charge_debits_wallet_and_records_before_after(self):
        wallet = get_or_create_sms_wallet(self.school)
        wallet.balance = 100
        wallet.save(update_fields=["balance", "updated_at"])

        tx = charge_sms_wallet(self.school, 5, category="attendance", narration="Attendance alert")
        wallet.refresh_from_db()

        self.assertEqual(wallet.balance, 95)
        self.assertEqual(tx.tx_type, SmsWalletTransaction.DEBIT)
        self.assertEqual(tx.credits, -5)
        self.assertEqual(tx.balance_before, 100)
        self.assertEqual(tx.balance_after, 95)
        self.assertEqual(tx.metadata["category"], "attendance")

    def test_charge_raises_when_balance_insufficient(self):
        wallet = get_or_create_sms_wallet(self.school)
        wallet.balance = 2
        wallet.save(update_fields=["balance", "updated_at"])

        with self.assertRaises(InsufficientSmsCreditsError):
            charge_sms_wallet(self.school, 5, category="attendance")

        wallet.refresh_from_db()
        self.assertEqual(wallet.balance, 2)
        self.assertEqual(SmsWalletTransaction.objects.filter(wallet=wallet, tx_type=SmsWalletTransaction.DEBIT).count(), 0)

    def test_charge_raises_when_wallet_locked(self):
        wallet = get_or_create_sms_wallet(self.school)
        wallet.balance = 100
        wallet.is_locked = True
        wallet.save(update_fields=["balance", "is_locked", "updated_at"])

        with self.assertRaises(SmsWalletLockedError):
            charge_sms_wallet(self.school, 5, category="attendance")

    def test_refund_restores_exact_amount_and_records_before_after(self):
        wallet = get_or_create_sms_wallet(self.school)
        wallet.balance = 100
        wallet.save(update_fields=["balance", "updated_at"])
        debit_tx = charge_sms_wallet(self.school, 5, category="attendance")

        refund_tx = refund_sms_wallet(debit_tx, reason="Delivery permanently failed")
        wallet.refresh_from_db()

        self.assertEqual(wallet.balance, 100)
        self.assertEqual(refund_tx.tx_type, SmsWalletTransaction.REFUND)
        self.assertEqual(refund_tx.credits, 5)
        self.assertEqual(refund_tx.balance_before, 95)
        self.assertEqual(refund_tx.balance_after, 100)
        self.assertEqual(refund_tx.metadata["refund_of"], str(debit_tx.id))

    def test_adjust_can_credit_and_debit_with_ledger_entry(self):
        wallet = get_or_create_sms_wallet(self.school)  # starts at 100 (welcome credit)

        credit_tx = adjust_sms_wallet(self.school, 20, reason="Goodwill credit", actor=self.admin)
        wallet.refresh_from_db()
        self.assertEqual(wallet.balance, 120)
        self.assertEqual(credit_tx.tx_type, SmsWalletTransaction.ADJUSTMENT)
        self.assertEqual(credit_tx.balance_before, 100)
        self.assertEqual(credit_tx.balance_after, 120)

        debit_tx = adjust_sms_wallet(self.school, -5, reason="Correction", actor=self.admin)
        wallet.refresh_from_db()
        self.assertEqual(wallet.balance, 115)
        self.assertEqual(debit_tx.balance_before, 120)
        self.assertEqual(debit_tx.balance_after, 115)

    def test_adjust_raises_rather_than_going_negative(self):
        wallet = get_or_create_sms_wallet(self.school)
        wallet.balance = 3
        wallet.save(update_fields=["balance", "updated_at"])

        with self.assertRaises(InsufficientSmsCreditsError):
            adjust_sms_wallet(self.school, -10, reason="Bad correction", actor=self.admin)

        wallet.refresh_from_db()
        self.assertEqual(wallet.balance, 3)

    @patch("finance.services.send_ebulksms")
    def test_send_wallet_sms_charges_ten_credits_and_logs_sent(self, mock_send):
        wallet = get_or_create_sms_wallet(self.school)
        wallet.balance = 50
        wallet.save(update_fields=["balance", "updated_at"])
        mock_send.return_value = {"status": "success"}

        log = send_wallet_sms(self.school, "2348012345678", "Test message", category=SmsMessageLog.BULK)
        wallet.refresh_from_db()

        self.assertEqual(wallet.balance, 40)
        self.assertEqual(log.delivery_status, SmsMessageLog.SENT)
        self.assertEqual(log.credits_charged, 10)
        self.assertIsNotNone(log.sent_at)
        debit_tx = SmsWalletTransaction.objects.get(related_message_log=log)
        self.assertEqual(debit_tx.tx_type, SmsWalletTransaction.DEBIT)
        self.assertEqual(debit_tx.balance_before, 50)
        self.assertEqual(debit_tx.balance_after, 40)

    @patch("finance.services.send_ebulksms")
    def test_send_wallet_sms_refunds_on_provider_failure(self, mock_send):
        wallet = get_or_create_sms_wallet(self.school)
        wallet.balance = 50
        wallet.save(update_fields=["balance", "updated_at"])
        mock_send.return_value = {"status": "error", "reason": "Invalid phone format"}

        log = send_wallet_sms(self.school, "2348012345678", "Test message", category=SmsMessageLog.BULK)
        wallet.refresh_from_db()

        self.assertEqual(wallet.balance, 50)
        self.assertEqual(log.delivery_status, SmsMessageLog.REFUNDED)
        self.assertIsNotNone(log.refunded_at)
        self.assertEqual(
            SmsWalletTransaction.objects.filter(wallet=wallet, tx_type=SmsWalletTransaction.REFUND).count(), 1
        )

    @patch("finance.services.send_ebulksms")
    def test_send_wallet_sms_raises_before_sending_when_balance_insufficient(self, mock_send):
        wallet = get_or_create_sms_wallet(self.school)
        wallet.balance = 5
        wallet.save(update_fields=["balance", "updated_at"])

        with self.assertRaises(InsufficientSmsCreditsError):
            send_wallet_sms(self.school, "2348012345678", "Test message", category=SmsMessageLog.BULK)

        mock_send.assert_not_called()
        self.assertEqual(SmsMessageLog.objects.filter(wallet=wallet).count(), 0)


class CrossTenantIsolationTests(TestCase):
    """
    Every test here proves a School A finance admin cannot read or act on School B's
    data by passing a School-B id/reference into a School-A-authenticated request.
    """

    def setUp(self):
        self.school_a = SchoolTenant.objects.create(name="School A", schema_name="school_a_iso", is_active=True)
        self.school_b = SchoolTenant.objects.create(name="School B", schema_name="school_b_iso", is_active=True)

        self.admin_a = User.objects.create_user(
            email="admin@a.test", password="AdminPass123", first_name="Admin", last_name="A",
            role="school_admin", tenant=self.school_a, is_active=True, is_verified=True,
        )
        self.admin_b = User.objects.create_user(
            email="admin@b.test", password="AdminPass123", first_name="Admin", last_name="B",
            role="school_admin", tenant=self.school_b, is_active=True, is_verified=True,
        )
        self.parent_b = User.objects.create_user(
            email="parent@b.test", password="ParentPass123", first_name="Parent", last_name="B",
            role="parent", tenant=self.school_b, is_active=True, is_verified=True,
        )

        self.client = APIClient()
        self.client.force_authenticate(self.admin_a)

    def test_admin_cannot_manage_another_schools_parent_virtual_account(self):
        response = self.client.get(f"/api/finance/admin/virtual-accounts/{self.parent_b.id}/")
        self.assertEqual(response.status_code, 404)

        response = self.client.post(
            f"/api/finance/admin/virtual-accounts/{self.parent_b.id}/",
            {"account_number": "0123456789", "bank_name": "Fake Bank", "account_name": "Attacker"},
            format="json",
        )
        self.assertEqual(response.status_code, 404)
        self.assertFalse(ParentVirtualAccount.objects.filter(parent=self.parent_b).exists())

    def test_admin_cannot_provision_dva_for_another_schools_parent(self):
        response = self.client.post(f"/api/finance/admin/virtual-accounts/{self.parent_b.id}/provision/")
        self.assertEqual(response.status_code, 404)

    def test_admin_cannot_send_fee_reminder_to_another_schools_parent(self):
        response = self.client.post(f"/api/finance/admin/virtual-accounts/{self.parent_b.id}/remind/")
        self.assertEqual(response.status_code, 404)

    def test_admin_cannot_view_another_schools_transaction(self):
        tx = Transaction.objects.create(
            amount=Decimal("1000.00"),
            tx_type=Transaction.SPLIT_PAYMENT,
            status=Transaction.STATUS_SUCCESS,
            reference="PAYCROSSTENANT001",
            paystack_ref="PAYCROSSTENANT001",
            school_id=self.school_b.id,
            parent_id=self.parent_b.id,
        )
        response = self.client.get(f"/api/finance/paystack/verify/?reference={tx.paystack_ref}")
        self.assertEqual(response.status_code, 404)

    def test_admin_cannot_credit_another_schools_sms_wallet_via_guessed_reference(self):
        from finance.models import SmsWallet
        wallet_b = SmsWallet.objects.create(tenant=self.school_b, balance=0)
        tx = SmsWalletTransaction.objects.create(
            wallet=wallet_b,
            tx_type=SmsWalletTransaction.PURCHASE,
            status=SmsWalletTransaction.STATUS_PENDING,
            credits=100,
            amount=Decimal("1000.00"),
            reference="SMSWCROSSTENANT01",
        )
        response = self.client.post(f"/api/finance/admin/sms-wallet/verify/{tx.reference}/")
        self.assertEqual(response.status_code, 404)
        tx.refresh_from_db()
        self.assertEqual(tx.status, SmsWalletTransaction.STATUS_PENDING)
        wallet_b.refresh_from_db()
        self.assertEqual(wallet_b.balance, 0)

    def test_parent_cannot_see_another_familys_fee_breakdown(self):
        from academic.models import Class
        from tenants.models import Tenant as LegacyTenant
        from users.models import ParentProfile, StudentProfile

        legacy_tenant_b = LegacyTenant.objects.create(name=self.school_b.name, slug=self.school_b.schema_name)
        school_class = Class.objects.create(tenant=legacy_tenant_b, name="Basic 1", section="A")
        student_user_b = User.objects.create_user(
            email="student@b.test", password="StudentPass123", first_name="Student", last_name="B",
            role="student", tenant=self.school_b, is_active=True, is_verified=True,
        )
        student_b = StudentProfile.objects.create(
            user=student_user_b, student_id="STB001", admission_number="ADM-B-001",
            admission_date=timezone.localdate(), guardian_name="Guardian", guardian_relation="Parent",
            current_class=school_class,
        )
        fee_b = SchoolFee.objects.create(
            student=student_b, title="Tuition", amount=Decimal("5000.00"),
            due_date=timezone.localdate(), status=SchoolFee.STATUS_PENDING,
        )

        parent_a = User.objects.create_user(
            email="parent@a.test", password="ParentPass123", first_name="Parent", last_name="A",
            role="parent", tenant=self.school_a, is_active=True, is_verified=True,
        )
        ParentProfile.objects.create(user=parent_a)
        self.client.force_authenticate(parent_a)

        response = self.client.post(
            "/api/finance/paystack/breakdown/",
            {"fee_ids": [str(fee_b.id)]},
            format="json",
        )
        self.assertEqual(response.status_code, 404)


class PaystackDvaReconciliationTests(TestCase):
    """Regression coverage: a parent's Paystack virtual-account payment must
    reconcile the fee balance and show up on the admin ledger and the
    student's own dashboard - not just trigger a receipt notification."""

    def setUp(self):
        self.school = SchoolTenant.objects.create(
            name="Reconcile School", schema_name="reconcile_school", is_active=True
        )
        self.legacy_tenant = Tenant.objects.create(name=self.school.name, slug=self.school.schema_name)

        self.admin_user = User.objects.create_user(
            email="admin@reconcile.edu", password="AdminPass123", first_name="Admin", last_name="User",
            role="school_admin", tenant=self.school, is_active=True, is_verified=True,
        )
        self.parent_user = User.objects.create_user(
            email="parent@reconcile.edu", password="ParentPass123", first_name="Parent", last_name="User",
            role="parent", tenant=self.school, is_active=True, is_verified=True,
        )
        self.parent_profile = ParentProfile.objects.create(user=self.parent_user)

        self.student_user = User.objects.create_user(
            email="student@reconcile.edu", password="StudentPass123", first_name="Stu", last_name="Dent",
            role="student", tenant=self.school, is_active=True, is_verified=True,
        )
        school_class = Class.objects.create(tenant=self.legacy_tenant, name="Basic 1", section="A")
        self.student = StudentProfile.objects.create(
            user=self.student_user, student_id="STR001", admission_number="ADM-R-001",
            admission_date=timezone.localdate(), guardian_name="Guardian", guardian_relation="Parent",
            current_class=school_class,
        )
        self.parent_profile.children.add(self.student)

        self.fee = SchoolFee.objects.create(
            student=self.student, title="Term Fee", amount=Decimal("50000.00"),
            due_date=timezone.localdate(), status=SchoolFee.STATUS_PENDING,
        )

        self.vac = ParentVirtualAccount.objects.create(
            parent=self.parent_user, tenant=self.school,
            account_number="1234567890", bank_name="Test Bank", account_name="Parent User",
        )

    def test_partial_dva_payment_reconciles_fee_amount_paid(self):
        result = process_virtual_account_payment(
            tenant=self.school,
            account_number=self.vac.account_number,
            amount_naira=Decimal("30000.00"),
            paystack_reference="DVA-TEST-PARTIAL",
        )
        self.assertEqual(result["status"], "success")

        self.fee.refresh_from_db()
        self.assertEqual(self.fee.status, SchoolFee.STATUS_PARTIAL)
        # This is the exact bug: amount_paid on the model was correct, but
        # fee_paid_amount() (what the admin table and student dashboard both
        # read) used to ignore FeeAllocation rows and report 0 here.
        self.assertEqual(fee_paid_amount(self.fee), Decimal("30000.00"))

    def test_full_dva_payment_reconciles_fee_status_and_amount(self):
        process_virtual_account_payment(
            tenant=self.school,
            account_number=self.vac.account_number,
            amount_naira=Decimal("50000.00"),
            paystack_reference="DVA-TEST-FULL",
        )
        self.fee.refresh_from_db()
        self.assertEqual(self.fee.status, SchoolFee.STATUS_PAID)
        self.assertEqual(fee_paid_amount(self.fee), Decimal("50000.00"))

    def test_dva_payment_appears_on_admin_finance_ledger(self):
        process_virtual_account_payment(
            tenant=self.school,
            account_number=self.vac.account_number,
            amount_naira=Decimal("50000.00"),
            paystack_reference="DVA-TEST-LEDGER",
        )
        tx = Transaction.objects.get(paystack_ref="DVA-TEST-LEDGER")

        client = APIClient()
        client.force_authenticate(self.admin_user)
        response = client.get("/api/finance/admin/overview/")

        self.assertEqual(response.status_code, 200)
        ledger_ids = [row["id"] for row in response.data["transaction_history"]]
        self.assertIn(str(tx.id), ledger_ids)

    def test_dva_payment_writes_a_finance_ledger_log_entry(self):
        process_virtual_account_payment(
            tenant=self.school,
            account_number=self.vac.account_number,
            amount_naira=Decimal("50000.00"),
            paystack_reference="DVA-TEST-AUDIT",
        )
        self.assertTrue(
            FinanceLedgerLog.objects.filter(tenant=self.school, reference="DVA-TEST-AUDIT").exists()
        )

    def test_dva_payment_appears_in_students_own_wallet_transactions(self):
        process_virtual_account_payment(
            tenant=self.school,
            account_number=self.vac.account_number,
            amount_naira=Decimal("50000.00"),
            paystack_reference="DVA-TEST-STUDENT",
        )
        tx = Transaction.objects.get(paystack_ref="DVA-TEST-STUDENT")

        client = APIClient()
        client.force_authenticate(self.student_user)
        response = client.get("/api/finance/wallet/")

        self.assertEqual(response.status_code, 200)
        transaction_ids = [row["id"] for row in response.data["transactions"]]
        self.assertIn(str(tx.id), transaction_ids)

    def test_dva_payment_sets_school_id_from_parents_tenant(self):
        process_virtual_account_payment(
            tenant=None,  # simulates Paystack metadata not resolving a tenant
            account_number=self.vac.account_number,
            amount_naira=Decimal("50000.00"),
            paystack_reference="DVA-TEST-NOTENANT",
        )
        # school_id is a UUIDField storing the (int) SchoolTenant pk - filtering
        # the same way the admin ledger query does is the real contract here.
        self.assertTrue(
            Transaction.objects.filter(paystack_ref="DVA-TEST-NOTENANT", school_id=self.school.id).exists()
        )

    def test_second_partial_payment_sms_shows_true_outstanding_not_stale_figure(self):
        """Regression: the SMS used to compute 'Outstanding' as fee_total minus
        only *this* transaction's amount, ignoring what was already paid
        before - so a second payment's SMS showed a stale, too-high balance."""
        self.parent_user.phone = "+2348012345678"
        self.parent_user.save(update_fields=["phone"])

        with patch("finance.services.send_ebulksms") as mock_sms:
            mock_sms.return_value = {"status": "success"}
            process_virtual_account_payment(
                tenant=self.school, account_number=self.vac.account_number,
                amount_naira=Decimal("20000.00"), paystack_reference="DVA-TEST-FIRST",
            )
            process_virtual_account_payment(
                tenant=self.school, account_number=self.vac.account_number,
                amount_naira=Decimal("20000.00"), paystack_reference="DVA-TEST-SECOND",
            )

        self.fee.refresh_from_db()
        self.assertEqual(self.fee.amount_paid, Decimal("40000.00"))
        second_call_message = mock_sms.call_args_list[1].args[1]
        # True outstanding after both payments: 50000 - 40000 = 10000.
        self.assertIn("Outstanding: 10,000", second_call_message)
        self.assertNotIn("Outstanding: 30,000", second_call_message)


class PaystackReceiptMessageTests(TestCase):
    """Unit coverage for the SMS receipt text helpers themselves."""

    def test_balance_remaining_override_is_used_when_provided(self):
        message = build_paystack_receipt_message(
            "Adaeze Chukwuemeka", "JSS 2", Decimal("20000"), Decimal("50000"), "partial",
            school_name="Test School", balance_remaining=Decimal("10000"),
        )
        self.assertIn("Outstanding: 10,000", message)

    def test_balance_remaining_falls_back_to_naive_calc_when_not_provided(self):
        message = build_paystack_receipt_message(
            "Adaeze Chukwuemeka", "JSS 2", Decimal("20000"), Decimal("50000"), "partial",
            school_name="Test School",
        )
        self.assertIn("Outstanding: 30,000", message)

    def test_receipt_link_is_never_truncated_even_with_a_long_message(self):
        long_message = "A" * 200
        combined = _sms_message_with_receipt_link(long_message, "https://schooldom.academy/r/abcd1234")
        self.assertIn("schooldom.academy/r/abcd1234", combined)
        self.assertLessEqual(len(combined), SMS_CHAR_LIMIT)

    def test_receipt_link_untouched_for_a_short_message(self):
        combined = _sms_message_with_receipt_link("Short message.", "https://schooldom.academy/r/abcd1234")
        self.assertEqual(combined, "Short message. Receipt: www.schooldom.academy/r/abcd1234")

    def test_compact_url_keeps_www_prefix_so_sms_apps_auto_detect_it(self):
        # A bare domain with no scheme/www. isn't reliably auto-linkified by
        # phone SMS apps (this is the exact bug reported: link visible as
        # plain text, not tappable) - www. is the shortest reliable prefix.
        from finance.services import sms_compact_url
        self.assertEqual(sms_compact_url("https://schooldom.academy/r/abcd1234"), "www.schooldom.academy/r/abcd1234")
        self.assertEqual(sms_compact_url("https://www.schooldom.academy/r/abcd1234"), "www.schooldom.academy/r/abcd1234")
