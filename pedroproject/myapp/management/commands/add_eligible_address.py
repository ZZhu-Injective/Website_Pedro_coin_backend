from django.core.management.base import BaseCommand

from myapp.models import EligibleAddress


class Command(BaseCommand):
    help = "Add one or more wallet addresses to the eligibility list."

    def add_arguments(self, parser):
        parser.add_argument(
            'addresses',
            nargs='+',
            help='One or more inj... addresses to mark eligible.',
        )
        parser.add_argument(
            '--note',
            default='',
            help='Optional note attached to every address added in this run.',
        )

    def handle(self, *args, **options):
        addresses = {a.strip() for a in options['addresses'] if a.strip()}
        note = options['note']

        created = EligibleAddress.objects.bulk_create(
            (EligibleAddress(address=a, note=note) for a in addresses),
            ignore_conflicts=True,
        )
        added = len(created)
        skipped = len(addresses) - added
        total = EligibleAddress.objects.count()

        self.stdout.write(
            self.style.SUCCESS(
                f"Added {added} new, skipped {skipped} existing. Table now holds {total}."
            )
        )
