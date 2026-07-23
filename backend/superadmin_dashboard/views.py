from django.contrib import messages
from django.contrib.auth.models import Group
from django.contrib.auth import get_user_model
from django.core.paginator import Paginator
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from .access import function_group_name, super_admin_required
from .forms import PlatformNotificationForm, SuperAdminCreateForm, SuperAdminFunctionsForm, SUPER_ADMIN_FUNCTIONS
from .models import PlatformNotification
from .services import dashboard_context, platform_models, search_queryset


def paginate(request, queryset, per_page=25):
    paginator = Paginator(queryset, per_page)
    return paginator.get_page(request.GET.get("page"))


def missing_module(request, title):
    return render(request, "superadmin_dashboard/list.html", {
        "title": title,
        "missing": True,
        "objects": [],
        "columns": [],
    })


def apply_function_groups(user, functions):
    platform_group, _ = Group.objects.get_or_create(name="Platform Admin")
    user.groups.add(platform_group)

    function_group_names = [function_group_name(key) for key in SUPER_ADMIN_FUNCTIONS]
    user.groups.remove(*Group.objects.filter(name__in=function_group_names))

    for function in functions:
        group, _ = Group.objects.get_or_create(name=function_group_name(function))
        user.groups.add(group)


def user_function_keys(user):
    names = set(user.groups.values_list("name", flat=True))
    return [
        key for key in SUPER_ADMIN_FUNCTIONS
        if function_group_name(key) in names
    ]


def create_staff_user(form):
    User = get_user_model()
    data = {
        "email": form.cleaned_data["email"],
        "password": form.cleaned_data["password"],
        "first_name": form.cleaned_data["first_name"],
        "last_name": form.cleaned_data["last_name"],
        "is_active": form.cleaned_data["is_active"],
        "is_staff": True,
    }
    field_names = {field.name for field in User._meta.fields}
    if "username" in field_names:
        data["username"] = form.cleaned_data["email"]
    return User.objects.create_user(**{
        key: value for key, value in data.items()
        if key in field_names or key == "password"
    })


@super_admin_required
def dashboard(request):
    return render(request, "superadmin_dashboard/dashboard.html", dashboard_context())


@super_admin_required(function="schools")
def schools(request):
    School = platform_models()["school"]
    if School is None:
        return missing_module(request, "Schools")
    queryset, query, status = search_queryset(School, request, ["name", "email", "schema_name", "domains__domain"])
    return render(request, "superadmin_dashboard/schools.html", {
        "objects": paginate(request, queryset),
        "query": query,
        "status": status,
    })


@require_POST
@super_admin_required(function="schools")
def school_action(request, pk, action):
    School = platform_models()["school"]
    school = get_object_or_404(School, pk=pk)
    transitions = {
        "approve": (True, "approved"),
        "suspend": (False, "suspended"),
        "reactivate": (True, "reactivated"),
    }
    if action not in transitions:
        messages.error(request, "Unknown school action.")
        return redirect("superadmin_dashboard:schools")
    next_is_active, action_label = transitions[action]
    if hasattr(school, "is_active"):
        school.is_active = next_is_active
        school.save(update_fields=["is_active"])
    else:
        setattr(school, "status", "active" if next_is_active else "suspended")
        school.save(update_fields=["status"])
    messages.success(request, f"{school} was {action_label}.")
    return redirect("superadmin_dashboard:schools")


@super_admin_required(function="schools")
def compliance(request):
    School = platform_models()["school"]
    if School is None:
        return missing_module(request, "Compliance")
    User = get_user_model()

    status_filter = request.GET.get("status", "submitted").strip()
    queryset = School.objects.all()
    if status_filter and status_filter != "all":
        queryset = queryset.filter(compliance_status=status_filter)
    queryset = queryset.order_by("-compliance_submitted_at", "-created_on")

    page_obj = paginate(request, queryset)
    rows = []
    for school in page_obj:
        director = (
            User.objects.filter(tenant=school, role__in=["school_admin", "principal", "school_superadmin"])
            .order_by("created_at")
            .first()
        )
        rows.append({"school": school, "director": director})

    return render(request, "superadmin_dashboard/compliance.html", {
        "rows": rows,
        "page_obj": page_obj,
        "status": status_filter,
        "status_choices": School.COMPLIANCE_STATUS_CHOICES,
    })


@require_POST
@super_admin_required(function="schools")
def compliance_action(request, pk, action):
    School = platform_models()["school"]
    school = get_object_or_404(School, pk=pk)

    if action == "approve":
        school.compliance_status = "approved"
        school.compliance_reviewed_at = timezone.now()
        school.compliance_reviewed_by = request.user
        school.save(update_fields=["compliance_status", "compliance_reviewed_at", "compliance_reviewed_by"])
        _send_compliance_review_email(school, approved=True)
        messages.success(request, f"{school} compliance documents were approved.")
    elif action == "reject":
        school.compliance_status = "rejected"
        school.compliance_reviewed_at = timezone.now()
        school.compliance_reviewed_by = request.user
        school.compliance_deadline_reference_at = timezone.now()
        school.compliance_reminder_stage = 0
        school.save(update_fields=[
            "compliance_status", "compliance_reviewed_at", "compliance_reviewed_by",
            "compliance_deadline_reference_at", "compliance_reminder_stage",
        ])
        _send_compliance_review_email(school, approved=False)
        messages.success(request, f"{school} compliance documents were rejected. They have 30 fresh days to resubmit.")
    else:
        messages.error(request, "Unknown compliance action.")
    return redirect("superadmin_dashboard:compliance")


def _send_compliance_review_email(school, approved):
    from django.conf import settings
    from django.core.mail import send_mail

    User = get_user_model()
    director = (
        User.objects.filter(tenant=school, role__in=["school_admin", "principal", "school_superadmin"])
        .order_by("created_at")
        .first()
    )
    recipient = (director.email if director else "") or school.email
    if not recipient:
        return
    if approved:
        subject = "Your SchoolDom compliance documents were approved"
        body = f"Good news! {school.name}'s compliance documents have been reviewed and approved."
    else:
        subject = "Your SchoolDom compliance documents need attention"
        body = (
            f"Your compliance documents for {school.name} were reviewed and could not be approved as submitted.\n\n"
            "Please log in, review the documents in School Settings, and resubmit. "
            "Contact support@schooldom.academy if you have questions."
        )
    try:
        send_mail(subject, body, settings.DEFAULT_FROM_EMAIL, [recipient], fail_silently=True)
    except Exception:
        pass


@super_admin_required(function="tokens")
def school_token_settings(request, pk):
    """Grant SMS credits / activation tokens to a school and adjust its token price.
    Writes directly to the real finance models (SmsWallet, ActivationCreditPool) that
    the actual purchase/activation flow reads - not a disconnected settings record."""
    from decimal import Decimal, InvalidOperation

    from finance.models import ActivationCreditTransaction, SmsWalletTransaction
    from finance.services import (
        generate_reference,
        get_or_create_activation_credit_pool,
        get_or_create_sms_wallet,
        record_finance_activity,
    )

    School = platform_models()["school"]
    school = get_object_or_404(School, pk=pk)
    wallet = get_or_create_sms_wallet(school)
    pool = get_or_create_activation_credit_pool(school)

    if request.method == "POST":
        action = request.POST.get("action")

        if action == "add_sms_credits":
            try:
                credits = int(request.POST.get("sms_credits") or 0)
            except ValueError:
                credits = 0
            if credits > 0:
                balance_before = wallet.balance
                wallet.balance += credits
                wallet.save(update_fields=["balance", "updated_at"])
                SmsWalletTransaction.objects.create(
                    wallet=wallet,
                    tx_type=SmsWalletTransaction.ADMIN_CREDIT,
                    status=SmsWalletTransaction.STATUS_SUCCESS,
                    credits=credits,
                    balance_before=balance_before,
                    balance_after=wallet.balance,
                    reference=generate_reference("SMSADM"),
                    narration=f"Manual credit grant by {request.user}",
                    created_by=request.user,
                )
                record_finance_activity(
                    school, request.user, "sms_credits_granted",
                    f"Granted {credits} SMS credits.", reference=str(wallet.id),
                    metadata={"credits": credits},
                )
                messages.success(request, f"Added {credits} SMS credits to {school}.")
            else:
                messages.error(request, "Enter a number of SMS credits greater than zero.")
            return redirect("superadmin_dashboard:school_token_settings", pk=pk)

        if action == "add_tokens":
            try:
                credits = int(request.POST.get("token_credits") or 0)
            except ValueError:
                credits = 0
            if credits > 0:
                pool.balance += credits
                pool.save(update_fields=["balance", "updated_at"])
                ActivationCreditTransaction.objects.create(
                    pool=pool,
                    tx_type=ActivationCreditTransaction.ADJUSTMENT,
                    status=ActivationCreditTransaction.STATUS_SUCCESS,
                    credits=credits,
                    price_per_credit=pool.price_per_credit,
                    amount=Decimal("0.00"),
                    reference=generate_reference("TOKADM"),
                    narration=f"Manual token grant by {request.user}",
                    created_by=request.user,
                )
                record_finance_activity(
                    school, request.user, "tokens_granted",
                    f"Granted {credits} activation tokens.", reference=str(pool.id),
                    metadata={"credits": credits},
                )
                messages.success(request, f"Added {credits} activation tokens to {school}.")
            else:
                messages.error(request, "Enter a number of tokens greater than zero.")
            return redirect("superadmin_dashboard:school_token_settings", pk=pk)

        if action == "update_token_price":
            try:
                new_price = Decimal(request.POST.get("token_price") or "0")
            except InvalidOperation:
                new_price = Decimal("0")
            if new_price > 0:
                old_price = pool.price_per_credit
                pool.price_per_credit = new_price
                pool.save(update_fields=["price_per_credit", "updated_at"])
                record_finance_activity(
                    school, request.user, "token_price_updated",
                    "Updated activation token price.", amount=new_price, reference=str(pool.id),
                    metadata={"old_price": str(old_price), "new_price": str(new_price)},
                )
                messages.success(request, f"Token price for {school} updated to {pool.currency} {new_price}.")
            else:
                messages.error(request, "Enter a token price greater than zero.")
            return redirect("superadmin_dashboard:school_token_settings", pk=pk)

        messages.error(request, "Unknown action.")
        return redirect("superadmin_dashboard:school_token_settings", pk=pk)

    return render(request, "superadmin_dashboard/school_token_settings.html", {
        "school": school,
        "wallet": wallet,
        "pool": pool,
    })


@super_admin_required(function="billing")
def subscriptions(request):
    model = platform_models()["subscription"]
    if model is None:
        return missing_module(request, "Subscriptions")
    queryset, query, status = search_queryset(model, request, ["name", "schema_name", "school_group__name"], default_order="name")
    return render(request, "superadmin_dashboard/list.html", {
        "title": "Subscriptions",
        "objects": paginate(request, queryset),
        "query": query,
        "status": status,
        "columns": ["name", "subscription_tier", "is_active", "created_on"],
    })


@super_admin_required(function="billing")
def payments(request):
    model = platform_models()["payment"] or platform_models()["transaction"]
    if model is None:
        return missing_module(request, "Payments and Transactions")
    queryset, query, status = search_queryset(model, request, ["provider_reference", "school__name", "provider", "payer_name"])
    return render(request, "superadmin_dashboard/list.html", {
        "title": "Payments and Transactions",
        "objects": paginate(request, queryset),
        "query": query,
        "status": status,
        "columns": ["provider_reference", "school", "gross_amount", "status", "paid_at"],
    })


@super_admin_required(function="billing")
def finance_ledger(request):
    model = platform_models()["finance_ledger"]
    if model is None:
        return missing_module(request, "Finance Ledger")
    queryset, query, status = search_queryset(model, request, ["action", "description", "reference", "tenant__name", "actor__email"])
    return render(request, "superadmin_dashboard/list.html", {
        "title": "Finance Ledger",
        "objects": paginate(request, queryset),
        "query": query,
        "status": status,
        "columns": ["tenant", "actor", "action", "description", "amount", "created_at"],
    })


@super_admin_required(function="virtual_accounts")
def virtual_accounts(request):
    model = platform_models()["virtual_account"]
    if model is None:
        return missing_module(request, "Virtual Accounts")
    queryset, query, status = search_queryset(model, request, ["account_number", "account_name", "bank_name", "school__name"])
    return render(request, "superadmin_dashboard/list.html", {
        "title": "Virtual Accounts",
        "objects": paginate(request, queryset),
        "query": query,
        "status": status,
        "columns": ["school", "bank_name", "account_number", "status"],
    })


@super_admin_required(function="support")
def support_tickets(request):
    model = platform_models()["ticket"]
    if model is None:
        return missing_module(request, "Support Tickets")
    queryset, query, status = search_queryset(model, request, ["subject", "school__name", "created_by__email"])
    return render(request, "superadmin_dashboard/list.html", {
        "title": "Support Tickets",
        "objects": paginate(request, queryset),
        "query": query,
        "status": status,
        "columns": ["subject", "school", "status", "priority", "created_at"],
    })


@super_admin_required(function="announcements")
def announcements(request):
    if request.method == "POST":
        form = PlatformNotificationForm(request.POST)
        if form.is_valid():
            notification = form.save(commit=False)
            notification.created_by = request.user
            notification.save()
            messages.success(request, "Notification was published.")
            return redirect("superadmin_dashboard:announcements")
    else:
        form = PlatformNotificationForm()

    queryset, query, status = search_queryset(PlatformNotification, request, ["title", "message", "audience"])
    return render(request, "superadmin_dashboard/announcements.html", {
        "title": "Announcements and Notifications",
        "objects": paginate(request, queryset),
        "query": query,
        "status": status,
        "form": form,
    })


@super_admin_required(function="users")
def users(request):
    User = get_user_model()
    queryset, query, status = search_queryset(User, request, ["email", "first_name", "last_name"], "email")
    return render(request, "superadmin_dashboard/list.html", {
        "title": "Users and Roles",
        "objects": paginate(request, queryset),
        "query": query,
        "status": status,
        "columns": ["email", "first_name", "last_name", "role", "is_active", "is_staff", "is_superuser"],
        "create_url": "superadmin_dashboard:create_super_admin",
    })


@super_admin_required(function="users")
def create_super_admin(request):
    if request.method == "POST":
        form = SuperAdminCreateForm(request.POST)
        if form.is_valid():
            User = get_user_model()
            user = create_staff_user(form)
            apply_function_groups(user, form.cleaned_data["functions"])
            messages.success(request, "Super admin was created with selected functions.")
            return redirect("superadmin_dashboard:users")
    else:
        form = SuperAdminCreateForm()
    return render(request, "superadmin_dashboard/super_admin_form.html", {
        "form": form,
        "title": "Create Super Admin",
    })


@super_admin_required(function="users")
def edit_super_admin_functions(request, pk):
    User = get_user_model()
    user = get_object_or_404(User, pk=pk)
    if request.method == "POST":
        form = SuperAdminFunctionsForm(request.POST)
        if form.is_valid():
            user.is_active = form.cleaned_data["is_active"]
            user.is_staff = True
            user.save(update_fields=["is_active", "is_staff"])
            apply_function_groups(user, form.cleaned_data["functions"])
            messages.success(request, "Super admin functions were updated.")
            return redirect("superadmin_dashboard:users")
    else:
        form = SuperAdminFunctionsForm(initial={
            "functions": user_function_keys(user),
            "is_active": user.is_active,
        })
    return render(request, "superadmin_dashboard/super_admin_form.html", {
        "form": form,
        "title": f"Edit Functions for {user.email}",
        "managed_user": user,
    })


@super_admin_required(function="audit_logs")
def audit_logs(request):
    model = platform_models()["audit_log"]
    if model is None:
        return missing_module(request, "Audit Logs")
    queryset, query, status = search_queryset(model, request, ["user__email", "object_repr", "change_message"], default_order="-action_time")
    return render(request, "superadmin_dashboard/list.html", {
        "title": "Audit Logs",
        "objects": paginate(request, queryset),
        "query": query,
        "status": status,
        "columns": ["user", "object_repr", "get_change_message", "action_time"],
    })


@super_admin_required(function="settings")
def system_settings(request):
    return render(request, "superadmin_dashboard/settings.html")


@super_admin_required(function="reports")
def reports(request):
    return render(request, "superadmin_dashboard/reports.html", dashboard_context())
