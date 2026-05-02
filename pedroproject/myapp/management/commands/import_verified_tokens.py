import json
import os

from django.core.management.base import BaseCommand

from myapp.models import VerifiedToken


class Command(BaseCommand):
    help = (
        "Import verified tokens from ACpedro_verified_token.json into the "
        "VerifiedToken table. Re-running is safe (existing rows are kept)."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            'path',
            nargs='?',
            default=None,
            help='Path to the JSON file. Defaults to myapp/ACpedro_verified_token.json.',
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
            path = os.path.join(myapp_dir, 'ACpedro_verified_token.json')

        if not os.path.exists(path):
            self.stderr.write(self.style.ERROR(f"File not found: {path}"))
            return

        with open(path, 'r', encoding='utf-8') as f:
            tokens = json.load(f)

        if not isinstance(tokens, list):
            self.stderr.write(self.style.ERROR(f"Expected a JSON list, got {type(tokens).__name__}"))
            return

        if options['clear']:
            deleted, _ = VerifiedToken.objects.all().delete()
            self.stdout.write(f"Cleared {deleted} existing rows.")

        objs = []
        seen = set()
        skipped = 0
        for t in tokens:
            denom = (t.get('denom') or '').strip()
            if not denom or denom in seen:
                skipped += 1
                continue
            seen.add(denom)
            objs.append(VerifiedToken(
                denom=denom,
                address=(t.get('address') or '')[:255],
                is_native=bool(t.get('isNative', False)),
                token_verification=(t.get('tokenVerification') or '')[:64],
                name=(t.get('name') or '')[:255],
                decimals=int(t.get('decimals') or 18),
                symbol=(t.get('symbol') or '')[:64],
                override_symbol=(t.get('overrideSymbol') or '')[:64],
                logo=(t.get('logo') or '')[:500],
                coin_gecko_id=(t.get('coinGeckoId') or '')[:128],
                token_type=(t.get('tokenType') or '')[:64],
                external_logo=(t.get('externalLogo') or '')[:255],
            ))

        VerifiedToken.objects.bulk_create(
            objs, ignore_conflicts=True, batch_size=500,
        )

        total = VerifiedToken.objects.count()
        self.stdout.write(self.style.SUCCESS(
            f"Imported {len(objs)} tokens (skipped {skipped}; table now holds {total})."
        ))
