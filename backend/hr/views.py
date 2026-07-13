import csv
import io
import qrcode
from decimal import Decimal, InvalidOperation

from django.db.models import Count, Q, Sum
from django.http import FileResponse, HttpResponse
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.utils.dateparse import parse_date
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from attendance.models import AttendanceQRCode
from users.models import User, generate_short_teacher_id, random_code_digits, school_code_letters
from users.models import TeacherProfile
from finance.models import ExpenseRecord
from finance.services import generate_reference, get_or_create_admin_wallet, initiate_admin_withdrawal, record_finance_activity
from .models import (
    LeaveRequest,
    PayrollRecord,
    SalaryAdvanceRequest,
    StaffActivity,
    StaffAttendance,
    StaffProfile,
)


ADMIN_ROLES = {"school_admin", "principal", "super_admin"}
SELF_SERVICE_ROLES = {"teacher", "staff", "accountant"}


def _tenant_for_user(user):
    tenant = getattr(user, "tenant", None)
    if tenant:
        return tenant
    return None


def _require_admin(user):
    return getattr(user, "role", "") in ADMIN_ROLES


def _money(value):
    try:
        return Decimal(str(value or "0")).quantize(Decimal("0.01"))
    except (InvalidOperation, TypeError, ValueError):
        return None


def _media_url(request, file_field):
    if not file_field:
        return ""
    try:
        url = file_field.url
    except Exception:
        return ""
    if not url:
        return ""
    try:
        return request.build_absolute_uri(url) if request else url
    except Exception:
        return url


def _staff_queryset(user):
    tenant = _tenant_for_user(user)
    if not tenant:
        return StaffProfile.objects.none()
    return StaffProfile.objects.filter(tenant=tenant)


def _unique_staff_code(tenant, preferred):
    base = str(preferred or "").strip()[:32] or f"SF{school_code_letters(tenant)}{random_code_digits()}"
    candidate = base
    suffix = 1
    while StaffProfile.objects.filter(tenant=tenant, staff_code__iexact=candidate).exists():
        suffix_text = f"-{suffix}"
        candidate = f"{base[:40 - len(suffix_text)]}{suffix_text}"
        suffix += 1
    return candidate


def _generate_short_staff_code(tenant, prefix, seed=""):
    school_letters = school_code_letters(tenant)
    candidate = f"{prefix}{school_letters}{random_code_digits()}"
    while StaffProfile.objects.filter(tenant=tenant, staff_code__iexact=candidate).exists():
        candidate = f"{prefix}{school_letters}{random_code_digits()}"
    return candidate


def _self_staff_profile(user, create_teacher_profile=True):
    tenant = _tenant_for_user(user)
    if not tenant or getattr(user, "role", "") not in SELF_SERVICE_ROLES:
        return None

    direct = StaffProfile.objects.filter(tenant=tenant, user=user).first()
    if direct:
        return direct

    if getattr(user, "email", ""):
        by_email = StaffProfile.objects.filter(tenant=tenant, email__iexact=user.email).first()
        if by_email:
            if not by_email.user_id:
                by_email.user = user
                by_email.save(update_fields=["user", "updated_at"])
            return by_email

    if user.role == "teacher" and create_teacher_profile:
        teacher_profile = TeacherProfile.objects.filter(user=user).first()
        staff = StaffProfile.objects.create(
            tenant=tenant,
            user=user,
            staff_code=_unique_staff_code(tenant, getattr(teacher_profile, "employee_id", "") or generate_short_teacher_id(user.id.hex, tenant)),
            first_name=user.first_name or user.get_short_name(),
            last_name=user.last_name or "",
            email=user.email,
            phone=user.phone,
            gender=user.gender or "",
            date_of_birth=user.date_of_birth,
            staff_type=StaffProfile.TEACHING,
            role=getattr(teacher_profile, "specialization", "") or "Teacher",
            department="Teaching",
            employment_type=getattr(teacher_profile, "employment_type", "") or "full_time",
            hire_date=getattr(teacher_profile, "hire_date", None) or timezone.localdate(),
            base_salary=getattr(teacher_profile, "monthly_salary", None) or Decimal("0.00"),
            emergency_contact_name=getattr(teacher_profile, "emergency_contact_name", "") or "",
            emergency_contact_phone=getattr(teacher_profile, "emergency_contact_phone", "") or "",
            emergency_contact_relation=getattr(teacher_profile, "emergency_contact_relation", "") or "",
        )
        _activity(tenant, staff, user, "staff_profile_self_linked", "Teacher HR profile created for self-service")
        return staff

    if user.role == "accountant":
        staff = StaffProfile.objects.create(
            tenant=tenant,
            user=user,
            staff_code=_unique_staff_code(tenant, f"AC{school_code_letters(tenant)}{random_code_digits()}"),
            first_name=user.first_name or user.get_short_name(),
            last_name=user.last_name or "",
            email=user.email,
            phone=user.phone,
            gender=user.gender or "",
            date_of_birth=user.date_of_birth,
            staff_type=StaffProfile.NON_TEACHING,
            role="Accountant",
            department="Finance",
            employment_type="contract",
            hire_date=timezone.localdate(),
            base_salary=Decimal("0.00"),
        )
        _activity(tenant, staff, user, "accountant_profile_self_linked", "Accountant HR profile created for self-service")
        return staff

    return None


def _staff_for_write_request(request):
    if _require_admin(request.user):
        return get_object_or_404(_staff_queryset(request.user), id=request.data.get("staff_id"))
    staff = _self_staff_profile(request.user)
    if staff:
        return staff
    return None


def _sync_staff_login_user(staff, data):
    email = str(data.get("email") if "email" in data else staff.email or "").strip().lower()
    password = str(data.get("staff_password") or data.get("password") or "").strip()
    confirm = str(data.get("confirm_staff_password") or data.get("confirm_password") or "").strip()

    if password or confirm:
        if password != confirm:
            return "Staff password and confirm password must match."
        if len(password) < 8:
            return "Staff password must be at least 8 characters."

    if not email and not password:
        return None

    linked_user = staff.user
    if email:
        existing = User.objects.filter(email__iexact=email).exclude(id=getattr(linked_user, "id", None)).first()
        if existing and existing.tenant_id and existing.tenant_id != staff.tenant_id:
            return "A user with this email belongs to another school."
        if existing and StaffProfile.objects.filter(user=existing).exclude(id=staff.id).exists():
            return "This email is already linked to another staff profile."
        if existing and not linked_user:
            linked_user = existing

    if not linked_user:
        if not email:
            return "Email is required before creating a staff login."
        if not password:
            return "Set a staff password to create a login account."
        linked_user = User(email=email)

    linked_user.first_name = staff.first_name
    linked_user.last_name = staff.last_name
    linked_user.email = email or linked_user.email
    linked_user.phone = staff.phone
    linked_user.gender = staff.gender
    linked_user.role = "accountant" if staff.staff_type == StaffProfile.NON_TEACHING and staff.role.strip().lower() == "accountant" else "staff"
    linked_user.tenant = staff.tenant
    linked_user.is_active = True
    linked_user.is_verified = True
    if password:
        linked_user.set_password(password)
    linked_user.save()
    if staff.user_id != linked_user.id:
        staff.user = linked_user
        staff.save(update_fields=["user", "updated_at"])
    return None


def _activity(tenant, staff, actor, action, details=""):
    StaffActivity.objects.create(tenant=tenant, staff=staff, actor=actor, action=action, details=details[:255])


def _staff_payload(staff, request=None):
    attendance = staff.attendance_records.all()
    total_attendance = attendance.count()
    present_count = attendance.filter(status=StaffAttendance.PRESENT).count()
    absent_count = attendance.filter(status=StaffAttendance.ABSENT).count()
    linked_user = getattr(staff, "user", None)
    date_of_birth = staff.date_of_birth or (getattr(linked_user, "date_of_birth", None) if linked_user else None)
    gender = staff.gender or (getattr(linked_user, "gender", "") if linked_user else "")
    cv_url = _media_url(request, staff.cv)
    credentials_url = _media_url(request, staff.credentials)
    guarantor_form_url = _media_url(request, staff.guarantor_form)
    profile_picture_url = _media_url(request, getattr(linked_user, "profile_picture", None)) if linked_user else ""
    teacher_profile = TeacherProfile.objects.filter(user=linked_user).first() if linked_user and getattr(linked_user, "role", "") == "teacher" else None
    if teacher_profile and not cv_url:
        cv_url = _media_url(request, teacher_profile.resume)
    return {
        "id": str(staff.id),
        "staff_code": staff.staff_code,
        "attendance_token": staff.attendance_token,
        "name": staff.full_name,
        "first_name": staff.first_name,
        "last_name": staff.last_name,
        "email": staff.email,
        "phone": staff.phone,
        "gender": gender,
        "date_of_birth": date_of_birth,
        "profile_picture": profile_picture_url,
        "address": staff.address,
        "nationality": staff.nationality,
        "marital_status": staff.marital_status,
        "cv": cv_url,
        "cv_url": cv_url,
        "credentials_url": credentials_url,
        "staff_type": staff.staff_type,
        "role": staff.role,
        "department": staff.department,
        "employment_type": staff.employment_type,
        "employment_status": staff.employment_status,
        "hire_date": staff.hire_date,
        "base_salary": staff.base_salary,
        "salary_balance": staff.salary_balance,
        "bank_name": staff.bank_name,
        "bank_code": staff.bank_code,
        "bank_account_name": staff.bank_account_name,
        "bank_account_number": staff.bank_account_number,
        "emergency_contact_name": staff.emergency_contact_name,
        "emergency_contact_phone": staff.emergency_contact_phone,
        "emergency_contact_relation": staff.emergency_contact_relation,
        "guarantor_name": staff.guarantor_name,
        "guarantor_phone": staff.guarantor_phone,
        "guarantor_address": staff.guarantor_address,
        "guarantor_relationship": staff.guarantor_relationship,
        "guarantor_form_url": guarantor_form_url,
        "notes": staff.notes,
        "attendance_rate": round((present_count / total_attendance) * 100, 1) if total_attendance else 0,
        "absent_count": absent_count,
        "created_at": staff.created_at,
    }


def _attendance_payload(record):
    return {
        "id": str(record.id),
        "staff_id": str(record.staff_id),
        "staff_name": record.staff.full_name,
        "date": record.date,
        "status": record.status,
        "check_in": record.check_in,
        "check_out": record.check_out,
        "notes": record.notes,
    }


def _leave_payload(item):
    return {
        "id": str(item.id),
        "staff_id": str(item.staff_id),
        "staff_name": item.staff.full_name,
        "leave_type": item.leave_type,
        "start_date": item.start_date,
        "end_date": item.end_date,
        "days": item.days,
        "reason": item.reason,
        "status": item.status,
        "admin_note": item.admin_note,
        "created_at": item.created_at,
    }


def _advance_payload(item):
    return {
        "id": str(item.id),
        "staff_id": str(item.staff_id),
        "staff_name": item.staff.full_name,
        "amount": item.amount,
        "reason": item.reason,
        "status": item.status,
        "request_date": item.request_date,
        "created_at": item.created_at,
    }


def _payroll_payload(item):
    return {
        "id": str(item.id),
        "staff_id": str(item.staff_id),
        "staff_name": item.staff.full_name,
        "period": item.period_label,
        "year": item.year,
        "month": item.month,
        "base_salary": item.base_salary,
        "allowances": item.allowances,
        "deductions": item.deductions,
        "advances_applied": item.advances_applied,
        "gross_salary": item.gross_salary,
        "net_salary": item.net_salary,
        "amount_paid": item.amount_paid,
        "balance_after_payment": item.balance_after_payment,
        "status": item.status,
        "notes": item.notes,
        "paid_at": item.paid_at,
    }


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def hr_snapshot(request):
    if not _require_admin(request.user):
        return Response({"success": False, "message": "Only admins can manage HR."}, status=status.HTTP_403_FORBIDDEN)
    tenant = _tenant_for_user(request.user)
    if not tenant:
        return Response({"success": False, "message": "Could not resolve school tenant."}, status=status.HTTP_400_BAD_REQUEST)

    staff = StaffProfile.objects.filter(tenant=tenant).prefetch_related("attendance_records").order_by("first_name", "last_name")
    today = timezone.localdate()
    month = today.month
    year = today.year
    attendance = StaffAttendance.objects.filter(staff__tenant=tenant)
    payroll = PayrollRecord.objects.filter(staff__tenant=tenant)
    leaves = LeaveRequest.objects.filter(staff__tenant=tenant)
    advances = SalaryAdvanceRequest.objects.filter(staff__tenant=tenant)

    active_staff = staff.exclude(employment_status=StaffProfile.EXITED)
    monthly_payroll = payroll.filter(year=year, month=month)
    total_salary = staff.aggregate(total=Sum("base_salary"))["total"] or Decimal("0.00")
    total_balances = staff.aggregate(total=Sum("salary_balance"))["total"] or Decimal("0.00")

    return Response(
        {
            "success": True,
            "summary": {
                "total_staff": staff.count(),
                "teaching_staff": staff.filter(staff_type=StaffProfile.TEACHING).count(),
                "non_teaching_staff": staff.filter(staff_type=StaffProfile.NON_TEACHING).count(),
                "active_staff": active_staff.count(),
                "total_monthly_salary": total_salary,
                "salary_balances": total_balances,
                "pending_leaves": leaves.filter(status=LeaveRequest.PENDING).count(),
                "pending_advances": advances.filter(status=SalaryAdvanceRequest.PENDING).count(),
                "today_present": attendance.filter(date=today, status=StaffAttendance.PRESENT).count(),
                "today_absent": attendance.filter(date=today, status=StaffAttendance.ABSENT).count(),
                "monthly_payroll": monthly_payroll.aggregate(total=Sum("net_salary"))["total"] or Decimal("0.00"),
                "monthly_paid": monthly_payroll.aggregate(total=Sum("amount_paid"))["total"] or Decimal("0.00"),
            },
            "staff": [_staff_payload(item, request=request) for item in staff[:100]],
            "attendance": [_attendance_payload(item) for item in attendance.select_related("staff").order_by("-date", "-created_at")[:80]],
            "absences": [_attendance_payload(item) for item in attendance.select_related("staff").filter(status=StaffAttendance.ABSENT).order_by("-date")[:30]],
            "payroll": [_payroll_payload(item) for item in payroll.select_related("staff").order_by("-year", "-month")[:80]],
            "advances": [_advance_payload(item) for item in advances.select_related("staff").order_by("-created_at")[:50]],
            "leaves": [_leave_payload(item) for item in leaves.select_related("staff").order_by("-created_at")[:50]],
            "departments": list(staff.exclude(department="").values_list("department", flat=True).distinct().order_by("department")),
            "activity": [
                {
                    "id": str(item.id),
                    "staff_name": item.staff.full_name if item.staff else "",
                    "action": item.action,
                    "details": item.details,
                    "created_at": item.created_at,
                    "actor": item.actor.get_full_name() if item.actor else "",
                }
                for item in StaffActivity.objects.filter(tenant=tenant).select_related("staff", "actor").order_by("-created_at")[:40]
            ],
        }
    )


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def activity_snapshot(request):
    if not _require_admin(request.user):
        return Response({"success": False, "message": "Only admins can view HR activity."}, status=status.HTTP_403_FORBIDDEN)
    tenant = _tenant_for_user(request.user)
    if not tenant:
        return Response({"success": False, "message": "Could not resolve school tenant."}, status=status.HTTP_400_BAD_REQUEST)
    activities = StaffActivity.objects.filter(tenant=tenant).select_related("staff", "actor").order_by("-created_at")[:200]
    teacher_leaves = LeaveRequest.objects.filter(
        staff__tenant=tenant,
        staff__staff_type=StaffProfile.TEACHING,
        status=LeaveRequest.PENDING,
    ).select_related("staff").order_by("-created_at")[:50]
    teacher_advances = SalaryAdvanceRequest.objects.filter(
        staff__tenant=tenant,
        staff__staff_type=StaffProfile.TEACHING,
        status=SalaryAdvanceRequest.PENDING,
    ).select_related("staff").order_by("-created_at")[:50]
    return Response(
        {
            "success": True,
            "summary": {
                "total_activity": StaffActivity.objects.filter(tenant=tenant).count(),
                "today_activity": StaffActivity.objects.filter(tenant=tenant, created_at__date=timezone.localdate()).count(),
                "pending_teacher_leaves": LeaveRequest.objects.filter(
                    staff__tenant=tenant,
                    staff__staff_type=StaffProfile.TEACHING,
                    status=LeaveRequest.PENDING,
                ).count(),
                "pending_teacher_advances": SalaryAdvanceRequest.objects.filter(
                    staff__tenant=tenant,
                    staff__staff_type=StaffProfile.TEACHING,
                    status=SalaryAdvanceRequest.PENDING,
                ).count(),
            },
            "teacher_leaves": [_leave_payload(item) for item in teacher_leaves],
            "teacher_advances": [_advance_payload(item) for item in teacher_advances],
            "activity": [
                {
                    "id": str(item.id),
                    "staff_name": item.staff.full_name if item.staff else "",
                    "staff_code": item.staff.staff_code if item.staff else "",
                    "action": item.action,
                    "details": item.details,
                    "created_at": item.created_at,
                    "actor": item.actor.get_full_name() if item.actor else "",
                }
                for item in activities
            ],
        }
    )


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def download_staff_csv(request):
    if not _require_admin(request.user):
        return Response({"success": False, "message": "Only admins can download staff data."}, status=status.HTTP_403_FORBIDDEN)
    staff_type = str(request.query_params.get("type") or "teaching").strip()
    staff = _staff_queryset(request.user).filter(staff_type=staff_type).order_by("first_name", "last_name")
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["Staff Code", "Name", "Type", "Role", "Department", "Email", "Phone", "Monthly Salary", "Salary Balance", "Status", "Hire Date"])
    for item in staff:
        writer.writerow([
            item.staff_code,
            item.full_name,
            item.get_staff_type_display(),
            item.role,
            item.department,
            item.email,
            item.phone,
            item.base_salary,
            item.salary_balance,
            item.employment_status,
            item.hire_date,
        ])
    response = HttpResponse(output.getvalue(), content_type="text/csv")
    response["Content-Disposition"] = f'attachment; filename="{staff_type}_staff_data.csv"'
    return response


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def download_staff_qr(request, staff_id):
    staff = get_object_or_404(_staff_queryset(request.user), id=staff_id)
    scan_url = request.build_absolute_uri(f"/api/hr/attendance/scan/{staff.attendance_token}/")
    qr = qrcode.QRCode(version=1, error_correction=qrcode.constants.ERROR_CORRECT_L, box_size=10, border=4)
    qr.add_data(scan_url)
    qr.make(fit=True)
    image = qr.make_image(fill_color="black", back_color="white")
    image_io = io.BytesIO()
    image.save(image_io, "PNG")
    image_io.seek(0)
    response = FileResponse(image_io, content_type="image/png")
    response["Content-Disposition"] = f'attachment; filename="{staff.staff_code}_attendance_qr.png"'
    return response


@api_view(["GET", "POST"])
@permission_classes([IsAuthenticated])
def scan_staff_attendance(request, token):
    staff = get_object_or_404(_staff_queryset(request.user), attendance_token=token)
    if request.method == "GET":
        return Response({"success": True, "staff": _staff_payload(staff), "message": "Staff QR verified."})
    date = timezone.localdate()
    attendance, _created = StaffAttendance.objects.update_or_create(
        staff=staff,
        date=date,
        defaults={
            "status": StaffAttendance.PRESENT,
            "notes": "Marked by staff QR code",
            "marked_by": request.user,
        },
    )
    _activity(staff.tenant, staff, request.user, "attendance_qr_marked", f"QR attendance marked for {attendance.date}")
    return Response({"success": True, "message": f"Attendance marked for {staff.full_name}.", "attendance": _attendance_payload(attendance)})


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def create_staff(request):
    if not _require_admin(request.user):
        return Response({"success": False, "message": "Only admins can create staff."}, status=status.HTTP_403_FORBIDDEN)
    tenant = _tenant_for_user(request.user)
    if not tenant:
        return Response({"success": False, "message": "Could not resolve school tenant."}, status=status.HTTP_400_BAD_REQUEST)

    first_name = str(request.data.get("first_name", "")).strip()
    last_name = str(request.data.get("last_name", "")).strip()
    role = str(request.data.get("role", "")).strip()
    gender = str(request.data.get("gender", "")).strip()
    if gender and gender not in {"M", "F", "O", "N"}:
        return Response({"success": False, "message": "gender must be one of M, F, O, or N."}, status=status.HTTP_400_BAD_REQUEST)
    if not first_name or not last_name or not role:
        return Response({"success": False, "message": "first_name, last_name, and role are required."}, status=status.HTTP_400_BAD_REQUEST)

    base_salary = _money(request.data.get("base_salary"))
    if base_salary is None:
        return Response({"success": False, "message": "base_salary must be a valid amount."}, status=status.HTTP_400_BAD_REQUEST)

    email = str(request.data.get("email", "")).strip().lower()
    staff_type = str(request.data.get("staff_type") or StaffProfile.TEACHING)
    staff_prefix = "NS" if staff_type == StaffProfile.NON_TEACHING else "TS"
    seed = f"{first_name}{last_name}{email}{timezone.now().strftime('%f')}"
    staff_code = str(request.data.get("staff_code", "")).strip() or _generate_short_staff_code(tenant, staff_prefix, seed)
    if StaffProfile.objects.filter(tenant=tenant, staff_code__iexact=staff_code).exists():
        return Response({"success": False, "message": "Staff code already exists."}, status=status.HTTP_400_BAD_REQUEST)

    hire_date = parse_date(str(request.data.get("hire_date") or "")) or timezone.localdate()
    staff_password = str(request.data.get("staff_password") or request.data.get("password") or "").strip()
    confirm_staff_password = str(request.data.get("confirm_staff_password") or request.data.get("confirm_password") or "").strip()
    linked_user = None

    if email and staff_password:
        account_role = "accountant" if staff_type == StaffProfile.NON_TEACHING and role.strip().lower() == "accountant" else "staff"
        if staff_password != confirm_staff_password:
            return Response({"success": False, "message": "Staff password and confirm password must match."}, status=status.HTTP_400_BAD_REQUEST)
        if len(staff_password) < 8:
            return Response({"success": False, "message": "Staff password must be at least 8 characters."}, status=status.HTTP_400_BAD_REQUEST)
        linked_user = User.objects.filter(email__iexact=email).first()
        if linked_user and linked_user.tenant and linked_user.tenant != tenant:
            return Response({"success": False, "message": "A user with this email belongs to another school."}, status=status.HTTP_400_BAD_REQUEST)
        if linked_user:
            linked_user.first_name = first_name
            linked_user.last_name = last_name
            linked_user.role = account_role
            linked_user.tenant = tenant
            linked_user.phone = str(request.data.get("phone", "")).strip()
            linked_user.gender = gender
            linked_user.is_active = True
            linked_user.is_verified = True
            linked_user.set_password(staff_password)
            linked_user.save(update_fields=["first_name", "last_name", "role", "tenant", "phone", "gender", "is_active", "is_verified", "password"])
        else:
            linked_user = User.objects.create_user(
                email=email,
                password=staff_password,
                first_name=first_name,
                last_name=last_name,
                role=account_role,
                tenant=tenant,
                phone=str(request.data.get("phone", "")).strip(),
                gender=gender,
                is_active=True,
                is_verified=True,
            )

    staff = StaffProfile.objects.create(
        tenant=tenant,
        user=linked_user,
        staff_code=staff_code,
        first_name=first_name,
        last_name=last_name,
        email=email,
        phone=str(request.data.get("phone", "")).strip(),
        gender=gender,
        address=str(request.data.get("address", "")).strip(),
        staff_type=staff_type,
        role=role,
        department=str(request.data.get("department", "")).strip(),
        employment_type=str(request.data.get("employment_type") or "full_time"),
        employment_status=str(request.data.get("employment_status") or StaffProfile.ACTIVE),
        hire_date=hire_date,
        base_salary=base_salary,
        bank_name=str(request.data.get("bank_name", "")).strip(),
        bank_code=str(request.data.get("bank_code", "")).strip(),
        bank_account_name=str(request.data.get("bank_account_name", "")).strip(),
        bank_account_number=str(request.data.get("bank_account_number", "")).strip(),
        emergency_contact_name=str(request.data.get("emergency_contact_name", "")).strip(),
        emergency_contact_phone=str(request.data.get("emergency_contact_phone", "")).strip(),
        emergency_contact_relation=str(request.data.get("emergency_contact_relation", "")).strip(),
        notes=str(request.data.get("notes", "")).strip(),
        created_by=request.user,
    )
    _activity(tenant, staff, request.user, "staff_created", f"Created staff profile for {staff.full_name}")
    return Response({"success": True, "message": "Staff profile created.", "staff": _staff_payload(staff)}, status=status.HTTP_201_CREATED)


@api_view(["PATCH", "DELETE"])
@permission_classes([IsAuthenticated])
def staff_detail(request, staff_id):
    if not _require_admin(request.user):
        return Response({"success": False, "message": "Only admins can update staff."}, status=status.HTTP_403_FORBIDDEN)
    staff = get_object_or_404(_staff_queryset(request.user), id=staff_id)
    if request.method == "DELETE":
        staff.employment_status = StaffProfile.EXITED
        staff.save(update_fields=["employment_status", "updated_at"])
        _activity(staff.tenant, staff, request.user, "staff_exited", f"Marked {staff.full_name} as exited")
        return Response({"success": True, "message": "Staff marked as exited."})

    fields = [
        "staff_code", "first_name", "last_name", "email", "phone", "gender", "address", "staff_type", "role",
        "department", "employment_type", "employment_status", "bank_name", "bank_code", "bank_account_name",
        "bank_account_number", "emergency_contact_name", "emergency_contact_phone", "emergency_contact_relation", "notes",
    ]
    update_fields = []
    for field in fields:
        if field in request.data:
            if field == "gender":
                gender = str(request.data.get(field) or "").strip()
                if gender and gender not in {"M", "F", "O", "N"}:
                    return Response({"success": False, "message": "gender must be one of M, F, O, or N."}, status=status.HTTP_400_BAD_REQUEST)
            setattr(staff, field, str(request.data.get(field) or "").strip())
            update_fields.append(field)
    if "base_salary" in request.data:
        base_salary = _money(request.data.get("base_salary"))
        if base_salary is None:
            return Response({"success": False, "message": "base_salary must be a valid amount."}, status=status.HTTP_400_BAD_REQUEST)
        staff.base_salary = base_salary
        update_fields.append("base_salary")
    if "hire_date" in request.data:
        hire_date = parse_date(str(request.data.get("hire_date") or ""))
        if hire_date:
            staff.hire_date = hire_date
            update_fields.append("hire_date")
    login_error = _sync_staff_login_user(staff, request.data)
    if login_error:
        return Response({"success": False, "message": login_error}, status=status.HTTP_400_BAD_REQUEST)
    if update_fields:
        staff.save(update_fields=sorted(set(update_fields + ["updated_at"])))
    if update_fields or any(field in request.data for field in ("staff_password", "password", "confirm_staff_password", "confirm_password")):
        _activity(staff.tenant, staff, request.user, "staff_updated", f"Updated staff profile for {staff.full_name}")
    return Response({"success": True, "message": "Staff profile updated.", "staff": _staff_payload(staff)})


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def mark_attendance(request):
    token = str(request.data.get("qr_token") or request.data.get("attendance_token") or "").strip()
    if not token:
        return Response({"success": False, "message": "Scan the shared staff QR code before marking attendance."}, status=status.HTTP_400_BAD_REQUEST)
    qr_code = AttendanceQRCode.verify_token(token)
    if not qr_code or qr_code.tenant != _tenant_for_user(request.user):
        return Response({"success": False, "message": "Invalid shared staff QR code."}, status=status.HTTP_400_BAD_REQUEST)
    if _require_admin(request.user):
        staff = get_object_or_404(_staff_queryset(request.user), id=request.data.get("staff_id"))
    else:
        staff = _self_staff_profile(request.user)
        if not staff:
            return Response({"success": False, "message": "Your account is not linked to a staff profile."}, status=status.HTTP_403_FORBIDDEN)
    date = parse_date(str(request.data.get("date") or "")) or timezone.localdate()
    attendance, _created = StaffAttendance.objects.update_or_create(
        staff=staff,
        date=date,
        defaults={
            "status": StaffAttendance.PRESENT,
            "notes": str(request.data.get("notes", "")).strip() or "Marked by shared staff QR code",
            "marked_by": request.user,
        },
    )
    _activity(staff.tenant, staff, request.user, "attendance_shared_qr_marked", f"{attendance.status} on {attendance.date}")
    return Response({"success": True, "message": "Attendance saved.", "attendance": _attendance_payload(attendance)})


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def create_leave_request(request):
    staff = _staff_for_write_request(request)
    if not staff:
        return Response({"success": False, "message": "Your account is not linked to a staff profile."}, status=status.HTTP_403_FORBIDDEN)
    start_date = parse_date(str(request.data.get("start_date") or ""))
    end_date = parse_date(str(request.data.get("end_date") or ""))
    if not start_date or not end_date or end_date < start_date:
        return Response({"success": False, "message": "Use a valid leave date range."}, status=status.HTTP_400_BAD_REQUEST)
    item = LeaveRequest.objects.create(
        staff=staff,
        leave_type=str(request.data.get("leave_type") or "Annual"),
        start_date=start_date,
        end_date=end_date,
        reason=str(request.data.get("reason", "")).strip(),
        requested_by=request.user,
    )
    _activity(staff.tenant, staff, request.user, "leave_requested", f"{item.leave_type} leave requested")
    return Response({"success": True, "message": "Leave request created.", "leave": _leave_payload(item)}, status=status.HTTP_201_CREATED)


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def review_leave_request(request, leave_id):
    if not _require_admin(request.user):
        return Response({"success": False, "message": "Only admins can review leave requests."}, status=status.HTTP_403_FORBIDDEN)
    leave = get_object_or_404(LeaveRequest.objects.select_related("staff"), id=leave_id, staff__in=_staff_queryset(request.user))
    decision = str(request.data.get("status") or "").strip().lower()
    if decision not in {LeaveRequest.APPROVED, LeaveRequest.REJECTED}:
        return Response({"success": False, "message": "status must be approved or rejected."}, status=status.HTTP_400_BAD_REQUEST)
    leave.status = decision
    leave.admin_note = str(request.data.get("admin_note", "")).strip()
    leave.reviewed_by = request.user
    leave.reviewed_at = timezone.now()
    leave.save(update_fields=["status", "admin_note", "reviewed_by", "reviewed_at", "updated_at"])
    if decision == LeaveRequest.APPROVED:
        leave.staff.employment_status = StaffProfile.ON_LEAVE
        leave.staff.save(update_fields=["employment_status", "updated_at"])
    _activity(leave.staff.tenant, leave.staff, request.user, f"leave_{decision}", f"{leave.leave_type} leave {decision}")
    return Response({"success": True, "message": f"Leave {decision}.", "leave": _leave_payload(leave)})


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def create_advance_request(request):
    staff = _staff_for_write_request(request)
    if not staff:
        return Response({"success": False, "message": "Your account is not linked to a staff profile."}, status=status.HTTP_403_FORBIDDEN)
    amount = _money(request.data.get("amount"))
    if amount is None or amount <= 0:
        return Response({"success": False, "message": "Enter a valid advance amount."}, status=status.HTTP_400_BAD_REQUEST)
    item = SalaryAdvanceRequest.objects.create(
        staff=staff,
        amount=amount,
        reason=str(request.data.get("reason", "")).strip(),
    )
    _activity(staff.tenant, staff, request.user, "advance_requested", f"Salary advance requested: {amount}")
    return Response({"success": True, "message": "Salary advance request created.", "advance": _advance_payload(item)}, status=status.HTTP_201_CREATED)


def _update_self_biodata(request, staff):
    user = request.user
    update_staff_fields = []
    update_user_fields = []
    data = request.data

    if "gender" in data:
        gender = str(data.get("gender") or "").strip()
        if gender and gender not in {"M", "F", "O", "N"}:
            return "gender must be one of M, F, O, or N."
        normalized_gender = gender or None
        if user.gender != normalized_gender:
            user.gender = normalized_gender
            update_user_fields.append("gender")
        if staff.gender != (gender or ""):
            staff.gender = gender or ""
            update_staff_fields.append("gender")

    if "date_of_birth" in data:
        raw_date_of_birth = str(data.get("date_of_birth") or "").strip()
        date_of_birth = parse_date(raw_date_of_birth) if raw_date_of_birth else None
        if raw_date_of_birth and not date_of_birth:
            return "date_of_birth must be in YYYY-MM-DD format."
        if user.date_of_birth != date_of_birth:
            user.date_of_birth = date_of_birth
            update_user_fields.append("date_of_birth")
        if staff.date_of_birth != date_of_birth:
            staff.date_of_birth = date_of_birth
            update_staff_fields.append("date_of_birth")

    profile_picture = request.FILES.get("profile_picture")
    if profile_picture:
        user.profile_picture = profile_picture
        update_user_fields.append("profile_picture")

    credentials_file = request.FILES.get("credentials")
    if credentials_file:
        staff.credentials = credentials_file
        update_staff_fields.append("credentials")

    guarantor_form_file = request.FILES.get("guarantor_form")
    if guarantor_form_file:
        staff.guarantor_form = guarantor_form_file
        update_staff_fields.append("guarantor_form")

    if "marital_status" in data:
        marital_status = str(data.get("marital_status") or "").strip().lower()
        valid_marital_statuses = {choice[0] for choice in StaffProfile.MARITAL_STATUS_CHOICES}
        if marital_status and marital_status not in valid_marital_statuses:
            return "marital_status must be one of: " + ", ".join(sorted(valid_marital_statuses)) + "."
        if staff.marital_status != marital_status:
            staff.marital_status = marital_status
            update_staff_fields.append("marital_status")

    text_fields = {
        "phone": "phone",
        "address": "address",
        "email": "email",
        "nationality": "nationality",
        "emergency_contact_name": "emergency_contact_name",
        "emergency_contact_phone": "emergency_contact_phone",
        "emergency_contact_relation": "emergency_contact_relation",
        "guarantor_name": "guarantor_name",
        "guarantor_phone": "guarantor_phone",
        "guarantor_address": "guarantor_address",
        "guarantor_relationship": "guarantor_relationship",
    }
    for payload_field, model_field in text_fields.items():
        if payload_field in data:
            value = str(data.get(payload_field) or "").strip()
            if getattr(staff, model_field) != value:
                setattr(staff, model_field, value)
                update_staff_fields.append(model_field)
            if payload_field == "phone" and user.phone != value:
                user.phone = value
                update_user_fields.append("phone")

    teacher_profile = TeacherProfile.objects.filter(user=user).first() if getattr(user, "role", "") == "teacher" else None
    if teacher_profile:
        teacher_fields = {
            "emergency_contact_name": "emergency_contact_name",
            "emergency_contact_phone": "emergency_contact_phone",
            "emergency_contact_relation": "emergency_contact_relation",
        }
        teacher_update_fields = []
        for payload_field, model_field in teacher_fields.items():
            if payload_field in data:
                value = str(data.get(payload_field) or "").strip()
                if getattr(teacher_profile, model_field) != value:
                    setattr(teacher_profile, model_field, value)
                    teacher_update_fields.append(model_field)
        resume_file = request.FILES.get("cv") or request.FILES.get("resume")
        if resume_file:
            teacher_profile.resume = resume_file
            teacher_update_fields.append("resume")
        if teacher_update_fields:
            teacher_profile.save(update_fields=sorted(set(teacher_update_fields + ["updated_at"])))
    else:
        cv_file = request.FILES.get("cv") or request.FILES.get("resume")
        if cv_file:
            staff.cv = cv_file
            update_staff_fields.append("cv")

    if update_user_fields:
        user.save(update_fields=sorted(set(update_user_fields)))
    if update_staff_fields:
        staff.save(update_fields=sorted(set(update_staff_fields + ["updated_at"])))
    return None


@api_view(["GET", "PATCH"])
@permission_classes([IsAuthenticated])
def staff_self_service_snapshot(request):
    staff = _self_staff_profile(request.user)
    if not staff:
        return Response({"success": False, "message": "Your account is not linked to a staff profile."}, status=status.HTTP_403_FORBIDDEN)
    if request.method == "PATCH":
        error_message = _update_self_biodata(request, staff)
        if error_message:
            return Response({"success": False, "message": error_message}, status=status.HTTP_400_BAD_REQUEST)
        staff.refresh_from_db()
        _activity(staff.tenant, staff, request.user, "staff_biodata_updated", "Self-service biodata updated")
        return Response({"success": True, "message": "Profile biodata updated.", "staff": _staff_payload(staff, request=request)})

    leaves = LeaveRequest.objects.filter(staff=staff).order_by("-created_at")
    advances = SalaryAdvanceRequest.objects.filter(staff=staff).order_by("-created_at")
    payroll = PayrollRecord.objects.filter(staff=staff).order_by("-year", "-month")
    attendance = StaffAttendance.objects.filter(staff=staff).order_by("-date", "-created_at")
    return Response(
        {
            "success": True,
            "staff": _staff_payload(staff, request=request),
            "summary": {
                "pending_leaves": leaves.filter(status=LeaveRequest.PENDING).count(),
                "pending_advances": advances.filter(status=SalaryAdvanceRequest.PENDING).count(),
                "salary_balance": staff.salary_balance,
                "attendance_rate": _staff_payload(staff)["attendance_rate"],
            },
            "leaves": [_leave_payload(item) for item in leaves[:20]],
            "advances": [_advance_payload(item) for item in advances[:20]],
            "payroll": [_payroll_payload(item) for item in payroll[:12]],
            "attendance": [_attendance_payload(item) for item in attendance[:20]],
        }
    )


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def staff_employment_letter(request):
    """Employment confirmation letter data for the caller's own HR record. No PDF
    generation server-side - the frontend renders this into a print-styled preview
    and uses the browser's print/save-as-PDF dialog, same as transcripts/testimonials."""
    staff = _self_staff_profile(request.user)
    if not staff:
        return Response({"success": False, "message": "Your account is not linked to a staff profile."}, status=status.HTTP_403_FORBIDDEN)

    tenant = staff.tenant
    employment_type_labels = {
        "full_time": "Full-time",
        "part_time": "Part-time",
        "contract": "Contract",
    }
    staff_type_labels = dict(StaffProfile.STAFF_TYPE_CHOICES)

    return Response(
        {
            "success": True,
            "school": {
                "name": getattr(tenant, "name", "") or "School",
                "address": getattr(tenant, "address", "") or "",
                "phone": getattr(tenant, "phone", "") or "",
                "email": getattr(tenant, "email", "") or "",
                "logo": _media_url(request, getattr(tenant, "logo", None)),
            },
            "staff": {
                "name": staff.full_name,
                "staff_code": staff.staff_code,
                "role": staff.role or staff_type_labels.get(staff.staff_type, ""),
                "department": staff.department,
                "employment_type": employment_type_labels.get(staff.employment_type, staff.employment_type),
                "employment_status": staff.get_employment_status_display(),
                "hire_date": staff.hire_date,
            },
            "generated_at": timezone.now(),
        }
    )


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def review_advance_request(request, advance_id):
    if not _require_admin(request.user):
        return Response({"success": False, "message": "Only admins can review salary advances."}, status=status.HTTP_403_FORBIDDEN)
    advance = get_object_or_404(SalaryAdvanceRequest.objects.select_related("staff"), id=advance_id, staff__in=_staff_queryset(request.user))
    decision = str(request.data.get("status") or "").strip().lower()
    if decision not in {SalaryAdvanceRequest.APPROVED, SalaryAdvanceRequest.REJECTED, SalaryAdvanceRequest.PAID}:
        return Response({"success": False, "message": "status must be approved, rejected, or paid."}, status=status.HTTP_400_BAD_REQUEST)
    previous_status = advance.status
    advance.status = decision
    advance.approved_by = request.user
    advance.approved_at = timezone.now()
    if decision == SalaryAdvanceRequest.PAID:
        advance.paid_at = timezone.now()
        advance.staff.salary_balance -= advance.amount
        advance.staff.save(update_fields=["salary_balance", "updated_at"])
    advance.save(update_fields=["status", "approved_by", "approved_at", "paid_at", "updated_at"])
    if decision == SalaryAdvanceRequest.PAID and previous_status != SalaryAdvanceRequest.PAID:
        # Record the payout as a school expense so it deducts from the Expenses ledger immediately;
        # it is separately netted off the staff member's next payroll run via PayrollRecord.advances_applied.
        ExpenseRecord.objects.create(
            tenant=advance.staff.tenant,
            title=f"Salary advance - {advance.staff.full_name}",
            vendor=advance.staff.full_name,
            amount=advance.amount,
            record_type=ExpenseRecord.TYPE_EXPENSE,
            category="Salary Advance",
            status=ExpenseRecord.STATUS_PAID,
            record_date=timezone.localdate(),
            note=advance.reason or f"Salary advance paid to {advance.staff.full_name}",
            created_by=request.user,
        )
        record_finance_activity(
            advance.staff.tenant,
            request.user,
            "salary_advance_paid",
            f"Salary advance of {advance.amount} paid to {advance.staff.full_name}.",
            amount=advance.amount,
            reference=str(advance.id),
            metadata={"staff_id": str(advance.staff_id)},
        )
    _activity(advance.staff.tenant, advance.staff, request.user, f"advance_{decision}", f"Salary advance {decision}: {advance.amount}")
    return Response({"success": True, "message": f"Salary advance {decision}.", "advance": _advance_payload(advance)})


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def create_payroll_record(request):
    if not _require_admin(request.user):
        return Response({"success": False, "message": "Only admins can process payroll."}, status=status.HTTP_403_FORBIDDEN)
    staff = get_object_or_404(_staff_queryset(request.user), id=request.data.get("staff_id"))
    today = timezone.localdate()
    year = int(request.data.get("year") or today.year)
    month = int(request.data.get("month") or today.month)
    allowances = _money(request.data.get("allowances")) or Decimal("0.00")
    deductions = _money(request.data.get("deductions")) or Decimal("0.00")
    amount_paid = _money(request.data.get("amount_paid")) or Decimal("0.00")
    pay_with_flutterwave = bool(request.data.get("pay_with_flutterwave"))
    paid_advances = staff.salary_advances.filter(status=SalaryAdvanceRequest.PAID, request_date__year=year, request_date__month=month)
    advances_applied = paid_advances.aggregate(total=Sum("amount"))["total"] or Decimal("0.00")
    gross_salary = staff.base_salary + allowances
    net_salary = max(gross_salary - deductions - advances_applied, Decimal("0.00"))
    if pay_with_flutterwave and amount_paid <= 0:
        amount_paid = net_salary
    if amount_paid > net_salary:
        return Response({"success": False, "message": "amount_paid cannot exceed net salary."}, status=status.HTTP_400_BAD_REQUEST)
    if pay_with_flutterwave and amount_paid <= 0:
        return Response({"success": False, "message": "There is no salary amount to pay."}, status=status.HTTP_400_BAD_REQUEST)
    bank_code = str(request.data.get("bank_code") or staff.bank_code or "").strip()
    bank_account_number = str(request.data.get("bank_account_number") or staff.bank_account_number or "").strip()
    bank_account_name = str(request.data.get("bank_account_name") or staff.bank_account_name or staff.full_name or "").strip()
    bank_name = str(request.data.get("bank_name") or staff.bank_name or "").strip()
    if pay_with_flutterwave and (not bank_code or not bank_account_number):
        return Response({"success": False, "message": "Staff bank code and account number are required for Flutterwave salary payment."}, status=status.HTTP_400_BAD_REQUEST)
    balance_after_payment = net_salary - amount_paid
    transfer_reference = ""
    transfer_result = None
    if pay_with_flutterwave:
        admin_wallet = get_or_create_admin_wallet(staff.tenant)
        transfer_reference = generate_reference("SAL")
        bank_payload = {
            "account_number": bank_account_number,
            "bank_code": bank_code,
            "account_name": bank_account_name,
            "bank_name": bank_name,
            "staff_id": str(staff.id),
            "staff_name": staff.full_name,
            "payroll_period": f"{year}-{month:02d}",
        }
        try:
            transfer_result = initiate_admin_withdrawal(
                admin_wallet,
                amount_paid,
                transfer_reference,
                bank_payload=bank_payload,
                actor=request.user,
            )
        except ValueError as exc:
            return Response({"success": False, "message": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as exc:
            return Response({"success": False, "message": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        staff.bank_code = bank_code
        staff.bank_account_number = bank_account_number
        staff.bank_account_name = bank_account_name
        staff.bank_name = bank_name
        staff.save(update_fields=["bank_code", "bank_account_number", "bank_account_name", "bank_name", "updated_at"])
    payroll, created = PayrollRecord.objects.update_or_create(
        staff=staff,
        year=year,
        month=month,
        defaults={
            "base_salary": staff.base_salary,
            "allowances": allowances,
            "deductions": deductions,
            "advances_applied": advances_applied,
            "gross_salary": gross_salary,
            "net_salary": net_salary,
            "amount_paid": amount_paid,
            "balance_after_payment": balance_after_payment,
            "status": PayrollRecord.PAID if amount_paid >= net_salary else PayrollRecord.APPROVED,
            "notes": str(request.data.get("notes", "")).strip()
            or ("Paid via Flutterwave transfer." if pay_with_flutterwave else ""),
            "processed_by": request.user,
            "paid_at": timezone.now() if amount_paid > 0 else None,
        },
    )
    staff.salary_balance = balance_after_payment
    staff.save(update_fields=["salary_balance", "updated_at"])
    if pay_with_flutterwave:
        _activity(staff.tenant, staff, request.user, "salary_paid_flutterwave", f"Salary payment sent for {payroll.period_label}: {amount_paid}")
        record_finance_activity(
            staff.tenant,
            request.user,
            "salary_payment_sent",
            f"Salary payment sent to {staff.full_name} for {payroll.period_label}.",
            amount=amount_paid,
            reference=transfer_reference,
            metadata={"staff_id": str(staff.id), "period": payroll.period_label, "status": payroll.status},
        )
        message = "Salary payment sent to staff via Flutterwave."
    else:
        _activity(staff.tenant, staff, request.user, "payroll_processed", f"Payroll {'created' if created else 'updated'} for {payroll.period_label}")
        record_finance_activity(
            staff.tenant,
            request.user,
            "payroll_processed",
            f"Payroll {'created' if created else 'updated'} for {staff.full_name} ({payroll.period_label}).",
            amount=payroll.net_salary,
            reference=str(payroll.id),
            metadata={"staff_id": str(staff.id), "period": payroll.period_label, "status": payroll.status},
        )
        message = "Payroll calculated."
    return Response(
        {
            "success": True,
            "message": message,
            "payroll": _payroll_payload(payroll),
            "transfer_reference": transfer_reference,
            "transfer_status": transfer_result.get("status") if transfer_result else "",
        },
        status=status.HTTP_201_CREATED if created else status.HTTP_200_OK,
    )
