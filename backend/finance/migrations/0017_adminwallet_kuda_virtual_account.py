from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("finance", "0016_banklink"),
    ]

    operations = [
        migrations.AddField(
            model_name="adminwallet",
            name="kuda_virtual_account_number",
            field=models.CharField(blank=True, max_length=20),
        ),
        migrations.AddField(
            model_name="adminwallet",
            name="kuda_virtual_account_name",
            field=models.CharField(blank=True, max_length=150),
        ),
        migrations.AddField(
            model_name="adminwallet",
            name="kuda_virtual_account_bank_name",
            field=models.CharField(blank=True, default="Kuda Microfinance Bank", max_length=80),
        ),
        migrations.AddField(
            model_name="adminwallet",
            name="kuda_virtual_account_reference",
            field=models.CharField(blank=True, max_length=100),
        ),
        migrations.AddField(
            model_name="adminwallet",
            name="kuda_virtual_account_status",
            field=models.CharField(blank=True, max_length=30),
        ),
        migrations.AddField(
            model_name="adminwallet",
            name="kuda_virtual_account_metadata",
            field=models.JSONField(blank=True, default=dict),
        ),
    ]
