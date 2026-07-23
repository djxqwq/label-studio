"""Django 训练后台任务 —— 直接调 cv-ultralytics / Ultralytics"""
import os
import sys
import shutil

_BASE = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
_CV_ULTRA = os.environ.get('CV_ULTRA_PATH', os.path.join(_BASE, 'cv-ultralytics'))
_ULTRA_SRC = os.path.join(_CV_ULTRA, 'ultralytics')
if _ULTRA_SRC not in sys.path:
    sys.path.insert(0, _ULTRA_SRC)

_PROJ_ROOT = os.path.join(_CV_ULTRA, 'ultralytics', 'ultralytics')


class TrainingStopped(Exception):
    """用户请求停止训练"""


def _close_db():
    from django.db import connections
    for conn in connections.all():
        conn.close_if_unusable_or_obsolete()


def _log(job, message, level='INFO'):
    from .models import TrainingLog
    _close_db()
    TrainingLog.objects.create(job=job, level=level, message=message)


def _progress(job, current_epoch, total_epochs):
    _close_db()
    job.refresh_from_db(fields=['stop_requested', 'status'])
    job.current_epoch = current_epoch
    job.total_epochs = total_epochs
    job.progress = int(current_epoch / total_epochs * 100) if total_epochs else 0
    job.save(update_fields=['current_epoch', 'total_epochs', 'progress', 'updated_at'])


def _is_stop_requested(job):
    _close_db()
    job.refresh_from_db(fields=['stop_requested', 'status'])
    return bool(job.stop_requested) or job.status == 'stopped'


def _count_images_with_exts(dir_path: str, image_exts) -> int:
    if not dir_path or not os.path.isdir(dir_path):
        return 0
    n = 0
    for _, _, files in os.walk(dir_path):
        n += sum(1 for f in files if f.lower().endswith(image_exts))
    return n


def _summarize_splits(dataset_dir: str, task_type: str, image_exts) -> dict:
    """统计划分后 train/valid(val)/test 图片数。"""
    if task_type == 'cls':
        phases = {
            'train': os.path.join(dataset_dir, 'train'),
            'val': os.path.join(dataset_dir, 'val'),
            'test': os.path.join(dataset_dir, 'test'),
        }
    else:
        phases = {
            'train': os.path.join(dataset_dir, 'train', 'images'),
            'val': os.path.join(dataset_dir, 'valid', 'images'),
            'test': os.path.join(dataset_dir, 'test', 'images'),
        }
    counts = {k: _count_images_with_exts(p, image_exts) for k, p in phases.items()}
    counts['total'] = sum(counts.values())
    return counts


def build_dataset(export_dir: str, dataset_name: str, task_type: str, classes: list, job_id=None, log_fn=None):
    """划分数据集并生成 data 配置。

    job_id 用于隔离目录/yaml，避免同配置并发训练互相覆盖。
    返回 (dataset_dir, data_ref)：
      - detect/obb/seg: data_ref 为 yaml stem（job_<id>）
      - cls: data_ref 为分类数据集根目录绝对路径（ImageFolder）
    """
    _datasets_process = os.path.join(_CV_ULTRA, 'datasets_process', 'utils')
    if _datasets_process not in sys.path:
        sys.path.insert(0, _datasets_process)

    from group_img import IMAGE_EXTS, split_cls_dataset, split_dataset

    def _l(msg):
        if log_fn:
            log_fn(msg)

    yaml_stem = f'job_{job_id}' if job_id is not None else dataset_name
    dst = os.path.join(_CV_ULTRA, 'datasets', yaml_stem, task_type)
    train_ratio, valid_ratio, test_ratio = 0.8, 0.15, 0.05

    if os.path.isdir(dst):
        shutil.rmtree(dst, ignore_errors=True)

    classes = list(classes or [])
    _l(f'开始构建数据集：任务={task_type}，类别数={len(classes)}，类别={classes}')
    _l(
        f'划分比例：训练集 {train_ratio:.0%} / 验证集 {valid_ratio:.0%} / 测试集 {test_ratio:.0%}'
        f'（与 cv-ultralytics 原仓库一致）'
    )

    if task_type == 'cls':
        classes_root = os.path.join(export_dir, 'classes')
        if not os.path.isdir(classes_root):
            raise FileNotFoundError(f'分类导出缺少 classes 目录：{classes_root}')
        per_class = {}
        img_count = 0
        for name in sorted(os.listdir(classes_root)):
            p = os.path.join(classes_root, name)
            if not os.path.isdir(p):
                continue
            c = _count_images_with_exts(p, IMAGE_EXTS)
            per_class[name] = c
            img_count += c
        if img_count < 2:
            raise ValueError(f'有效图片过少（{img_count}），至少需要 2 张才能划分训练/验证集')
        _l(f'导出分类样本合计 {img_count} 张')
        for cn, cn_n in per_class.items():
            _l(f'  - 类别「{cn}」：{cn_n} 张')

        split_cls_dataset(export_dir, dst, train_ratio=train_ratio, valid_ratio=valid_ratio, test_ratio=test_ratio)
        splits = _summarize_splits(dst, 'cls', IMAGE_EXTS)
        _l(
            f'划分完成：训练集 {splits["train"]} 张，验证集 {splits["val"]} 张，'
            f'测试集 {splits["test"]} 张，合计 {splits["total"]} 张'
        )
        for phase, label in (('train', '训练集'), ('val', '验证集')):
            phase_dir = os.path.join(dst, phase)
            if not os.path.isdir(phase_dir):
                continue
            parts = []
            for cn in sorted(os.listdir(phase_dir)):
                cp = os.path.join(phase_dir, cn)
                if os.path.isdir(cp):
                    parts.append(f'{cn}={_count_images_with_exts(cp, IMAGE_EXTS)}')
            if parts:
                _l(f'  {label}按类：{", ".join(parts)}')
        return dst, dst

    # detect / obb / seg
    src_img = os.path.join(export_dir, 'images')
    src_lbl = os.path.join(export_dir, 'labels')

    if not os.path.isdir(src_img):
        for item in os.listdir(export_dir):
            p = os.path.join(export_dir, item)
            if os.path.isdir(p) and os.path.isdir(os.path.join(p, 'images')):
                src_img = os.path.join(p, 'images')
                src_lbl = os.path.join(p, 'labels')
                export_dir = p
                break

    if not os.path.isdir(src_img) or not os.path.isdir(src_lbl):
        raise FileNotFoundError(
            f'导出数据不完整：images={os.path.isdir(src_img)}, labels={os.path.isdir(src_lbl)}'
        )

    img_files = [f for f in os.listdir(src_img) if f.lower().endswith(IMAGE_EXTS)]
    lbl_files = {f for f in os.listdir(src_lbl) if f.endswith('.txt')}
    paired = sum(1 for f in img_files if (os.path.splitext(f)[0] + '.txt') in lbl_files)
    unpaired = len(img_files) - paired
    _l(
        f'导出检测样本：图片 {len(img_files)} 张，标签 {len(lbl_files)} 个，'
        f'可配对 {paired}，缺标签跳过 {unpaired}'
    )

    if paired < 2:
        raise ValueError(f'有效图片过少（可配对 {paired}），至少需要 2 张才能划分训练/验证集')

    split_dataset(export_dir, dst, train_ratio=train_ratio, valid_ratio=valid_ratio, test_ratio=test_ratio)
    splits = _summarize_splits(dst, task_type, IMAGE_EXTS)
    _l(
        f'划分完成：训练集 {splits["train"]} 张，验证集 {splits["val"]} 张，'
        f'测试集 {splits["test"]} 张，合计 {splits["total"]} 张'
    )
    if splits['total']:
        _l(
            f'实际占比：train {splits["train"] / splits["total"] * 100:.1f}% / '
            f'val {splits["val"] / splits["total"] * 100:.1f}% / '
            f'test {splits["test"] / splits["total"] * 100:.1f}%'
        )

    yaml_path = os.path.join(_PROJ_ROOT, 'cfg', 'datasets', f'{yaml_stem}.yaml')
    dst_safe = dst.replace('\\', '/')
    content = f"""# Auto-generated by Training Service (job={job_id}, task={task_type})
train: {dst_safe}/train/images
val: {dst_safe}/valid/images
test: {dst_safe}/test/images

nc: {len(classes)}
names:
"""
    for i, c in enumerate(classes):
        content += f"  {i}: {c}\n"

    os.makedirs(os.path.dirname(yaml_path), exist_ok=True)
    with open(yaml_path, 'w', encoding='utf-8') as f:
        f.write(content)
    _l(f'已生成数据配置：{yaml_stem}.yaml（nc={len(classes)}）')

    return dst, yaml_stem


def _download_model_weights(model_name: str, dest_dir: str, log_fn=None) -> str:
    from .weights import download_model_weights
    return download_model_weights(model_name, dest_dir=dest_dir, log_fn=log_fn)


def _extract_model_scale(model_yaml: str, model_pt: str) -> str:
    """从 yaml/pt 名解析尺度字母（含 v9 的 t/c/e、v10 的 b、v5 的 *u）。"""
    import re
    for name in (model_yaml or '', model_pt or ''):
        # yolov8x-obb / yolov5xu / yolov9c-seg / yolov10b / yolo11n
        m = re.search(
            r'yolo(?:v)?\d+([ntsmlxceb])(?:u)?(?:-|$|\.|$)',
            name,
            re.I,
        )
        if m:
            return m.group(1).lower()
    return 'x'


def run_training(job, model_yaml: str, model_pt: str, data_yaml: str, task_type: str = 'obb', **params):
    """直接调 YOLO model.train()，写进度和日志到 DB；支持 stop_requested 中断"""
    from datetime import datetime

    from ultralytics import YOLO
    from ultralytics.utils import SETTINGS

    if _is_stop_requested(job):
        raise TrainingStopped('训练在开始前已被停止')

    epochs = params.get('epochs', 1000)

    _models_dir = os.path.join(_PROJ_ROOT, 'models')
    os.makedirs(_models_dir, exist_ok=True)
    SETTINGS['weights_dir'] = _models_dir

    model_pt_path = os.path.join(_models_dir, f'{model_pt}.pt')
    scale = _extract_model_scale(model_yaml, model_pt)
    local_pts = []
    if os.path.isdir(_models_dir):
        local_pts = sorted(f for f in os.listdir(_models_dir) if f.endswith('.pt'))

    _log(job, f'======== 模型加载 ========')
    _log(job, f'预训练权重：{model_pt}.pt（任务={task_type}，尺寸档={scale}）')
    _log(job, f'本地已有权重文件 {len(local_pts)} 个' + (f'：{", ".join(local_pts[:8])}' + ('…' if len(local_pts) > 8 else '') if local_pts else ''))

    def _load_model(pt_path):
        """优先用 .pt 构建（结构与权重一致）；避免 YOLO(yolov8-obb.yaml) 丢尺度变成 n。"""
        if os.path.isfile(pt_path):
            _log(job, f'从本地权重加载：{os.path.basename(pt_path)}')
            return YOLO(pt_path)
        yaml_name = model_yaml if model_yaml.endswith('.yaml') else f'{model_yaml}.yaml'
        import re
        if re.match(r'^yolov\d+-(obb|seg|cls|pose)?\.yaml$', yaml_name) and scale:
            yaml_name = yaml_name.replace('yolov8-', f'yolov8{scale}-').replace('yolov5-', f'yolov5{scale}-')
        _log(job, f'按结构名构建模型：{yaml_name}')
        return YOLO(yaml_name)

    if os.path.exists(model_pt_path):
        model = _load_model(model_pt_path)
    else:
        _log(job, f'本地没有 {model_pt}.pt，开始镜像下载…')
        try:
            downloaded = _download_model_weights(
                model_pt, _models_dir, log_fn=lambda msg: _log(job, msg),
            )
            model = _load_model(downloaded)
        except RuntimeError as e:
            _log(job, f'镜像下载失败：{e}，回退到 YOLO 自带下载 …', level='WARNING')
            model = YOLO(f'{model_pt}.pt')

    # cls: data_yaml 实际是数据集目录；其它任务是 yaml stem
    if task_type == 'cls' or (isinstance(data_yaml, str) and os.path.isdir(data_yaml)):
        data_path = data_yaml
        if not os.path.isdir(data_path):
            raise FileNotFoundError(f'分类数据集目录不存在：{data_path}')
    else:
        data_path = os.path.join(_PROJ_ROOT, 'cfg', 'datasets', f'{data_yaml}.yaml')
        if not os.path.isfile(data_path):
            raise FileNotFoundError(f'数据集配置不存在：{data_path}，请确认 build_dataset 已成功生成 data.yaml')

    def _epoch_callback(trainer):
        if _is_stop_requested(job):
            _log(job, '收到停止请求，正在中断训练…', level='WARNING')
            trainer.stop = True
            return
        if hasattr(trainer, 'epoch') and trainer.epoch is not None:
            cur = trainer.epoch + 1
            _progress(job, cur, epochs)
            parts = [f'Epoch {cur}/{epochs}']
            # 训练 loss
            tloss = getattr(trainer, 'tloss', None)
            if tloss is not None:
                try:
                    if hasattr(tloss, 'mean'):
                        parts.append(f'loss={float(tloss.mean()):.4f}')
                    else:
                        parts.append(f'loss={float(tloss):.4f}')
                except Exception:
                    pass
            # 验证指标（若本轮已算）
            metrics = getattr(trainer, 'metrics', None) or {}
            if isinstance(metrics, dict):
                for key, label in (
                    ('metrics/mAP50(B)', 'mAP50'),
                    ('metrics/mAP50-95(B)', 'mAP50-95'),
                    ('metrics/precision(B)', 'P'),
                    ('metrics/recall(B)', 'R'),
                    ('metrics/accuracy_top1', 'acc@1'),
                ):
                    if key in metrics and metrics[key] is not None:
                        try:
                            parts.append(f'{label}={float(metrics[key]):.4f}')
                        except Exception:
                            pass
            _log(job, ' | '.join(parts))

    model.add_callback('on_train_epoch_end', _epoch_callback)

    import torch
    device = params.get('device', 'auto') or 'auto'
    if device != 'cpu' and not torch.cuda.is_available():
        device = 'cpu'
        _log(job, 'CUDA 不可用，改用 CPU 训练', level='WARNING')
    elif device == 'auto':
        device = 0 if torch.cuda.is_available() else 'cpu'

    from .params import BLOCKED_TRAIN_KEYS, merge_train_params
    train_kwargs = merge_train_params(params)
    for key in list(train_kwargs.keys()):
        if key in BLOCKED_TRAIN_KEYS or key in (
            'project_ids', 'task_type', 'yolo_version', 'yolo_scale',
            'model_pt', 'model_yaml', 'config_name',
        ):
            train_kwargs.pop(key, None)

    train_kwargs['data'] = data_path
    train_kwargs['device'] = device
    train_kwargs['epochs'] = epochs
    if isinstance(train_kwargs.get('device'), str) and train_kwargs['device'].isdigit():
        train_kwargs['device'] = int(train_kwargs['device'])

    from .cleanup import job_runs_root
    runs_root = job_runs_root(job.id)
    os.makedirs(runs_root, exist_ok=True)
    train_kwargs['project'] = runs_root
    train_kwargs['name'] = task_type or 'train'
    train_kwargs['exist_ok'] = True

    # 人类可读的关键参数摘要
    batch = train_kwargs.get('batch', 16)
    imgsz = train_kwargs.get('imgsz', 640)
    patience = train_kwargs.get('patience', '-')
    workers = train_kwargs.get('workers', '-')
    lr0 = train_kwargs.get('lr0', '-')
    device_label = (
        f'cuda:{device}' if isinstance(device, int)
        else ('CPU' if str(device) == 'cpu' else str(device))
    )
    if isinstance(device, int) and torch.cuda.is_available():
        try:
            device_label = f'cuda:{device}（{torch.cuda.get_device_name(device)}）'
        except Exception:
            pass

    _log(job, '======== 开始训练 ========')
    _log(job, f'设备：{device_label} | epochs={epochs} | batch={batch} | imgsz={imgsz} | patience={patience}')
    _log(job, f'优化：lr0={lr0} | workers={workers} | optimizer={train_kwargs.get("optimizer", "auto")}')
    _log(job, f'数据配置：{os.path.basename(str(data_path)) if not os.path.isdir(data_path) else data_path}')
    _log(job, f'输出目录：runs/job_{job.id}/{train_kwargs["name"]}')

    # 次要参数一行摘要（避免整 dict 刷屏，又保留可查）
    skip_keys = {
        'data', 'device', 'epochs', 'batch', 'imgsz', 'patience', 'workers',
        'lr0', 'optimizer', 'project', 'name', 'exist_ok',
    }
    extras = {k: train_kwargs[k] for k in sorted(train_kwargs) if k not in skip_keys}
    if extras:
        _log(job, f'其它训练参数：{extras}')

    model.train(**train_kwargs)

    if _is_stop_requested(job):
        raise TrainingStopped('训练已被用户停止')

    _log(job, '======== 训练结束，开始评估 ========')
    metrics = {}
    try:
        val_results = model.val()
        metrics = val_results.results_dict if val_results else {}
        if task_type == 'cls':
            _log(
                job,
                f'评估完成：acc@1={metrics.get("metrics/accuracy_top1", "N/A")}，'
                f'acc@5={metrics.get("metrics/accuracy_top5", "N/A")}',
            )
        else:
            _log(
                job,
                f'评估完成：mAP50={metrics.get("metrics/mAP50(B)", "N/A")}，'
                f'mAP50-95={metrics.get("metrics/mAP50-95(B)", "N/A")}，'
                f'P={metrics.get("metrics/precision(B)", "N/A")}，'
                f'R={metrics.get("metrics/recall(B)", "N/A")}',
            )
    except Exception as e:
        _log(job, f'评估失败（不影响模型保存）：{e}', level='WARNING')

    version = datetime.now().strftime('%Y%m%d%H%M%S')
    save_dir = os.path.join(_CV_ULTRA, 'trained_models', f'model_v{version}')
    os.makedirs(save_dir, exist_ok=True)

    # 优先保存 Ultralytics 产出的 best.pt / last.pt（而不是只 save 当前内存权重）
    trainer = getattr(model, 'trainer', None)
    saved_models = []  # (name, path, variant)

    def _copy_weight(src, dest_name, variant):
        if not src:
            return None
        src_path = str(src)
        if not os.path.isfile(src_path):
            return None
        dest = os.path.join(save_dir, dest_name)
        shutil.copy2(src_path, dest)
        return dest_name, dest, variant

    _log(job, '======== 保存产物 ========')
    if trainer is not None:
        best_src = getattr(trainer, 'best', None)
        last_src = getattr(trainer, 'last', None)
        for src, name, variant in (
            (best_src, 'best.pt', 'best'),
            (last_src, 'last.pt', 'last'),
        ):
            copied = _copy_weight(src, name, variant)
            if copied:
                saved_models.append(copied)
                try:
                    size_mb = round(os.path.getsize(copied[1]) / (1024 * 1024), 1)
                except OSError:
                    size_mb = '?'
                _log(job, f'已保存 {copied[0]}（{size_mb} MB）')

    # 兜底：若 trainer 无 best/last，再保存当前 model
    if not saved_models:
        model_path = os.path.join(save_dir, 'model.pt')
        model.save(model_path)
        saved_models.append(('model.pt', model_path, 'model'))
        _log(job, '未找到 best/last，已保存当前权重：model.pt')
    elif not any(v == 'best' for _, _, v in saved_models):
        _log(job, '未找到 best.pt（可能未完成有效验证），仅提供 last', level='WARNING')

    _log(job, f'模型目录：model_v{version}，产出={[n for n, _, _ in saved_models]}')

    artifacts = {}
    try:
        trainer_dir = getattr(trainer, 'save_dir', None) if trainer else None
        if trainer_dir:
            for plot_name in ('F1_curve.png', 'PR_curve.png', 'results.png', 'confusion_matrix.png'):
                src = os.path.join(str(trainer_dir), plot_name)
                if os.path.isfile(src):
                    dest = os.path.join(save_dir, plot_name)
                    shutil.copy2(src, dest)
                    key = plot_name.rsplit('.', 1)[0]
                    artifacts[key] = dest
                    _log(job, f'已保存训练曲线：{plot_name}')
        if not artifacts.get('F1_curve') and task_type != 'cls':
            _log(job, '未找到 F1_curve.png（可能未生成评估曲线）', level='WARNING')
    except Exception as e:
        _log(job, f'保存训练曲线失败：{e}', level='WARNING')

    from .models import TrainedModel
    _close_db()
    # best 优先写入（列表展示更靠前时配合 ordering 也可按名称）
    for name, path, variant in sorted(saved_models, key=lambda x: 0 if x[2] == 'best' else 1):
        TrainedModel.objects.create(
            job=job,
            name=name,
            file_path=path,
            file_size=os.path.getsize(path),
            metrics={**(metrics or {}), 'variant': variant},
        )

    # 记录可清理路径：删除任务时一并去掉 runs / trained_models
    trainer_save = None
    if trainer is not None:
        trainer_save = getattr(trainer, 'save_dir', None)
    artifacts['runs_dir'] = runs_root
    if trainer_save:
        artifacts['ultralytics_save_dir'] = str(trainer_save)
    artifacts['trained_dir'] = save_dir

    job.result = metrics
    job.artifacts = artifacts
    job.save(update_fields=['result', 'artifacts', 'updated_at'])

    return save_dir
