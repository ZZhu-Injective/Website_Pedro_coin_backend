import os

import pandas as pd
from django.core.management.base import BaseCommand

from myapp.models import Talent


def _str(v):
    if v is None:
        return ''
    if isinstance(v, float) and pd.isna(v):
        return ''
    return str(v).strip()


def _datetime_or_none(v):
    try:
        if v is None or (isinstance(v, float) and pd.isna(v)):
            return None
        ts = pd.to_datetime(v, errors='coerce')
        if pd.isna(ts):
            return None
        return ts.to_pydatetime()
    except Exception:
        return None


COLUMN_TO_FIELD = {
    'Name': 'name',
    'Role': 'role',
    'Injective Role': 'injective_role',
    'Experience': 'experience',
    'Education': 'education',
    'Location': 'location',
    'Availability': 'availability',
    'Monthly Rate': 'monthly_rate',
    'Skills': 'skills',
    'Languages': 'languages',
    'Discord': 'discord',
    'Email': 'email',
    'Phone': 'phone',
    'Telegram': 'telegram',
    'X': 'x',
    'Github': 'github',
    'Wallet Address': 'wallet_address',
    'Wallet Type': 'wallet_type',
    'NFT Holdings': 'nft_holdings',
    'Token Holdings': 'token_holdings',
    'Portfolio': 'portfolio',
    'CV': 'cv',
    'Image url': 'image_url',
    'Bio': 'bio',
    'Submission date': 'submission_date',
    'Status': 'status',
}

# Fields with a max_length that need clipping if Excel data exceeds it.
TRUNCATE = {
    'name': 255, 'role': 255, 'injective_role': 255, 'experience': 255,
    'education': 255, 'location': 255, 'availability': 64, 'monthly_rate': 64,
    'languages': 255, 'discord': 128, 'email': 255, 'phone': 64,
    'telegram': 128, 'x': 128, 'github': 255, 'wallet_address': 64,
    'wallet_type': 64, 'portfolio': 500, 'cv': 500, 'image_url': 500,
    'status': 32,
}


class Command(BaseCommand):
    help = (
        "Import talent submissions from Atalent_submissions.xlsx into the "
        "Talent table. --clear refreshes the table."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            'path',
            nargs='?',
            default=None,
            help='Path to the .xlsx file. Defaults to pedroproject/Atalent_submissions.xlsx.',
        )
        parser.add_argument(
            '--clear',
            action='store_true',
            help='Delete all existing rows before importing.',
        )

    def handle(self, *args, **options):
        path = options['path']
        if path is None:
            project_dir = os.path.dirname(
                os.path.dirname(
                    os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
                )
            )
            path = os.path.join(project_dir, 'Atalent_submissions.xlsx')

        if not os.path.exists(path):
            self.stderr.write(self.style.ERROR(f"File not found: {path}"))
            return

        df = pd.read_excel(path)
        missing = [c for c in COLUMN_TO_FIELD if c not in df.columns]
        if missing:
            self.stderr.write(self.style.ERROR(f"Missing columns: {missing}"))
            return

        if options['clear']:
            deleted, _ = Talent.objects.all().delete()
            self.stdout.write(f"Cleared {deleted} existing rows.")

        objs = []
        for _, row in df.iterrows():
            kwargs = {}
            for col, field in COLUMN_TO_FIELD.items():
                value = row.get(col)
                if field == 'submission_date':
                    kwargs[field] = _datetime_or_none(value)
                else:
                    s = _str(value)
                    if field in TRUNCATE:
                        s = s[:TRUNCATE[field]]
                    kwargs[field] = s
            if not kwargs.get('status'):
                kwargs['status'] = 'Pending'
            if not kwargs.get('name'):
                continue  # skip blank rows
            objs.append(Talent(**kwargs))

        Talent.objects.bulk_create(objs, batch_size=500)

        total = Talent.objects.count()
        self.stdout.write(self.style.SUCCESS(
            f"Imported {len(objs)} talent rows (table now holds {total})."
        ))
