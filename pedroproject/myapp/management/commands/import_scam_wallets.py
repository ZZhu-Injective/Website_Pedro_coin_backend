import json
import os

from django.core.management.base import BaseCommand

from myapp.models import ScamWallet


class Command(BaseCommand):
    help = (
        "Import scam wallet addresses from ADpedro_scam_wallet.json into the "
        "ScamWallet table. Re-running is safe (existing rows are kept)."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            'path',
            nargs='?',
            default=None,
            help='Path to the JSON file. Defaults to myapp/ADpedro_scam_wallet.json.',
        )
        parser.add_argument(
            '--clear',
            action='store_true',
            help='Delete all existing rows before importing.',
        )

    def handle(self, *args, **options):
        path = options['path']
        if path is None:
            myapp_dir = os.path.dirname(
                os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            )
            path = os.path.join(myapp_dir, 'ADpedro_scam_wallet.json')

        if not os.path.exists(path):
            self.stderr.write(self.style.ERROR(f"File not found: {path}"))
            return

        with open(path, 'r', encoding='utf-8') as f:
            data = json.load(f)

        addresses_raw = data.get('scam_addresses', []) if isinstance(data, dict) else []
        addresses = {a.strip() for a in addresses_raw if isinstance(a, str) and a.strip()}

        if options['clear']:
            deleted, _ = ScamWallet.objects.all().delete()
            self.stdout.write(f"Cleared {deleted} existing rows.")

        ScamWallet.objects.bulk_create(
            (ScamWallet(address=a) for a in addresses),
            ignore_conflicts=True,
            batch_size=500,
        )

        total = ScamWallet.objects.count()
        self.stdout.write(self.style.SUCCESS(
            f"Imported {len(addresses)} scam addresses (table now holds {total})."
        ))
