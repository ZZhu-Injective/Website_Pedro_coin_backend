from django.db import migrations, models


class Migration(migrations.Migration):
    """Adds a unique tx_hash column to RaffleFreeClaim — proof-of-burn for
    free-ticket claims. Single AddField so PostgreSQL doesn't try to create
    the implicit `_like` index twice (the bug in the original two-step
    Add+Alter version of this migration).
    """

    dependencies = [
        ('myapp', '0008_raffle'),
    ]

    operations = [
        migrations.AddField(
            model_name='rafflefreeclaim',
            name='tx_hash',
            field=models.CharField(max_length=128, null=True, unique=True),
        ),
    ]
