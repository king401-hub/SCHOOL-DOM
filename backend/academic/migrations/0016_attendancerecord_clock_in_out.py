from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('academic', '0015_gradescale_grade_point'),
    ]

    operations = [
        migrations.AddField(
            model_name='attendancerecord',
            name='clock_in_at',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='attendancerecord',
            name='clock_out_at',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='attendancerecord',
            name='clock_out_latitude',
            field=models.DecimalField(blank=True, decimal_places=7, max_digits=10, null=True),
        ),
        migrations.AddField(
            model_name='attendancerecord',
            name='clock_out_longitude',
            field=models.DecimalField(blank=True, decimal_places=7, max_digits=10, null=True),
        ),
        migrations.AddField(
            model_name='attendancerecord',
            name='clock_out_accuracy_meters',
            field=models.DecimalField(blank=True, decimal_places=2, max_digits=9, null=True),
        ),
        migrations.AddField(
            model_name='attendancerecord',
            name='clock_out_address',
            field=models.TextField(blank=True, default=''),
        ),
        migrations.AddField(
            model_name='attendancerecord',
            name='clock_out_device_info',
            field=models.TextField(blank=True, default=''),
        ),
        migrations.AddField(
            model_name='attendancerecord',
            name='clock_out_recorded_by',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='clocked_out_attendance', to=settings.AUTH_USER_MODEL),
        ),
    ]
