"""训练产物磁盘清理：trained_models / Ultralytics runs / artifacts"""
import logging
import os
import shutil

logger = logging.getLogger(__name__)

_BASE = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
_CV_ULTRA = os.environ.get('CV_ULTRA_PATH', os.path.join(_BASE, 'cv-ultralytics'))


def job_runs_root(job_id) -> str:
    """每个任务独立的 Ultralytics runs 根目录"""
    return os.path.join(_CV_ULTRA, 'runs', f'job_{job_id}')


def cleanup_job_files(job) -> int:
    """删除任务关联的模型文件、artifacts、runs 目录。返回删除的文件/目录计数。"""
    removed = 0
    parent_dirs = set()

    for m in job.models.all():
        path = m.file_path
        if path and os.path.isfile(path):
            try:
                os.remove(path)
                removed += 1
                parent = os.path.dirname(path)
                if parent:
                    parent_dirs.add(parent)
            except OSError:
                logger.exception('删除模型文件失败: %s', path)

    artifacts = job.artifacts or {}
    for key, path in artifacts.items():
        if key in ('runs_dir', 'trained_dir'):
            continue
        if path and os.path.isfile(path):
            try:
                os.remove(path)
                removed += 1
                parent = os.path.dirname(path)
                if parent:
                    parent_dirs.add(parent)
            except OSError:
                logger.exception('删除训练产物失败: %s', path)

    for parent in parent_dirs:
        try:
            if os.path.isdir(parent) and not os.listdir(parent):
                os.rmdir(parent)
                removed += 1
        except OSError:
            pass

    # Ultralytics runs：优先用 artifacts 记录，否则按 job_id 约定路径
    runs_dirs = set()
    recorded = artifacts.get('runs_dir')
    if recorded:
        runs_dirs.add(recorded)
    runs_dirs.add(job_runs_root(job.id))

    for runs_dir in runs_dirs:
        if runs_dir and os.path.isdir(runs_dir):
            try:
                shutil.rmtree(runs_dir, ignore_errors=False)
                removed += 1
                logger.info('已删除 runs 目录: %s', runs_dir)
            except OSError:
                logger.exception('删除 runs 目录失败: %s', runs_dir)
                shutil.rmtree(runs_dir, ignore_errors=True)

    trained_dir = artifacts.get('trained_dir')
    if trained_dir and os.path.isdir(trained_dir):
        try:
            shutil.rmtree(trained_dir, ignore_errors=True)
            removed += 1
        except OSError:
            logger.exception('删除 trained_models 目录失败: %s', trained_dir)

    return removed
