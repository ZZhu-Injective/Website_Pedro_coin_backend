from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('myapp', '0004_gameleaderboardentry_gameupgradestate'),
    ]

    operations = [
        migrations.CreateModel(
            name='GovernanceVoterSnapshot',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('month', models.CharField(db_index=True, max_length=7)),
                ('address', models.CharField(db_index=True, max_length=64)),
                ('nft_count', models.IntegerField()),
                ('captured_at', models.DateTimeField(auto_now_add=True)),
            ],
            options={
                'ordering': ['-month', '-nft_count'],
                'unique_together': {('month', 'address')},
            },
        ),
        migrations.CreateModel(
            name='GovernanceVote',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('address', models.CharField(db_index=True, max_length=64)),
                ('month', models.CharField(db_index=True, max_length=7)),
                ('choice', models.CharField(db_index=True, max_length=32)),
                ('points', models.IntegerField()),
                ('tx_hash', models.CharField(db_index=True, max_length=128, unique=True)),
                ('voted_at', models.DateTimeField(auto_now_add=True)),
            ],
            options={
                'ordering': ['-voted_at'],
                'unique_together': {('address', 'month')},
            },
        ),
        migrations.CreateModel(
            name='GovernanceMonthResult',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('month', models.CharField(db_index=True, max_length=7, unique=True)),
                ('winning_choice', models.CharField(blank=True, max_length=32)),
                ('points_liquidity', models.IntegerField(default=0)),
                ('points_buy_nfts', models.IntegerField(default=0)),
                ('points_giveaway', models.IntegerField(default=0)),
                ('payout_tx_hash', models.CharField(blank=True, max_length=128)),
                ('payout_amount', models.CharField(blank=True, max_length=64)),
                ('notes', models.TextField(blank=True)),
                ('finalized_at', models.DateTimeField(auto_now=True)),
            ],
            options={
                'ordering': ['-month'],
            },
        ),
    ]
