# Generated manually for the SMS Wallet system (per-school prepaid SMS credits).

import uuid
from decimal import Decimal

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0001_initial'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('finance', '0026_paymentreceiptlink_short_code'),
    ]

    operations = [
        migrations.CreateModel(
            name='SmsBundle',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('name', models.CharField(max_length=100)),
                ('credits', models.PositiveIntegerField(help_text='Number of SMS credits (1 credit = 1 SMS, up to 160 chars).')),
                ('bonus_credits', models.PositiveIntegerField(default=0)),
                ('price', models.DecimalField(decimal_places=2, max_digits=10)),
                ('currency', models.CharField(default='NGN', max_length=5)),
                ('is_active', models.BooleanField(default=True)),
                ('sort_order', models.PositiveIntegerField(default=0)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
            options={
                'ordering': ['sort_order', 'credits'],
            },
        ),
        migrations.CreateModel(
            name='SmsWallet',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('balance', models.PositiveIntegerField(default=0)),
                ('low_balance_threshold', models.PositiveIntegerField(default=50)),
                ('is_locked', models.BooleanField(default=False, help_text='Kill switch - blocks all sends for this school.')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('tenant', models.OneToOneField(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='sms_wallet', to='core.schooltenant')),
            ],
        ),
        migrations.CreateModel(
            name='SmsMessageLog',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('category', models.CharField(choices=[('attendance', 'Attendance'), ('fee_reminder', 'Fee Reminder'), ('results', 'Results'), ('otp', 'OTP'), ('parent_alert', 'Parent Alert'), ('teacher_notice', 'Teacher Notice'), ('bulk', 'Bulk Message'), ('other', 'Other')], default='other', max_length=20)),
                ('recipient_phone', models.CharField(max_length=20)),
                ('message', models.TextField()),
                ('credits_charged', models.PositiveIntegerField(default=1)),
                ('delivery_status', models.CharField(choices=[('queued', 'Queued'), ('sent', 'Sent'), ('delivered', 'Delivered'), ('failed', 'Failed'), ('refunded', 'Refunded')], default='queued', max_length=16)),
                ('provider_response', models.JSONField(blank=True, default=dict)),
                ('provider_message_id', models.CharField(blank=True, max_length=100)),
                ('sent_at', models.DateTimeField(blank=True, null=True)),
                ('refunded_at', models.DateTimeField(blank=True, null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('tenant', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='sms_message_logs', to='core.schooltenant')),
                ('wallet', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='message_logs', to='finance.smswallet')),
                ('created_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='sms_message_logs', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'ordering': ['-created_at'],
            },
        ),
        migrations.CreateModel(
            name='SmsWalletTransaction',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('tx_type', models.CharField(choices=[('purchase', 'Purchase'), ('debit', 'Debit'), ('refund', 'Refund'), ('admin_credit', 'Admin Credit'), ('adjustment', 'Adjustment')], max_length=20)),
                ('status', models.CharField(choices=[('pending', 'Pending'), ('successful', 'Successful'), ('failed', 'Failed')], default='successful', max_length=16)),
                ('credits', models.IntegerField(help_text='Signed: positive for purchase/refund/admin_credit, negative for debit.')),
                ('balance_before', models.PositiveIntegerField(blank=True, null=True)),
                ('balance_after', models.PositiveIntegerField(blank=True, null=True)),
                ('amount', models.DecimalField(decimal_places=2, default=Decimal('0.00'), max_digits=12)),
                ('reference', models.CharField(max_length=64, unique=True)),
                ('narration', models.CharField(blank=True, max_length=255)),
                ('provider', models.CharField(default='paystack', max_length=30)),
                ('metadata', models.JSONField(blank=True, default=dict)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('wallet', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='transactions', to='finance.smswallet')),
                ('bundle', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='purchases', to='finance.smsbundle')),
                ('related_message_log', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='wallet_transactions', to='finance.smsmessagelog')),
                ('created_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='sms_wallet_transactions', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'ordering': ['-created_at'],
            },
        ),
        migrations.AddIndex(
            model_name='smsmessagelog',
            index=models.Index(fields=['tenant', 'created_at'], name='finance_smsmsg_tc_idx'),
        ),
        migrations.AddIndex(
            model_name='smsmessagelog',
            index=models.Index(fields=['wallet', 'delivery_status'], name='finance_smsmsg_wds_idx'),
        ),
        migrations.AddIndex(
            model_name='smsmessagelog',
            index=models.Index(fields=['category'], name='finance_smsmsg_cat_idx'),
        ),
        migrations.AddIndex(
            model_name='smswallettransaction',
            index=models.Index(fields=['wallet', 'tx_type'], name='finance_smswtx_wt_idx'),
        ),
        migrations.AddIndex(
            model_name='smswallettransaction',
            index=models.Index(fields=['created_at'], name='finance_smswtx_ca_idx'),
        ),
    ]
