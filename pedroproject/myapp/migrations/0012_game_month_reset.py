from datetime import datetime, timezone

from django.db import migrations, models


def _seed_locked_names_and_snapshot_past_months(apps, schema_editor):
    """One-shot housekeeping at upgrade time:

    1. Backfill `GameUpgradeState.locked_name` from each address's first ever
       leaderboard submission (so the name lock survives the upcoming wipe).
    2. For every past month with leaderboard entries, snapshot the top winner
       into `GameMonthPayout` (only when the winner fields are still empty),
       then delete those leaderboard rows.
    3. Stamp every existing `GameUpgradeState` with the current month so the
       lazy reset doesn't wipe progress mid-month at deploy time.
    """
    GameLeaderboardEntry = apps.get_model('myapp', 'GameLeaderboardEntry')
    GameUpgradeState = apps.get_model('myapp', 'GameUpgradeState')
    GameMonthPayout = apps.get_model('myapp', 'GameMonthPayout')

    current_month = datetime.now(timezone.utc).strftime('%Y-%m')

    # 1. Backfill locked_name from earliest leaderboard submission per address.
    addresses_with_entries = (
        GameLeaderboardEntry.objects
        .values_list('address', flat=True)
        .distinct()
    )
    for address in addresses_with_entries:
        first_name = (
            GameLeaderboardEntry.objects
            .filter(address=address)
            .order_by('submitted_at', 'id')
            .values_list('name', flat=True)
            .first()
        )
        if not first_name:
            continue
        state, _ = GameUpgradeState.objects.get_or_create(address=address)
        if not state.locked_name:
            state.locked_name = first_name[:64]
            state.save(update_fields=['locked_name', 'updated_at'])

    # 2. Snapshot past-month winners and delete the now-stale leaderboard rows.
    past_months = (
        GameLeaderboardEntry.objects
        .exclude(month=current_month)
        .values_list('month', flat=True)
        .distinct()
    )
    for month in list(past_months):
        top = (
            GameLeaderboardEntry.objects
            .filter(month=month)
            .order_by('-score', 'submitted_at', 'id')
            .first()
        )
        if top:
            payout, _ = GameMonthPayout.objects.get_or_create(month=month)
            if not payout.winning_address:
                payout.winning_address = top.address
                payout.winning_name = (top.name or '')[:64]
                payout.winning_score = top.score
                payout.winning_tx_hash = top.tx_hash
                payout.save(update_fields=[
                    'winning_address', 'winning_name',
                    'winning_score', 'winning_tx_hash', 'updated_at',
                ])
        GameLeaderboardEntry.objects.filter(month=month).delete()

    # 3. Stamp current_month on every existing GameUpgradeState row so the
    #    lazy reset only triggers at the next real month boundary.
    GameUpgradeState.objects.filter(current_month='').update(
        current_month=current_month,
    )


def _noop_reverse(apps, schema_editor):
    """Reverse is a no-op — deleted leaderboard rows are unrecoverable, and
    re-padding locked_name / current_month back to '' would break the live
    reset logic."""
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('myapp', '0011_special_proposals_game_payout'),
    ]

    operations = [
        migrations.AddField(
            model_name='gameupgradestate',
            name='locked_name',
            field=models.CharField(blank=True, default='', max_length=64),
        ),
        migrations.AddField(
            model_name='gameupgradestate',
            name='current_month',
            field=models.CharField(blank=True, default='', max_length=7),
        ),
        migrations.AddField(
            model_name='gamemonthpayout',
            name='winning_address',
            field=models.CharField(blank=True, db_index=True, max_length=64),
        ),
        migrations.AddField(
            model_name='gamemonthpayout',
            name='winning_name',
            field=models.CharField(blank=True, max_length=64),
        ),
        migrations.AddField(
            model_name='gamemonthpayout',
            name='winning_score',
            field=models.BigIntegerField(default=0),
        ),
        migrations.AddField(
            model_name='gamemonthpayout',
            name='winning_tx_hash',
            field=models.CharField(blank=True, max_length=128),
        ),
        migrations.RunPython(
            _seed_locked_names_and_snapshot_past_months,
            _noop_reverse,
        ),
    ]
