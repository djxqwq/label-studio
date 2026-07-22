"""YOLO 预训练权重：本地扫描、命名规则、国内镜像下载"""
import logging
import os
import tempfile
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

logger = logging.getLogger(__name__)

_BASE = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
_CV_ULTRA = os.environ.get('CV_ULTRA_PATH', os.path.join(_BASE, 'cv-ultralytics'))
_MODELS_DIR = os.path.join(_CV_ULTRA, 'ultralytics', 'ultralytics', 'models')

# 官方 release tag（权重文件名稳定）
GITHUB_RELEASE = os.environ.get('YOLO_WEIGHTS_RELEASE', 'v8.2.0')

YOLO_VERSIONS = ['8']
YOLO_SCALES = [
    {'value': 'n', 'label': 'n (nano，最快最小)'},
    {'value': 's', 'label': 's (small)'},
    {'value': 'm', 'label': 'm (medium)'},
    {'value': 'l', 'label': 'l (large)'},
    {'value': 'x', 'label': 'x (xlarge，精度优先)'},
]

# task_type → 权重名后缀（detect 无后缀）
TASK_SUFFIX = {
    'detect': '',
    'obb': '-obb',
    'seg': '-seg',
    'cls': '-cls',
}


def models_dir() -> str:
    return os.environ.get('YOLO_MODELS_DIR', _MODELS_DIR)


def build_weight_stem(version: str, scale: str, task_type: str) -> str:
    """yolov8x-obb / yolov8n / yolov8s-seg ..."""
    ver = str(version or '8').lstrip('vV')
    sc = (scale or 'x').lower()
    if sc not in {s['value'] for s in YOLO_SCALES}:
        sc = 'x'
    suffix = TASK_SUFFIX.get(task_type or 'detect', '')
    return f'yolov{ver}{sc}{suffix}'


def build_model_names(version: str, scale: str, task_type: str) -> dict:
    stem = build_weight_stem(version, scale, task_type)
    # yaml：Ultralytics 接受 yolov8x-obb.yaml 这种带尺度名；基座文件为 yolov8-obb.yaml
    return {
        'stem': stem,
        'model_pt': stem,
        'model_yaml': stem,
        'filename': f'{stem}.pt',
    }


def list_local_weights():
    """扫描本地已有 .pt"""
    root = Path(models_dir())
    items = []
    if not root.is_dir():
        return items
    for p in sorted(root.glob('*.pt')):
        try:
            size = p.stat().st_size
        except OSError:
            continue
        if size < 100_000:
            continue
        items.append({
            'name': p.stem,
            'filename': p.name,
            'path': str(p),
            'size': size,
            'size_mb': round(size / (1024 * 1024), 2),
            'local': True,
        })
    return items


def weight_catalog(task_type: str = 'obb', version: str = '8'):
    """某任务下可选的全部尺度（含是否本地存在）"""
    local = {w['name']: w for w in list_local_weights()}
    options = []
    for s in YOLO_SCALES:
        names = build_model_names(version, s['value'], task_type)
        stem = names['stem']
        loc = local.get(stem)
        options.append({
            'version': version,
            'scale': s['value'],
            'scale_label': s['label'],
            'task_type': task_type,
            'stem': stem,
            'model_pt': names['model_pt'],
            'model_yaml': names['model_yaml'],
            'filename': names['filename'],
            'local': bool(loc),
            'size_mb': loc['size_mb'] if loc else None,
            'path': loc['path'] if loc else None,
        })
    return options


def weights_api_payload(task_type: str = 'obb', version: str = '8'):
    return {
        'versions': YOLO_VERSIONS,
        'scales': YOLO_SCALES,
        'task_types': list(TASK_SUFFIX.keys()),
        'models_dir': models_dir(),
        'local': list_local_weights(),
        'options': weight_catalog(task_type=task_type, version=version),
        'mirrors_hint': [
            'https://ghfast.top/…（GitHub 加速，实测可用）',
            'https://hf-mirror.com/Ultralytics/YOLOv8/…（HF 国内镜像，实测可用）',
        ],
    }


def weight_mirror_urls(model_name: str):
    """国内可直连优先的镜像列表（可用 YOLO_WEIGHTS_MIRRORS 覆盖）。

    实测（无需 VPN）：
    - ghfast.top 代理 GitHub releases
    - hf-mirror.com 的 Ultralytics/YOLOv8
    """
    filename = f'{model_name}.pt' if not str(model_name).endswith('.pt') else model_name
    stem = filename[:-3] if filename.endswith('.pt') else model_name
    github = (
        f'https://github.com/ultralytics/assets/releases/download/'
        f'{GITHUB_RELEASE}/{filename}'
    )
    custom = os.environ.get('YOLO_WEIGHTS_MIRRORS', '').strip()
    if custom:
        urls = []
        for tmpl in custom.split(','):
            tmpl = tmpl.strip()
            if not tmpl:
                continue
            urls.append(
                tmpl.replace('{name}', stem)
                .replace('{file}', filename)
                .replace('{github}', github)
            )
        return urls

    return [
        # 实测可用、国内无需 VPN（按响应速度大致排序）
        f'https://gh-proxy.com/{github}',
        f'https://ghfast.top/{github}',
        f'https://ghproxy.net/{github}',
        f'https://hf-mirror.com/Ultralytics/YOLOv8/resolve/main/{filename}',
        f'https://edgeone.gh-proxy.com/{github}',
        f'https://mirror.ghproxy.com/{github}',
        # 官方兜底
        f'https://ultralytics.com/assets/{filename}',
        f'https://huggingface.co/Ultralytics/YOLOv8/resolve/main/{filename}',
        github,
    ]


def download_model_weights(model_name: str, dest_dir: str = None, log_fn=None) -> str:
    """本地有则直接返回；否则多镜像并行竞速下载。"""
    import requests

    dest_dir = dest_dir or models_dir()
    stem = model_name[:-3] if str(model_name).endswith('.pt') else model_name
    dest_path = Path(dest_dir) / f'{stem}.pt'
    if dest_path.exists() and dest_path.stat().st_size > 1_000_000:
        if log_fn:
            log_fn(f'本地已有权重，跳过下载：{dest_path}')
        return str(dest_path)

    os.makedirs(dest_dir, exist_ok=True)
    mirrors = weight_mirror_urls(stem)
    stop_event = threading.Event()
    errors = []
    min_bytes = 1_000_000

    def _one(url):
        if stop_event.is_set():
            return None
        tmp = None
        try:
            if log_fn:
                log_fn(f'尝试下载：{url[:100]}...')
            with requests.get(url, timeout=(6, 180), stream=True, allow_redirects=True) as resp:
                if resp.status_code != 200:
                    raise RuntimeError(f'HTTP {resp.status_code}')
                fd, tmp = tempfile.mkstemp(suffix='.pt', dir=dest_dir)
                os.close(fd)
                size = 0
                with open(tmp, 'wb') as f:
                    for chunk in resp.iter_content(chunk_size=1024 * 512):
                        if stop_event.is_set():
                            raise RuntimeError('cancelled')
                        if chunk:
                            f.write(chunk)
                            size += len(chunk)
                if size < min_bytes:
                    raise RuntimeError(f'file too small ({size} bytes)')
                return tmp, url, size
        except Exception as e:
            errors.append(f'{url}: {e}')
            if tmp and os.path.exists(tmp):
                try:
                    os.remove(tmp)
                except OSError:
                    pass
            return None

    winners = []
    with ThreadPoolExecutor(max_workers=min(5, len(mirrors))) as pool:
        futures = [pool.submit(_one, u) for u in mirrors]
        for fut in as_completed(futures):
            result = fut.result()
            if result:
                stop_event.set()
                winners.append(result)
                break

    if not winners:
        raise RuntimeError(
            f'无法下载 {stem}.pt，已尝试 {len(mirrors)} 个源。\n'
            f'可设置 YOLO_WEIGHTS_MIRRORS，或手动放到 {dest_dir}\n'
            f'推荐手动：https://ghfast.top/{weight_mirror_urls(stem)[-1] if False else "https://github.com/ultralytics/assets/releases/download/" + GITHUB_RELEASE + "/" + stem + ".pt"}\n'
            f'或：https://hf-mirror.com/Ultralytics/YOLOv8/resolve/main/{stem}.pt\n'
            f'错误摘要：{errors[:4]}'
        )

    tmp, url, size = winners[0]
    if dest_path.exists():
        dest_path.unlink(missing_ok=True)
    os.replace(tmp, dest_path)
    if log_fn:
        log_fn(f'下载成功（{round(size / 1024 / 1024, 1)} MB）：{url}')
    logger.info('downloaded %s from %s (%s bytes)', dest_path, url, size)
    return str(dest_path)
