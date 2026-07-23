"""训练数据通道：共享盘 / SSH(SCP) / HTTP。

TRAINING_DATA_MODE=shared
  两边挂同一 mydata / cv-ultralytics（单机默认）。

TRAINING_DATA_MODE=ssh  （双机无共享盘时推荐）
  标注服导出后打 zip；训练服 scp 拉取 → 训练 → scp 回传 best.pt，并改 DB 路径。

TRAINING_DATA_MODE=http
  备选：走 HTTP 拉包/回传（需 TRAINING_WORKER_TOKEN）。
"""
from __future__ import annotations

import logging
import os
import shutil
import subprocess
import tempfile
import zipfile
from typing import Optional

logger = logging.getLogger(__name__)

_REMOTE_MODES = frozenset({'ssh', 'http'})


def data_mode() -> str:
    from django.conf import settings
    mode = (
        getattr(settings, 'TRAINING_DATA_MODE', None)
        or os.environ.get('TRAINING_DATA_MODE')
        or 'shared'
    ).lower().strip()
    if mode in ('shared', 'ssh', 'http'):
        return mode
    return 'shared'


def needs_packaging(mode: str = None) -> bool:
    return (mode or data_mode()) in _REMOTE_MODES


def worker_token() -> str:
    from django.conf import settings
    return (
        getattr(settings, 'TRAINING_WORKER_TOKEN', None)
        or os.environ.get('TRAINING_WORKER_TOKEN')
        or ''
    )


def annotation_base_url() -> str:
    from django.conf import settings
    return (
        getattr(settings, 'TRAINING_ANNOTATION_URL', None)
        or os.environ.get('TRAINING_ANNOTATION_URL')
        or getattr(settings, 'HOSTNAME', None)
        or os.environ.get('LABEL_STUDIO_HOST')
        or ''
    ).rstrip('/')


def ssh_config() -> dict:
    """训练服 SSH 到标注服宿主机的配置。"""
    from django.conf import settings

    def _g(name, default=''):
        return getattr(settings, name, None) or os.environ.get(name, default) or default

    return {
        'host': _g('TRAINING_SSH_HOST'),
        'user': _g('TRAINING_SSH_USER', 'root'),
        'port': int(_g('TRAINING_SSH_PORT', '22') or 22),
        'key': _g('TRAINING_SSH_KEY', ''),
        # 标注服宿主机上 mydata 目录（与 compose 卷 ./mydata 对应）
        'remote_data': _g('TRAINING_SSH_REMOTE_DATA', '').rstrip('/'),
        # 标注服容器内 DATA 路径（写入 DB，供下载 API 打开）
        'anno_data': _g('TRAINING_ANNOTATION_DATA_DIR', '/label-studio/data').rstrip('/'),
    }


def xfer_job_dir(job_id) -> str:
    from django.conf import settings
    root = os.path.join(settings.MEDIA_ROOT, 'training_xfer', f'job_{job_id}')
    os.makedirs(root, exist_ok=True)
    return root


def pack_export_for_transfer(job_id, export_dir, cleanup_dir=None, mode=None) -> dict:
    """把导出目录打成 zip，放到 MEDIA，供 Worker SSH/HTTP 拉取。"""
    if not export_dir or not os.path.isdir(export_dir):
        raise FileNotFoundError(f'导出目录不存在: {export_dir}')

    mode = mode or data_mode()
    dest_dir = xfer_job_dir(job_id)
    zip_path = os.path.join(dest_dir, 'export.zip')
    if os.path.isfile(zip_path):
        os.remove(zip_path)

    with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zf:
        for root, _, files in os.walk(export_dir):
            for name in files:
                full = os.path.join(root, name)
                arc = os.path.join('merged', os.path.relpath(full, export_dir))
                zf.write(full, arc.replace('\\', '/'))
        stats = None
        if cleanup_dir:
            candidate = os.path.join(cleanup_dir, 'export_stats.json')
            if os.path.isfile(candidate):
                stats = candidate
        if not stats:
            sibling = os.path.join(os.path.dirname(export_dir.rstrip('/\\')), 'export_stats.json')
            if os.path.isfile(sibling):
                stats = sibling
        if stats:
            zf.write(stats, 'export_stats.json')

    from django.conf import settings
    rel_from_media = os.path.relpath(zip_path, settings.MEDIA_ROOT).replace('\\', '/')
    size = os.path.getsize(zip_path)
    logger.info('packed export for job %s -> %s (%s bytes) mode=%s', job_id, zip_path, size, mode)
    return {
        'package_path': zip_path,
        'package_rel': rel_from_media,
        'package_size': size,
        'data_mode': mode,
    }


def _extract_package(zip_path: str, dest_root: str) -> str:
    if os.path.isdir(dest_root):
        shutil.rmtree(dest_root, ignore_errors=True)
    os.makedirs(dest_root, exist_ok=True)
    with zipfile.ZipFile(zip_path, 'r') as zf:
        zf.extractall(dest_root)
    merged = os.path.join(dest_root, 'merged')
    if os.path.isdir(merged):
        return merged
    return dest_root


def _ssh_base_cmd(cfg: dict) -> list:
    cmd = [
        'ssh',
        '-p', str(cfg['port']),
        '-o', 'StrictHostKeyChecking=accept-new',
        '-o', 'BatchMode=yes',
        '-o', 'ConnectTimeout=30',
    ]
    if cfg.get('key'):
        cmd.extend(['-i', cfg['key']])
    return cmd


def _scp_base_cmd(cfg: dict) -> list:
    cmd = [
        'scp',
        '-P', str(cfg['port']),
        '-o', 'StrictHostKeyChecking=accept-new',
        '-o', 'BatchMode=yes',
        '-o', 'ConnectTimeout=30',
    ]
    if cfg.get('key'):
        cmd.extend(['-i', cfg['key']])
    return cmd


def _run(cmd: list, log_fn=None, timeout=3600):
    def _log(msg):
        if log_fn:
            log_fn(msg)
        else:
            logger.info(msg)

    _log('$ ' + ' '.join(cmd[:8]) + (' ...' if len(cmd) > 8 else ''))
    try:
        proc = subprocess.run(
            cmd, capture_output=True, text=True, timeout=timeout, check=False,
        )
    except FileNotFoundError as e:
        raise RuntimeError(
            f'未找到命令 {cmd[0]}，请在训练服镜像/环境安装 openssh-client'
        ) from e
    if proc.returncode != 0:
        err = (proc.stderr or proc.stdout or '').strip()
        raise RuntimeError(f'命令失败 ({proc.returncode}): {err[:800]}')
    return proc


def _require_ssh(cfg: dict):
    if not cfg.get('host'):
        raise RuntimeError('TRAINING_DATA_MODE=ssh 需要配置 TRAINING_SSH_HOST')
    if not cfg.get('remote_data'):
        raise RuntimeError(
            'TRAINING_DATA_MODE=ssh 需要配置 TRAINING_SSH_REMOTE_DATA='
            '标注服宿主机上的 mydata 绝对路径（如 /opt/label-studio/mydata）'
        )


def remote_package_host_path(job_id, cfg: dict = None) -> str:
    cfg = cfg or ssh_config()
    return f"{cfg['remote_data']}/media/training_xfer/job_{job_id}/export.zip"


def remote_artifacts_host_dir(job_id, cfg: dict = None) -> str:
    cfg = cfg or ssh_config()
    return f"{cfg['remote_data']}/media/training_xfer/job_{job_id}/artifacts"


def annotation_artifact_container_path(job_id, filename: str, cfg: dict = None) -> str:
    """标注服容器内可读路径（写入 TrainedModel.file_path）。"""
    cfg = cfg or ssh_config()
    return f"{cfg['anno_data']}/media/training_xfer/job_{job_id}/artifacts/{filename}"


def pull_export_via_ssh(job_id, params=None, log_fn=None) -> str:
    """Worker：scp 标注服上的 export.zip 到本地并解压。"""
    def _log(msg):
        if log_fn:
            log_fn(msg)
        else:
            logger.info(msg)

    cfg = ssh_config()
    _require_ssh(cfg)
    remote = remote_package_host_path(job_id, cfg)
    # 允许 params 覆盖远程包路径
    if params and params.get('package_rel'):
        remote = f"{cfg['remote_data']}/media/{params['package_rel']}"

    dest_root = tempfile.mkdtemp(prefix=f'ls_train_ssh_{job_id}_')
    zip_path = os.path.join(dest_root, 'export.zip')
    target = f"{cfg['user']}@{cfg['host']}:{remote}"
    _log(f'SSH 拉取导出包：{target}')
    _run(_scp_base_cmd(cfg) + [target, zip_path], log_fn=log_fn, timeout=3600)
    size_mb = round(os.path.getsize(zip_path) / (1024 * 1024), 1)
    _log(f'导出包已拉取（{size_mb} MB），开始解压')
    return _extract_package(zip_path, os.path.join(dest_root, 'data'))


def pull_export_package_http(job_id, params, log_fn=None) -> str:
    """Worker：HTTP 拉取（备选）。"""
    import urllib.request

    def _log(msg):
        if log_fn:
            log_fn(msg)
        else:
            logger.info(msg)

    base = annotation_base_url()
    token = worker_token()
    if not base:
        raise RuntimeError('TRAINING_DATA_MODE=http 需配置 TRAINING_ANNOTATION_URL')
    if not token:
        raise RuntimeError('TRAINING_DATA_MODE=http 需配置 TRAINING_WORKER_TOKEN')

    url = f'{base}/api/train/jobs/{job_id}/package'
    _log(f'HTTP 拉取导出包：{url}')
    req = urllib.request.Request(url, headers={'X-Training-Token': token})
    dest_root = tempfile.mkdtemp(prefix=f'ls_train_pull_{job_id}_')
    zip_path = os.path.join(dest_root, 'export.zip')
    with urllib.request.urlopen(req, timeout=600) as resp:
        with open(zip_path, 'wb') as f:
            shutil.copyfileobj(resp, f)
    size_mb = round(os.path.getsize(zip_path) / (1024 * 1024), 1)
    _log(f'导出包已下载（{size_mb} MB），开始解压')
    return _extract_package(zip_path, os.path.join(dest_root, 'data'))


def resolve_export_dir(job_id, export_dir, params, log_fn=None) -> tuple[str, Optional[str]]:
    """返回 (可用的 export_dir, 临时目录需清理或 None)。"""
    if export_dir and os.path.isdir(export_dir):
        return export_dir, None

    mode = (params or {}).get('data_mode') or data_mode()
    package_path = (params or {}).get('package_path')
    if package_path and os.path.isfile(package_path):
        dest = tempfile.mkdtemp(prefix=f'ls_train_pkg_{job_id}_')
        if log_fn:
            log_fn(f'从本地包解压：{package_path}')
        return _extract_package(package_path, dest), dest

    if mode == 'ssh':
        pulled = pull_export_via_ssh(job_id, params, log_fn=log_fn)
        cleanup = os.path.dirname(pulled.rstrip('/\\'))
        parent = os.path.dirname(cleanup)
        return pulled, parent

    if mode == 'http' or (params or {}).get('package_rel'):
        pulled = pull_export_package_http(job_id, params, log_fn=log_fn)
        cleanup = os.path.dirname(pulled.rstrip('/\\'))
        parent = os.path.dirname(cleanup)
        return pulled, parent

    raise FileNotFoundError(
        f'导出目录不可读：{export_dir}。'
        '双机请设 TRAINING_DATA_MODE=ssh，并配置 TRAINING_SSH_HOST / '
        'TRAINING_SSH_REMOTE_DATA / TRAINING_SSH_KEY；'
        '或挂载共享盘（shared）。'
    )


def push_artifacts_via_ssh(job_id, file_map: dict, log_fn=None) -> dict:
    """scp 产物到标注服，并把 DB 中的路径改成标注服容器路径。"""
    from .models import TrainedModel, TrainingJob

    def _log(msg):
        if log_fn:
            log_fn(msg)
        else:
            logger.info(msg)

    cfg = ssh_config()
    _require_ssh(cfg)
    job = TrainingJob.objects.filter(pk=job_id).first()
    if not job:
        raise RuntimeError(f'TrainingJob {job_id} 不存在')

    remote_dir = remote_artifacts_host_dir(job_id, cfg)
    remote_spec = f"{cfg['user']}@{cfg['host']}"
    _log(f'SSH 创建远端目录：{remote_dir}')
    _run(
        _ssh_base_cmd(cfg) + [remote_spec, f'mkdir -p {remote_dir}'],
        log_fn=log_fn,
        timeout=60,
    )

    saved = []
    artifacts = dict(job.artifacts or {})

    for key, path in file_map.items():
        if not path or not os.path.isfile(path):
            continue
        filename = os.path.basename(path)
        remote_file = f'{remote_dir}/{filename}'
        _log(f'SCP 回传 {filename} → {remote_spec}:{remote_file}')
        _run(
            _scp_base_cmd(cfg) + [path, f'{remote_spec}:{remote_file}'],
            log_fn=log_fn,
            timeout=3600,
        )
        container_path = annotation_artifact_container_path(job_id, filename, cfg)
        saved.append(filename)

        if key.startswith('model_'):
            variant = key[len('model_'):] or 'model'
            existing = None
            for m in job.models.all():
                v = (m.metrics or {}).get('variant') or ''
                if v == variant or (not v and variant in (m.name or '').lower()):
                    existing = m
                    break
            size = os.path.getsize(path)
            if existing:
                existing.file_path = container_path
                existing.name = filename
                existing.file_size = size
                metrics = dict(existing.metrics or {})
                metrics['variant'] = variant
                existing.metrics = metrics
                existing.save(update_fields=['file_path', 'name', 'file_size', 'metrics'])
            else:
                TrainedModel.objects.create(
                    job=job,
                    name=filename,
                    file_path=container_path,
                    file_size=size,
                    metrics={'variant': variant},
                )
        elif key.startswith('artifact_'):
            art_key = key[len('artifact_'):]
            artifacts[art_key] = container_path

    if artifacts != (job.artifacts or {}):
        job.artifacts = artifacts
        job.save(update_fields=['artifacts', 'updated_at'])

    _log(f'SSH 回传完成：{len(saved)} 个文件')
    return {'ok': True, 'saved': saved, 'count': len(saved)}


def push_artifacts_to_annotation(job_id, file_map: dict, log_fn=None, mode=None) -> dict:
    """按 data_mode 回传产物。"""
    mode = mode or data_mode()
    if mode == 'ssh':
        return push_artifacts_via_ssh(job_id, file_map, log_fn=log_fn)
    if mode == 'http':
        return _push_artifacts_http(job_id, file_map, log_fn=log_fn)
    return {}


def _push_artifacts_http(job_id, file_map: dict, log_fn=None) -> dict:
    import json
    import uuid
    import urllib.request
    from urllib.error import HTTPError

    def _log(msg):
        if log_fn:
            log_fn(msg)
        else:
            logger.info(msg)

    base = annotation_base_url()
    token = worker_token()
    if not base or not token:
        _log('跳过 HTTP 产物回传：未配置 TRAINING_ANNOTATION_URL 或 TRAINING_WORKER_TOKEN')
        return {}

    boundary = f'----LSTrain{uuid.uuid4().hex}'
    body = bytearray()
    for name, path in file_map.items():
        if not path or not os.path.isfile(path):
            continue
        filename = os.path.basename(path)
        body.extend(f'--{boundary}\r\n'.encode())
        body.extend(
            f'Content-Disposition: form-data; name="{name}"; filename="{filename}"\r\n'
            f'Content-Type: application/octet-stream\r\n\r\n'.encode()
        )
        with open(path, 'rb') as f:
            body.extend(f.read())
        body.extend(b'\r\n')
    body.extend(f'--{boundary}--\r\n'.encode())

    url = f'{base}/api/train/jobs/{job_id}/receive-artifacts'
    _log(f'HTTP 回传训练产物：{url}')
    req = urllib.request.Request(
        url,
        data=bytes(body),
        headers={
            'Content-Type': f'multipart/form-data; boundary={boundary}',
            'X-Training-Token': token,
        },
        method='POST',
    )
    try:
        with urllib.request.urlopen(req, timeout=600) as resp:
            raw = resp.read().decode('utf-8', errors='replace')
        return json.loads(raw) if raw else {}
    except HTTPError as e:
        err = e.read().decode('utf-8', errors='replace')
        raise RuntimeError(f'产物回传失败 HTTP {e.code}: {err}') from e


def collect_job_artifact_files(job) -> dict:
    files = {}
    for m in job.models.all():
        if m.file_path and os.path.isfile(m.file_path):
            variant = (m.metrics or {}).get('variant') or m.name or 'model'
            files[f'model_{variant}'] = m.file_path
    for key, path in (job.artifacts or {}).items():
        if key in ('runs_dir', 'trained_dir', 'ultralytics_save_dir'):
            continue
        if path and os.path.isfile(path):
            files[f'artifact_{key}'] = path
    return files
