from decimal import Decimal

from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name="SchoolTokenPaymentSetting",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("school_model", models.CharField(max_length=120)),
                ("school_pk", models.CharField(max_length=64)),
                ("school_name", models.CharField(max_length=255)),
                ("token_price", models.DecimalField(decimal_places=2, default=Decimal("0.00"), max_digits=12)),
                ("tokens_per_payment", models.PositiveIntegerField(default=1)),
                ("minimum_tokens", models.PositiveIntegerField(default=0)),
                ("payment_required", models.BooleanField(default=True)),
                ("is_active", models.BooleanField(default=True)),
                ("notes", models.TextField(blank=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={
                "ordering": ("school_name",),
                "unique_together": {("school_model", "school_pk")},
            },
        ),
    ]
