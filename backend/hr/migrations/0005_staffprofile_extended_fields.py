from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("hr", "0004_staffprofile_bank_code"),
    ]

    operations = [
        migrations.AddField(
            model_name="staffprofile",
            name="nationality",
            field=models.CharField(blank=True, max_length=100),
        ),
        migrations.AddField(
            model_name="staffprofile",
            name="credentials",
            field=models.FileField(blank=True, null=True, upload_to="staff/credentials/"),
        ),
        migrations.AddField(
            model_name="staffprofile",
            name="marital_status",
            field=models.CharField(
                blank=True,
                choices=[
                    ("single", "Single"),
                    ("married", "Married"),
                    ("divorced", "Divorced"),
                    ("widowed", "Widowed"),
                    ("separated", "Separated"),
                ],
                max_length=20,
            ),
        ),
        migrations.AddField(
            model_name="staffprofile",
            name="guarantor_name",
            field=models.CharField(blank=True, max_length=150),
        ),
        migrations.AddField(
            model_name="staffprofile",
            name="guarantor_phone",
            field=models.CharField(blank=True, max_length=30),
        ),
        migrations.AddField(
            model_name="staffprofile",
            name="guarantor_address",
            field=models.TextField(blank=True),
        ),
        migrations.AddField(
            model_name="staffprofile",
            name="guarantor_relationship",
            field=models.CharField(blank=True, max_length=100),
        ),
        migrations.AddField(
            model_name="staffprofile",
            name="guarantor_form",
            field=models.FileField(blank=True, null=True, upload_to="staff/guarantor/"),
        ),
    ]
