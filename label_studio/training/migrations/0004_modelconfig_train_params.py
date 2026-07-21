# Generated manually: add train_params JSON for full YOLO hyperparams

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("training", "0003_multiproject_and_stop"),
    ]

    operations = [
        migrations.AddField(
            model_name="modelconfig",
            name="train_params",
            field=models.JSONField(
                blank=True,
                default=dict,
                help_text="完整 YOLO 训练超参，覆盖默认值",
            ),
        ),
    ]
