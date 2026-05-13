"""API endpoints for wallet and fee management."""
from decimal import Decimal
from hmac import compare_digest
from datetime import datetime

from django.conf import settings
from django.db.models import Count, Q, Sum
from django.utils import timezone
from django.utils.dateparse import parse_date
from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from django.views.decorators.csrf import csrf_exempt
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from academic.models import Class
from finance.models import (
    ActivationCreditPool,
    ActivationCreditTransaction,
    AdminWallet,
    BankPayment,
    ClassFee,
    ExpenseRecord,
    SchoolFee,
    StudentActivationCredit,
    StudentPaymentReference,
    Transaction,
    Wallet,
)
from finance.serializers import (
    ActivationCreditPoolSerializer,
    AdminWalletSerializer,
    BankPaymentSerializer,
    ClassFeeSerializer,
    ExpenseRecordSerializer,
    SchoolFeeSerializer,
    StudentPaymentReferenceSerializer,
    TransactionSerializer,
    WalletSerializer,
)
from finance.services import (
    activation_credit_bonus_for_purchase,
    credit_wallet,
    debit_wallet,
    ensure_student_wallet,
    add_activation_credits_to_pool,
    assign_monthly_activation_credits,
    eligible_students_for_activation_credits,
    ensure_monthly_credit_reminder,
    generate_reference,
    get_or_create_admin_wallet,
    get_or_create_activation_credit_pool,
    get_or_create_student_activation_credit,
    initialize_activation_credit_purchase,
    initialize_flutterwave_transaction,
    initiate_admin_withdrawal,
    process_due_fees,
    fee_paid_amount,
    sync_class_fee_assignments,
    sync_student_class_fees,
    sync_tenant_class_fees,
    run_configured_monthly_auto_assignment,
    complete_flutterwave_reference,
    complete_wallet_funding,
    get_or_create_student_payment_reference,
    ingest_bank_payment,
    apply_bank_payment_to_student,
    update_student_activation_alerts,
    verify_activation_credit_purchase,
)
from hr.models import PayrollRecord
from tenants.models import Tenant
from users.models import StudentProfile, User


ADMIN_ROLES = {"school_admin", "principal", "super_admin"}


def _parse_amount(raw_amount):
    try:
        amount = Decimal(str(raw_amount))
        if amount <= 0:
            raise ValueError
        return amount.quantize(Decimal("0.01"))
    except Exception:
        raise ValueError("Enter a valid positive amount.")


def _parse_bool(value, default=True):
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


def _legacy_tenant_for_user(user):
    if not getattr(user, "tenant", None):
        return None
    tenant, _ = Tenant.objects.get_or_create(
        slug=user.tenant.schema_name,
        defaults={"name": user.tenant.name},
    )
    return tenant


def _class_label(class_obj):
    if not class_obj:
        return "Unassigned"
    section = getattr(class_obj, "section", "") or ""
    return f"{class_obj.name} - {section}" if section else class_obj.name


def _school_payload(request, school):
    if not school:
        return {}
    try:
        logo = request.build_absolute_uri(school.logo.url) if school.logo else ""
    except Exception:
        logo = ""
    return {
        "id": school.id,
        "name": school.name,
        "school_code": school.schema_name,
        "email": school.email or "",
        "phone": school.phone or "",
        "address": school.address or "",
        "logo": logo,
    }


def _classes_for_user(user):
    legacy_tenant = _legacy_tenant_for_user(user)
    if not legacy_tenant:
        return Class.objects.none()
    return Class.objects.filter(tenant=legacy_tenant)


def _admin_finance_snapshot(user):
    sync_tenant_class_fees(user.tenant, actor=user)
    update_student_activation_alerts(user.tenant)
    ensure_monthly_credit_reminder(user.tenant)
    try:
        run_configured_monthly_auto_assignment(user.tenant, actor=user)
    except ValueError:
        pass

    students = list(
        StudentProfile.objects.select_related("user", "current_class")
        .filter(user__tenant=user.tenant)
        .order_by("user__last_name", "user__first_name", "created_at")
    )
    class_ids = list(_classes_for_user(user).values_list("id", flat=True))
    class_fees = list(
        ClassFee.objects.select_related("school_class")
        .filter(is_active=True, school_class_id__in=class_ids)
        .order_by("school_class__name", "school_class__section", "due_date", "title")
    )
    fees_by_class = {}
    for class_fee in class_fees:
        fees_by_class.setdefault(class_fee.school_class_id, []).append(class_fee)

    generated_fees = SchoolFee.objects.filter(
        student__in=students,
        class_fee__in=class_fees,
    ).select_related("student", "class_fee")
    fee_by_student_and_class_fee = {
        (fee.student_id, fee.class_fee_id): fee
        for fee in generated_fees
    }

    student_rows = []
    activation_rows = []
    expected_total = Decimal("0.00")
    amount_received = Decimal("0.00")
    pending_payments = 0
    active_credit_count = 0
    inactive_credit_count = 0
    excluded_credit_count = 0

    for student in students:
        activation_credit = get_or_create_student_activation_credit(student)
        has_login_credit = activation_credit.has_login_credit
        if has_login_credit:
            active_credit_count += 1
        else:
            inactive_credit_count += 1
        if activation_credit.is_excluded_from_auto_deductions:
            excluded_credit_count += 1

        expected_for_student = Decimal("0.00")
        paid_for_student = Decimal("0.00")
        for class_fee in fees_by_class.get(student.current_class_id, []):
            expected_for_student += class_fee.amount
            fee = fee_by_student_and_class_fee.get((student.id, class_fee.id))
            if fee:
                paid_for_student += fee_paid_amount(fee)

        remaining = max(expected_for_student - paid_for_student, Decimal("0.00"))
        if expected_for_student <= 0:
            payment_status = "unassigned"
        elif remaining <= 0:
            payment_status = "paid"
        elif paid_for_student > 0:
            payment_status = "partial"
        else:
            payment_status = "pending"

        if remaining > 0:
            pending_payments += 1
        expected_total += expected_for_student
        amount_received += paid_for_student
        payment_reference = get_or_create_student_payment_reference(student)
        student_rows.append(
            {
                "id": str(student.id),
                "name": student.user.get_full_name() or student.user.email,
                "student_id": student.student_id or student.admission_number,
                "class_name": _class_label(student.current_class),
                "payment_reference": payment_reference.code,
                "payment_status": payment_status,
                "expected_amount": expected_for_student,
                "amount_paid": paid_for_student,
                "remaining_balance": remaining,
                "has_login_credit": has_login_credit,
                "activation_active_until": activation_credit.active_until,
                "credit_excluded": activation_credit.is_excluded_from_auto_deductions,
            }
        )
        activation_rows.append(
            {
                "id": str(activation_credit.id),
                "student_id": str(student.id),
                "student_name": student.user.get_full_name() or student.user.email,
                "student_identifier": student.student_id or student.admission_number,
                "class_name": _class_label(student.current_class),
                "active_until": activation_credit.active_until,
                "credits_assigned": activation_credit.credits_assigned,
                "inactive_since": activation_credit.inactive_since,
                "inactive_flagged_at": activation_credit.inactive_flagged_at,
                "is_excluded_from_auto_deductions": activation_credit.is_excluded_from_auto_deductions,
                "has_login_credit": has_login_credit,
                "paid_ratio": float(_student_paid_ratio_for_snapshot(expected_for_student, paid_for_student)),
            }
        )

    class_counts = (
        StudentProfile.objects.filter(user__tenant=user.tenant, current_class__isnull=False)
        .values("current_class")
        .annotate(total=Count("id"))
    )
    count_by_class = {entry["current_class"]: entry["total"] for entry in class_counts}
    class_fee_rows = []
    for class_fee in class_fees:
        student_count = count_by_class.get(class_fee.school_class_id, 0)
        generated_for_fee = [fee for fee in generated_fees if fee.class_fee_id == class_fee.id]
        paid_for_fee = sum((fee_paid_amount(fee) for fee in generated_for_fee), Decimal("0.00"))
        expected_for_fee = class_fee.amount * student_count
        class_fee_rows.append(
            {
                "id": str(class_fee.id),
                "school_class": class_fee.school_class_id,
                "class_label": _class_label(class_fee.school_class),
                "title": class_fee.title,
                "amount": class_fee.amount,
                "currency": class_fee.currency,
                "due_date": class_fee.due_date,
                "is_active": class_fee.is_active,
                "student_count": student_count,
                "expected_amount": expected_for_fee,
                "amount_received": paid_for_fee,
                "outstanding_amount": max(expected_for_fee - paid_for_fee, Decimal("0.00")),
            }
        )

    pool = get_or_create_activation_credit_pool(user.tenant)
    bank_payments = BankPayment.objects.select_related("student", "student__user", "payment_reference").filter(tenant=user.tenant)
    transaction_history = Transaction.objects.filter(admin_wallet__tenant=user.tenant).order_by("-created_at")[:100]
    credit_purchase_history = [
        {
            "id": str(item.id),
            "reference": item.reference,
            "credits": item.credits,
            "purchased_credits": (item.metadata or {}).get("purchased_credits", item.credits),
            "bonus_credits": (item.metadata or {}).get("bonus_credits", 0),
            "total_credits": (item.metadata or {}).get("total_credits", item.credits),
            "amount": item.amount,
            "currency": pool.currency,
            "price_per_credit": item.price_per_credit,
            "status": item.status,
            "provider": item.provider,
            "narration": item.narration,
            "created_by": item.created_by.get_full_name() if item.created_by else "",
            "created_at": item.created_at,
        }
        for item in pool.transactions.filter(tx_type=ActivationCreditTransaction.PURCHASE)
        .select_related("created_by")
        .order_by("-created_at")[:100]
    ]
    return {
        "expected_fee_amount": expected_total,
        "amount_received": amount_received,
        "outstanding_balance": max(expected_total - amount_received, Decimal("0.00")),
        "pending_payments": pending_payments,
        "debtors_count": sum(1 for row in student_rows if row["remaining_balance"] > 0),
        "confirmed_bank_payments": bank_payments.filter(status__in=[BankPayment.STATUS_CONFIRMED, BankPayment.STATUS_PARTIAL]).count(),
        "unmatched_bank_payments": bank_payments.filter(status=BankPayment.STATUS_UNMATCHED).count(),
        "student_payment_rows": student_rows,
        "class_fee_rows": class_fee_rows,
        "bank_payment_rows": BankPaymentSerializer(bank_payments[:100], many=True).data,
        "transaction_history": TransactionSerializer(transaction_history, many=True).data,
        "activation_credit_pool": ActivationCreditPoolSerializer(pool).data,
        "activation_credit_summary": {
            "price_per_credit": pool.price_per_credit,
            "available_credits": pool.balance,
            "active_students": active_credit_count,
            "inactive_students": inactive_credit_count,
            "excluded_students": excluded_credit_count,
            "eligible_all": len(eligible_students_for_activation_credits(user.tenant, scope="all")),
            "eligible_paid_50": len(eligible_students_for_activation_credits(user.tenant, scope="paid_50")),
        },
        "activation_credit_rows": activation_rows,
        "activation_credit_purchase_history": credit_purchase_history,
    }


def _student_paid_ratio_for_snapshot(expected, paid):
    if not expected:
        return Decimal("0.00")
    return min(Decimal("1.00"), Decimal(paid) / Decimal(expected))


def _student_wallet_snapshot(user):
    """
    Shared helper to return wallet, transactions, and fees for a student.
    Ensures the wallet exists and processes due fees before serialization.
    """
    if user.role != "student":
        return None, None, None, None, None

    wallet = Wallet.objects.filter(user=user).first()
    if not wallet:
        wallet = ensure_student_wallet(user)

    student_profile = StudentProfile.objects.filter(user=user).first()
    if student_profile:
        sync_student_class_fees(student_profile, actor=user)
        process_due_fees(student_profile, actor=user)
    payment_reference = get_or_create_student_payment_reference(student_profile) if student_profile else None
    bank_payments = BankPayment.objects.filter(student=student_profile).order_by("-created_at")[:20] if student_profile else BankPayment.objects.none()

    wallet = (
        Wallet.objects.select_related("user")
        .prefetch_related("transactions")
        .get(pk=wallet.pk)
    )
    transactions = wallet.transactions.order_by("-created_at")[:20]
    fees = SchoolFee.objects.filter(student__user=user).order_by("due_date")[:12]
    return wallet, transactions, fees, payment_reference, bank_payments


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def wallet_summary(request):
    """Return the student's wallet, transactions, and fees."""
    user = request.user
    wallet, transactions, fees, payment_reference, bank_payments = _student_wallet_snapshot(user)
    if wallet is None:
        return Response({"success": False, "message": "Only students have wallets."}, status=status.HTTP_403_FORBIDDEN)

    admin_wallet = get_or_create_admin_wallet(user.tenant)
    return Response(
        {
            "success": True,
            "school": _school_payload(request, user.tenant),
            "wallet": WalletSerializer(wallet).data,
            "transactions": TransactionSerializer(transactions, many=True).data,
            "fees": SchoolFeeSerializer(fees, many=True).data,
            "payment_reference": StudentPaymentReferenceSerializer(payment_reference).data if payment_reference else None,
            "bank_payments": BankPaymentSerializer(bank_payments, many=True).data,
            "payment_instructions": {
                "bank_account_name": admin_wallet.bank_account_name,
                "bank_account_number": admin_wallet.bank_account_number,
                "bank_name": admin_wallet.bank_code,
                "bank_code": admin_wallet.bank_code,
                "reference_code": payment_reference.code if payment_reference else "",
                "narration": f"School fees {payment_reference.code}" if payment_reference else "",
            },
        }
    )


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def wallet_fund(request):
    """Initialize Flutterwave school-fee payment for a student."""
    user = request.user
    if user.role != "student":
        return Response({"success": False, "message": "Only students can fund this wallet."}, status=status.HTTP_403_FORBIDDEN)

    wallet = ensure_student_wallet(user)
    try:
        amount = _parse_amount(request.data.get("amount"))
    except ValueError as exc:
        return Response({"success": False, "message": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

    reference = generate_reference("PAY")
    tx = Transaction.objects.create(
        wallet=wallet,
        amount=amount,
        currency=wallet.currency,
        tx_type=Transaction.FUNDING,
        status=Transaction.STATUS_PENDING,
        reference=reference,
        provider="flutterwave",
        narration="School fee payment via Flutterwave",
        created_by=user,
        metadata={"requested_amount": float(amount)},
    )

    try:
        init_payload = initialize_flutterwave_transaction(
            user=user,
            amount=amount,
            reference=reference,
            metadata={"user_id": str(user.id), "wallet_id": str(wallet.id)},
        )
    except Exception as exc:
        tx.status = Transaction.STATUS_FAILED
        tx.metadata = {"error": str(exc)}
        tx.save(update_fields=["status", "metadata", "updated_at"])
        return Response(
            {"success": False, "message": str(exc)},
            status=status.HTTP_400_BAD_REQUEST,
        )

    tx.metadata.update({"access_code": init_payload.get("access_code")})
    tx.save(update_fields=["metadata", "updated_at"])

    return Response(
        {
            "success": True,
            "authorization_url": init_payload.get("authorization_url") or init_payload.get("link"),
            "link": init_payload.get("link") or init_payload.get("authorization_url"),
            "reference": reference,
            "access_code": init_payload.get("access_code"),
            "message": "Flutterwave checkout initialized for school fee payment.",
        },
        status=status.HTTP_201_CREATED,
    )


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def wallet_verify(request):
    """Verify Flutterwave payment and move the funds to the admin wallet."""
    user = request.user
    if user.role != "student":
        return Response({"success": False, "message": "Only students can verify their wallet payments."}, status=status.HTTP_403_FORBIDDEN)

    reference = str(request.data.get("reference", "")).strip()
    if not reference:
        return Response({"success": False, "message": "reference is required."}, status=status.HTTP_400_BAD_REQUEST)

    tx = get_object_or_404(Transaction, reference=reference, wallet__user=user)
    if tx.status == Transaction.STATUS_SUCCESS:
        complete_wallet_funding(reference, actor=user)
        wallet, transactions, fees, payment_reference, bank_payments = _student_wallet_snapshot(user)
        admin_wallet = get_or_create_admin_wallet(user.tenant)
        return Response(
            {
                "success": True,
                "school": _school_payload(request, user.tenant),
                "wallet": WalletSerializer(wallet).data,
                "transactions": TransactionSerializer(transactions, many=True).data,
                "fees": SchoolFeeSerializer(fees, many=True).data,
                "payment_reference": StudentPaymentReferenceSerializer(payment_reference).data if payment_reference else None,
                "bank_payments": BankPaymentSerializer(bank_payments, many=True).data,
                "payment_instructions": {
                    "bank_account_name": admin_wallet.bank_account_name,
                    "bank_account_number": admin_wallet.bank_account_number,
                    "bank_name": admin_wallet.bank_code,
                    "bank_code": admin_wallet.bank_code,
                    "reference_code": payment_reference.code if payment_reference else "",
                    "narration": f"School fees {payment_reference.code}" if payment_reference else "",
                },
            }
        )

    try:
        complete_wallet_funding(reference, actor=user)
    except Exception as exc:
        return Response({"success": False, "message": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

    wallet, transactions, fees, payment_reference, bank_payments = _student_wallet_snapshot(user)
    admin_wallet = get_or_create_admin_wallet(user.tenant)
    return Response(
        {
            "success": True,
            "school": _school_payload(request, user.tenant),
            "wallet": WalletSerializer(wallet).data,
            "transactions": TransactionSerializer(transactions, many=True).data,
            "fees": SchoolFeeSerializer(fees, many=True).data,
            "payment_reference": StudentPaymentReferenceSerializer(payment_reference).data if payment_reference else None,
            "bank_payments": BankPaymentSerializer(bank_payments, many=True).data,
            "payment_instructions": {
                "bank_account_name": admin_wallet.bank_account_name,
                "bank_account_number": admin_wallet.bank_account_number,
                "bank_name": admin_wallet.bank_code,
                "bank_code": admin_wallet.bank_code,
                "reference_code": payment_reference.code if payment_reference else "",
                "narration": f"School fees {payment_reference.code}" if payment_reference else "",
            },
        }
    )


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def admin_overview(request):
    """Finance overview for administrators."""
    user = request.user
    if user.role not in ADMIN_ROLES:
        return Response({"success": False, "message": "Admin role required."}, status=status.HTTP_403_FORBIDDEN)

    admin_wallet = get_or_create_admin_wallet(user.tenant)
    finance_snapshot = _admin_finance_snapshot(user)
    overdue_fees = SchoolFee.objects.filter(
        student__user__tenant=user.tenant,
        status=SchoolFee.STATUS_OVERDUE,
    ).count()
    pending_fees = SchoolFee.objects.filter(
        student__user__tenant=user.tenant,
        status=SchoolFee.STATUS_PENDING,
    ).count()
    recent_student_wallets = Wallet.objects.filter(user__tenant=user.tenant).select_related("user").order_by("-created_at")[:8]
    recent_students_payload = []
    try:
        recent_students = (
            StudentProfile.objects.select_related("user", "current_class")
            .filter(user__tenant=user.tenant)
            .order_by("-created_at")[:8]
        )
        recent_students_payload = [
            {
                "id": str(s.id),
                "name": s.user.get_full_name() or s.user.email,
                "student_id": getattr(s, "student_id", "") or getattr(s, "admission_number", "") or getattr(s, "registration_no", ""),
                "class_name": getattr(s, "current_class", None).name if getattr(s, "current_class", None) else "",
                "created_at": s.created_at,
            }
            for s in recent_students
        ]
    except Exception:
        # If anything goes wrong (e.g., legacy data mismatch), don't fail the entire overview.
        recent_students_payload = []
    return Response(
        {
            "success": True,
            "admin_wallet": AdminWalletSerializer(admin_wallet).data,
            "pending_fees": pending_fees,
            "overdue_fees": overdue_fees,
            "expected_fee_amount": finance_snapshot["expected_fee_amount"],
            "amount_received": finance_snapshot["amount_received"],
            "outstanding_balance": finance_snapshot["outstanding_balance"],
            "pending_payments": finance_snapshot["pending_payments"],
            "debtors_count": finance_snapshot["debtors_count"],
            "confirmed_bank_payments": finance_snapshot["confirmed_bank_payments"],
            "unmatched_bank_payments": finance_snapshot["unmatched_bank_payments"],
            "student_payment_rows": finance_snapshot["student_payment_rows"],
            "class_fee_rows": finance_snapshot["class_fee_rows"],
            "bank_payment_rows": finance_snapshot["bank_payment_rows"],
            "transaction_history": finance_snapshot["transaction_history"],
            "activation_credit_pool": finance_snapshot["activation_credit_pool"],
            "activation_credit_summary": finance_snapshot["activation_credit_summary"],
            "activation_credit_rows": finance_snapshot["activation_credit_rows"],
            "activation_credit_purchase_history": finance_snapshot["activation_credit_purchase_history"],
            "class_options": [
                {
                    "id": item.id,
                    "label": _class_label(item),
                }
                for item in _classes_for_user(user).order_by("name", "section")[:200]
            ],
            "recent_student_wallets": [
                {
                    "id": str(w.user.id),
                    "name": w.user.get_full_name() or w.user.email,
                    "balance": w.balance,
                    "currency": w.currency,
                }
                for w in recent_student_wallets
            ],
            "recent_students": recent_students_payload,
            "announcements": [],
        }
    )


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def admin_payment_account(request):
    """Save the school bank account shown to students for fee transfers."""
    user = request.user
    if user.role not in ADMIN_ROLES:
        return Response({"success": False, "message": "Admin role required."}, status=status.HTTP_403_FORBIDDEN)

    bank_account_name = str(request.data.get("bank_account_name") or request.data.get("account_name") or "").strip()
    bank_account_number = str(request.data.get("bank_account_number") or request.data.get("account_number") or "").strip()
    bank_code = str(request.data.get("bank_name") or request.data.get("bank_code") or "").strip()

    if not bank_account_name:
        return Response({"success": False, "message": "Account name is required."}, status=status.HTTP_400_BAD_REQUEST)
    if not bank_account_number:
        return Response({"success": False, "message": "Account number is required."}, status=status.HTTP_400_BAD_REQUEST)
    if not bank_account_number.isdigit() or not 6 <= len(bank_account_number) <= 20:
        return Response(
            {"success": False, "message": "Enter a valid account number using 6 to 20 digits."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    admin_wallet = get_or_create_admin_wallet(user.tenant)
    admin_wallet.bank_account_name = bank_account_name
    admin_wallet.bank_account_number = bank_account_number
    admin_wallet.bank_code = bank_code
    admin_wallet.save(update_fields=["bank_account_name", "bank_account_number", "bank_code", "updated_at"])

    return Response(
        {
            "success": True,
            "admin_wallet": AdminWalletSerializer(admin_wallet).data,
            "message": "School fee receiving account saved.",
        }
    )


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def admin_class_fee_create(request):
    """Create a class fee and sync it to students in that class."""
    user = request.user
    if user.role not in ADMIN_ROLES:
        return Response({"success": False, "message": "Admin role required."}, status=status.HTTP_403_FORBIDDEN)

    title = str(request.data.get("title", "")).strip() or "School Fee"
    school_class_id = request.data.get("school_class") or request.data.get("class_id")
    due_date = parse_date(str(request.data.get("due_date", "")).strip())
    if not due_date:
        return Response({"success": False, "message": "due_date must be YYYY-MM-DD."}, status=status.HTTP_400_BAD_REQUEST)

    try:
        amount = _parse_amount(request.data.get("amount"))
    except ValueError as exc:
        return Response({"success": False, "message": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

    school_class = get_object_or_404(_classes_for_user(user), id=school_class_id)
    class_fee, _ = ClassFee.objects.update_or_create(
        school_class=school_class,
        title=title,
        due_date=due_date,
        defaults={
            "amount": amount,
            "currency": "NGN",
            "is_active": _parse_bool(request.data.get("is_active"), default=True),
            "created_by": user,
        },
    )
    sync_class_fee_assignments(class_fee, actor=user)
    return Response({"success": True, "class_fee": ClassFeeSerializer(class_fee).data}, status=status.HTTP_201_CREATED)


@api_view(["PATCH", "DELETE"])
@permission_classes([IsAuthenticated])
def admin_class_fee_detail(request, fee_id):
    """Edit or deactivate a class fee."""
    user = request.user
    if user.role not in ADMIN_ROLES:
        return Response({"success": False, "message": "Admin role required."}, status=status.HTTP_403_FORBIDDEN)

    class_fee = get_object_or_404(
        ClassFee.objects.select_related("school_class").filter(school_class__in=_classes_for_user(user)),
        id=fee_id,
    )
    if request.method == "DELETE":
        class_fee.is_active = False
        class_fee.save(update_fields=["is_active", "updated_at"])
        return Response({"success": True, "message": "Class fee deactivated."})

    update_fields = []
    if "title" in request.data:
        title = str(request.data.get("title") or "").strip()
        if not title:
            return Response({"success": False, "message": "title cannot be blank."}, status=status.HTTP_400_BAD_REQUEST)
        class_fee.title = title
        update_fields.append("title")
    if "amount" in request.data:
        try:
            class_fee.amount = _parse_amount(request.data.get("amount"))
        except ValueError as exc:
            return Response({"success": False, "message": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        update_fields.append("amount")
    if "due_date" in request.data:
        due_date = parse_date(str(request.data.get("due_date") or "").strip())
        if not due_date:
            return Response({"success": False, "message": "due_date must be YYYY-MM-DD."}, status=status.HTTP_400_BAD_REQUEST)
        class_fee.due_date = due_date
        update_fields.append("due_date")
    if "is_active" in request.data:
        class_fee.is_active = _parse_bool(request.data.get("is_active"), default=True)
        update_fields.append("is_active")
    if "school_class" in request.data or "class_id" in request.data:
        school_class_id = request.data.get("school_class") or request.data.get("class_id")
        class_fee.school_class = get_object_or_404(_classes_for_user(user), id=school_class_id)
        update_fields.append("school_class")

    if update_fields:
        update_fields.append("updated_at")
        class_fee.save(update_fields=sorted(set(update_fields)))
        sync_class_fee_assignments(class_fee, actor=user)
    return Response({"success": True, "class_fee": ClassFeeSerializer(class_fee).data})


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def admin_activation_credit_purchase(request):
    """Add purchased activation tokens to the school pool at fixed N200 per token."""
    user = request.user
    if user.role not in ADMIN_ROLES:
        return Response({"success": False, "message": "Admin role required."}, status=status.HTTP_403_FORBIDDEN)

    try:
        credits = int(request.data.get("credits") or 0)
        init_payload = initialize_activation_credit_purchase(user.tenant, credits, actor=user)
        bonus_credits = activation_credit_bonus_for_purchase(credits)
    except ValueError as exc:
        return Response({"success": False, "message": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
    except Exception as exc:
        return Response({"success": False, "message": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

    return Response(
        {
            "success": True,
            "authorization_url": init_payload.get("authorization_url") or init_payload.get("link"),
            "link": init_payload.get("link") or init_payload.get("authorization_url"),
            "access_code": init_payload.get("access_code"),
            "reference": init_payload.get("reference"),
            "amount": init_payload.get("amount"),
            "credits": credits,
            "bonus_credits": bonus_credits,
            "total_credits": credits + bonus_credits,
            "message": f"Flutterwave checkout initialized for {credits} activation tokens plus {bonus_credits} free bonus tokens.",
        },
        status=status.HTTP_201_CREATED,
    )


@csrf_exempt
@api_view(["POST"])
@permission_classes([])
def flutterwave_webhook(request):
    """Complete successful Flutterwave payments as soon as Flutterwave notifies us."""
    configured_hash = getattr(settings, "FLUTTERWAVE_WEBHOOK_SECRET_HASH", "")
    received_hash = request.headers.get("verif-hash", "")
    if configured_hash and not compare_digest(received_hash, configured_hash):
        return Response({"success": False, "message": "Invalid webhook signature."}, status=status.HTTP_401_UNAUTHORIZED)

    payload = request.data or {}
    event = str(payload.get("event") or "").lower()
    data = payload.get("data") or {}
    reference = str(data.get("tx_ref") or data.get("reference") or payload.get("tx_ref") or "").strip()
    provider_status = str(data.get("status") or "").lower()

    if event and "charge" not in event:
        return Response({"success": True, "message": "Webhook ignored."})
    if provider_status and provider_status != "successful":
        return Response({"success": True, "message": "Payment is not successful yet."})
    if not reference:
        return Response({"success": False, "message": "Missing payment reference."}, status=status.HTTP_400_BAD_REQUEST)

    try:
        result = complete_flutterwave_reference(reference)
    except ValueError as exc:
        return Response({"success": True, "message": str(exc)})
    except Exception as exc:
        return Response({"success": False, "message": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

    return Response({"success": True, "message": "Payment completed.", **result})


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def admin_activation_credit_verify(request):
    """Verify a Flutterwave activation-token purchase and add tokens to the pool."""
    user = request.user
    if user.role not in ADMIN_ROLES:
        return Response({"success": False, "message": "Admin role required."}, status=status.HTTP_403_FORBIDDEN)

    reference = str(request.data.get("reference") or "").strip()
    if not reference:
        return Response({"success": False, "message": "reference is required."}, status=status.HTTP_400_BAD_REQUEST)

    try:
        pool = verify_activation_credit_purchase(reference, actor=user)
    except (ActivationCreditTransaction.DoesNotExist, ValueError) as exc:
        return Response({"success": False, "message": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
    except Exception as exc:
        return Response({"success": False, "message": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

    return Response({"success": True, "pool": ActivationCreditPoolSerializer(pool).data})


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def admin_activation_credit_assign(request):
    """Assign monthly activation tokens to all students or students with at least 50% fees paid."""
    user = request.user
    if user.role not in ADMIN_ROLES:
        return Response({"success": False, "message": "Admin role required."}, status=status.HTTP_403_FORBIDDEN)

    scope = str(request.data.get("scope") or "all").strip()
    try:
        months = int(request.data.get("months") or 1)
        result = assign_monthly_activation_credits(user.tenant, scope=scope, months=months, actor=user, auto=False)
    except ValueError as exc:
        return Response({"success": False, "message": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

    return Response(
        {
            "success": True,
            "assigned": result["assigned"],
            "pool": ActivationCreditPoolSerializer(result["pool"]).data,
        }
    )


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def admin_activation_credit_settings(request):
    """Enable or disable monthly auto-assignment of activation tokens."""
    user = request.user
    if user.role not in ADMIN_ROLES:
        return Response({"success": False, "message": "Admin role required."}, status=status.HTTP_403_FORBIDDEN)

    pool = get_or_create_activation_credit_pool(user.tenant)
    scope = str(request.data.get("scope") or pool.auto_assign_scope or "all").strip()
    if scope not in {"all", "paid_50"}:
        return Response({"success": False, "message": "scope must be 'all' or 'paid_50'."}, status=status.HTTP_400_BAD_REQUEST)
    pool.auto_assign_enabled = _parse_bool(request.data.get("enabled"), default=pool.auto_assign_enabled)
    pool.auto_assign_scope = scope
    pool.save(update_fields=["auto_assign_enabled", "auto_assign_scope", "updated_at"])
    return Response({"success": True, "pool": ActivationCreditPoolSerializer(pool).data})


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def admin_activation_credit_run_auto(request):
    """Run configured monthly auto-assignment now."""
    user = request.user
    if user.role not in ADMIN_ROLES:
        return Response({"success": False, "message": "Admin role required."}, status=status.HTTP_403_FORBIDDEN)

    pool = get_or_create_activation_credit_pool(user.tenant)
    if not pool.auto_assign_enabled:
        return Response({"success": False, "message": "Auto-assignment is disabled."}, status=status.HTTP_400_BAD_REQUEST)
    try:
        result = assign_monthly_activation_credits(
            user.tenant,
            scope=pool.auto_assign_scope,
            months=1,
            actor=user,
            auto=True,
        )
    except ValueError as exc:
        return Response({"success": False, "message": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
    return Response({"success": True, "assigned": result["assigned"], "pool": ActivationCreditPoolSerializer(result["pool"]).data})


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def admin_bank_payment_ingest(request):
    """Ingest bank statement rows and match transfer narrations to student references."""
    user = request.user
    if user.role not in ADMIN_ROLES:
        return Response({"success": False, "message": "Admin role required."}, status=status.HTTP_403_FORBIDDEN)

    rows = request.data.get("transactions")
    if not isinstance(rows, list):
        rows = [request.data]

    processed = []
    for row in rows:
        try:
            payment, created = ingest_bank_payment(
                tenant=user.tenant,
                amount=row.get("amount"),
                narration=row.get("narration") or row.get("description") or "",
                bank_reference=row.get("bank_reference") or row.get("reference"),
                currency=row.get("currency") or "NGN",
                metadata={"raw": row},
                actor=user,
            )
            processed.append({"created": created, "payment": BankPaymentSerializer(payment).data})
        except Exception as exc:
            processed.append({"created": False, "error": str(exc), "raw": row})

    return Response({"success": True, "processed": processed, "finance": _admin_finance_snapshot(user)})


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def admin_bank_payment_recover(request, payment_id):
    """Manually attach an unmatched or wrong-narration payment to the correct student."""
    user = request.user
    if user.role not in ADMIN_ROLES:
        return Response({"success": False, "message": "Admin role required."}, status=status.HTTP_403_FORBIDDEN)

    payment = get_object_or_404(BankPayment.objects.filter(tenant=user.tenant), id=payment_id)
    student_lookup = str(request.data.get("student_id") or request.data.get("student") or "").strip()
    reference_code = str(request.data.get("reference_code") or "").strip()
    student = None

    if reference_code:
        reference = get_object_or_404(StudentPaymentReference.objects.filter(tenant=user.tenant), code__iexact=reference_code)
        student = reference.student
    elif student_lookup:
        student_qs = StudentProfile.objects.select_related("user").filter(user__tenant=user.tenant)
        student = student_qs.filter(
            Q(student_id__iexact=student_lookup)
            | Q(admission_number__iexact=student_lookup)
            | Q(user__email__iexact=student_lookup)
        ).first()
        if not student:
            try:
                student = student_qs.filter(id=student_lookup).first()
            except Exception:
                student = None
    if not student:
        return Response({"success": False, "message": "Student not found."}, status=status.HTTP_404_NOT_FOUND)

    reference = get_or_create_student_payment_reference(student)
    payment.payment_reference = reference
    payment.save(update_fields=["payment_reference", "updated_at"])
    payment = apply_bank_payment_to_student(payment, student, actor=user)
    return Response({"success": True, "payment": BankPaymentSerializer(payment).data, "finance": _admin_finance_snapshot(user)})


@api_view(["GET", "POST"])
@permission_classes([IsAuthenticated])
def admin_expense_records(request):
    """List or create tenant-scoped bills, expenses, and receipts."""
    user = request.user
    if user.role not in ADMIN_ROLES:
        return Response({"success": False, "message": "Admin role required."}, status=status.HTTP_403_FORBIDDEN)

    if request.method == "GET":
        records = ExpenseRecord.objects.filter(tenant=user.tenant)
        finance_snapshot = _admin_finance_snapshot(user)
        payroll_records = PayrollRecord.objects.select_related("staff").filter(staff__tenant=user.tenant).order_by("-year", "-month")[:80]
        unsettled_payroll = [
            item
            for item in payroll_records
            if item.status != PayrollRecord.PAID or item.balance_after_payment > 0
        ]
        unsettled_payroll_total = sum((item.balance_after_payment for item in unsettled_payroll), Decimal("0.00"))
        return Response(
            {
                "success": True,
                "records": ExpenseRecordSerializer(records, many=True).data,
                "class_fee_rows": finance_snapshot["class_fee_rows"],
                "salary_payment_summary": {
                    "records": len(payroll_records),
                    "unsettled_count": len(unsettled_payroll),
                    "unsettled_amount": unsettled_payroll_total,
                },
                "salary_payment_rows": [
                    {
                        "id": str(item.id),
                        "staff_id": str(item.staff_id),
                        "staff_name": item.staff.full_name,
                        "period": item.period_label,
                        "net_salary": item.net_salary,
                        "amount_paid": item.amount_paid,
                        "balance_after_payment": item.balance_after_payment,
                        "status": item.status,
                    }
                    for item in payroll_records
                ],
                "class_options": [
                    {
                        "id": item.id,
                        "label": _class_label(item),
                    }
                    for item in _classes_for_user(user).order_by("name", "section")[:200]
                ],
            }
        )

    serializer = ExpenseRecordSerializer(data=request.data)
    if not serializer.is_valid():
        return Response({"success": False, "message": "Invalid expense record.", "errors": serializer.errors}, status=status.HTTP_400_BAD_REQUEST)
    record = serializer.save(tenant=user.tenant, created_by=user, currency="NGN")
    records = ExpenseRecord.objects.filter(tenant=user.tenant)
    return Response(
        {
            "success": True,
            "record": ExpenseRecordSerializer(record).data,
            "records": ExpenseRecordSerializer(records, many=True).data,
        },
        status=status.HTTP_201_CREATED,
    )


@api_view(["DELETE"])
@permission_classes([IsAuthenticated])
def admin_expense_record_detail(request, record_id):
    """Delete one tenant-scoped expense tracker record."""
    user = request.user
    if user.role not in ADMIN_ROLES:
        return Response({"success": False, "message": "Admin role required."}, status=status.HTTP_403_FORBIDDEN)

    record = get_object_or_404(ExpenseRecord.objects.filter(tenant=user.tenant), id=record_id)
    record.delete()
    records = ExpenseRecord.objects.filter(tenant=user.tenant)
    return Response({"success": True, "records": ExpenseRecordSerializer(records, many=True).data})


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def bank_payment_receipt(request, payment_id):
    """Download a lightweight receipt for a confirmed/partial bank payment."""
    user = request.user
    payments = BankPayment.objects.select_related("student", "student__user", "payment_reference", "tenant")
    if user.role == "student":
        payments = payments.filter(student__user=user)
    elif user.role in ADMIN_ROLES:
        payments = payments.filter(tenant=user.tenant)
    else:
        return Response({"success": False, "message": "Access denied."}, status=status.HTTP_403_FORBIDDEN)

    payment = get_object_or_404(payments, id=payment_id)
    if payment.status not in {BankPayment.STATUS_CONFIRMED, BankPayment.STATUS_PARTIAL}:
        return Response({"success": False, "message": "Receipt is available after a payment is confirmed."}, status=status.HTTP_400_BAD_REQUEST)

    school = payment.tenant
    student_name = payment.student.user.get_full_name() or payment.student.user.email if payment.student_id else "Unmatched"
    content = "\n".join(
        [
            f"{school.name if school else 'SchoolDom'} Payment Receipt",
            f"Logo: {getattr(school, 'logo', '') or 'School logo'}",
            f"Receipt: {payment.receipt_number or payment.bank_reference}",
            f"Student: {student_name}",
            f"Reference Code: {payment.payment_reference.code if payment.payment_reference_id else ''}",
            f"Amount: {payment.currency} {payment.amount}",
            f"Applied: {payment.currency} {payment.applied_amount}",
            f"Status: {payment.status.title()}",
            f"Bank Reference: {payment.bank_reference}",
            f"Narration: {payment.narration}",
            f"Date: {payment.matched_at or payment.created_at}",
        ]
    )
    response = HttpResponse(content, content_type="text/plain")
    response["Content-Disposition"] = f'attachment; filename="receipt-{payment.receipt_number or payment.bank_reference}.txt"'
    return response


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def admin_adjust_wallet(request):
    """Allow admins to adjust an existing student wallet balance."""
    user = request.user
    if user.role not in ADMIN_ROLES:
        return Response({"success": False, "message": "Admin role required."}, status=status.HTTP_403_FORBIDDEN)

    student_id = request.data.get("student_id")
    direction = str(request.data.get("direction", "")).lower()
    note = str(request.data.get("note", "")).strip() or "Manual adjustment"

    try:
        amount = _parse_amount(request.data.get("amount"))
    except ValueError as exc:
        return Response({"success": False, "message": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

    lookup_value = str(student_id or "").strip()
    student_qs = StudentProfile.objects.select_related("user").filter(user__tenant=user.tenant)
    student_profile = None
    # Try UUID lookup first; if it fails, fall back to student identifiers
    try:
        student_profile = student_qs.get(id=lookup_value)
    except Exception:
        student_profile = student_qs.filter(
            Q(student_id=lookup_value) | Q(admission_number=lookup_value) | Q(user__email=lookup_value)
        ).first()
    if not student_profile:
        return Response({"success": False, "message": "Student not found."}, status=status.HTTP_404_NOT_FOUND)
    wallet = Wallet.objects.filter(user=student_profile.user).first()
    if not wallet:
        return Response(
            {"success": False, "message": "Student wallet not provisioned (wallets are created via student registration)."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    reference = generate_reference("ADJ")
    try:
        if direction == "credit":
            wallet = credit_wallet(wallet, amount, Transaction.ADJUSTMENT_CREDIT, reference, narration=note, created_by=user)
        elif direction == "debit":
            wallet = debit_wallet(wallet, amount, Transaction.ADJUSTMENT_DEBIT, reference, narration=note, created_by=user)
        else:
            return Response(
                {"success": False, "message": "direction must be 'credit' or 'debit'."},
                status=status.HTTP_400_BAD_REQUEST,
            )
    except ValueError as exc:
        return Response({"success": False, "message": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

    return Response(
        {
            "success": True,
            "wallet": WalletSerializer(wallet).data,
            "reference": reference,
        }
    )


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def admin_assign_fee(request):
    """Create a school fee schedule for a student."""
    user = request.user
    if user.role not in ADMIN_ROLES:
        return Response({"success": False, "message": "Admin role required."}, status=status.HTTP_403_FORBIDDEN)

    student_id = request.data.get("student_id")
    title = str(request.data.get("title", "")).strip() or "School Fee"
    due_date_raw = str(request.data.get("due_date", "")).strip()
    auto_deduct = bool(request.data.get("auto_deduct", True))

    try:
        amount = _parse_amount(request.data.get("amount"))
    except ValueError as exc:
        return Response({"success": False, "message": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

    try:
        due_date = datetime.strptime(due_date_raw, "%Y-%m-%d").date()
    except Exception:
        return Response({"success": False, "message": "due_date must be YYYY-MM-DD."}, status=status.HTTP_400_BAD_REQUEST)

    student_profile = get_object_or_404(
        StudentProfile.objects.select_related("user").filter(user__tenant=user.tenant),
        id=student_id,
    )
    fee = SchoolFee.objects.create(
        student=student_profile,
        title=title,
        amount=amount,
        currency="NGN",
        due_date=due_date,
        auto_deduct=auto_deduct,
        created_by=user,
    )
    return Response({"success": True, "fee": SchoolFeeSerializer(fee).data}, status=status.HTTP_201_CREATED)


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def admin_withdraw(request):
    """Withdraw funds from the admin wallet to a bank account."""
    user = request.user
    if user.role not in ADMIN_ROLES:
        return Response({"success": False, "message": "Admin role required."}, status=status.HTTP_403_FORBIDDEN)

    try:
        amount = _parse_amount(request.data.get("amount"))
    except ValueError as exc:
        return Response({"success": False, "message": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

    bank_account_number = str(request.data.get("account_number", "")).strip()
    bank_code = str(request.data.get("bank_name") or request.data.get("bank_code", "")).strip()
    bank_account_name = str(request.data.get("account_name", "")).strip()
    if not (bank_account_number and bank_code and bank_account_name):
        return Response(
            {"success": False, "message": "account_number, bank_name, and account_name are required."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    admin_wallet = get_or_create_admin_wallet(user.tenant)
    reference = generate_reference("WD")
    bank_payload = {
        "account_number": bank_account_number,
        "bank_code": bank_code,
        "account_name": bank_account_name,
    }
    try:
        result = initiate_admin_withdrawal(admin_wallet, amount, reference, bank_payload=bank_payload, actor=user)
    except ValueError as exc:
        return Response({"success": False, "message": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
    except Exception as exc:
        return Response({"success": False, "message": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

    admin_wallet.refresh_from_db()
    admin_wallet.bank_account_name = bank_account_name
    admin_wallet.bank_account_number = bank_account_number
    admin_wallet.bank_code = bank_code
    admin_wallet.last_settled_at = timezone.now()
    admin_wallet.save(
        update_fields=[
            "bank_account_name",
            "bank_account_number",
            "bank_code",
            "last_settled_at",
            "updated_at",
        ]
    )
    return Response(
        {
            "success": True,
            "status": result.get("status"),
            "admin_wallet": AdminWalletSerializer(admin_wallet).data,
            "reference": reference,
            "message": "Withdrawal sent to the school account via Flutterwave.",
        }
    )
