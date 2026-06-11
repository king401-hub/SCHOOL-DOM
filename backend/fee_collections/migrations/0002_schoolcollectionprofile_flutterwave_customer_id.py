from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("fee_collections", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="schoolcollectionprofile",
            name="flutterwave_customer_id",
            field=models.CharField(blank=True, max_length=80),
        ),
    ]
