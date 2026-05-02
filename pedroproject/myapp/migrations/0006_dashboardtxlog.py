from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('myapp', '0005_governance_models'),
    ]

    operations = [
        migrations.CreateModel(
            name='DashboardTxLog',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('tx_hash', models.CharField(db_index=True, max_length=128, unique=True)),
                ('feature', models.CharField(
                    choices=[
                        ('converter', 'Converter'),
                        ('airdrop', 'Airdrop'),
                        ('launcher', 'Launcher'),
                    ],
                    db_index=True,
                    max_length=32,
                )),
                ('address', models.CharField(db_index=True, max_length=64)),
                ('summary', models.CharField(blank=True, max_length=255)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
            ],
            options={
                'ordering': ['-created_at'],
            },
        ),
    ]
