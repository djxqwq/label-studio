"""Django 训练后台任务 —— 直接调 cv-ultralytics 现有脚本"""
import os
import sys
import random
import shutil

_BASE = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
_CV_ULTRA = os.environ.get('CV_ULTRA_PATH', os.path.join(_BASE, 'cv-ultralytics'))
_ULTRA_SRC = os.path.join(_CV_ULTRA, 'ultralytics')
if _ULTRA_SRC not in sys.path:
    sys.path.insert(0, _ULTRA_SRC)

_PROJ_ROOT = os.path.join(_CV_ULTRA, 'ultralytics', 'ultralytics')


def _log(job, message, level='INFO'):
    """写入训练日志到 DB"""
    from .models import TrainingLog
    TrainingLog.objects.create(job=job, level=level, message=message)


def _progress(job, current_epoch, total_epochs):
    job.current_epoch = current_epoch
    job.total_epochs = total_epochs
    job.progress = int(current_epoch / total_epochs * 100) if total_epochs else 0
    job.save()


def build_dataset(export_dir: str, dataset_name: str, task_type: str, classes: list):
    """
    调用 group_img.py 的逻辑来划分数据集 + 自动生成 data.yaml
    """
    # 导入 group_img 模块
    _datasets_process = os.path.join(_CV_ULTRA, 'datasets_process', 'utils')
    if _datasets_process not in sys.path:
        sys.path.insert(0, _datasets_process)

    from group_img import log as group_log

    dst = os.path.join(_CV_ULTRA, 'datasets', dataset_name, task_type)
    group_log.info(f"========== 数据集分割开始 ==========")
    group_log.info(f"源数据目录：{export_dir}")
    group_log.info(f"目标数据目录：{dst}")

    # 定义数据集的比例
    train_ratio = 0.8
    valid_ratio = 0.15
    test_ratio = 0.05

    group_log.info(f"分割比例 -> 训练集：{train_ratio}  验证集：{valid_ratio}  测试集：{test_ratio}")

    # 获取所有图像文件和标签文件的列表
    src_img = os.path.join(export_dir, 'images')
    src_lbl = os.path.join(export_dir, 'labels')

    # 如果直接路径不存在，尝试找子目录
    if not os.path.isdir(src_img):
        for item in os.listdir(export_dir):
            p = os.path.join(export_dir, item)
            if os.path.isdir(p) and os.path.isdir(os.path.join(p, 'images')):
                src_img = os.path.join(p, 'images')
                src_lbl = os.path.join(p, 'labels')
                break

    if not os.path.isdir(src_img) or not os.path.isdir(src_lbl):
        raise FileNotFoundError(f'导出数据不完整：images={os.path.isdir(src_img)}, labels={os.path.isdir(src_lbl)}')

    images = [f for f in os.listdir(src_img) if f.lower().endswith(('.jpg', '.jpeg', '.png'))]
    labels = [f for f in os.listdir(src_lbl) if f.endswith('.txt')]

    group_log.info("---------- 原始数据统计 ----------")
    group_log.info(f"图像文件总数：{len(images)}")
    group_log.info(f"标签文件总数：{len(labels)}")

    # 创建一个字典来存储图像和对应的标签文件
    data_dict = {}
    skipped = []
    for img in images:
        base_name = os.path.splitext(img)[0]
        txt_file = base_name + '.txt'
        if txt_file in labels:
            data_dict[img] = txt_file
        else:
            skipped.append(img)
            group_log.warning(f"跳过无对应标签文件的图像：{img}")

    group_log.info(f"成功配对图像 - 标签数：{len(data_dict)}")
    group_log.info(f"因缺少标签而跳过的图像数：{len(skipped)}")

    # 将图像和标签文件配对
    data_pairs = list(data_dict.items())

    # 随机打乱数据集
    random.shuffle(data_pairs)
    group_log.info("数据集已随机打乱")

    # 计算每个数据集的大小（保证验证集至少有 1 张）
    total_data = len(data_pairs)
    train_size = int(total_data * train_ratio)
    valid_size = max(1, int(total_data * valid_ratio))  # 保证验证集至少 1 张
    test_size = total_data - train_size - valid_size

    # 如果测试集为负数，从训练集借
    if test_size < 0:
        train_size += test_size
        test_size = 0

    group_log.info("---------- 分组统计 ----------")
    group_log.info(f"数据集总量：{total_data}")
    group_log.info(f"训练集数量：{train_size}（{train_size / total_data * 100:.1f}%）")
    group_log.info(f"验证集数量：{valid_size}（{valid_size / total_data * 100:.1f}%）")
    group_log.info(f"测试集数量：{test_size}（{test_size / total_data * 100:.1f}%）")

    # 分割数据集
    train_data = data_pairs[:train_size]
    valid_data = data_pairs[train_size:train_size + valid_size]
    test_data = data_pairs[train_size + valid_size:]

    # 清空目标目录
    group_log.info("---------- 准备目标目录 ----------")
    if os.path.exists(dst):
        group_log.info(f"目标目录已存在，正在清空：{dst}")
        shutil.rmtree(dst)
        os.makedirs(dst)
        group_log.info(f"目标目录已重建：{dst}")
    else:
        group_log.info(f"目标目录不存在，正在创建：{dst}")
        os.makedirs(dst)

    # 创建目标目录
    for phase in ['train', 'valid', 'test']:
        img_dir = os.path.join(dst, phase, 'images')
        lbl_dir = os.path.join(dst, phase, 'labels')
        os.makedirs(img_dir, exist_ok=True)
        os.makedirs(lbl_dir, exist_ok=True)
        group_log.info(f"已创建目录：{img_dir}")
        group_log.info(f"已创建目录：{lbl_dir}")

    # 复制文件到目标目录
    group_log.info("---------- 开始复制文件 ----------")
    phase_map = [('train', train_data), ('valid', valid_data), ('test', test_data)]
    for phase, data in phase_map:
        group_log.info(f"[{phase}] 开始复制，共 {len(data)} 条样本")
        for img, label in data:
            img_src = os.path.join(src_img, img)
            label_src = os.path.join(src_lbl, label)
            img_dst = os.path.join(dst, phase, 'images', img)
            label_dst = os.path.join(dst, phase, 'labels', label)
            shutil.copy2(img_src, img_dst)
            shutil.copy2(label_src, label_dst)
        group_log.info(f"[{phase}] 复制完成")

    group_log.info("========== 数据集分割完成 ==========")

    # 自动生成 data.yaml（路径统一用正斜杠，跨平台兼容）
    yaml_path = os.path.join(_PROJ_ROOT, 'cfg', 'datasets', f'{dataset_name}.yaml')
    dst_safe = dst.replace('\\', '/')
    content = f"""# Auto-generated by Training Service
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

    group_log.info(f"data.yaml 已生成：{yaml_path}")

    return True


def _download_model_weights(model_name: str, dest_dir: str) -> str:
    """
    下载预训练权重，优先从本地和镜像下载。
    返回权重文件路径，失败抛 RuntimeError。
    """
    import requests
    from pathlib import Path

    dest_path = Path(dest_dir) / f'{model_name}.pt'
    if dest_path.exists():
        return str(dest_path)

    # 下载源优先级：官方 CDN > 镜像 > GitHub 直连
    base_url = f'https://github.com/ultralytics/assets/releases/download/v8.2.0/{model_name}.pt'
    mirrors = [
        f'https://ultralytics.com/assets/{model_name}.pt',  # 官方 CDN
        f'https://ghproxy.net/{base_url}',
        f'https://gh-proxy.cn/{base_url}',
        f'https://gh.ddlc.top/{base_url}',
        base_url,  # 最后尝试直连
    ]

    last_error = None
    for url in mirrors:
        try:
            resp = requests.get(url, timeout=30, stream=True)
            if resp.status_code == 200:
                total = int(resp.headers.get('content-length', 0))
                with open(dest_path, 'wb') as f:
                    for chunk in resp.iter_content(chunk_size=8192):
                        f.write(chunk)
                # 校验文件大小（权重文件至少 1MB）
                if dest_path.stat().st_size > 1_000_000:
                    return str(dest_path)
                else:
                    dest_path.unlink(missing_ok=True)
        except Exception as e:
            last_error = e
            continue

    raise RuntimeError(
        f'无法下载 {model_name}.pt，已尝试 {len(mirrors)} 个源。\n'
        f'请手动下载后放到 {dest_dir} 目录下。\n'
        f'下载地址：{base_url}\n'
        f'最后错误：{last_error}'
    )


def run_training(job, model_yaml: str, model_pt: str, data_yaml: str, **params):
    """直接调 YOLO model.train()，写进度和日志到 DB"""
    from ultralytics import YOLO
    from ultralytics.utils import SETTINGS
    from datetime import datetime
    import os as os_mod

    epochs = params.get('epochs', 1000)

    _models_dir = os.path.join(_PROJ_ROOT, 'models')
    os.makedirs(_models_dir, exist_ok=True)
    SETTINGS['weights_dir'] = _models_dir

    _log(job, f'权重目录：{_models_dir}')
    _log(job, f'目录内容：{os.listdir(_models_dir) if os.path.exists(_models_dir) else "不存在"}')

    model_yaml_path = os.path.join(_PROJ_ROOT, 'cfg', 'models', 'v8', f'{model_yaml}.yaml')
    model_pt_path = os.path.join(_models_dir, f'{model_pt}.pt')

    _log(job, f'加载模型：{model_yaml} / {model_pt}')
    _log(job, f'权重路径：{model_pt_path}')

    if os.path.exists(model_pt_path):
        _log(job, f'使用本地权重：{model_pt_path}')
        model = YOLO(model_yaml_path).load(model_pt_path)
    else:
        _log(job, f'本地权重不存在，尝试下载 {model_pt}.pt ...')
        try:
            downloaded = _download_model_weights(model_pt, _models_dir)
            _log(job, f'下载成功：{downloaded}')
            model = YOLO(model_yaml_path).load(downloaded)
        except RuntimeError:
            _log(job, f'镜像下载失败，回退到 YOLO 自带下载 ...')
            model = YOLO(f'{model_pt}.pt')

    data_path = os.path.join(_PROJ_ROOT, 'cfg', 'datasets', f'{data_yaml}.yaml')
    _log(job, f'开始训练，epochs={epochs}, batch={params.get("batch", 16)}')

    # 添加进度回调（使用 callback 机制）
    def _epoch_callback(trainer):
        if hasattr(trainer, 'epoch') and trainer.epoch is not None:
            _progress(job, trainer.epoch + 1, epochs)
            _log(job, f'Epoch {trainer.epoch + 1}/{epochs}')

    model.add_callback("on_train_epoch_end", _epoch_callback)

    # 自动检测 GPU：有 CUDA 用 GPU，没有用 CPU
    import torch
    device = params.get('device', 'auto')
    # 如果配置了 GPU 但没有 CUDA，自动回退到 CPU
    if device != 'cpu' and not torch.cuda.is_available():
        device = 'cpu'
        _log(job, f'CUDA 不可用，使用 CPU 训练')
    elif device == 'auto':
        device = 0 if torch.cuda.is_available() else 'cpu'
        _log(job, f'自动选择设备：{device}')

    results = model.train(
        data=data_path,
        epochs=epochs,
        batch=params.get('batch', 16),
        patience=params.get('patience', 200),
        imgsz=params.get('imgsz', 640),
        device=device,
        pretrained=True,
        plots=True,
    )

    _log(job, '训练完成，开始评估...')
    val_results = model.val()
    metrics = val_results.results_dict if val_results else {}

    # 保存模型
    version = datetime.now().strftime('%Y%m%d%H%M%S')
    save_dir = os.path.join(_CV_ULTRA, 'trained_models', f'model_v{version}')
    os.makedirs(save_dir, exist_ok=True)
    model_path = os.path.join(save_dir, 'model.pt')
    model.save(model_path)

    _log(job, f'模型已保存：model_v{version}')
    _log(job, f'指标：mAP50={metrics.get("metrics/mAP50(B)", "N/A")}')

    # 记录到 DB
    from .models import TrainedModel
    TrainedModel.objects.create(
        job=job,
        name=f'model_v{version}.pt',
        file_path=model_path,
        file_size=os_mod.path.getsize(model_path),
        metrics=metrics,
    )
    job.result = metrics
    job.save()

    return save_dir
