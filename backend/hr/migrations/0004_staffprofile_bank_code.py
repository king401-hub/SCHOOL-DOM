from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("hr", "0003_staffprofile_biodata"),
    ]

    operations = [
        migrations.AddField(
            model_name="staffprofile",
            name="bank_code",
            field=models.CharField(blank=True, max_length=20),
        ),
    ]
