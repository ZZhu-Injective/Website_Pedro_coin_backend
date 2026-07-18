from django.core.management.base import BaseCommand

from myapp.views import _current_month, _ensure_month_rolled_over


class Command(BaseCommand):
    help = (
        "Run the monthly game rollover: snapshot each finished month's winner "
        "into GameMonthPayout (the Hall of Fame), then wipe the three live game "
        "tables — GameLeaderboardEntry, GameUpgradeState, GameStealLog — so the "
        "new month starts empty. Idempotent. Schedule this at 00:00 UTC on the "
        "1st of every month (cron / Windows Task Scheduler) for an exact reset; "
        "otherwise it also runs lazily on the first request of the new month."
    )

    def handle(self, *args, **options):
        month = _current_month()
        self.stdout.write(f"Running game rollover for current month {month}…")
        try:
            _ensure_month_rolled_over(month)
        except Exception as e:
            self.stderr.write(self.style.ERROR(f"Rollover failed: {e}"))
            raise SystemExit(1)
        self.stdout.write(
            self.style.SUCCESS(
                "Rollover complete — winner(s) snapshotted, live tables reset."
            )
        )
