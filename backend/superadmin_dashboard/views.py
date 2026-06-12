from django.contrib import messages
from django.contrib.auth.models import Group
from django.contrib.auth import get_user_model
from django.core.paginator import Paginator
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from .access import function_group_name, super_admin_required
from .forms import PlatformNotificationForm, SchoolTokenPaymentSettingForm, SuperAdminCreateForm, SuperAdminFunctionsForm, SUPER_ADMIN_FUNCTIONS
from .models import PlatformNotification, SchoolTokenPaymentSetting
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


def school_token_setting_for(school):
    return SchoolTokenPaymentSetting.objects.get_or_create(
        school_model=f"{school._meta.app_label}.{school._meta.model_name}",
        school_pk=str(school.pk),
        defaults={"school_name": str(school)},
    )[0]


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


@super_admin_required(function="tokens")
def school_token_settings(request, pk):
    School = platform_models()["school"]
    school = get_object_or_404(School, pk=pk)
    setting = school_token_setting_for(school)
    if setting.school_name != str(school):
        setting.school_name = str(school)
        setting.save(update_fields=["school_name", "updated_at"])

    if request.method == "POST":
        form = SchoolTokenPaymentSettingForm(request.POST, instance=setting)
        if form.is_valid():
            form.save()
            messages.success(request, "Token payment settings were updated.")
            return redirect("superadmin_dashboard:schools")
    else:
        form = SchoolTokenPaymentSettingForm(instance=setting)

    return render(request, "superadmin_dashboard/school_token_settings.html", {
        "school": school,
        "setting": setting,
        "form": form,
    })


@super_admin_required(function="billing")
def subscriptions(request):
    model = platform_models()["subscription"]
    if model is None:
        return missing_module(request, "Subscriptions")
    queryset, query, status = search_queryset(model, request, ["plan", "school__name", "reference"])
    return render(request, "superadmin_dashboard/list.html", {
        "title": "Subscriptions",
        "objects": paginate(request, queryset),
        "query": query,
        "status": status,
        "columns": ["school", "plan", "status", "created_at"],
    })


@super_admin_required(function="billing")
def payments(request):
    model = platform_models()["payment"] or platform_models()["transaction"]
    if model is None:
        return missing_module(request, "Payments and Transactions")
    queryset, query, status = search_queryset(model, request, ["reference", "school__name", "provider"])
    return render(request, "superadmin_dashboard/list.html", {
        "title": "Payments and Transactions",
        "objects": paginate(request, queryset),
        "query": query,
        "status": status,
        "columns": ["reference", "school", "amount", "status", "created_at"],
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
    queryset, query, status = search_queryset(model, request, ["action", "actor__email", "object_repr", "ip_address"])
    return render(request, "superadmin_dashboard/list.html", {
        "title": "Audit Logs",
        "objects": paginate(request, queryset),
        "query": query,
        "status": status,
        "columns": ["actor", "action", "object_repr", "ip_address", "created_at"],
    })


@super_admin_required(function="settings")
def system_settings(request):
    return render(request, "superadmin_dashboard/settings.html")


@super_admin_required(function="reports")
def reports(request):
    return render(request, "superadmin_dashboard/reports.html", dashboard_context())
