from django import forms
from django.contrib.auth import get_user_model

from .models import PlatformNotification, SchoolTokenPaymentSetting


SUPER_ADMIN_FUNCTIONS = {
    "analytics": "Dashboard analytics and platform statistics",
    "schools": "School management and approval",
    "billing": "Subscriptions, billing, payments, and transactions",
    "virtual_accounts": "Virtual account management",
    "support": "Support ticket management",
    "announcements": "Announcements and notifications",
    "users": "User and role management",
    "audit_logs": "Audit logs and activity tracking",
    "settings": "System settings",
    "reports": "Reports and exports",
    "tokens": "School token pricing and payment controls",
}


class SuperAdminCreateForm(forms.Form):
    email = forms.EmailField()
    first_name = forms.CharField(max_length=150, required=False)
    last_name = forms.CharField(max_length=150, required=False)
    password = forms.CharField(widget=forms.PasswordInput, min_length=8)
    functions = forms.MultipleChoiceField(
        choices=list(SUPER_ADMIN_FUNCTIONS.items()),
        widget=forms.CheckboxSelectMultiple,
        required=False,
    )
    is_active = forms.BooleanField(required=False, initial=True)

    def clean_email(self):
        email = self.cleaned_data["email"].strip().lower()
        User = get_user_model()
        if User.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError("A user with this email already exists.")
        return email


class SuperAdminFunctionsForm(forms.Form):
    functions = forms.MultipleChoiceField(
        choices=list(SUPER_ADMIN_FUNCTIONS.items()),
        widget=forms.CheckboxSelectMultiple,
        required=False,
    )
    is_active = forms.BooleanField(required=False)


class SchoolTokenPaymentSettingForm(forms.ModelForm):
    class Meta:
        model = SchoolTokenPaymentSetting
        fields = [
            "token_price",
            "tokens_per_payment",
            "minimum_tokens",
            "payment_required",
            "is_active",
            "notes",
        ]
        widgets = {
            "notes": forms.Textarea(attrs={"rows": 3}),
        }


class PlatformNotificationForm(forms.ModelForm):
    class Meta:
        model = PlatformNotification
        fields = ["title", "message", "audience", "is_active", "publish_at"]
        widgets = {
            "message": forms.Textarea(attrs={"rows": 4}),
            "publish_at": forms.DateTimeInput(attrs={"type": "datetime-local"}),
        }
