from decimal import Decimal
from unittest.mock import patch

from django.test import TestCase
from django.utils import timezone

from core.models import SchoolTenant
from finance.models import ActivationCreditTransaction, StudentPaymentReference
from finance.services import (
    ACTIVATION_CREDIT_PRICE,
    activation_credit_bonus_for_purchase,
    get_or_create_activation_credit_pool,
    get_or_create_student_payment_reference,
    verify_activation_credit_purchase,
)
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
