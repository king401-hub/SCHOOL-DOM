"""Management command for attendance system setup and testing."""
from django.core.management.base import BaseCommand
from django.utils import timezone
from django.contrib.auth import get_user_model
from datetime import timedelta
import random

from attendance.models import AttendanceQRCode, TeacherAttendance
from core.models import SchoolTenant

User = get_user_model()


class Command(BaseCommand):
    help = 'Setup and manage attendance system (generate QR codes, test data)'

    def add_arguments(self, parser):
        parser.add_argument(
            '--action',
            type=str,
            choices=['setup', 'generate-sample', 'clear'],
            default='setup',
            help='Action to perform'
        )
        parser.add_argument(
            '--tenant-id',
            type=str,
            help='Tenant ID (optional, will use first tenant if not specified)'
        )
        parser.add_argument(
            '--days',
            type=int,
            default=30,
            help='Number of days for sample data (default: 30)'
        )

    def handle(self, *args, **options):
        action = options['action']

        if action == 'setup':
            self.setup_attendance_system(options)
        elif action == 'generate-sample':
            self.generate_sample_data(options)
        elif action == 'clear':
            self.clear_attendance_data(options)

    def setup_attendance_system(self, options):
        """Initialize attendance system for all tenants."""
        self.stdout.write("🔧 Setting up attendance system...\n")

        if options['tenant_id']:
            tenants = SchoolTenant.objects.filter(id=options['tenant_id'])
        else:
            tenants = SchoolTenant.objects.all()

        if not tenants.exists():
            self.stdout.write(self.style.ERROR('❌ No tenants found'))
            return

        for tenant in tenants:
            qr_code, created = AttendanceQRCode.get_or_create_for_tenant(tenant)

            if created:
                self.stdout.write(
                    self.style.SUCCESS(
                        f"✅ Created QR code for {tenant.name}\n"
                        f"   Token: {qr_code.token[:20]}...\n"
                        f"   URL: /api/attendance/scan/{qr_code.token}/"
                    )
                )
            else:
                self.stdout.write(
                    self.style.WARNING(
                        f"⏭️  QR code already exists for {tenant.name}"
                    )
                )

            # Display setup info
            self.stdout.write("\n📋 Next Steps:")
            self.stdout.write(f"  1. Log in as admin")
            self.stdout.write(f"  2. Go to: /api/attendance/qr-code/download/")
            self.stdout.write(f"  3. Download and print the QR code")
            self.stdout.write(f"  4. Teachers can scan it to mark attendance\n")

    def generate_sample_data(self, options):
        """Generate sample attendance data for testing."""
        self.stdout.write("📊 Generating sample attendance data...\n")

        if options['tenant_id']:
            tenants = SchoolTenant.objects.filter(id=options['tenant_id'])
        else:
            tenants = SchoolTenant.objects.all()

        if not tenants.exists():
            self.stdout.write(self.style.ERROR('❌ No tenants found'))
            return

        days = options['days']
        status_choices = ['present', 'late', 'absent']

        for tenant in tenants:
            self.stdout.write(f"\n📌 Generating data for: {tenant.name}")

            # Get or create QR code
            qr_code, _ = AttendanceQRCode.get_or_create_for_tenant(tenant)

            # Get all teachers
            teachers = User.objects.filter(tenant=tenant, role='teacher')

            if not teachers.exists():
                self.stdout.write(self.style.WARNING(f"  ⚠️  No teachers found in {tenant.name}"))
                continue

            # Generate attendance for each day
            record_count = 0
            for day_offset in range(days):
                date = timezone.localdate() - timedelta(days=day_offset)

                # Skip weekends
                if date.weekday() >= 5:  # Saturday = 5, Sunday = 6
                    continue

                # Random attendance (70% attendance rate)
                for teacher in teachers:
                    if random.random() < 0.7:  # 70% attendance
                        # Check if already exists
                        if not TeacherAttendance.objects.filter(
                            teacher=teacher,
                            attendance_date=date
                        ).exists():
                            # Random check-in time between 8:00 AM and 9:30 AM
                            hour = random.randint(8, 9)
                            minute = random.randint(0, 59)
                            check_in_time = timezone.make_aware(
                                timezone.datetime.combine(
                                    date,
                                    timezone.datetime.min.time().replace(hour=hour, minute=minute)
                                )
                            )

                            # Determine status based on time
                            if hour > 8 or (hour == 8 and minute > 30):
                                status = 'late'
                            else:
                                status = random.choice(['present', 'late'])

                            TeacherAttendance.objects.create(
                                teacher=teacher,
                                tenant=tenant,
                                qr_code=qr_code,
                                attendance_date=date,
                                check_in_time=check_in_time,
                                status=status,
                                device_info='Sample Data Generator'
                            )
                            record_count += 1

            self.stdout.write(
                self.style.SUCCESS(
                    f"✅ Created {record_count} attendance records\n"
                    f"   Teachers: {teachers.count()}\n"
                    f"   Period: {days} days"
                )
            )

        self.stdout.write(self.style.SUCCESS("\n✅ Sample data generation complete!"))

    def clear_attendance_data(self, options):
        """Clear all attendance data (careful!)."""
        if options['tenant_id']:
            tenants = SchoolTenant.objects.filter(id=options['tenant_id'])
        else:
            tenants = SchoolTenant.objects.all()

        if not tenants.exists():
            self.stdout.write(self.style.ERROR('❌ No tenants found'))
            return

        confirmation = input("⚠️  This will delete ALL attendance records. Type 'yes' to confirm: ")
        if confirmation.lower() != 'yes':
            self.stdout.write("❌ Operation cancelled")
            return

        for tenant in tenants:
            count, _ = TeacherAttendance.objects.filter(tenant=tenant).delete()
            self.stdout.write(
                self.style.WARNING(f"🗑️  Deleted {count} records from {tenant.name}")
            )

        self.stdout.write(self.style.SUCCESS("\n✅ Cleanup complete!"))


# Usage examples:
# python manage.py attendance_setup --action setup
# python manage.py attendance_setup --action generate-sample --days 30
# python manage.py attendance_setup --action generate-sample --tenant-id <uuid>
# python manage.py attendance_setup --action clear
