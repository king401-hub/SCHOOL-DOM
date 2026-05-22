from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("academic", "0009_studentclasspromotion"),
    ]

    operations = [
        migrations.AddField(
            model_name="attendancerecord",
            name="latitude",
            field=models.DecimalField(blank=True, decimal_places=7, max_digits=10, null=True),
        ),
        migrations.AddField(
            model_name="attendancerecord",
            name="longitude",
            field=models.DecimalField(blank=True, decimal_places=7, max_digits=10, null=True),
        ),
        migrations.AddField(
            model_name="attendancerecord",
            name="location_accuracy_meters",
            field=models.DecimalField(blank=True, decimal_places=2, max_digits=9, null=True),
        ),
        migrations.AddField(
            model_name="attendancerecord",
            name="location_address",
            field=models.TextField(blank=True, default=""),
        ),
        migrations.AddField(
            model_name="attendancerecord",
            name="device_info",
            field=models.TextField(blank=True, default=""),
        ),
    ]
