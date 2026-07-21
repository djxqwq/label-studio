# Generated manually: TrainingJob.artifacts for F1_curve etc.

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('training', '0005_organization_isolation'),
    ]

    operations = [
        migrations.AddField(
            model_name='trainingjob',
            name='artifacts',
            field=models.JSONField(blank=True, default=dict, help_text='训练产物路径，如 F1_curve'),
        ),
    ]
