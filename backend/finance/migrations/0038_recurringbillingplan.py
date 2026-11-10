import uuid

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('academic', '0027_studenttraitrecord'),
        ('core', '0017_schooltenant_parent_faq'),
        ('finance', '0037_classfee_term_schoolfee_closed_at_schoolfee_term'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='RecurringBillingPlan',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('title', models.CharField(max_length=150)),
                ('description', models.TextField(blank=True)),
                ('amount', models.DecimalField(decimal_places=2, max_digits=12)),
                ('currency', models.CharField(default='NGN', max_length=5)),
                ('classes', models.ManyToManyField(blank=True, related_name='recurring_billing_plans', to='academic.class')),
                ('applies_to_all_classes', models.BooleanField(default=False)),
                ('frequency', models.CharField(choices=[('monthly', 'Monthly')], default='monthly', max_length=20)),
                ('effective_start_date', models.DateField(help_text='Only students admitted on or after this date are ever auto-enrolled - see finance.services.apply_eligible_recurring_plans_for_new_student.')),
                ('effective_end_date', models.DateField(blank=True, null=True)),
                ('auto_apply_to_new_students', models.BooleanField(default=True)),
                ('status', models.CharField(choices=[('active', 'Active'), ('paused', 'Paused'), ('archived', 'Archived')], default='active', max_length=10)),
                ('created_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='created_recurring_billing_plans', to=settings.AUTH_USER_MODEL)),
                ('tenant', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='recurring_billing_plans', to='core.schooltenant')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
            options={
                'ordering': ['-created_at'],
            },
        ),
        migrations.AddIndex(
            model_name='recurringbillingplan',
            index=models.Index(fields=['tenant', 'status'], name='finance_rec_tenant__1abffa_idx'),
        ),
    ]
