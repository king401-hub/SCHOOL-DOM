from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("fee_collections", "0002_schoolcollectionprofile_flutterwave_customer_id"),
    ]

    operations = [
        migrations.AddField(
            model_name="schoolcollectionprofile",
            name="flutterwave_customer_reference",
            field=models.CharField(blank=True, max_length=80),
        ),
        migrations.AddField(
            model_name="schoolcollectionprofile",
            name="flutterwave_customer_metadata",
            field=models.JSONField(blank=True, default=dict),
        ),
    ]
