from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('myapp', '0008_raffle'),
    ]

    operations = [
        # Two-step add of a unique field on a populated table:
        # 1. Add nullable so existing rows don't violate the constraint.
        # 2. Add the unique constraint separately. Existing rows get NULL,
        #    which is permitted under SQL's standard treatment of NULL in
        #    UNIQUE constraints (each NULL is distinct).
        migrations.AddField(
            model_name='rafflefreeclaim',
            name='tx_hash',
            field=models.CharField(blank=True, db_index=True, max_length=128, null=True),
        ),
        migrations.AlterField(
            model_name='rafflefreeclaim',
            name='tx_hash',
            field=models.CharField(db_index=True, max_length=128, unique=True, null=True),
        ),
    ]
