"""训练相关共享路径约定。

标注服与训练服分机时，下列路径必须在两侧挂载为同一内容（NFS/共享盘）：

- DATA_ROOT（Label Studio BASE_DATA_DIR，compose 下为 /label-studio/data ← ./mydata）
  · 导出临时目录：DATA_ROOT/tmp/ls_train_multi_*
  · 上传媒体：DATA_ROOT/media/...
- CV_ULTRA_PATH（compose 下为 /label-studio/cv-ultralytics ← ./cv-ultralytics）
  · 预训练权重：.../ultralytics/ultralytics/models/
  · 划分数据集：.../datasets/job_<id>/
  · 训练 runs：.../runs/job_<id>/
  · 可下载模型：.../trained_models/model_v*/

标注服下载 best.pt / 曲线图时读的是 DB 里存的绝对路径；路径只有在
两侧 CV_ULTRA_PATH 与挂载一致时才能打开。
"""
import os

_BASE = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))


def cv_ultra_root() -> str:
    return os.environ.get('CV_ULTRA_PATH', os.path.join(_BASE, 'cv-ultralytics'))


def data_root() -> str:
    from django.conf import settings
    return getattr(settings, 'BASE_DATA_DIR', None) or os.environ.get(
        'LABEL_STUDIO_BASE_DATA_DIR', os.path.join(_BASE, 'data'),
    )


def training_export_tmp_root() -> str:
    """标注服写出、训练服读取的导出工作目录根（须在共享 DATA_ROOT 下）。"""
    root = os.path.join(data_root(), 'tmp')
    os.makedirs(root, exist_ok=True)
    return root


def job_dataset_root(job_id) -> str:
    return os.path.join(cv_ultra_root(), 'datasets', f'job_{job_id}')


def job_runs_root(job_id) -> str:
    return os.path.join(cv_ultra_root(), 'runs', f'job_{job_id}')


def trained_models_root() -> str:
    return os.path.join(cv_ultra_root(), 'trained_models')


def models_weights_dir() -> str:
    return os.path.join(cv_ultra_root(), 'ultralytics', 'ultralytics', 'models')
