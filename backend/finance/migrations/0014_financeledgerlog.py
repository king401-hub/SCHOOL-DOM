from decimal import Decimal
import uuid

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0004_auditlog_user_and_more"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("finance", "0013_schoolfee_is_customized"),
    ]

    operations = [
        migrations.CreateModel(
            name="FinanceLedgerLog",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("action", models.CharField(max_length=80)),
                ("description", models.CharField(max_length=255)),
                ("amount", models.DecimalField(decimal_places=2, default=Decimal("0.00"), max_digits=16)),
                ("currency", models.CharField(default="NGN", max_length=5)),
                ("reference", models.CharField(blank=True, max_length=100)),
                ("metadata", models.JSONField(blank=True, default=dict)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("actor", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="finance_ledger_logs", to=settings.AUTH_USER_MODEL)),
                ("tenant", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="finance_ledger_logs", to="core.schooltenant")),
            ],
            options={
                "ordering": ["-created_at"],
            },
        ),
        migrations.AddIndex(
            model_name="financeledgerlog",
            index=models.Index(fields=["tenant", "created_at"], name="finance_fin_tenant__52c38a_idx"),
        ),
        migrations.AddIndex(
            model_name="financeledgerlog",
            index=models.Index(fields=["action"], name="finance_fin_action_d8eb4f_idx"),
        ),
        migrations.AddIndex(
            model_name="financeledgerlog",
            index=models.Index(fields=["reference"], name="finance_fin_referen_23fa6b_idx"),
        ),
    ]
