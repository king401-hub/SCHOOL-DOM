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
    SchoolFee,
    StudentPaymentReference,
    Transaction,
)
from finance.services import (
    ACTIVATION_CREDIT_PRICE,
    activation_credit_bonus_for_purchase,
    complete_wallet_funding,
    deduct_document_generation_credit,
    ensure_student_wallet,
    fee_paid_amount,
    get_or_create_activation_credit_pool,
    get_or_create_student_payment_reference,
    sync_class_fee_assignments,
    verify_activation_credit_purchase,
)
from notifications.models import Notification
from tenants.models import Tenant
from users.models import StudentProfile, User, generate_short_student_id, generate_short_teacher_id


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
