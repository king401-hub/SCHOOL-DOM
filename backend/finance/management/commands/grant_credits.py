from django.core.management.base import BaseCommand
from django.db import transaction

from core.models import SchoolTenant
from finance.services import add_activation_credits_to_pool


class Command(BaseCommand):
    help = "Grant activation credits to a school for testing purposes."

    def add_arguments(self, parser):
        parser.add_argument(
            "schema_name",
            type=str,
            help="The schema name of the school tenant",
        )
        parser.add_argument(
            "credits",
            type=int,
            help="Number of credits to grant",
        )

    def handle(self, *args, **options):
        schema_name = options["schema_name"]
        credits = options["credits"]
        
        try:
            tenant = SchoolTenant.objects.get(schema_name=schema_name)
            with transaction.atomic():
                pool = add_activation_credits_to_pool(tenant, credits, actor=None)
            self.stdout.write(
                self.style.SUCCESS(
                    f"Granted {credits} credits to {schema_name}. New balance: {pool.balance}"
                )
            )
        except SchoolTenant.DoesNotExist:
            self.stdout.write(
                self.style.ERROR(f"School tenant '{schema_name}' not found.")
            )
        except Exception as exc:
            self.stdout.write(self.style.ERROR(f"Error granting credits: {exc}"))