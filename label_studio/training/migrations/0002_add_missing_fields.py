# Generated migration to add missing fields and tables

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("projects", "0030_project_search_vector_index"),
        ("training", "0001_initial"),
    ]

    operations = [
        # ====== TrainingJob: 补充缺失的 progress / current_epoch / total_epochs 字段 ======
        migrations.AddField(
            model_name="trainingjob",
            name="progress",
            field=models.IntegerField(default=0, help_text="0-100"),
        ),
        migrations.AddField(
            model_name="trainingjob",
            name="current_epoch",
            field=models.IntegerField(default=0),
        ),
        migrations.AddField(
            model_name="trainingjob",
            name="total_epochs",
            field=models.IntegerField(default=0),
        ),
        # ====== TrainingLog 训练日志表 ======
        migrations.CreateModel(
            name="TrainingLog",
            fields=[
                (
                    "id",
                    models.AutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("level", models.CharField(default="INFO", max_length=10)),
                ("message", models.TextField()),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "job",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="logs",
                        to="training.trainingjob",
                    ),
                ),
            ],
            options={
                "ordering": ["created_at"],
            },
        ),
        # ====== TrainedModel 训练产出模型表 ======
        migrations.CreateModel(
            name="TrainedModel",
            fields=[
                (
                    "id",
                    models.AutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("name", models.CharField(max_length=255)),
                ("file_path", models.CharField(max_length=1024)),
                ("file_size", models.BigIntegerField(default=0)),
                ("metrics", models.JSONField(default=dict)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "job",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="models",
                        to="training.trainingjob",
                    ),
                ),
            ],
            options={
                "ordering": ["-created_at"],
            },
        ),
    ]
