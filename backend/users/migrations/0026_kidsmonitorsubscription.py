from django.db import migrations, models
import django.db.models.deletion
import uuid


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0001_initial'),
        ('users', '0025_user_director_address_user_director_id_document_and_more'),
    ]

    operations = [
        migrations.CreateModel(
            name='KidsMonitorSubscription',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('is_active', models.BooleanField(default=False)),
                ('paystack_ref', models.CharField(blank=True, max_length=100)),
                ('activated_at', models.DateTimeField(blank=True, null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('parent', models.OneToOneField(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='kids_monitor',
                    to='users.parentprofile',
                )),
                ('school', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='kids_monitor_subscriptions',
                    to='core.schooltenant',
                )),
            ],
            options={
                'indexes': [
                    models.Index(fields=['school', 'is_active'], name='users_kidsm_school__is_ac_idx'),
                ],
            },
        ),
    ]
