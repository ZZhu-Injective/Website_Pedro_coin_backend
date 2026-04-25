from django.core.management.base import BaseCommand

from myapp.models import EligibleAddress


class Command(BaseCommand):
    help = "Remove one or more wallet addresses from the eligibility list."

    def add_arguments(self, parser):
        parser.add_argument(
            'addresses',
            nargs='+',
            help='One or more inj... addresses to remove.',
        )

    def handle(self, *args, **options):
        addresses = {a.strip() for a in options['addresses'] if a.strip()}

        deleted, _ = EligibleAddress.objects.filter(address__in=addresses).delete()
        total = EligibleAddress.objects.count()

        self.stdout.write(
            self.style.SUCCESS(
                f"Removed {deleted} of {len(addresses)} requested. Table now holds {total}."
            )
        )
