import os

import pandas as pd
from django.core.management.base import BaseCommand

from myapp.models import GameLeaderboardEntry


class Command(BaseCommand):
    help = (
        "Import leaderboard entries from an Excel file into the "
        "GameLeaderboardEntry table. Re-running is safe — existing rows "
        "(matched by tx_hash) are kept."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            'path',
            nargs='?',
            default=None,
            help=(
                'Path to .xlsx with columns: address, name, score, tx_hash, '
                'month (YYYY-MM). Defaults to myapp/leaderboard.xlsx.'
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
            myapp_dir = os.path.dirname(
                os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            )
            path = os.path.join(myapp_dir, 'leaderboard.xlsx')

        rows = []
        if os.path.exists(path):
            df = pd.read_excel(path)
            df.columns = [str(c).strip().lower() for c in df.columns]
            required = {'address', 'name', 'score', 'tx_hash', 'month'}
            missing = required - set(df.columns)
            if missing:
                self.stderr.write(
                    self.style.ERROR(
                        f"Excel missing columns: {sorted(missing)}. "
                        f"Found: {list(df.columns)}"
                    )
                )
                return

            for _, r in df.iterrows():
                address = str(r['address']).strip()
                tx_hash = str(r['tx_hash']).strip()
                if not address or not tx_hash:
                    continue
                try:
                    score = int(r['score'])
                except (TypeError, ValueError):
                    continue
                rows.append(GameLeaderboardEntry(
                    address=address,
                    name=str(r['name']).strip()[:64],
                    score=score,
                    tx_hash=tx_hash,
                    month=str(r['month']).strip()[:7],
                ))
        else:
            self.stdout.write(
                self.style.WARNING(f"No file at {path}, skipping import.")
            )

        if options['clear']:
            deleted, _ = GameLeaderboardEntry.objects.all().delete()
            self.stdout.write(f"Cleared {deleted} existing rows.")

        if rows:
            GameLeaderboardEntry.objects.bulk_create(
                rows,
                ignore_conflicts=True,
                batch_size=500,
            )

        total = GameLeaderboardEntry.objects.count()
        self.stdout.write(
            self.style.SUCCESS(
                f"Imported {len(rows)} leaderboard rows "
                f"(table now holds {total})."
            )
        )
