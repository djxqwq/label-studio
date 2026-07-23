"""RQ worker entry for YOLO training jobs.

Annotation server enqueues after export; GPU training server runs
`python manage.py rqworker training` and executes this job.

Also exposed as ``training.jobs`` for the split-deploy plan naming.
"""
import json
import logging
import os
import shutil
from types import SimpleNamespace

from django.db import close_old_connections

from .paths import cv_ultra_root, job_dataset_root
from .tasks import TrainingStopped, build_dataset, run_training
from .transfer import (
    collect_job_artifact_files,
    data_mode,
    push_artifacts_to_annotation,
    resolve_export_dir,
)

logger = logging.getLogger(__name__)

_CV_ULTRA = cv_ultra_root()


def execute_training_job(job_id, export_dir, cleanup_dir, config_dict, params):
    """Build dataset and run training for a TrainingJob row.

    Args:
        job_id: TrainingJob.pk
        export_dir: merged export path (shared disk) or may be missing under http mode
        cleanup_dir: temp work dir to remove after train (annotation-side path)
        config_dict: serializable fields (name, task_type, classes, ...)
        params: train hyper-params + transfer metadata
    """
    close_old_connections()
    from .models import TrainingJob

    job = TrainingJob.objects.filter(pk=job_id).first()
    if not job:
        logger.error('TrainingJob %s not found', job_id)
        return

    config = SimpleNamespace(**(config_dict or {}))
    params = params or {}
    pull_cleanup = None

    dataset_root = job_dataset_root(job.id)
    dataset_dir = os.path.join(dataset_root, config.task_type)
    data_yaml_path = os.path.join(
        _CV_ULTRA, 'ultralytics', 'ultralytics',
        'cfg', 'datasets', f'job_{job.id}.yaml',
    )
    try:
        job.refresh_from_db()
        if job.stop_requested:
            job.status = 'stopped'
            job.save(update_fields=['status', 'updated_at'])
            return

        data_name = config.data_yaml or config.name
        from .tasks import _log as train_log

        project_ids = params.get('project_ids') or []
        mode = params.get('data_mode') or data_mode()
        train_log(job, '======== 训练任务开始 ========')
        train_log(
            job,
            f'任务 #{job.id} | 配置={config.name} | 类型={config.task_type} | '
            f'类别={list(config.classes or [])}',
        )
        train_log(
            job,
            f'预训练：{config.model_pt}.pt | 项目数={len(project_ids)} | '
            f'epochs={params.get("epochs")} batch={params.get("batch")} imgsz={params.get("imgsz")}',
        )
        train_log(job, f'执行端：RQ worker | data_mode={mode} | export={export_dir}')

        export_dir, pull_cleanup = resolve_export_dir(
            job.id, export_dir, params, log_fn=lambda msg: train_log(job, msg),
        )

        stats_path = os.path.join(os.path.dirname(export_dir.rstrip('/\\')), 'export_stats.json')
        if os.path.isfile(stats_path):
            try:
                with open(stats_path, encoding='utf-8') as f:
                    stats = json.load(f)
                train_log(job, '-------- 导出统计 --------')
                train_log(
                    job,
                    f'共 {stats.get("project_count")} 个项目，合并后图片 {stats.get("merged_images")} 张',
                )
                for p in stats.get('projects') or []:
                    train_log(
                        job,
                        f'  - 项目「{p.get("title")}」(#{p.get("id")})：'
                        f'图片 {p.get("images")} 张，可配对标签 {p.get("paired")}',
                    )
            except Exception:
                logger.exception('read export_stats failed')

        train_log(job, '-------- 数据集划分 --------')
        _, data_ref = build_dataset(
            export_dir, data_name, config.task_type, config.classes,
            job_id=job.id, log_fn=lambda msg: train_log(job, msg),
        )

        job.refresh_from_db()
        if job.stop_requested:
            train_log(job, '划分完成后检测到停止请求，跳过训练', level='WARNING')
            job.status = 'stopped'
            job.save(update_fields=['status', 'updated_at'])
            return

        job.status = 'training'
        job.save(update_fields=['status', 'updated_at'])

        train_kwargs = {
            k: v for k, v in params.items()
            if k not in (
                'model_pt', 'model_yaml', 'task_type', 'data_yaml', 'job', 'rq_job_id',
                'data_mode', 'package_path', 'package_rel', 'package_size',
            )
        }
        run_training(
            job=job,
            model_yaml=config.model_yaml,
            model_pt=config.model_pt,
            data_yaml=data_ref,
            task_type=config.task_type,
            **train_kwargs,
        )

        # 远程模式：把 best/last/曲线回传到标注服，保证下载可读
        if mode in ('ssh', 'http'):
            job.refresh_from_db()
            files = collect_job_artifact_files(job)
            if files:
                try:
                    push_artifacts_to_annotation(
                        job.id, files, log_fn=lambda msg: train_log(job, msg), mode=mode,
                    )
                except Exception as e:
                    train_log(job, f'产物回传失败：{e}', level='WARNING')
                    logger.exception('artifact push failed')

        job.refresh_from_db()
        if job.stop_requested:
            job.status = 'stopped'
        else:
            job.status = 'completed'
            job.progress = 100
        job.save(update_fields=['status', 'progress', 'updated_at'])
    except TrainingStopped as e:
        logger.info('training stopped: %s', e)
        job.status = 'stopped'
        job.error_message = str(e)
        job.save(update_fields=['status', 'error_message', 'updated_at'])
    except Exception as e:
        logger.exception('训练失败：%s', e)
        job.status = 'failed'
        job.error_message = str(e)
        job.save(update_fields=['status', 'error_message', 'updated_at'])
    finally:
        close_old_connections()
        # cleanup_dir 在标注服本地；http 模式下训练服路径无效，忽略即可
        if cleanup_dir and os.path.exists(cleanup_dir):
            shutil.rmtree(cleanup_dir, ignore_errors=True)
        if pull_cleanup and os.path.exists(pull_cleanup):
            shutil.rmtree(pull_cleanup, ignore_errors=True)
        if os.path.exists(dataset_root):
            shutil.rmtree(dataset_root, ignore_errors=True)
        elif os.path.exists(dataset_dir):
            shutil.rmtree(dataset_dir, ignore_errors=True)
        if os.path.isfile(data_yaml_path):
            try:
                os.remove(data_yaml_path)
            except OSError:
                logger.exception('删除 data.yaml 失败: %s', data_yaml_path)
