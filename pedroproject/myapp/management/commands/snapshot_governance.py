import asyncio
from datetime import datetime, timezone

from django.core.management.base import BaseCommand
from django.db import transaction

from myapp.injective_nft_holders import InjectiveHolders2
from myapp.models import GovernanceVoterSnapshot

PEDRO_NFT_CONTRACT = 'inj1uq453kp4yda7ruc0axpmd9vzfm0fj62padhe0p'

# Addresses excluded from voting power: burn + project pools/marketplaces.
# Mirrors the lists used by injective_nft_holders.py so creators / contracts
# can't vote on community proposals.
EXCLUDED_ADDRESSES = {
    'inj1qqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqe2hm49',  # burn
    'inj1l9nh9wv24fktjvclc4zgrgyzees7rwdtx45f54',  # Talis Marketplace
}


def _current_month():
    return datetime.now(timezone.utc).strftime('%Y-%m')


class Command(BaseCommand):
    help = (
        "Snapshot Pedro NFT holders into the GovernanceVoterSnapshot table. "
        "Run on the 1st of each month (UTC) — each address's NFT count at the "
        "moment of snapshot becomes their voting power for that month."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--month',
            default=None,
            help='Override target month (YYYY-MM). Defaults to current UTC month.',
        )
        parser.add_argument(
            '--contract',
            default=PEDRO_NFT_CONTRACT,
            help='NFT contract address to snapshot (default: Pedro NFT).',
        )
        parser.add_argument(
            '--replace',
            action='store_true',
            help='Delete existing snapshot rows for this month before writing.',
        )

    def handle(self, *args, **options):
        month = options['month'] or _current_month()
        contract = options['contract']
        replace = options['replace']

        existing = GovernanceVoterSnapshot.objects.filter(month=month).count()
        if existing and not replace:
            self.stdout.write(
                self.style.WARNING(
                    f"Snapshot for {month} already has {existing} rows. "
                    f"Pass --replace to overwrite."
                )
            )
            return

        self.stdout.write(f"Fetching {contract} holders…")
        try:
            data = asyncio.run(InjectiveHolders2().fetch_holder_nft(contract))
        except Exception as e:
            self.stderr.write(self.style.ERROR(f"Failed to fetch holders: {e}"))
            return

        holders = data.get('holders') or []
        rows = []
        for h in holders:
            owner = h.get('owner')
            total = h.get('total')
            if not owner or not total:
                continue
            if owner in EXCLUDED_ADDRESSES:
                continue
            try:
                count = int(total)
            except (TypeError, ValueError):
                continue
            if count <= 0:
                continue
            rows.append(GovernanceVoterSnapshot(
                month=month,
                address=owner,
                nft_count=count,
            ))

        with transaction.atomic():
            if replace:
                GovernanceVoterSnapshot.objects.filter(month=month).delete()
            GovernanceVoterSnapshot.objects.bulk_create(
                rows,
                ignore_conflicts=True,
                batch_size=500,
            )

        total = GovernanceVoterSnapshot.objects.filter(month=month).count()
        total_power = sum(r.nft_count for r in rows)
        self.stdout.write(
            self.style.SUCCESS(
                f"Snapshot for {month}: {total} eligible voters, "
                f"{total_power} total voting points."
            )
        )
