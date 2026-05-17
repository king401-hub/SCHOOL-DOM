from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("attendance", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="teacherattendance",
            name="client_device_info",
            field=models.TextField(blank=True, default=""),
        ),
        migrations.AddField(
            model_name="teacherattendance",
            name="check_in_latitude",
            field=models.DecimalField(blank=True, decimal_places=7, max_digits=10, null=True),
        ),
        migrations.AddField(
            model_name="teacherattendance",
            name="check_in_longitude",
            field=models.DecimalField(blank=True, decimal_places=7, max_digits=10, null=True),
        ),
        migrations.AddField(
            model_name="teacherattendance",
            name="check_in_accuracy_meters",
            field=models.DecimalField(blank=True, decimal_places=2, max_digits=9, null=True),
        ),
        migrations.AddField(
            model_name="teacherattendance",
            name="check_in_address",
            field=models.TextField(blank=True, default=""),
        ),
        migrations.AddField(
            model_name="teacherattendance",
            name="check_out_latitude",
            field=models.DecimalField(blank=True, decimal_places=7, max_digits=10, null=True),
        ),
        migrations.AddField(
            model_name="teacherattendance",
            name="check_out_longitude",
            field=models.DecimalField(blank=True, decimal_places=7, max_digits=10, null=True),
        ),
        migrations.AddField(
            model_name="teacherattendance",
            name="check_out_accuracy_meters",
            field=models.DecimalField(blank=True, decimal_places=2, max_digits=9, null=True),
        ),
        migrations.AddField(
            model_name="teacherattendance",
            name="check_out_address",
            field=models.TextField(blank=True, default=""),
        ),
    ]
