import csv
import re
import secrets
import string
from io import StringIO
from decimal import Decimal

from django.contrib import messages
from django.contrib.auth import get_user_model, login, views as auth_views
from django.contrib.auth.decorators import login_required
from django.db.models import Sum
from django.db import transaction
from django.http import HttpResponse, JsonResponse
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils.text import slugify
from django.views import View
from django.views.generic import TemplateView

from core.models import SchoolGroup, SchoolTenant
from fee_collections.models import FeePayment
from finance.models import SchoolFee
from hr.models import StaffProfile
from users.models import StudentProfile


class LoginView(auth_views.LoginView):
    template_name = "auth/login.html"
    redirect_authenticated_user = True

    def get_success_url(self):
        user = self.request.user
        if getattr(user, "role", "") == "school_superadmin":
            return reverse("school_superadmin_dashboard")
        return super().get_success_url()


class LogoutView(auth_views.LogoutView):
    next_page = "login"


class RegisterView(TemplateView):
    template_name = "auth/register.html"

    def post(self, request, *args, **kwargs):
        data = request.POST
        role = data.get("role")
        email = (data.get("email") or "").strip().lower()
        password = data.get("password") or ""
        full_name = (data.get("full_name") or "").strip()

        if role not in {"school_superadmin", "school_admin"}:
            messages.error(request, "Please choose a valid account type.")
            return self.get(request, *args, **kwargs)

        if not email or not password or not full_name:
            messages.error(request, "Please enter your name, email, and password.")
            return self.get(request, *args, **kwargs)

        User = get_user_model()
        if User.objects.filter(email__iexact=email).exists():
            messages.error(request, "An account with this email already exists.")
            return self.get(request, *args, **kwargs)

        first_name, last_name = split_full_name(full_name)

        try:
            with transaction.atomic():
                if role == "school_superadmin":
                    user = User.objects.create_user(
                        email=email,
                        password=password,
                        first_name=first_name,
                        last_name=last_name,
                        role="school_superadmin",
                        is_active=True,
                        is_verified=True,
                    )
                    group_name = (data.get("school_group_name") or "").strip()
                    if not group_name:
                        raise ValueError("Please enter your school group name.")
                    group = SchoolGroup.objects.create(name=group_name, owner=user)
                    user.school_group = group
                    user.save(update_fields=["school_group"])
                    messages.success(request, "School Superadmin account created. Add your schools from here.")
                    login(request, user)
                    return redirect("school_superadmin_dashboard")

                school_name = (data.get("school_name") or "").strip()
                school_address = (data.get("school_address") or "").strip()
                school_role = data.get("school_admin_role") or "school_admin"
                if school_role not in {"school_admin", "principal"}:
                    school_role = "school_admin"
                if not school_name:
                    raise ValueError("Please enter the school name.")

                school = SchoolTenant.objects.create(
                    name=school_name,
                    schema_name=unique_schema_name(school_name),
                    address=school_address,
                    email=email,
                    currency="NGN",
                )
                user = User.objects.create_user(
                    email=email,
                    password=password,
                    first_name=first_name,
                    last_name=last_name,
                    role=school_role,
                    tenant=school,
                    is_active=True,
                    is_verified=True,
                )
                messages.success(request, "School account created successfully.")
                login(request, user)
                return redirect("school_settings")
        except ValueError as exc:
            messages.error(request, str(exc))
        except Exception:
            messages.error(request, "We could not create the account. Please try again.")

        return self.get(request, *args, **kwargs)


def split_full_name(full_name):
    parts = full_name.split()
    if not parts:
        return "", ""
    if len(parts) == 1:
        return parts[0], ""
    return parts[0], " ".join(parts[1:])


def unique_schema_name(name):
    base = slugify(name).replace("-", "_")
    base = re.sub(r"[^a-zA-Z0-9_]", "", base).lower()[:50] or "school"
    candidate = base
    index = 2
    while SchoolTenant.objects.filter(schema_name=candidate).exists():
        suffix = f"_{index}"
        candidate = f"{base[:63 - len(suffix)]}{suffix}"
        index += 1
    return candidate


def temporary_password(length=10):
    alphabet = string.ascii_letters + string.digits
    return "".join(secrets.choice(alphabet) for _ in range(length))


def money_value(value):
    return value or Decimal("0.00")


def collection_status(collected, outstanding):
    total_expected = collected + outstanding
    if total_expected <= 0:
        return "No data", Decimal("0")

    rate = (collected / total_expected) * Decimal("100")
    if rate < 40:
        return "Critical", rate
    if rate < 60:
        return "At Risk", rate
    return "Healthy", rate


def school_superadmin_finance_context(group):
    rows = []
    totals = {
        "students": 0,
        "staff": 0,
        "collected": Decimal("0.00"),
        "outstanding": Decimal("0.00"),
    }

    schools = group.schools.order_by("name")
    for school in schools:
        collected = money_value(
            FeePayment.objects.filter(
                school=school,
                status=FeePayment.STATUS_SUCCESSFUL,
            ).aggregate(total=Sum("gross_amount"))["total"]
        )
        outstanding = money_value(
            SchoolFee.objects.filter(
                student__user__tenant=school,
                status__in=[SchoolFee.STATUS_PENDING, SchoolFee.STATUS_OVERDUE],
            ).aggregate(total=Sum("amount"))["total"]
        )
        students = StudentProfile.objects.filter(user__tenant=school).count()
        staff = StaffProfile.objects.filter(tenant=school).count()
        status, rate = collection_status(collected, outstanding)

        totals["students"] += students
        totals["staff"] += staff
        totals["collected"] += collected
        totals["outstanding"] += outstanding
        rows.append({
            "school": school,
            "students": students,
            "staff": staff,
            "collected": collected,
            "outstanding": outstanding,
            "status": status,
            "rate": rate,
        })

    total_status, total_rate = collection_status(totals["collected"], totals["outstanding"])
    defaulters = (
        SchoolFee.objects
        .filter(
            student__user__tenant__school_group=group,
            status__in=[SchoolFee.STATUS_PENDING, SchoolFee.STATUS_OVERDUE],
        )
        .select_related("student__user", "student__user__tenant")
        .order_by("-amount")[:5]
    )

    return {
        "finance_rows": rows,
        "finance_totals": {
            **totals,
            "status": total_status,
            "rate": total_rate,
        },
        "top_defaulters": defaulters,
    }


def export_school_superadmin_finance_csv(group):
    context = school_superadmin_finance_context(group)
    buffer = StringIO()
    writer = csv.writer(buffer)
    writer.writerow(["Branch", "Students", "Staff", "Collected", "Outstanding", "Collection Rate", "Status"])
    for row in context["finance_rows"]:
        writer.writerow([
            row["school"].name,
            row["students"],
            row["staff"],
            row["collected"],
            row["outstanding"],
            f"{row['rate']:.1f}%",
            row["status"],
        ])
    totals = context["finance_totals"]
    writer.writerow([
        "Total",
        totals["students"],
        totals["staff"],
        totals["collected"],
        totals["outstanding"],
        f"{totals['rate']:.1f}%",
        totals["status"],
    ])

    response = HttpResponse(content_type="text/csv")
    response["Content-Disposition"] = 'attachment; filename="school-superadmin-finance.csv"'
    response.write(buffer.getvalue())
    return response


@login_required(login_url="/login/")
def school_superadmin_dashboard(request):
    user = request.user
    if getattr(user, "role", "") != "school_superadmin":
        messages.error(request, "Only School Superadmins can access this page.")
        return redirect("school_settings")

    group = user.school_group or user.owned_school_groups.first()
    if not group:
        group = SchoolGroup.objects.create(name=f"{user.get_full_name() or user.email} Schools", owner=user)
        user.school_group = group
        user.save(update_fields=["school_group"])

    if request.GET.get("export") == "finance_csv":
        return export_school_superadmin_finance_csv(group)

    generated_login = None

    if request.method == "POST":
        action = request.POST.get("action")
        try:
            with transaction.atomic():
                if action == "add_school":
                    school_name = (request.POST.get("school_name") or "").strip()
                    if not school_name:
                        raise ValueError("Enter a school name.")
                    SchoolTenant.objects.create(
                        name=school_name,
                        schema_name=unique_schema_name(school_name),
                        school_group=group,
                        address=(request.POST.get("school_address") or "").strip(),
                        email=(request.POST.get("school_email") or "").strip(),
                        currency="NGN",
                    )
                    messages.success(request, f"{school_name} was added to your school group.")
                    return redirect("school_superadmin_dashboard")

                if action == "add_admin":
                    school = group.schools.get(pk=request.POST.get("school_id"))
                    email = (request.POST.get("admin_email") or "").strip().lower()
                    full_name = (request.POST.get("admin_name") or "").strip()
                    admin_role = request.POST.get("admin_role") or "school_admin"
                    if admin_role not in {"school_admin", "principal", "accountant"}:
                        admin_role = "school_admin"
                    if not email or not full_name:
                        raise ValueError("Enter the admin name and email.")

                    User = get_user_model()
                    if User.objects.filter(email__iexact=email).exists():
                        raise ValueError("An account with this admin email already exists.")

                    first_name, last_name = split_full_name(full_name)
                    password = temporary_password()
                    User.objects.create_user(
                        email=email,
                        password=password,
                        first_name=first_name,
                        last_name=last_name,
                        role=admin_role,
                        tenant=school,
                        school_group=group,
                        is_active=True,
                        is_verified=True,
                    )
                    generated_login = {
                        "school": school.name,
                        "email": email,
                        "password": password,
                    }
                    messages.success(request, f"Admin login created for {school.name}.")

                if action == "send_reminders":
                    defaulter_count = SchoolFee.objects.filter(
                        student__user__tenant__school_group=group,
                        status__in=[SchoolFee.STATUS_PENDING, SchoolFee.STATUS_OVERDUE],
                    ).values("student_id").distinct().count()
                    messages.success(
                        request,
                        f"Reminder workflow queued for {defaulter_count} defaulter"
                        f"{'' if defaulter_count == 1 else 's'} across your schools.",
                    )
                    return redirect("school_superadmin_dashboard")
        except SchoolTenant.DoesNotExist:
            messages.error(request, "That school does not belong to your group.")
        except ValueError as exc:
            messages.error(request, str(exc))

    finance_context = school_superadmin_finance_context(group)
    return render(request, "auth/school_superadmin_dashboard.html", {
        "group": group,
        "schools": group.schools.order_by("name"),
        "admins": get_user_model().objects.filter(school_group=group).exclude(pk=user.pk).select_related("tenant").order_by("tenant__name", "email"),
        "generated_login": generated_login,
        **finance_context,
    })


class APILoginView(View):
    def post(self, request, *args, **kwargs):
        return JsonResponse({"detail": "Not implemented yet."}, status=501)


class APIRegisterView(View):
    def post(self, request, *args, **kwargs):
        return JsonResponse({"detail": "Not implemented yet."}, status=501)


class CheckEmailView(View):
    def get(self, request, *args, **kwargs):
        return JsonResponse({"detail": "Not implemented yet."}, status=501)


class SendVerificationView(View):
    def post(self, request, *args, **kwargs):
        return JsonResponse({"detail": "Not implemented yet."}, status=501)


class GoogleLoginView(View):
    def post(self, request, *args, **kwargs):
        return JsonResponse({"detail": "Not implemented yet."}, status=501)


class MicrosoftLoginView(View):
    def post(self, request, *args, **kwargs):
        return JsonResponse({"detail": "Not implemented yet."}, status=501)
