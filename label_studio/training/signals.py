"""删除标注项目时，清理仅关联该项目的训练任务及磁盘产物。"""
import logging

from django.db.models.signals import pre_delete
from django.dispatch import receiver

logger = logging.getLogger(__name__)


@receiver(pre_delete, sender='projects.Project')
def cleanup_training_when_project_deleted(sender, instance, **kwargs):
    try:
        from .cleanup import cleanup_job_files
        from .models import TrainingJob
    except Exception:
        logger.exception('training cleanup import failed')
        return

    # 通过 M2M 或旧 FK 关联到该项目的任务
    job_ids = set(
        TrainingJob.objects.filter(projects=instance).values_list('id', flat=True)
    )
    job_ids.update(
        TrainingJob.objects.filter(project_id=instance.pk).values_list('id', flat=True)
    )

    for job in TrainingJob.objects.filter(id__in=job_ids).prefetch_related('models', 'projects'):
        remaining = job.projects.exclude(pk=instance.pk)
        # 若还挂着其它项目，只解除关联，不删任务
        if remaining.exists():
            job.projects.remove(instance)
            if job.project_id == instance.pk:
                first = remaining.first()
                job.project = first
                job.save(update_fields=['project', 'updated_at'])
            continue

        # 仅属于本项目：删文件 + 删任务记录
        try:
            cleanup_job_files(job)
        except Exception:
            logger.exception('cleanup files for training job %s failed', job.id)
        try:
            job.delete()
            logger.info('deleted training job %s with project %s', job.id, instance.pk)
        except Exception:
            logger.exception('delete training job %s failed', job.id)
