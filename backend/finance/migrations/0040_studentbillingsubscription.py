import uuid

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('finance', '0039_onetimebillingcharge'),
        ('users', '0034_user_phone_otp_attempts_user_phone_otp_challenge_and_more'),
    ]

    operations = [
        migrations.CreateModel(
            name='StudentBillingSubscription',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('billing_anchor_date', models.DateField()),
                ('next_billing_date', models.DateField()),
                ('cycles_billed', models.PositiveIntegerField(default=0)),
                ('status', models.CharField(choices=[('active', 'Active'), ('paused', 'Paused'), ('cancelled', 'Cancelled')], default='active', max_length=10)),
                ('cancelled_at', models.DateTimeField(blank=True, null=True)),
                ('plan', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='subscriptions', to='finance.recurringbillingplan')),
                ('student', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='billing_subscriptions', to='users.studentprofile')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
            options={
                'ordering': ['next_billing_date'],
            },
        ),
        migrations.AddIndex(
            model_name='studentbillingsubscription',
            index=models.Index(fields=['status', 'next_billing_date'], name='finance_stu_status_f50c38_idx'),
        ),
        migrations.AddConstraint(
            model_name='studentbillingsubscription',
            constraint=models.UniqueConstraint(fields=('plan', 'student'), name='unique_subscription_per_plan_per_student'),
        ),
    ]
