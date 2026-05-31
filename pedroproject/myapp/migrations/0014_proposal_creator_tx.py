from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('myapp', '0013_game_payout_nft_tx'),
    ]

    operations = [
        migrations.AddField(
            model_name='specialproposal',
            name='creator_address',
            field=models.CharField(blank=True, db_index=True, max_length=64),
        ),
        migrations.AddField(
            model_name='specialproposal',
            name='creation_tx_hash',
            field=models.CharField(blank=True, db_index=True, max_length=128),
        ),
    ]
