import os

import pandas as pd
from django.core.management.base import BaseCommand

from myapp.models import ScamReport


def _str(v):
    if v is None:
        return ''
    if isinstance(v, float) and pd.isna(v):
        return ''
    return str(v).strip()


class Command(BaseCommand):
    help = (
        "Import scam reports from scam.xlsx into the ScamReport table. "
        "Re-running with --clear is the only safe way to refresh."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            'path',
            nargs='?',
            default=None,
            help='Path to the .xlsx file. Defaults to myapp/scam.xlsx.',
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
            path = os.path.join(myapp_dir, 'scam.xlsx')

        if not os.path.exists(path):
            self.stderr.write(self.style.ERROR(f"File not found: {path}"))
            return

        df = pd.read_excel(path)
        required = ['Address', 'Time', 'Project', 'Amount', 'Info', 'Group']
        missing = [c for c in required if c not in df.columns]
        if missing:
            self.stderr.write(self.style.ERROR(f"Missing columns: {missing}"))
            return

        if options['clear']:
            deleted, _ = ScamReport.objects.all().delete()
            self.stdout.write(f"Cleared {deleted} existing rows.")

        objs = [
            ScamReport(
                address=_str(row.get('Address'))[:255],
                time=_str(row.get('Time'))[:64],
                project=_str(row.get('Project'))[:255],
                amount=_str(row.get('Amount'))[:128],
                info=_str(row.get('Info')),
                group=_str(row.get('Group'))[:100],
            )
            for _, row in df.iterrows()
        ]
        ScamReport.objects.bulk_create(objs, batch_size=500)

        total = ScamReport.objects.count()
        self.stdout.write(self.style.SUCCESS(
            f"Imported {len(objs)} scam reports (table now holds {total})."
        ))
