import os

import pandas as pd
from django.core.management.base import BaseCommand

from myapp.models import EligibleAddress


class Command(BaseCommand):
    help = (
        "Import eligible wallet addresses from an Excel file into the "
        "EligibleAddress table. Re-running is safe (existing rows are kept)."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            'path',
            nargs='?',
            default=None,
            help=(
                'Path to .xlsx with an "Address" column. '
                'Defaults to myapp/eligable.xlsx.'
            ),
        )
        parser.add_argument(
            '--clear',
            action='store_true',
            help='Delete all existing rows before importing.',
        )

    def handle(self, *args, **options):
        path = options['path']
        if path is None:
            # myapp/management/commands/this_file.py -> myapp/
            myapp_dir = os.path.dirname(
                os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            )
            path = os.path.join(myapp_dir, 'eligable.xlsx')

        if not os.path.exists(path):
            self.stderr.write(self.style.ERROR(f"File not found: {path}"))
            return

        df = pd.read_excel(path)
        if 'Address' not in df.columns:
            self.stderr.write(
                self.style.ERROR(
                    f"Excel must contain an 'Address' column. Found: {list(df.columns)}"
                )
            )
            return

        addresses = {
            str(a).strip()
            for a in df['Address'].dropna()
            if str(a).strip()
        }

        if options['clear']:
            deleted, _ = EligibleAddress.objects.all().delete()
            self.stdout.write(f"Cleared {deleted} existing rows.")

        EligibleAddress.objects.bulk_create(
            (EligibleAddress(address=a) for a in addresses),
            ignore_conflicts=True,
            batch_size=500,
        )

        total = EligibleAddress.objects.count()
        self.stdout.write(
            self.style.SUCCESS(
                f"Imported {len(addresses)} addresses (table now holds {total})."
            )
        )
