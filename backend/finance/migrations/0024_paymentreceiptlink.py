import uuid
import django.db.models.deletion
import django.utils.timezone
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0001_initial'),
        ('finance', '0023_adminwallet_dva_split_code_and_more'),
    ]

    operations = [
        migrations.CreateModel(
            name='PaymentReceiptLink',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('token', models.UUIDField(default=uuid.uuid4, editable=False, unique=True)),
                ('receipt_type', models.CharField(choices=[('receipt', 'Receipt'), ('bill', 'Bill')], default='receipt', max_length=20)),
                ('phone', models.CharField(blank=True, max_length=20)),
                ('data', models.JSONField(default=dict)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('expires_at', models.DateTimeField(blank=True, null=True)),
                ('tenant', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='receipt_links', to='core.schooltenant')),
            ],
            options={
                'indexes': [models.Index(fields=['token'], name='finance_pay_token_idx')],
            },
        ),
    ]
