from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('myapp', '0014_proposal_creator_tx'),
    ]

    operations = [
        migrations.AddField(
            model_name='specialproposal',
            name='options',
            field=models.JSONField(blank=True, default=list),
        ),
        migrations.AlterField(
            model_name='specialvote',
            name='choice',
            field=models.CharField(max_length=16),
        ),
    ]
