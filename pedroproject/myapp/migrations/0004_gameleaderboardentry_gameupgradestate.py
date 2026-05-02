from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('myapp', '0003_marketplacelisting_scamreport_talent'),
    ]

    operations = [
        migrations.CreateModel(
            name='GameLeaderboardEntry',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('address', models.CharField(db_index=True, max_length=64)),
                ('name', models.CharField(max_length=64)),
                ('score', models.BigIntegerField()),
                ('tx_hash', models.CharField(db_index=True, max_length=128, unique=True)),
                ('month', models.CharField(db_index=True, max_length=7)),
                ('submitted_at', models.DateTimeField(auto_now_add=True)),
            ],
            options={
                'ordering': ['-score', 'submitted_at'],
            },
        ),
        migrations.CreateModel(
            name='GameUpgradeState',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('address', models.CharField(db_index=True, max_length=64, unique=True)),
                ('click_level', models.IntegerField(default=0)),
                ('auto_level', models.IntegerField(default=0)),
                ('score', models.BigIntegerField(default=0)),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
        ),
    ]
