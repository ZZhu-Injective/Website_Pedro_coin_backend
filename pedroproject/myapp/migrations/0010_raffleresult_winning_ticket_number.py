from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('myapp', '0009_rafflefreeclaim_tx_hash'),
    ]

    operations = [
        migrations.AddField(
            model_name='raffleresult',
            name='winning_ticket_number',
            field=models.IntegerField(default=0),
        ),
    ]
