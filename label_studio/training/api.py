"""训练管理 API（全局，支持多项目合并训练集）"""
import io
import logging
import os
import shutil
import tempfile
import threading
import zipfile

from django.conf import settings as django_settings
from django.db import close_old_connections
from django.http import FileResponse
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from core.permissions import all_permissions
from core.utils.common import batch
from data_export.models import DataExport
from data_export.serializers import ExportDataSerializer
from projects.models import Project
from tasks.models import Task

from .models import ModelConfig, TrainingJob, TrainedModel
from .serializers import TrainRequestSerializer, ModelConfigSerializer
from .tasks import TrainingStopped, build_dataset, run_training

logger = logging.getLogger(__name__)
_BASE = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))


# ==================== 模型配置 CRUD ====================

_DEFAULT_CONFIGS = [
    ("tree-obb", "obb", "yolov8x-obb", "yolov8x-obb", ["tree"]),
    ("jasmine-blooming-obb", "obb", "yolov8x-obb", "yolov8x-obb", ["blooming"]),
    ("jasmine-seed-obb", "obb", "yolov8x-obb", "yolov8x-obb", ["seed"]),
    ("jasmine-wither-obb", "obb", "yolov8x-obb", "yolov8x-obb", ["wither"]),
    ("jasmine-obb", "obb", "yolov8x-obb", "yolov8x-obb", ["jasmine"]),
    ("orange-obb", "obb", "yolov8x-obb", "yolov8x-obb", ["orange"]),
    ("orange-detect", "detect", "yolov8x", "yolov8x", ["orange"]),
    ("tray-obb", "obb", "yolov8x-obb", "yolov8x-obb", ["tray"]),
    ("tray-detect", "detect", "yolov8x", "yolov8x", ["tray"]),
    ("tray-obb-single", "obb", "yolov8x-obb", "yolov8x-obb", ["tray"]),
    ("scab-obb", "obb", "yolov8x-obb", "yolov8x-obb", ["scab"]),
    ("scab-detect", "detect", "yolov8x", "yolov8x", ["scab"]),
    ("zebrafish-obb", "obb", "yolov8x-obb", "yolov8x-obb", ["zebrafish"]),
    ("uniform-obb", "obb", "yolov8x-obb", "yolov8x-obb", ["uniform"]),
    ("flavor-injection-obb", "obb", "yolov8x-obb", "yolov8x-obb", ["flavor"]),
    ("diantou-obb", "obb", "yolov8x-obb", "yolov8x-obb", ["diantou"]),
]

_SEED_ORGS = set()
_SEED_LOCK = threading.Lock()


def _active_org(request):
    org = getattr(request.user, 'active_organization', None)
    if not org:
        raise ValueError('当前用户未加入组织')
    return org


def _seed_defaults(request):
    """为当前组织种子默认配置（仅该组织缺失时创建）"""
    try:
        org = _active_org(request)
    except ValueError:
        return
    org_id = org.id
    if org_id in _SEED_ORGS:
        return
    with _SEED_LOCK:
        if org_id in _SEED_ORGS:
            return
        if not request.user.is_authenticated:
            return
        try:
            for name, task_type, yaml, pt, classes in _DEFAULT_CONFIGS:
                ModelConfig.objects.update_or_create(
                    organization=org,
                    name=name,
                    defaults=dict(
                        task_type=task_type, model_yaml=yaml, model_pt=pt,
                        classes=classes, created_by=request.user,
                    ),
                )
            _SEED_ORGS.add(org_id)
        except Exception:
            logger.exception('seed default model configs failed')


def _org_configs(request):
    org = _active_org(request)
    return ModelConfig.objects.filter(organization=org), org


def _org_jobs(request):
    org = _active_org(request)
    return TrainingJob.objects.filter(organization=org), org


def _project_label_names(project):
    """从项目 labeling config 提取标签名集合"""
    parsed = project.get_parsed_config() or {}
    names = set()
    for ctrl in parsed.values():
        if not isinstance(ctrl, dict):
            continue
        for label in ctrl.get('labels') or []:
            if isinstance(label, str):
                names.add(label)
            elif isinstance(label, dict) and 'value' in label:
                names.add(str(label['value']))
    return names


def _validate_projects_classes(projects, config):
    """类别必须与配置完全一致，不一致直接报错"""
    expected = set(config.classes or [])
    if not expected:
        raise ValueError('模型配置未设置类别 classes')

    for project in projects:
        actual = _project_label_names(project)
        if not actual:
            raise ValueError(f'项目「{project.title}」(id={project.id}) 未配置标签类别')
        if actual != expected:
            raise ValueError(
                f'项目「{project.title}」(id={project.id}) 类别与配置不一致：'
                f'项目={sorted(actual)}，配置={sorted(expected)}'
            )


def _param_or_default(params, key, default):
    value = params.get(key)
    return default if value is None else value


def _find_images_root(export_dir):
    img = os.path.join(export_dir, 'images')
    if os.path.isdir(img):
        return export_dir
    classes = os.path.join(export_dir, 'classes')
    if os.path.isdir(classes):
        return export_dir
    for item in os.listdir(export_dir):
        p = os.path.join(export_dir, item)
        if os.path.isdir(p) and (
            os.path.isdir(os.path.join(p, 'images')) or os.path.isdir(os.path.join(p, 'classes'))
        ):
            return p
    return None


def _export_format_for_task(task_type):
    if task_type == 'obb':
        return 'YOLO_OBB_WITH_IMAGES'
    if task_type in ('detect', 'seg'):
        # seg 使用 YOLO 多边形标注（PolygonLabels），与 detect 同为 YOLO_WITH_IMAGES
        return 'YOLO_WITH_IMAGES'
    return None


def _extract_choice_label(annotation):
    """从 annotation.result 提取 Choices 分类标签"""
    result = annotation.get('result') if isinstance(annotation, dict) else None
    if result is None and hasattr(annotation, 'result'):
        result = annotation.result
    if not result:
        return None
    for item in result:
        if not isinstance(item, dict):
            continue
        itype = (item.get('type') or '').lower()
        value = item.get('value') or {}
        if itype == 'choices':
            choices = value.get('choices') or []
            if choices:
                return str(choices[0])
        if itype in ('taxonomy', 'labels'):
            labels = value.get('taxonomy') or value.get('labels') or []
            if labels:
                return str(labels[0] if not isinstance(labels[0], list) else labels[0][-1])
    return None


def _task_image_url(task_data):
    if not isinstance(task_data, dict):
        return None
    for key in ('image', 'img', 'photo', 'picture'):
        if task_data.get(key):
            return task_data[key]
    for val in task_data.values():
        if isinstance(val, str) and val:
            lower = val.lower()
            if any(lower.endswith(ext) for ext in ('.jpg', '.jpeg', '.png', '.bmp', '.webp', '.tif', '.tiff')):
                return val
            if '/data/' in val or val.startswith('http'):
                return val
    return None


def _resolve_image_file(url, hostname, access_token):
    """尽量把任务图片落到本地文件路径"""
    if not url:
        return None
    # 上传文件相对路径
    if isinstance(url, str) and '/data/upload/' in url:
        from django.conf import settings
        rel = url.split('/data/upload/', 1)[-1].split('?', 1)[0]
        from urllib.parse import unquote
        rel = unquote(rel)
        candidate = os.path.join(settings.MEDIA_ROOT, settings.UPLOAD_DIR, rel)
        if os.path.isfile(candidate):
            return candidate
    try:
        from label_studio_sdk._extensions.label_studio_tools.core.utils.io import get_local_path
        path = get_local_path(
            url,
            hostname=hostname,
            access_token=access_token,
            download_resources=True,
        )
        if path and os.path.isfile(path):
            return path
    except Exception:
        logger.debug('get_local_path failed for %s', url, exc_info=True)
    return None


def _export_cls_project(request, project, config, tmp_root):
    """分类任务：导出为 classes/<label>/*.jpg"""
    project_dir = tempfile.mkdtemp(dir=tmp_root, prefix=f'proj_{project.id}_cls_')
    classes_root = os.path.join(project_dir, 'classes')
    os.makedirs(classes_root, exist_ok=True)

    hostname = request.build_absolute_uri('/')
    access_token = None
    try:
        if project.organization and project.organization.created_by_id:
            access_token = project.organization.created_by.auth_token.key
    except Exception:
        pass

    expected = set(config.classes or [])
    count = 0
    task_qs = Task.objects.filter(project=project, annotations__isnull=False).distinct()
    for task in task_qs.prefetch_related('annotations'):
        ann = task.annotations.filter(was_cancelled=False).order_by('-updated_at').first()
        if not ann:
            continue
        label = _extract_choice_label({'result': ann.result})
        if not label:
            continue
        if expected and label not in expected:
            raise ValueError(
                f'项目「{project.title}」任务#{task.id} 类别「{label}」不在配置 classes={sorted(expected)} 中'
            )
        image_url = _task_image_url(task.data or {})
        src = _resolve_image_file(image_url, hostname, access_token)
        if not src:
            logger.warning('skip cls task %s: cannot resolve image %s', task.id, image_url)
            continue

        ext = os.path.splitext(src)[1] or '.jpg'
        out_dir = os.path.join(classes_root, label)
        os.makedirs(out_dir, exist_ok=True)
        dest = os.path.join(out_dir, f't{task.id}_{count}{ext}')
        shutil.copy2(src, dest)
        count += 1

    if count == 0:
        raise ValueError(
            f'项目「{project.title}」(id={project.id}) 没有可用的分类标注'
            f'（需要 Choices 标签，且图片可访问）'
        )
    return project_dir


def _export_one_project(request, project, config, tmp_root):
    """导出单个项目，返回含 images/labels 或 classes 的根目录"""
    if config.task_type == 'cls':
        return _export_cls_project(request, project, config, tmp_root)

    tasks = []
    task_qs = Task.objects.filter(project=project, annotations__isnull=False).distinct()
    for _ids in batch(task_qs.values_list('id', flat=True), 1000):
        tasks += ExportDataSerializer(
            Task.objects.filter(id__in=_ids)
            .select_related('project')
            .prefetch_related('annotations', 'predictions'),
            many=True,
            expand=['drafts'],
        ).data

    if not tasks:
        raise ValueError(f'项目「{project.title}」(id={project.id}) 没有标注数据')

    saved_tmp = os.environ.get('TMP'), os.environ.get('TEMP'), os.environ.get('TMPDIR')
    os.environ['TMP'] = os.environ['TEMP'] = os.environ['TMPDIR'] = tmp_root
    try:
        export_format = _export_format_for_task(config.task_type)
        if not export_format:
            raise ValueError(f'不支持的任务类型：{config.task_type}')
        export_file, _, _ = DataExport.generate_export_file(
            project, tasks, export_format, download_resources=True,
            get_args=request.GET, hostname=request.build_absolute_uri('/'),
        )
    finally:
        for key, val in zip(('TMP', 'TEMP', 'TMPDIR'), saved_tmp):
            if val is not None:
                os.environ[key] = val
            else:
                os.environ.pop(key, None)

    if hasattr(export_file, 'read'):
        data = export_file.read()
        export_file.close()
    elif isinstance(export_file, str) and os.path.isfile(export_file):
        with open(export_file, 'rb') as f:
            data = f.read()
    else:
        raise RuntimeError(f'项目「{project.title}」导出文件无法读取')

    project_dir = tempfile.mkdtemp(dir=tmp_root, prefix=f'proj_{project.id}_')
    with zipfile.ZipFile(io.BytesIO(data)) as zf:
        zf.extractall(project_dir)

    root = _find_images_root(project_dir)
    if not root:
        raise RuntimeError(f'项目「{project.title}」导出结构不完整（缺少 images）')
    return root


def _merge_export_dirs(source_roots, merge_dir, task_type='detect'):
    """合并多项目导出，文件名加项目前缀避免冲突"""
    if task_type == 'cls':
        classes_dst = os.path.join(merge_dir, 'classes')
        os.makedirs(classes_dst, exist_ok=True)
        total = 0
        for idx, root in enumerate(source_roots):
            src_classes = os.path.join(root, 'classes')
            if not os.path.isdir(src_classes):
                continue
            for cls_name in os.listdir(src_classes):
                src_dir = os.path.join(src_classes, cls_name)
                if not os.path.isdir(src_dir):
                    continue
                out_dir = os.path.join(classes_dst, cls_name)
                os.makedirs(out_dir, exist_ok=True)
                for name in os.listdir(src_dir):
                    src = os.path.join(src_dir, name)
                    if not os.path.isfile(src):
                        continue
                    base, ext = os.path.splitext(name)
                    shutil.copy2(src, os.path.join(out_dir, f'p{idx}_{base}{ext}'))
                    total += 1
        if total == 0:
            raise ValueError('合并后没有可用分类图片')
        return total

    img_dst = os.path.join(merge_dir, 'images')
    lbl_dst = os.path.join(merge_dir, 'labels')
    os.makedirs(img_dst, exist_ok=True)
    os.makedirs(lbl_dst, exist_ok=True)

    total = 0
    for idx, root in enumerate(source_roots):
        src_img = os.path.join(root, 'images')
        src_lbl = os.path.join(root, 'labels')
        if not os.path.isdir(src_img):
            continue
        for name in os.listdir(src_img):
            src = os.path.join(src_img, name)
            if not os.path.isfile(src):
                continue
            base, ext = os.path.splitext(name)
            new_name = f'p{idx}_{base}{ext}'
            shutil.copy2(src, os.path.join(img_dst, new_name))
            lbl_name = f'{base}.txt'
            lbl_src = os.path.join(src_lbl, lbl_name) if os.path.isdir(src_lbl) else None
            if lbl_src and os.path.isfile(lbl_src):
                shutil.copy2(lbl_src, os.path.join(lbl_dst, f'p{idx}_{base}.txt'))
            total += 1
    if total == 0:
        raise ValueError('合并后没有可用图片')
    return total


def _do_multi_project_export(request, projects, config):
    tmp_root = os.path.join(django_settings.BASE_DATA_DIR, 'tmp')
    os.makedirs(tmp_root, exist_ok=True)
    work_dir = tempfile.mkdtemp(dir=tmp_root, prefix='ls_train_multi_')
    source_roots = []
    try:
        for project in projects:
            source_roots.append(_export_one_project(request, project, config, tmp_root))
        merge_dir = os.path.join(work_dir, 'merged')
        count = _merge_export_dirs(source_roots, merge_dir, task_type=config.task_type)
        logger.info('multi export merged %s images from %s projects into %s', count, len(projects), merge_dir)
        return merge_dir, work_dir
    except Exception:
        shutil.rmtree(work_dir, ignore_errors=True)
        raise


def _start_train_thread(job, config, params, export_dir, cleanup_dir):
    def _train():
        close_old_connections()
        # 按 job.id 隔离，避免同配置并发训练互相覆盖数据集 / data.yaml
        dataset_root = os.path.join(_BASE, 'cv-ultralytics', 'datasets', f'job_{job.id}')
        dataset_dir = os.path.join(dataset_root, config.task_type)
        data_yaml_path = os.path.join(
            _BASE, 'cv-ultralytics', 'ultralytics', 'ultralytics',
            'cfg', 'datasets', f'job_{job.id}.yaml',
        )
        try:
            job.refresh_from_db()
            if job.stop_requested:
                job.status = 'stopped'
                job.save(update_fields=['status', 'updated_at'])
                return

            data_name = config.data_yaml or config.name
            _, data_ref = build_dataset(
                export_dir, data_name, config.task_type, config.classes, job_id=job.id,
            )
            job.status = 'training'
            job.save(update_fields=['status', 'updated_at'])

            run_training(
                job=job,
                model_yaml=config.model_yaml,
                model_pt=config.model_pt,
                data_yaml=data_ref,
                task_type=config.task_type,
                **params,
            )

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
            if cleanup_dir and os.path.exists(cleanup_dir):
                shutil.rmtree(cleanup_dir, ignore_errors=True)
            if os.path.exists(dataset_root):
                shutil.rmtree(dataset_root, ignore_errors=True)
            elif os.path.exists(dataset_dir):
                shutil.rmtree(dataset_dir, ignore_errors=True)
            if os.path.isfile(data_yaml_path):
                try:
                    os.remove(data_yaml_path)
                except OSError:
                    logger.exception('删除 data.yaml 失败: %s', data_yaml_path)

    threading.Thread(target=_train, daemon=True).start()


class ModelConfigListAPI(APIView):
    permission_required = all_permissions.projects_view

    def get(self, request):
        try:
            _seed_defaults(request)
            qs, _ = _org_configs(request)
        except ValueError as e:
            return Response({'error': str(e)}, status=400)
        return Response([c.to_dict() for c in qs])

    def post(self, request):
        try:
            qs, org = _org_configs(request)
        except ValueError as e:
            return Response({'error': str(e)}, status=400)
        serializer = ModelConfigSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        fields = serializer.to_model_fields()
        if qs.filter(name=fields['name']).exists():
            return Response({'error': f'配置名已存在: {fields["name"]}'}, status=400)
        config = ModelConfig.objects.create(
            organization=org, created_by=request.user, **fields,
        )
        return Response(config.to_dict(), status=status.HTTP_201_CREATED)


class ModelConfigDetailAPI(APIView):
    permission_required = all_permissions.projects_change

    def put(self, request, config_id):
        try:
            qs, _ = _org_configs(request)
        except ValueError as e:
            return Response({'error': str(e)}, status=400)
        config = qs.filter(id=config_id).first()
        if not config:
            return Response({'error': '配置不存在'}, status=404)
        serializer = ModelConfigSerializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        fields = serializer.to_model_fields(existing=config.to_dict())
        if qs.filter(name=fields['name']).exclude(id=config.id).exists():
            return Response({'error': f'配置名已存在: {fields["name"]}'}, status=400)
        for key, value in fields.items():
            setattr(config, key, value)
        config.save()
        return Response(config.to_dict())

    def delete(self, request, config_id):
        try:
            qs, _ = _org_configs(request)
        except ValueError as e:
            return Response({'error': str(e)}, status=400)
        config = qs.filter(id=config_id).first()
        if not config:
            return Response({'error': '配置不存在'}, status=404)
        config.delete()
        return Response({'ok': True})


class TrainStartAPI(APIView):
    """POST /api/train — 启动训练（可多项目，限当前组织）"""
    permission_required = all_permissions.projects_change

    def post(self, request):
        try:
            org = _active_org(request)
        except ValueError as e:
            return Response({'error': str(e)}, status=400)

        serializer = TrainRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        config_name = data['config_name']
        project_ids = list(dict.fromkeys(data['project_ids']))

        config = ModelConfig.objects.filter(organization=org, name=config_name).first()
        if not config:
            return Response({'error': f'未知模型: {config_name}'}, status=400)

        projects = list(Project.objects.filter(
            id__in=project_ids, organization=org,
        ))
        found_ids = {p.id for p in projects}
        missing = [pid for pid in project_ids if pid not in found_ids]
        if missing:
            return Response(
                {'error': f'项目不存在或不属于当前组织: {missing}'},
                status=400,
            )

        projects = sorted(projects, key=lambda p: project_ids.index(p.id))

        try:
            _validate_projects_classes(projects, config)
            export_dir, cleanup_dir = _do_multi_project_export(request, projects, config)
        except ValueError as e:
            return Response({'error': str(e)}, status=400)
        except Exception as e:
            logger.exception('导出失败')
            return Response({'error': f'导出失败: {e}'}, status=500)

        from .params import extract_train_params_from_config, merge_train_params
        params = merge_train_params(
            extract_train_params_from_config(config),
            serializer.validated_train_params(),
        )
        params['project_ids'] = project_ids

        job = TrainingJob.objects.create(
            organization=org,
            project=projects[0],
            created_by=request.user,
            config_name=config_name,
            status='building',
            params=params,
            total_epochs=int(params.get('epochs') or config.epochs or 0),
        )
        job.projects.set(projects)

        _start_train_thread(job, config, params, export_dir, cleanup_dir)
        return Response(job.to_dict(detail=True), status=status.HTTP_201_CREATED)


class TrainJobListAPI(APIView):
    """GET /api/train/jobs — 当前组织任务列表（组织内全员可见）"""
    permission_required = all_permissions.projects_view

    def get(self, request):
        from django.db.models import Q

        try:
            qs, _ = _org_jobs(request)
        except ValueError as e:
            return Response({'error': str(e)}, status=400)

        qs = qs.prefetch_related('projects', 'models').select_related('created_by')
        status_filter = request.GET.get('status')
        if status_filter:
            qs = qs.filter(status=status_filter)

        project_q = (request.GET.get('project') or request.GET.get('q') or '').strip()
        if project_q:
            q_filter = Q(projects__title__icontains=project_q) | Q(project__title__icontains=project_q)
            if project_q.isdigit():
                q_filter |= Q(projects__id=int(project_q)) | Q(project_id=int(project_q))
            qs = qs.filter(q_filter).distinct()

        page = max(int(request.GET.get('page', 1)), 1)
        page_size = min(max(int(request.GET.get('page_size', 20)), 1), 100)
        total = qs.count()
        start = (page - 1) * page_size
        jobs = qs[start:start + page_size]
        return Response({
            'count': total,
            'page': page,
            'page_size': page_size,
            'results': [j.to_dict(detail=True) for j in jobs],
        })


class TrainJobDetailAPI(APIView):
    """GET/DELETE /api/train/jobs/{job_id}"""
    permission_required = all_permissions.projects_view

    def get(self, request, job_id):
        try:
            qs, _ = _org_jobs(request)
        except ValueError as e:
            return Response({'error': str(e)}, status=400)
        job = (
            qs.filter(id=job_id)
            .prefetch_related('projects', 'models')
            .select_related('created_by')
            .first()
        )
        if not job:
            return Response({'error': '任务不存在'}, status=404)
        return Response(job.to_dict(detail=True))

    def delete(self, request, job_id):
        """删除任务及其日志、模型文件（释放磁盘）"""
        try:
            qs, _ = _org_jobs(request)
        except ValueError as e:
            return Response({'error': str(e)}, status=400)

        job = qs.filter(id=job_id).prefetch_related('models').first()
        if not job:
            return Response({'error': '任务不存在'}, status=404)
        if job.status in ('pending', 'building', 'training'):
            return Response({'error': '任务仍在运行，请先停止再删除'}, status=400)

        removed_files = 0
        parent_dirs = set()
        for m in job.models.all():
            if m.file_path and os.path.exists(m.file_path):
                try:
                    os.remove(m.file_path)
                    removed_files += 1
                    parent = os.path.dirname(m.file_path)
                    if parent:
                        parent_dirs.add(parent)
                except OSError:
                    logger.exception('删除模型文件失败: %s', m.file_path)
        for path in (job.artifacts or {}).values():
            if path and os.path.isfile(path):
                try:
                    os.remove(path)
                    removed_files += 1
                    parent = os.path.dirname(path)
                    if parent:
                        parent_dirs.add(parent)
                except OSError:
                    logger.exception('删除训练产物失败: %s', path)
        for parent in parent_dirs:
            try:
                if os.path.isdir(parent) and not os.listdir(parent):
                    os.rmdir(parent)
            except OSError:
                pass
        job_id_val = job.id
        job.delete()
        return Response({'ok': True, 'deleted_job_id': job_id_val, 'removed_files': removed_files})


class TrainJobLogsAPI(APIView):
    """GET/DELETE /api/train/jobs/{job_id}/logs"""
    permission_required = all_permissions.projects_view

    def get(self, request, job_id):
        try:
            qs, _ = _org_jobs(request)
        except ValueError as e:
            return Response({'error': str(e)}, status=400)
        job = qs.filter(id=job_id).first()
        if not job:
            return Response({'error': '任务不存在'}, status=404)
        since = int(request.GET.get('since', 0))
        entries = [
            {
                'id': log.id,
                'level': log.level,
                'message': log.message,
                'created_at': log.created_at.strftime('%Y-%m-%d %H:%M:%S'),
            }
            for log in job.logs.filter(id__gt=since)
        ]
        return Response({'logs': entries, 'job_id': job.id, 'status': job.status})

    def delete(self, request, job_id):
        try:
            qs, _ = _org_jobs(request)
        except ValueError as e:
            return Response({'error': str(e)}, status=400)
        job = qs.filter(id=job_id).first()
        if not job:
            return Response({'error': '任务不存在'}, status=404)
        job.logs.all().delete()
        return Response({'ok': True})


class TrainJobStopAPI(APIView):
    """POST /api/train/jobs/{job_id}/stop"""
    permission_required = all_permissions.projects_change

    def post(self, request, job_id):
        try:
            qs, _ = _org_jobs(request)
        except ValueError as e:
            return Response({'error': str(e)}, status=400)
        job = qs.filter(id=job_id).first()
        if not job:
            return Response({'error': '任务不存在'}, status=404)
        if job.status not in ('pending', 'building', 'training'):
            return Response({'error': f'任务状态为 {job.status}，无法停止'}, status=400)
        job.stop_requested = True
        job.status = 'stopped'
        job.save(update_fields=['stop_requested', 'status', 'updated_at'])
        return Response(job.to_dict())


class TrainJobModelsAPI(APIView):
    """GET /api/train/jobs/{job_id}/models"""
    permission_required = all_permissions.projects_view

    def get(self, request, job_id):
        try:
            qs, _ = _org_jobs(request)
        except ValueError as e:
            return Response({'error': str(e)}, status=400)
        job = qs.filter(id=job_id).first()
        if not job:
            return Response({'error': '任务不存在'}, status=404)
        return Response([m.to_dict() for m in job.models.all()])


class TrainModelDownloadAPI(APIView):
    """GET /api/train/models/{mid}/download"""
    permission_required = all_permissions.projects_view

    def get(self, request, mid):
        try:
            org = _active_org(request)
        except ValueError as e:
            return Response({'error': str(e)}, status=400)
        m = TrainedModel.objects.filter(id=mid, job__organization=org).first()
        if not m or not os.path.exists(m.file_path):
            return Response({'error': '模型文件不存在'}, status=404)
        return FileResponse(open(m.file_path, 'rb'), as_attachment=True, filename=m.name)


class TrainJobArtifactAPI(APIView):
    """GET /api/train/jobs/{job_id}/artifacts/{key} —— 查看 F1_curve 等训练曲线图"""
    permission_required = all_permissions.projects_view

    ALLOWED_KEYS = {'F1_curve', 'PR_curve', 'results', 'confusion_matrix'}

    def get(self, request, job_id, key):
        if key not in self.ALLOWED_KEYS:
            return Response({'error': '不支持的产物类型'}, status=400)
        try:
            qs, _ = _org_jobs(request)
        except ValueError as e:
            return Response({'error': str(e)}, status=400)
        job = qs.filter(id=job_id).first()
        if not job:
            return Response({'error': '任务不存在'}, status=404)
        path = (job.artifacts or {}).get(key)
        if not path or not os.path.isfile(path):
            return Response({'error': '产物文件不存在'}, status=404)
        filename = os.path.basename(path)
        return FileResponse(open(path, 'rb'), content_type='image/png', filename=filename)
