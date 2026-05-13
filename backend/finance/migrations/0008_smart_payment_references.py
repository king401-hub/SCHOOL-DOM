from decimal import Decimal
import uuid

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0001_initial"),
        ("users", "0001_initial"),
        ("finance", "0007_alter_transaction_provider"),
    ]

    operations = [
        migrations.CreateModel(
            name="StudentPaymentReference",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("code", models.CharField(max_length=32, unique=True)),
                ("is_active", models.BooleanField(default=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("student", models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name="payment_reference", to="users.studentprofile")),
                ("tenant", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name="student_payment_references", to="core.schooltenant")),
            ],
        ),
        migrations.CreateModel(
            name="BankPayment",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("amount", models.DecimalField(decimal_places=2, max_digits=14)),
                ("currency", models.CharField(default="NGN", max_length=5)),
                ("narration", models.CharField(max_length=255)),
                ("bank_reference", models.CharField(max_length=100, unique=True)),
                ("status", models.CharField(choices=[("pending", "Pending"), ("confirmed", "Confirmed"), ("partial", "Partial"), ("failed", "Failed"), ("unmatched", "Unmatched")], default="pending", max_length=16)),
                ("applied_amount", models.DecimalField(decimal_places=2, default=Decimal("0.00"), max_digits=14)),
                ("unapplied_amount", models.DecimalField(decimal_places=2, default=Decimal("0.00"), max_digits=14)),
                ("matched_at", models.DateTimeField(blank=True, null=True)),
                ("receipt_number", models.CharField(blank=True, max_length=64, null=True, unique=True)),
                ("metadata", models.JSONField(blank=True, default=dict)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("payment_reference", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="bank_payments", to="finance.studentpaymentreference")),
                ("student", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="bank_payments", to="users.studentprofile")),
                ("tenant", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name="bank_payments", to="core.schooltenant")),
            ],
            options={
                "ordering": ["-created_at"],
            },
        ),
        migrations.AddIndex(
            model_name="studentpaymentreference",
            index=models.Index(fields=["tenant", "code"], name="finance_stu_tenant__5e24fb_idx"),
        ),
        migrations.AddIndex(
            model_name="studentpaymentreference",
            index=models.Index(fields=["student"], name="finance_stu_student_9c4f3a_idx"),
        ),
        migrations.AddIndex(
            model_name="bankpayment",
            index=models.Index(fields=["tenant", "status"], name="finance_ban_tenant__ce1f3c_idx"),
        ),
        migrations.AddIndex(
            model_name="bankpayment",
            index=models.Index(fields=["student", "created_at"], name="finance_ban_student_fde675_idx"),
        ),
        migrations.AddIndex(
            model_name="bankpayment",
            index=models.Index(fields=["bank_reference"], name="finance_ban_bank_re_7f5b52_idx"),
        ),
    ]
