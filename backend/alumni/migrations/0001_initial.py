from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import uuid


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('core', '0013_schooltenant_welcome_email_sent_at'),
        ('users', '0031_serviceagreement'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='ArchivedStudentRecord',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('student_id', models.CharField(db_index=True, max_length=50)),
                ('admission_number', models.CharField(blank=True, max_length=50)),
                ('full_name', models.CharField(db_index=True, max_length=255)),
                ('email', models.EmailField(blank=True, max_length=254)),
                ('gender', models.CharField(blank=True, max_length=5)),
                ('profile_picture_url', models.TextField(blank=True)),
                ('last_class_name', models.CharField(blank=True, db_index=True, max_length=160)),
                ('last_class_id', models.IntegerField(blank=True, null=True)),
                ('last_academic_year', models.CharField(blank=True, db_index=True, max_length=120)),
                ('admission_date', models.DateField(blank=True, null=True)),
                ('graduation_year', models.CharField(blank=True, db_index=True, max_length=20)),
                ('archive_reason', models.CharField(choices=[('graduated', 'Graduated'), ('transferred', 'Transferred'), ('withdrawn', 'Withdrawn'), ('deleted', 'Removed from active students'), ('manual', 'Manually archived')], default='manual', max_length=20)),
                ('archive_note', models.TextField(blank=True)),
                ('snapshot', models.JSONField(blank=True, default=dict)),
                ('snapshot_version', models.PositiveIntegerField(default=1)),
                ('is_sealed', models.BooleanField(db_index=True, default=False)),
                ('sealed_at', models.DateTimeField(blank=True, null=True)),
                ('archived_at', models.DateTimeField(auto_now_add=True)),
                ('refreshed_at', models.DateTimeField(auto_now=True)),
                ('archived_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='archived_student_records', to=settings.AUTH_USER_MODEL)),
                ('source_student', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='archive_records', to='users.studentprofile')),
                ('tenant', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='archived_students', to='core.schooltenant')),
            ],
            options={
                'verbose_name': 'archived student record',
                'verbose_name_plural': 'archived student records',
                'ordering': ['-archived_at'],
            },
        ),
        migrations.AddIndex(
            model_name='archivedstudentrecord',
            index=models.Index(fields=['tenant', 'last_academic_year'], name='alumni_asr_year_idx'),
        ),
        migrations.AddIndex(
            model_name='archivedstudentrecord',
            index=models.Index(fields=['tenant', 'last_class_name'], name='alumni_asr_class_idx'),
        ),
        migrations.AddIndex(
            model_name='archivedstudentrecord',
            index=models.Index(fields=['tenant', 'student_id'], name='alumni_asr_stuid_idx'),
        ),
        migrations.AddIndex(
            model_name='archivedstudentrecord',
            index=models.Index(fields=['tenant', 'is_sealed'], name='alumni_asr_sealed_idx'),
        ),
    ]
