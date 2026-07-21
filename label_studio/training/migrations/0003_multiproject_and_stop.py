# Generated manually for multi-project training support

import django.db.models.deletion
from django.db import migrations, models


def migrate_project_to_m2m(apps, schema_editor):
    TrainingJob = apps.get_model('training', 'TrainingJob')
    for job in TrainingJob.objects.all():
        if job.project_id:
            job.projects.add(job.project_id)


def reverse_m2m_to_project(apps, schema_editor):
    TrainingJob = apps.get_model('training', 'TrainingJob')
    for job in TrainingJob.objects.all():
        first = job.projects.first()
        if first and not job.project_id:
            job.project_id = first.id
            job.save(update_fields=['project_id'])


class Migration(migrations.Migration):

    dependencies = [
        ("projects", "0030_project_search_vector_index"),
        ("training", "0002_add_missing_fields"),
    ]

    operations = [
        migrations.AlterField(
            model_name="trainingjob",
            name="project",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="training_jobs",
                to="projects.project",
            ),
        ),
        migrations.AddField(
            model_name="trainingjob",
            name="projects",
            field=models.ManyToManyField(
                blank=True,
                related_name="training_jobs_multi",
                to="projects.project",
            ),
        ),
        migrations.AddField(
            model_name="trainingjob",
            name="stop_requested",
            field=models.BooleanField(default=False),
        ),
        migrations.RunPython(migrate_project_to_m2m, reverse_m2m_to_project),
    ]
