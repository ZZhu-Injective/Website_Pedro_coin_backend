from django.core.management.base import BaseCommand

from myapp.views import _refresh_nft_holders


class Command(BaseCommand):
    help = (
        "Rebuild the Pedro NFT holder cache (address -> NFT count) by scanning "
        "the full contract state, and write it to the shared cache. Run on a "
        "short cron (every ~5 minutes) so the raffle / eligibility endpoints "
        "always read a warm cache and never block a user request on the scan."
    )

    def handle(self, *args, **options):
        self.stdout.write("Refreshing Pedro NFT holder cache…")
        try:
            counts = _refresh_nft_holders()
        except Exception as e:
            self.stderr.write(self.style.ERROR(f"Refresh failed: {e}"))
            raise SystemExit(1)
        self.stdout.write(
            self.style.SUCCESS(
                f"Cached {len(counts)} holders, {sum(counts.values())} NFTs."
            )
        )
