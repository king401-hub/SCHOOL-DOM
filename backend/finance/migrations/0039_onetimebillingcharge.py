import uuid

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('academic', '0027_studenttraitrecord'),
        ('core', '0017_schooltenant_parent_faq'),
        ('finance', '0038_recurringbillingplan'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='OneTimeBillingCharge',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('title', models.CharField(max_length=150)),
                ('description', models.TextField(blank=True)),
                ('amount', models.DecimalField(decimal_places=2, max_digits=12)),
                ('currency', models.CharField(default='NGN', max_length=5)),
                ('classes', models.ManyToManyField(blank=True, related_name='one_time_billing_charges', to='academic.class')),
                ('applies_to_all_classes', models.BooleanField(default=False)),
                ('effective_start_date', models.DateField(help_text='Only students admitted on or after this date are ever auto-applied - see finance.services.apply_eligible_one_time_charges_for_new_student.')),
                ('expiry_date', models.DateField(blank=True, null=True)),
                ('due_in_days', models.PositiveIntegerField(default=0)),
                ('auto_apply_to_new_students', models.BooleanField(default=True)),
                ('status', models.CharField(choices=[('active', 'Active'), ('paused', 'Paused'), ('archived', 'Archived')], default='active', max_length=10)),
                ('created_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='created_one_time_billing_charges', to=settings.AUTH_USER_MODEL)),
                ('tenant', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='one_time_billing_charges', to='core.schooltenant')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
            options={
                'ordering': ['-created_at'],
            },
        ),
        migrations.AddIndex(
            model_name='onetimebillingcharge',
            index=models.Index(fields=['tenant', 'status'], name='finance_one_tenant__fd645a_idx'),
        ),
    ]
