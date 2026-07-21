# Generated manually: organization isolation for training

import django.db.models.deletion
from django.db import migrations, models


def backfill_organization(apps, schema_editor):
    ModelConfig = apps.get_model('training', 'ModelConfig')
    TrainingJob = apps.get_model('training', 'TrainingJob')
    Organization = apps.get_model('organizations', 'Organization')
    User = apps.get_model('users', 'User')
    Project = apps.get_model('projects', 'Project')

    default_org = Organization.objects.order_by('id').first()

    for cfg in ModelConfig.objects.filter(organization__isnull=True):
        org_id = None
        if cfg.created_by_id:
            user = User.objects.filter(id=cfg.created_by_id).first()
            if user and getattr(user, 'active_organization_id', None):
                org_id = user.active_organization_id
        cfg.organization_id = org_id or (default_org.id if default_org else None)
        cfg.save(update_fields=['organization_id'])

    for job in TrainingJob.objects.filter(organization__isnull=True):
        org_id = None
        if job.project_id:
            project = Project.objects.filter(id=job.project_id).first()
            if project and project.organization_id:
                org_id = project.organization_id
        if not org_id and job.created_by_id:
            user = User.objects.filter(id=job.created_by_id).first()
            if user and getattr(user, 'active_organization_id', None):
                org_id = user.active_organization_id
        job.organization_id = org_id or (default_org.id if default_org else None)
        job.save(update_fields=['organization_id'])


def noop_reverse(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("organizations", "0006_alter_organizationmember_deleted_at"),
        ("training", "0004_modelconfig_train_params"),
    ]

    operations = [
        migrations.AddField(
            model_name="modelconfig",
            name="organization",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name="training_model_configs",
                to="organizations.organization",
            ),
        ),
        migrations.AddField(
            model_name="trainingjob",
            name="organization",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name="training_jobs",
                to="organizations.organization",
            ),
        ),
        migrations.AlterField(
            model_name="modelconfig",
            name="name",
            field=models.CharField(max_length=255),
        ),
        migrations.AlterUniqueTogether(
            name="modelconfig",
            unique_together={("organization", "name")},
        ),
        migrations.RunPython(backfill_organization, noop_reverse),
    ]
