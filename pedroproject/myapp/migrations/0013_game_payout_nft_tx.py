from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('myapp', '0012_game_month_reset'),
    ]

    operations = [
        migrations.AddField(
            model_name='gamemonthpayout',
            name='payout_nft_tx_hash',
            field=models.CharField(blank=True, max_length=128),
        ),
    ]
