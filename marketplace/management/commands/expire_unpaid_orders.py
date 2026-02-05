from django.core.management.base import BaseCommand
from marketplace.tasks import expire_unpaid_orders


class Command(BaseCommand):
    help = 'Expire unpaid orders older than the configured timeout.'

    def handle(self, *args, **options):
        count = expire_unpaid_orders()
        self.stdout.write(self.style.SUCCESS(f'Expired {count} unpaid orders'))
