from django.core.management.base import BaseCommand

from myapp.models import EligibleAddress


class Command(BaseCommand):
    help = "List eligibility table contents (count, addresses, optional search)."

    def add_arguments(self, parser):
        parser.add_argument(
            '--search',
            default=None,
            help='Only show rows where the address contains this substring.',
        )
        parser.add_argument(
            '--limit',
            type=int,
            default=50,
            help='Max rows to print (default 50). Use 0 for no limit.',
        )
        parser.add_argument(
            '--count-only',
            action='store_true',
            help='Just print the row count and exit.',
        )

    def handle(self, *args, **options):
        qs = EligibleAddress.objects.all()
        if options['search']:
            qs = qs.filter(address__icontains=options['search'])

        total = qs.count()
        self.stdout.write(self.style.SUCCESS(f"Total rows: {total}"))

        if options['count_only'] or total == 0:
            return

        limit = options['limit']
        rows = qs.order_by('-added_at')
        if limit > 0:
            rows = rows[:limit]

        self.stdout.write('')
        self.stdout.write(f"{'#':>4}  {'address':<48}  {'added':<19}  note")
        self.stdout.write('-' * 90)
        for i, row in enumerate(rows, start=1):
            added = row.added_at.strftime('%Y-%m-%d %H:%M:%S') if row.added_at else ''
            self.stdout.write(
                f"{i:>4}  {row.address:<48}  {added:<19}  {row.note}"
            )

        if limit > 0 and total > limit:
            self.stdout.write('')
            self.stdout.write(
                f"… {total - limit} more rows. Use --limit 0 to show all."
            )
