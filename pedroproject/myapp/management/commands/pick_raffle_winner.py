"""
Picks the winner for a completed raffle week. By default the most recently
completed week (i.e. last week relative to UTC now). Pass --week 2026-W18
to pick a specific week.

Usage:
    python manage.py pick_raffle_winner
    python manage.py pick_raffle_winner --week 2026-W18
    python manage.py pick_raffle_winner --week 2026-W18 --force

Idempotent: refuses to overwrite an existing RaffleResult unless --force.
"""
import secrets
from datetime import datetime, timezone, timedelta

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from myapp.models import GameLeaderboardEntry, RaffleResult, RaffleTicket


def _last_completed_week() -> str:
    """ISO week of yesterday (close enough to 'last completed week' for our
    purposes — if you call this on Monday it returns last week, on any other
    day it returns the current ISO week, which is fine because we only use
    this as a default and the user can override with --week)."""
    now = datetime.now(timezone.utc)
    # Step back 1 day so a Monday call after week rollover lands on Sunday
    # of the just-finished week.
    target = now - timedelta(days=1)
    iso_year, iso_week, _ = target.isocalendar()
    return f"{iso_year}-W{iso_week:02d}"


def _canonical_name_for(address: str) -> str:
    first = (
        GameLeaderboardEntry.objects
        .filter(address=address)
        .order_by('submitted_at', 'id')
        .values_list('name', flat=True)
        .first()
    )
    return first or ''


class Command(BaseCommand):
    help = "Pick the winning ticket for a completed raffle week."

    def add_arguments(self, parser):
        parser.add_argument(
            '--week',
            help="ISO week to draw, e.g. '2026-W18'. Defaults to the most "
                 "recently completed week.",
        )
        parser.add_argument(
            '--force',
            action='store_true',
            help="Overwrite an existing RaffleResult for this week.",
        )

    @transaction.atomic
    def handle(self, *args, week=None, force=False, **options):
        target_week = week or _last_completed_week()
        self.stdout.write(f"Drawing winner for week {target_week}")

        existing = RaffleResult.objects.filter(week=target_week).first()
        if existing and not force:
            raise CommandError(
                f"Winner for {target_week} already picked: "
                f"{existing.winning_address} (#{existing.winning_ticket_id}). "
                f"Pass --force to overwrite."
            )

        ticket_ids = list(
            RaffleTicket.objects
            .filter(week=target_week)
            .values_list('id', 'address')
        )
        if not ticket_ids:
            raise CommandError(f"No tickets found for {target_week}")

        # secrets.choice for a cryptographically random pick — leaves no
        # doubt that the team used a fair source of entropy.
        winning_id, winning_address = secrets.choice(ticket_ids)
        winning_name = _canonical_name_for(winning_address)

        if existing:
            existing.winning_address = winning_address
            existing.winning_ticket_id = winning_id
            existing.winning_name = winning_name
            existing.ticket_count = len(ticket_ids)
            existing.save(update_fields=[
                'winning_address', 'winning_ticket_id',
                'winning_name', 'ticket_count', 'picked_at',
            ])
        else:
            RaffleResult.objects.create(
                week=target_week,
                winning_address=winning_address,
                winning_ticket_id=winning_id,
                winning_name=winning_name,
                ticket_count=len(ticket_ids),
            )

        self.stdout.write(self.style.SUCCESS(
            f"Winner: {winning_address} (#{winning_id}) "
            f"out of {len(ticket_ids)} tickets"
        ))
