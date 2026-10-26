import uuid

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('finance', '0035_alter_smswallettransaction_status'),
        ('core', '0014_schooltenant_product_schoolgatepayment'),
        ('users', '0004_teacherprofile_subjects_text'),
    ]

    operations = [
        migrations.CreateModel(
            name='FeeWaiver',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('title', models.CharField(max_length=150)),
                ('amount', models.DecimalField(decimal_places=2, max_digits=12)),
                ('status', models.CharField(choices=[('authorized', 'Authorized'), ('memoed', 'Memoed')], default='authorized', max_length=12)),
                ('reason', models.TextField(blank=True, default='')),
                ('granted_at', models.DateTimeField(auto_now_add=True)),
                ('fee', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='waivers', to='finance.schoolfee')),
                ('granted_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='granted_fee_waivers', to=settings.AUTH_USER_MODEL)),
                ('student', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='fee_waivers', to='users.studentprofile')),
                ('tenant', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='fee_waivers', to='core.schooltenant')),
            ],
            options={
                'ordering': ['-granted_at'],
            },
        ),
        migrations.AddIndex(
            model_name='feewaiver',
            index=models.Index(fields=['student', 'granted_at'], name='finance_fee_student_1f9b36_idx'),
        ),
    ]
