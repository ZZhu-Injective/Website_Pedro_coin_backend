import os

import pandas as pd
from django.core.management.base import BaseCommand

from myapp.models import MarketplaceListing


def _str(v):
    if v is None:
        return ''
    if isinstance(v, float) and pd.isna(v):
        return ''
    return str(v).strip()


def _int_or_none(v):
    try:
        if v is None or (isinstance(v, float) and pd.isna(v)):
            return None
        return int(float(v))
    except (TypeError, ValueError):
        return None


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


class Command(BaseCommand):
    help = (
        "Import marketplace listings from Amarketplace_submissions.xlsx into "
        "the MarketplaceListing table. --clear refreshes the table."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            'path',
            nargs='?',
            default=None,
            help='Path to the .xlsx file. Defaults to pedroproject/Amarketplace_submissions.xlsx.',
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
            path = os.path.join(project_dir, 'Amarketplace_submissions.xlsx')

        if not os.path.exists(path):
            self.stderr.write(self.style.ERROR(f"File not found: {path}"))
            return

        df = pd.read_excel(path)
        required = [
            'id', 'WalletAddress', 'title', 'description', 'category', 'price',
            'skills', 'images', 'sellerName', 'discordTag', 'createdAt', 'Views', 'Status',
        ]
        missing = [c for c in required if c not in df.columns]
        if missing:
            self.stderr.write(self.style.ERROR(f"Missing columns: {missing}"))
            return

        if options['clear']:
            deleted, _ = MarketplaceListing.objects.all().delete()
            self.stdout.write(f"Cleared {deleted} existing rows.")

        objs = [
            MarketplaceListing(
                legacy_id=_int_or_none(row.get('id')),
                wallet_address=_str(row.get('WalletAddress'))[:64],
                title=_str(row.get('title'))[:255],
                description=_str(row.get('description')),
                category=_str(row.get('category'))[:100],
                price=_str(row.get('price'))[:64],
                skills=_str(row.get('skills')),
                images=_str(row.get('images')),
                seller_name=_str(row.get('sellerName'))[:255],
                discord_tag=_str(row.get('discordTag'))[:128],
                created_at=_datetime_or_none(row.get('createdAt')),
                views=_int_or_none(row.get('Views')) or 0,
                status=_str(row.get('Status'))[:32] or 'Pending',
            )
            for _, row in df.iterrows()
        ]
        MarketplaceListing.objects.bulk_create(objs, batch_size=500)

        total = MarketplaceListing.objects.count()
        self.stdout.write(self.style.SUCCESS(
            f"Imported {len(objs)} marketplace listings (table now holds {total})."
        ))
