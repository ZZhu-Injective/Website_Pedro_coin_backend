from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('myapp', '0007_game_steal'),
    ]

    operations = [
        migrations.CreateModel(
            name='RaffleTicket',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('week', models.CharField(db_index=True, max_length=10)),
                ('address', models.CharField(db_index=True, max_length=64)),
                ('source', models.CharField(
                    choices=[('free', 'Free (NFT holder)'), ('paid', 'Paid')],
                    max_length=16,
                )),
                ('tx_hash', models.CharField(blank=True, db_index=True, max_length=128)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
            ],
            options={
                'ordering': ['-created_at'],
            },
        ),
        migrations.AddIndex(
            model_name='raffleticket',
            index=models.Index(fields=['week', 'address'], name='myapp_raffl_week_addr_idx'),
        ),
        migrations.CreateModel(
            name='RaffleFreeClaim',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('address', models.CharField(db_index=True, max_length=64)),
                ('week', models.CharField(db_index=True, max_length=10)),
                ('nft_count_at_claim', models.IntegerField()),
                ('tickets_granted', models.IntegerField()),
                ('claimed_at', models.DateTimeField(auto_now_add=True)),
            ],
            options={
                'ordering': ['-claimed_at'],
                'unique_together': {('address', 'week')},
            },
        ),
        migrations.CreateModel(
            name='RafflePurchase',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('tx_hash', models.CharField(db_index=True, max_length=128, unique=True)),
                ('address', models.CharField(db_index=True, max_length=64)),
                ('week', models.CharField(db_index=True, max_length=10)),
                ('tickets', models.IntegerField()),
                ('pedro_burned', models.IntegerField()),
                ('created_at', models.DateTimeField(auto_now_add=True)),
            ],
            options={
                'ordering': ['-created_at'],
            },
        ),
        migrations.CreateModel(
            name='RaffleResult',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('week', models.CharField(db_index=True, max_length=10, unique=True)),
                ('winning_address', models.CharField(db_index=True, max_length=64)),
                ('winning_ticket_id', models.BigIntegerField()),
                ('winning_name', models.CharField(blank=True, max_length=64)),
                ('ticket_count', models.IntegerField()),
                ('picked_at', models.DateTimeField(auto_now_add=True)),
                ('payout_tx_hash', models.CharField(blank=True, max_length=128)),
            ],
            options={
                'ordering': ['-week'],
            },
        ),
    ]
