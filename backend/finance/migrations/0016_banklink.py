from django.db import migrations, models
import uuid


DEFAULT_BANK_LINKS = [
    ("GTBank", "gtbank://pay?account={{account_number}}&amount={{amount}}&narration={{narration}}"),
    ("Zenith", "zenith://transfer?to={{account_number}}&amt={{amount}}&desc={{student_name}}"),
    ("UBA", "uba://payment?acct={{account_number}}&amt={{amount}}&ref={{student_ref}}"),
    ("Access", "access://transfer?to={{account_number}}&amt={{amount}}&ref={{student_ref}}"),
    ("FirstBank", "firstbank://transfer?account={{account_number}}&amount={{amount}}&narration={{narration}}"),
]


def seed_bank_links(apps, schema_editor):
    BankLink = apps.get_model("finance", "BankLink")
    for bank_name, template in DEFAULT_BANK_LINKS:
        BankLink.objects.get_or_create(
            bank_name=bank_name,
            defaults={"deep_link_template": template, "nuban_format": "10-digit NUBAN"},
        )


class Migration(migrations.Migration):

    dependencies = [
        ("finance", "0015_rename_finance_fin_tenant__52c38a_idx_finance_fin_tenant__731435_idx_and_more"),
    ]

    operations = [
        migrations.CreateModel(
            name="BankLink",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("bank_name", models.CharField(max_length=80, unique=True)),
                ("deep_link_template", models.CharField(max_length=500)),
                ("nuban_format", models.CharField(blank=True, max_length=120)),
                ("is_active", models.BooleanField(default=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={
                "ordering": ["bank_name"],
            },
        ),
        migrations.AddIndex(
            model_name="banklink",
            index=models.Index(fields=["bank_name", "is_active"], name="finance_ban_bank_na_3ce2a8_idx"),
        ),
        migrations.RunPython(seed_bank_links, migrations.RunPython.noop),
    ]
