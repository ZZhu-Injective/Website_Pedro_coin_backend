from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('myapp', '0006_dashboardtxlog'),
    ]

    operations = [
        migrations.AddField(
            model_name='gameupgradestate',
            name='steal_level',
            field=models.IntegerField(default=0),
        ),
        migrations.AddField(
            model_name='gameupgradestate',
            name='last_steal_at',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.CreateModel(
            name='GameStealLog',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('attacker', models.CharField(db_index=True, max_length=64)),
                ('target', models.CharField(db_index=True, max_length=64)),
                ('amount', models.BigIntegerField()),
                ('attacker_level', models.IntegerField(default=0)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
            ],
            options={
                'ordering': ['-created_at'],
            },
        ),
    ]
