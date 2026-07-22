"""YOLO 预训练权重：多版本目录、本地扫描、国内镜像下载"""
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

# 官方 release：latest/download 可拿到各版本权重；也可用 YOLO_WEIGHTS_RELEASE=v8.3.0 固定
GITHUB_RELEASE = os.environ.get('YOLO_WEIGHTS_RELEASE', 'latest')

# 与当前 vendored Ultralytics（约 8.x）对齐的可用家族：
# - v5：detect（权重名 yolov5{n}u.pt）
# - v8：detect/obb/seg/cls（yolov8{n}[-obb|-seg|-cls].pt）
# - v9：detect(t/s/m/c/e)；seg 仅 c/e；无 obb/cls
# - v10：detect(n/s/m/b/l/x)；无 obb/seg/cls
YOLO_FAMILIES = {
    '5': {
        'value': '5',
        'label': 'YOLOv5',
        'default_scale': 'x',
        'scales': [
            {'value': 'n', 'label': 'n (nano)'},
            {'value': 's', 'label': 's (small)'},
            {'value': 'm', 'label': 'm (medium)'},
            {'value': 'l', 'label': 'l (large)'},
            {'value': 'x', 'label': 'x (xlarge)'},
        ],
        'tasks': {
            'detect': ['n', 's', 'm', 'l', 'x'],
        },
        # Ultralytics 重写版权重带 u 后缀
        'stem': lambda scale, suffix: f'yolov5{scale}u',
    },
    '8': {
        'value': '8',
        'label': 'YOLOv8',
        'default_scale': 'x',
        'scales': [
            {'value': 'n', 'label': 'n (nano，最快最小)'},
            {'value': 's', 'label': 's (small)'},
            {'value': 'm', 'label': 'm (medium)'},
            {'value': 'l', 'label': 'l (large)'},
            {'value': 'x', 'label': 'x (xlarge，精度优先)'},
        ],
        'tasks': {
            'detect': ['n', 's', 'm', 'l', 'x'],
            'obb': ['n', 's', 'm', 'l', 'x'],
            'seg': ['n', 's', 'm', 'l', 'x'],
            'cls': ['n', 's', 'm', 'l', 'x'],
        },
        'stem': lambda scale, suffix: f'yolov8{scale}{suffix}',
    },
    '9': {
        'value': '9',
        'label': 'YOLOv9',
        'default_scale': 'c',
        'scales': [
            {'value': 't', 'label': 't (tiny)'},
            {'value': 's', 'label': 's (small)'},
            {'value': 'm', 'label': 'm (medium)'},
            {'value': 'c', 'label': 'c (compact，常用)'},
            {'value': 'e', 'label': 'e (extended，更大)'},
        ],
        'tasks': {
            'detect': ['t', 's', 'm', 'c', 'e'],
            'seg': ['c', 'e'],
        },
        'stem': lambda scale, suffix: f'yolov9{scale}{suffix}',
    },
    '10': {
        'value': '10',
        'label': 'YOLOv10',
        'default_scale': 'x',
        'scales': [
            {'value': 'n', 'label': 'n (nano)'},
            {'value': 's', 'label': 's (small)'},
            {'value': 'm', 'label': 'm (medium)'},
            {'value': 'b', 'label': 'b (balanced)'},
            {'value': 'l', 'label': 'l (large)'},
            {'value': 'x', 'label': 'x (xlarge)'},
        ],
        'tasks': {
            'detect': ['n', 's', 'm', 'b', 'l', 'x'],
        },
        'stem': lambda scale, suffix: f'yolov10{scale}',
    },
}

TASK_SUFFIX = {
    'detect': '',
    'obb': '-obb',
    'seg': '-seg',
    'cls': '-cls',
}

# 兼容旧常量
YOLO_VERSIONS = list(YOLO_FAMILIES.keys())
YOLO_SCALES = YOLO_FAMILIES['8']['scales']


def models_dir() -> str:
    return os.environ.get('YOLO_MODELS_DIR', _MODELS_DIR)


def get_family(version: str) -> dict:
    ver = str(version or '8').lstrip('vV')
    return YOLO_FAMILIES.get(ver) or YOLO_FAMILIES['8']


def versions_for_task(task_type: str):
    """某任务类型下可选的 YOLO 版本（过滤不支持的家族）。"""
    task = (task_type or 'detect').lower()
    out = []
    for fam in YOLO_FAMILIES.values():
        if task in fam['tasks']:
            out.append({
                'value': fam['value'],
                'label': fam['label'],
                'default_scale': fam['default_scale'],
            })
    return out or [{'value': '8', 'label': 'YOLOv8', 'default_scale': 'x'}]


def scales_for(version: str, task_type: str):
    fam = get_family(version)
    task = (task_type or 'detect').lower()
    allowed = fam['tasks'].get(task) or fam['tasks'].get('detect') or []
    return [s for s in fam['scales'] if s['value'] in allowed]


def build_weight_stem(version: str, scale: str, task_type: str) -> str:
    """yolov8x-obb / yolov5xu / yolov9c-seg / yolov10x ..."""
    fam = get_family(version)
    task = (task_type or 'detect').lower()
    allowed = set(fam['tasks'].get(task) or [])
    sc = (scale or fam['default_scale']).lower()
    if sc not in allowed:
        sc = fam['default_scale'] if fam['default_scale'] in allowed else (next(iter(allowed), 'n'))
    # v10 无任务后缀；v5 的 stem 函数忽略 suffix；其余按 task 加后缀
    suffix = '' if fam['value'] in ('5', '10') else TASK_SUFFIX.get(task, '')
    if fam['value'] == '9' and task == 'detect':
        suffix = ''
    return fam['stem'](sc, suffix)


def build_model_names(version: str, scale: str, task_type: str) -> dict:
    stem = build_weight_stem(version, scale, task_type)
    return {
        'stem': stem,
        'model_pt': stem,
        'model_yaml': stem,
        'filename': f'{stem}.pt',
        'version': get_family(version)['value'],
        'scale': scale,
        'task_type': task_type,
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
    """某任务 + 版本下可选的全部尺度（含是否本地存在）"""
    local = {w['name']: w for w in list_local_weights()}
    fam = get_family(version)
    task = (task_type or 'detect').lower()
    # 该版本不支持此任务时回退到 v8（若 v8 支持）或第一个可用版本
    if task not in fam['tasks']:
        for fallback in versions_for_task(task):
            fam = get_family(fallback['value'])
            version = fam['value']
            break
    options = []
    for s in scales_for(version, task):
        names = build_model_names(version, s['value'], task)
        stem = names['stem']
        loc = local.get(stem)
        options.append({
            'version': fam['value'],
            'scale': s['value'],
            'scale_label': s['label'],
            'task_type': task,
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
    task = (task_type or 'obb').lower()
    versions = versions_for_task(task)
    ver_values = {v['value'] for v in versions}
    ver = str(version or '8').lstrip('vV')
    if ver not in ver_values:
        ver = versions[0]['value'] if versions else '8'
    fam = get_family(ver)
    return {
        'versions': versions,
        'version': ver,
        'scales': scales_for(ver, task),
        'default_scale': fam['default_scale'],
        'task_types': list(TASK_SUFFIX.keys()),
        'task_type': task,
        'models_dir': models_dir(),
        'local': list_local_weights(),
        'options': weight_catalog(task_type=task, version=ver),
        'mirrors_hint': [
            'https://ghfast.top/…（GitHub 加速）',
            'https://hf-mirror.com/Ultralytics/YOLOv8/…（仅部分 v8 权重）',
        ],
        'notes': {
            '5': 'YOLOv5 仅 detect；权重名为 yolov5nu.pt 等形式',
            '8': 'YOLOv8 支持 detect / obb / seg / cls',
            '9': 'YOLOv9 支持 detect；seg 仅 c/e；无 obb/cls',
            '10': 'YOLOv10 仅 detect',
        },
    }


def weight_mirror_urls(model_name: str):
    """国内可直连优先的镜像列表（可用 YOLO_WEIGHTS_MIRRORS 覆盖）。"""
    filename = f'{model_name}.pt' if not str(model_name).endswith('.pt') else model_name
    stem = filename[:-3] if filename.endswith('.pt') else model_name
    if GITHUB_RELEASE == 'latest':
        github = f'https://github.com/ultralytics/assets/releases/latest/download/{filename}'
    else:
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

    urls = [
        f'https://gh-proxy.com/{github}',
        f'https://ghfast.top/{github}',
        f'https://ghproxy.net/{github}',
        f'https://edgeone.gh-proxy.com/{github}',
    ]
    # HF 镜像主要托管 YOLOv8 系列；其它版本仍放上作为附加尝试
    urls.append(f'https://hf-mirror.com/Ultralytics/YOLOv8/resolve/main/{filename}')
    urls.extend([
        f'https://ultralytics.com/assets/{filename}',
        f'https://huggingface.co/Ultralytics/YOLOv8/resolve/main/{filename}',
        github,
    ])
    return urls


def download_model_weights(model_name: str, dest_dir: str = None, log_fn=None) -> str:
    """本地有则直接返回；否则多镜像并行竞速下载，并向 log_fn 汇报进度（不刷每个镜像 URL）。"""
    import time
    import requests

    dest_dir = dest_dir or models_dir()
    stem = model_name[:-3] if str(model_name).endswith('.pt') else model_name
    dest_path = Path(dest_dir) / f'{stem}.pt'
    if dest_path.exists() and dest_path.stat().st_size > 1_000_000:
        if log_fn:
            log_fn(f'本地已有权重，跳过下载：{dest_path.name}')
        return str(dest_path)

    os.makedirs(dest_dir, exist_ok=True)
    mirrors = weight_mirror_urls(stem)
    stop_event = threading.Event()
    errors = []
    min_bytes = 1_000_000
    progress_lock = threading.Lock()
    # best_downloaded, last_log_ts, last_logged_mb
    progress_state = {'bytes': 0, 'total': 0, 'last_ts': 0.0, 'last_mb': -1.0}

    def _emit_progress(downloaded: int, total: int = 0):
        if not log_fn:
            return
        now = time.time()
        mb = downloaded / (1024 * 1024)
        with progress_lock:
            # 只跟踪当前领先的那一路，避免多镜像互相刷屏
            if downloaded < progress_state['bytes'] and not stop_event.is_set():
                return
            progress_state['bytes'] = max(progress_state['bytes'], downloaded)
            if total > 0:
                progress_state['total'] = total
            total = progress_state['total']
            # 至少间隔 1.5s，或每增加约 5MB 打一条
            if (
                mb - progress_state['last_mb'] < 5
                and now - progress_state['last_ts'] < 1.5
                and not (total > 0 and downloaded >= total)
            ):
                return
            progress_state['last_ts'] = now
            progress_state['last_mb'] = mb
            if total > 0:
                pct = min(99, int(downloaded * 100 / total))
                total_mb = total / (1024 * 1024)
                msg = f'下载进度：{pct}%（{mb:.1f}/{total_mb:.1f} MB）'
            else:
                msg = f'下载进度：已下载 {mb:.1f} MB'
        log_fn(msg)

    def _one(url):
        if stop_event.is_set():
            return None
        tmp = None
        try:
            logger.debug('weight mirror try: %s', url)
            with requests.get(url, timeout=(8, 180), stream=True, allow_redirects=True) as resp:
                if resp.status_code != 200:
                    raise RuntimeError(f'HTTP {resp.status_code}')
                total = int(resp.headers.get('Content-Length') or 0)
                fd, tmp = tempfile.mkstemp(suffix='.pt', dir=dest_dir)
                os.close(fd)
                size = 0
                with open(tmp, 'wb') as f:
                    for chunk in resp.iter_content(chunk_size=1024 * 256):
                        if stop_event.is_set():
                            raise RuntimeError('cancelled')
                        if chunk:
                            f.write(chunk)
                            size += len(chunk)
                            _emit_progress(size, total)
                if size < min_bytes:
                    raise RuntimeError(f'file too small ({size} bytes)')
                return tmp, url, size
        except Exception as e:
            errors.append(f'{url}: {e}')
            logger.debug('weight mirror fail %s: %s', url, e)
            if tmp and os.path.exists(tmp):
                try:
                    os.remove(tmp)
                except OSError:
                    pass
            return None

    if log_fn:
        log_fn(f'开始下载 {stem}.pt（多镜像竞速）…')

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
            f'推荐：https://ghfast.top/https://github.com/ultralytics/assets/releases/latest/download/{stem}.pt\n'
            f'错误摘要：{errors[:4]}'
        )

    tmp, url, size = winners[0]
    if dest_path.exists():
        dest_path.unlink(missing_ok=True)
    os.replace(tmp, dest_path)
    mb = round(size / 1024 / 1024, 1)
    if log_fn:
        # 完成时给 100%，只保留主机名，不刷完整镜像链
        host = url.split('/')[2] if '://' in url else url[:40]
        log_fn(f'下载完成：100%（{mb} MB）← {host}')
    logger.info('downloaded %s from %s (%s bytes)', dest_path, url, size)
    return str(dest_path)
