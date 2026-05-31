import datetime
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('myapp', '0010_raffleresult_winning_ticket_number'),
    ]

    operations = [
        migrations.CreateModel(
            name='SpecialProposal',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('title', models.CharField(max_length=200)),
                ('description', models.TextField()),
                ('choice_yes_label', models.CharField(default='Yes', max_length=64)),
                ('choice_no_label', models.CharField(default='No', max_length=64)),
                ('is_active', models.BooleanField(db_index=True, default=True)),
                ('start_date', models.DateField()),
                ('end_date', models.DateField()),
                ('created_at', models.DateTimeField(auto_now_add=True)),
            ],
            options={
                'ordering': ['-start_date'],
            },
        ),
        migrations.CreateModel(
            name='SpecialVote',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('proposal', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='votes', to='myapp.specialproposal')),
                ('address', models.CharField(db_index=True, max_length=64)),
                ('choice', models.CharField(max_length=8)),
                ('points', models.IntegerField()),
                ('tx_hash', models.CharField(db_index=True, max_length=128, unique=True)),
                ('voted_at', models.DateTimeField(auto_now_add=True)),
            ],
            options={
                'ordering': ['-voted_at'],
                'unique_together': {('proposal', 'address')},
            },
        ),
        migrations.CreateModel(
            name='GameMonthPayout',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('month', models.CharField(db_index=True, max_length=7, unique=True)),
                ('payout_tx_hash', models.CharField(blank=True, max_length=128)),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
            options={
                'ordering': ['-month'],
            },
        ),
        # Seed the first special proposal: CEO vote
        migrations.RunPython(
            code=lambda apps, schema_editor: apps.get_model('myapp', 'SpecialProposal').objects.create(
                title='Time for a New CEO?',
                description=(
                    'Should Pedro have a new CEO who focuses fully on development? '
                    'A dev-focused leader would prioritise shipping features, '
                    'improving the ecosystem, and building long-term value for the community.'
                ),
                choice_yes_label='Yes — new dev CEO',
                choice_no_label='No — keep current',
                is_active=True,
                start_date=datetime.date(2026, 5, 22),
                end_date=datetime.date(2026, 6, 30),
            ),
            reverse_code=lambda apps, schema_editor: apps.get_model('myapp', 'SpecialProposal').objects.filter(
                title='Time for a New CEO?'
            ).delete(),
        ),
    ]
