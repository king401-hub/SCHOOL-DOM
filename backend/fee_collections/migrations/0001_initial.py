from decimal import Decimal
import uuid

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ("core", "0001_initial"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="CollectionConfig",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("commission_type", models.CharField(choices=[("percentage", "Percentage"), ("flat", "Flat")], default="percentage", max_length=16)),
                ("commission_value", models.DecimalField(decimal_places=2, default=Decimal("1.50"), max_digits=10)),
                ("minimum_commission", models.DecimalField(decimal_places=2, default=Decimal("0.00"), max_digits=12)),
                ("maximum_commission", models.DecimalField(blank=True, decimal_places=2, max_digits=12, null=True)),
                ("settlement_frequency", models.CharField(choices=[("daily", "Daily"), ("weekly", "Weekly")], default="daily", max_length=16)),
                ("settlement_weekday", models.PositiveSmallIntegerField(default=0, help_text="Monday=0, Sunday=6")),
                ("auto_settlement_enabled", models.BooleanField(default=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={
                "verbose_name": "Collection configuration",
                "verbose_name_plural": "Collection configuration",
            },
        ),
        migrations.CreateModel(
            name="SchoolCollectionProfile",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("status", models.CharField(choices=[("pending", "Pending"), ("approved", "Approved"), ("suspended", "Suspended")], default="pending", max_length=16)),
                ("bank_name", models.CharField(max_length=120)),
                ("bank_code", models.CharField(max_length=30)),
                ("account_number", models.CharField(max_length=20)),
                ("account_name", models.CharField(max_length=160)),
                ("approved_at", models.DateTimeField(blank=True, null=True)),
                ("metadata", models.JSONField(blank=True, default=dict)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("approved_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="approved_collection_profiles", to=settings.AUTH_USER_MODEL)),
                ("school", models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name="collection_profile", to="core.schooltenant")),
            ],
        ),
        migrations.CreateModel(
            name="SchoolVirtualAccount",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("provider", models.CharField(default="flutterwave", max_length=30)),
                ("account_number", models.CharField(max_length=20, unique=True)),
                ("account_name", models.CharField(max_length=160)),
                ("bank_name", models.CharField(default="Flutterwave", max_length=120)),
                ("provider_reference", models.CharField(max_length=120, unique=True)),
                ("order_reference", models.CharField(blank=True, max_length=120)),
                ("status", models.CharField(choices=[("pending", "Pending"), ("active", "Active"), ("failed", "Failed"), ("disabled", "Disabled")], default="pending", max_length=16)),
                ("raw_response", models.JSONField(blank=True, default=dict)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("school", models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name="fee_virtual_account", to="core.schooltenant")),
            ],
        ),
        migrations.CreateModel(
            name="FeePayment",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("provider", models.CharField(default="flutterwave", max_length=30)),
                ("provider_reference", models.CharField(max_length=120, unique=True)),
                ("session_id", models.CharField(blank=True, db_index=True, max_length=120)),
                ("payer_name", models.CharField(blank=True, max_length=160)),
                ("payer_account_number", models.CharField(blank=True, max_length=30)),
                ("payer_bank_name", models.CharField(blank=True, max_length=120)),
                ("narration", models.CharField(blank=True, max_length=255)),
                ("currency", models.CharField(default="NGN", max_length=5)),
                ("gross_amount", models.DecimalField(decimal_places=2, max_digits=14)),
                ("platform_fee", models.DecimalField(decimal_places=2, max_digits=14)),
                ("net_amount", models.DecimalField(decimal_places=2, max_digits=14)),
                ("status", models.CharField(choices=[("pending", "Pending"), ("successful", "Successful"), ("failed", "Failed"), ("duplicate", "Duplicate")], default="successful", max_length=16)),
                ("paid_at", models.DateTimeField()),
                ("raw_payload", models.JSONField(blank=True, default=dict)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("school", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="fee_collection_payments", to="core.schooltenant")),
                ("virtual_account", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="payments", to="fee_collections.schoolvirtualaccount")),
            ],
            options={
                "ordering": ["-paid_at", "-created_at"],
            },
        ),
        migrations.CreateModel(
            name="SchoolSettlement",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("gross_amount", models.DecimalField(decimal_places=2, default=Decimal("0.00"), max_digits=14)),
                ("platform_fee", models.DecimalField(decimal_places=2, default=Decimal("0.00"), max_digits=14)),
                ("net_amount", models.DecimalField(decimal_places=2, max_digits=14)),
                ("currency", models.CharField(default="NGN", max_length=5)),
                ("transfer_reference", models.CharField(max_length=120, unique=True)),
                ("provider_transfer_id", models.CharField(blank=True, max_length=120)),
                ("status", models.CharField(choices=[("pending", "Pending"), ("processing", "Processing"), ("successful", "Successful"), ("failed", "Failed")], default="pending", max_length=16)),
                ("scheduled_for", models.DateField()),
                ("settled_at", models.DateTimeField(blank=True, null=True)),
                ("failure_reason", models.TextField(blank=True)),
                ("raw_response", models.JSONField(blank=True, default=dict)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("payments", models.ManyToManyField(blank=True, related_name="settlements", to="fee_collections.feepayment")),
                ("school", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="fee_settlements", to="core.schooltenant")),
            ],
            options={
                "ordering": ["-created_at"],
            },
        ),
        migrations.CreateModel(
            name="CollectionAuditLog",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("action", models.CharField(max_length=80)),
                ("reference", models.CharField(blank=True, max_length=120)),
                ("message", models.CharField(max_length=255)),
                ("metadata", models.JSONField(blank=True, default=dict)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("actor", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="collection_audit_logs", to=settings.AUTH_USER_MODEL)),
                ("school", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="collection_audit_logs", to="core.schooltenant")),
            ],
            options={
                "ordering": ["-created_at"],
            },
        ),
        migrations.AddIndex(model_name="schoolcollectionprofile", index=models.Index(fields=["school", "status"], name="fee_collect_school__9f2f6b_idx")),
        migrations.AddIndex(model_name="schoolcollectionprofile", index=models.Index(fields=["status"], name="fee_collect_status_28d9ff_idx")),
        migrations.AddIndex(model_name="schoolvirtualaccount", index=models.Index(fields=["account_number"], name="fee_collect_account_0337e2_idx")),
        migrations.AddIndex(model_name="schoolvirtualaccount", index=models.Index(fields=["provider_reference"], name="fee_collect_provide_948c7d_idx")),
        migrations.AddIndex(model_name="schoolvirtualaccount", index=models.Index(fields=["school", "status"], name="fee_collect_school__ff4e07_idx")),
        migrations.AddIndex(model_name="feepayment", index=models.Index(fields=["school", "status", "paid_at"], name="fee_collect_school__01a13f_idx")),
        migrations.AddIndex(model_name="feepayment", index=models.Index(fields=["provider_reference"], name="fee_collect_provide_162ce7_idx")),
        migrations.AddIndex(model_name="feepayment", index=models.Index(fields=["session_id"], name="fee_collect_session_2c3d97_idx")),
        migrations.AddIndex(model_name="schoolsettlement", index=models.Index(fields=["school", "status"], name="fee_collect_school__8b7110_idx")),
        migrations.AddIndex(model_name="schoolsettlement", index=models.Index(fields=["scheduled_for", "status"], name="fee_collect_schedul_854bf1_idx")),
        migrations.AddIndex(model_name="schoolsettlement", index=models.Index(fields=["transfer_reference"], name="fee_collect_transfe_2f0ccd_idx")),
        migrations.AddIndex(model_name="collectionauditlog", index=models.Index(fields=["school", "created_at"], name="fee_collect_school__f37025_idx")),
        migrations.AddIndex(model_name="collectionauditlog", index=models.Index(fields=["action"], name="fee_collect_action_2d3a18_idx")),
        migrations.AddIndex(model_name="collectionauditlog", index=models.Index(fields=["reference"], name="fee_collect_referen_e208b6_idx")),
    ]
