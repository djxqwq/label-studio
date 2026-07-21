"""训练超参定义：默认值 + 中英文标签（供前后端共用约定）"""

# 传给 ultralytics model.train() 的参数（不含 data/model 路径）
DEFAULT_TRAIN_PARAMS = {
    # 基础训练
    'epochs': 1000,
    'patience': 200,
    'batch': 16,
    'imgsz': 640,
    'device': '0',
    'workers': 8,
    'seed': 0,
    'pretrained': True,
    'optimizer': 'auto',
    'cos_lr': False,
    'amp': True,
    'close_mosaic': 10,
    'fraction': 1.0,
    'deterministic': True,
    'single_cls': False,
    'rect': False,
    'multi_scale': False,
    'save_period': -1,
    'cache': False,
    'plots': True,
    'val': True,
    # 学习率 / 优化
    'lr0': 0.01,
    'lrf': 0.01,
    'momentum': 0.937,
    'weight_decay': 0.0005,
    'warmup_epochs': 3.0,
    'warmup_momentum': 0.8,
    'warmup_bias_lr': 0.1,
    'box': 7.5,
    'cls': 0.5,
    'dfl': 1.5,
    'label_smoothing': 0.0,
    'nbs': 64,
    'dropout': 0.0,
    # 数据增强
    'hsv_h': 0.015,
    'hsv_s': 0.7,
    'hsv_v': 0.4,
    'degrees': 0.0,
    'translate': 0.1,
    'scale': 0.5,
    'shear': 0.0,
    'perspective': 0.0,
    'flipud': 0.0,
    'fliplr': 0.5,
    'bgr': 0.0,
    'mosaic': 1.0,
    'mixup': 0.0,
    'copy_paste': 0.0,
    'erasing': 0.4,
    'crop_fraction': 1.0,
    # 分割
    'overlap_mask': True,
    'mask_ratio': 4,
}

# 不允许通过 API 覆盖的 train() 键
BLOCKED_TRAIN_KEYS = {
    'data', 'model', 'project', 'name', 'exist_ok', 'resume', 'cfg',
    'source', 'tracker', 'format', 'keras', 'optimize', 'int8', 'dynamic',
    'simplify', 'opset', 'workspace', 'nms',
}


def merge_train_params(*sources):
    """从左到右合并，后面覆盖前面；过滤非法键"""
    merged = dict(DEFAULT_TRAIN_PARAMS)
    for src in sources:
        if not isinstance(src, dict):
            continue
        for key, value in src.items():
            if key in BLOCKED_TRAIN_KEYS:
                continue
            if key in DEFAULT_TRAIN_PARAMS or key in ('device',):
                merged[key] = value
    return merged


def extract_train_params_from_config(config):
    """从 ModelConfig 组装完整 train_params"""
    base = {}
    if getattr(config, 'train_params', None):
        base.update(config.train_params or {})
    # 兼容旧字段
    for key in ('epochs', 'batch', 'patience', 'imgsz', 'device'):
        val = getattr(config, key, None)
        if val is not None and key not in base:
            base[key] = val
    return merge_train_params(base)
