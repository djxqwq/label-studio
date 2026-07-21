"""训练管理 API"""
import logging
import os
import shutil
import threading

from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from core.permissions import all_permissions
from projects.models import Project

from .models import ModelConfig, TrainingJob, TrainingLog, TrainedModel
from .serializers import TrainRequestSerializer, ModelConfigSerializer
from .tasks import build_dataset, run_training

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


_SEED_DONE = False
_SEED_LOCK = threading.Lock()


def _seed_defaults(request):
    global _SEED_DONE
    if _SEED_DONE:
        return
    with _SEED_LOCK:
        if _SEED_DONE:
            return
        if not request.user.is_authenticated:
            return
        try:
            for name, task_type, yaml, pt, classes in _DEFAULT_CONFIGS:
                ModelConfig.objects.update_or_create(
                    name=name,
                    defaults=dict(task_type=task_type, model_yaml=yaml, model_pt=pt,
                                  classes=classes, created_by=request.user),
                )
            _SEED_DONE = True
        except Exception:
            pass


class ModelConfigListAPI(APIView):
    permission_required = all_permissions.projects_view

    def get(self, request):
        _seed_defaults(request)
        return Response([c.to_dict() for c in ModelConfig.objects.all()])

    def post(self, request):
        serializer = ModelConfigSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        config = ModelConfig.objects.create(created_by=request.user, **serializer.validated_data)
        return Response(config.to_dict(), status=status.HTTP_201_CREATED)


class ModelConfigDetailAPI(APIView):
    permission_required = all_permissions.projects_change

    def put(self, request, config_id):
        config = ModelConfig.objects.filter(id=config_id).first()
        if not config:
            return Response({'error': '配置不存在'}, status=404)
        serializer = ModelConfigSerializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        for key, value in serializer.validated_data.items():
            setattr(config, key, value)
        config.save()
        return Response(config.to_dict())

    def delete(self, request, config_id):
        config = ModelConfig.objects.filter(id=config_id).first()
        if not config:
            return Response({'error': '配置不存在'}, status=404)
        config.delete()
        return Response({'ok': True})


# ==================== 训练 ====================

class TrainStartAPI(APIView):
    """POST /api/projects/{pk}/train -- 启动训练"""
    permission_required = all_permissions.projects_change

    def post(self, request, pk):
        serializer = TrainRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        config_name = serializer.validated_data['config_name']

        config = ModelConfig.objects.filter(name=config_name).first()
        if not config:
            return Response({'error': f'未知模型: {config_name}'}, status=400)

        export_dir = self._do_yolo_export(request, pk, config)
        params = serializer.validated_data
        project = Project.objects.get(pk=pk)

        job = TrainingJob.objects.create(
            project=project, created_by=request.user,
            config_name=config_name, status='building',
            params=params,
        )

        def _train():
            data_name = config.data_yaml or config.name
            dataset_dir = os.path.join(_BASE, 'cv-ultralytics', 'datasets', data_name, config.task_type)
            try:
                build_dataset(export_dir, data_name, config.task_type, config.classes)
                job.status = 'training'; job.save()
                run_training(
                    job=job,
                    model_yaml=config.model_yaml, model_pt=config.model_pt,
                    data_yaml=data_name,
                    epochs=params.get('epochs') or config.epochs,
                    batch=params.get('batch') or config.batch,
                    patience=params.get('patience') or config.patience,
                    imgsz=params.get('imgsz') or config.imgsz,
                    device=params.get('device') or config.device,
                )
                job.status = 'completed'; job.progress = 100; job.save()
            except Exception as e:
                logger.exception(f'训练失败：{e}')
                job.status = 'failed'; job.error_message = str(e); job.save()
            finally:
                # 清理临时导出目录（压缩包解压后的文件）
                if os.path.exists(export_dir):
                    logger.info(f'清理临时导出目录：{export_dir}')
                    shutil.rmtree(export_dir, ignore_errors=True)
                # 清理分割后的数据集目录
                if os.path.exists(dataset_dir):
                    logger.info(f'清理数据集目录：{dataset_dir}')
                    shutil.rmtree(dataset_dir, ignore_errors=True)

        threading.Thread(target=_train, daemon=True).start()
        return Response({'job_id': job.id, 'status': 'building'}, status=status.HTTP_201_CREATED)

    def _do_yolo_export(self, request, pk, config):
        import io, tempfile, zipfile
        from data_export.models import DataExport
        from data_export.serializers import ExportDataSerializer
        from tasks.models import Task
        from core.utils.common import batch
        from django.conf import settings as django_settings

        project = Project.objects.get(pk=pk)
        tasks = []
        task_qs = Task.objects.filter(project=project, annotations__isnull=False).distinct()
        for _ids in batch(task_qs.values_list('id', flat=True), 1000):
            tasks += ExportDataSerializer(
                Task.objects.filter(id__in=_ids).select_related('project').prefetch_related('annotations', 'predictions'),
                many=True, expand=['drafts'],
            ).data

        if not tasks:
            raise ValueError('没有标注数据')

        # 确保临时目录和图片文件在同一盘符，避免 Windows 跨盘符 os.path.relpath() 报错
        _saved_tmp = os.environ.get('TMP'), os.environ.get('TEMP'), os.environ.get('TMPDIR')
        _tmp_on_data = os.path.join(django_settings.BASE_DATA_DIR, 'tmp')
        os.makedirs(_tmp_on_data, exist_ok=True)
        os.environ['TMP'] = os.environ['TEMP'] = os.environ['TMPDIR'] = _tmp_on_data
        try:
            # 根据任务类型选择导出格式：obb 用 YOLO_OBB_WITH_IMAGES，其他用 YOLO_WITH_IMAGES
            export_format = 'YOLO_OBB_WITH_IMAGES' if config.task_type == 'obb' else 'YOLO_WITH_IMAGES'
            export_file, _, _ = DataExport.generate_export_file(
                project, tasks, export_format, download_resources=True,
                get_args=request.GET, hostname=request.build_absolute_uri('/'),
            )
        finally:
            for key, val in zip(('TMP', 'TEMP', 'TMPDIR'), _saved_tmp):
                if val is not None:
                    os.environ[key] = val
                else:
                    os.environ.pop(key, None)

        export_dir = tempfile.mkdtemp(dir=_tmp_on_data, prefix=f'ls_train_{pk}_')
        logger.info(f'_do_yolo_export: export_dir={export_dir}')
        logger.info(f'_do_yolo_export: 找到 {len(tasks)} 个标注任务')

        if hasattr(export_file, 'read'):
            data = export_file.read(); export_file.close()
        elif isinstance(export_file, str) and os.path.isfile(export_file):
            with open(export_file, 'rb') as f:
                data = f.read()
        else:
            raise RuntimeError(f'无法读取导出文件')

        logger.info(f'_do_yolo_export: 导出数据大小={len(data)} bytes')

        with zipfile.ZipFile(io.BytesIO(data)) as zf:
            zf.extractall(export_dir)
            logger.info(f'_do_yolo_export: zip 内容={zf.namelist()[:20]}')

        logger.info(f'_do_yolo_export: 解压后目录结构={os.listdir(export_dir)}')

        img = os.path.join(export_dir, 'images')
        if not os.path.isdir(img):
            for item in os.listdir(export_dir):
                p = os.path.join(export_dir, item)
                if os.path.isdir(p) and os.path.isdir(os.path.join(p, 'images')):
                    img = os.path.join(p, 'images'); break

        if not os.path.isdir(img):
            raise RuntimeError('导出结构不完整')

        img_count = len(os.listdir(img))
        logger.info(f'_do_yolo_export: 导出图片数={img_count}')
        return export_dir


class TrainStatusAPI(APIView):
    """GET /api/projects/{pk}/train/status"""
    permission_required = all_permissions.projects_view

    def get(self, request, pk):
        job = TrainingJob.objects.filter(project_id=pk).order_by('-created_at').first()
        if not job:
            return Response({'status': 'none'})
        return Response(job.to_dict())


class TrainLogsAPI(APIView):
    """GET/DELETE /api/projects/{pk}/train/logs"""
    permission_required = all_permissions.projects_view

    def get(self, request, pk):
        job = TrainingJob.objects.filter(project_id=pk).order_by('-created_at').first()
        if not job:
            return Response({'logs': []})
        since = int(request.GET.get('since', 0))
        entries = job.logs.filter(id__gt=since).values('id', 'level', 'message', 'created_at')
        return Response({'logs': list(entries)})

    def delete(self, request, pk):
        """清空训练日志"""
        job = TrainingJob.objects.filter(project_id=pk).order_by('-created_at').first()
        if job:
            job.logs.all().delete()
        return Response({'ok': True})


class TrainStopAPI(APIView):
    """POST /api/projects/{pk}/train/stop"""
    permission_required = all_permissions.projects_change

    def post(self, request, pk):
        job = TrainingJob.objects.filter(project_id=pk, status__in=['pending','building','training']).first()
        if not job:
            return Response({'error': '无运行中的训练任务'}, status=400)
        job.status = 'stopped'; job.save()
        return Response({'ok': True})


# ==================== 模型管理 ====================

class ModelListAPI(APIView):
    """GET /api/projects/{pk}/train/models"""
    permission_required = all_permissions.projects_view

    def get(self, request, pk):
        models = TrainedModel.objects.filter(job__project_id=pk).order_by('-created_at')
        return Response([m.to_dict() for m in models])


class ModelDownloadAPI(APIView):
    """GET /api/projects/{pk}/train/models/{mid}/download"""
    permission_required = all_permissions.projects_view

    def get(self, request, pk, mid):
        m = TrainedModel.objects.filter(id=mid, job__project_id=pk).first()
        if not m or not os.path.exists(m.file_path):
            return Response({'error': '模型文件不存在'}, status=404)
        from django.http import FileResponse
        return FileResponse(open(m.file_path, 'rb'), as_attachment=True, filename=m.name)


class ModelDeleteAPI(APIView):
    """DELETE /api/projects/{pk}/train/models/{mid}"""
    permission_required = all_permissions.projects_change

    def delete(self, request, pk, mid):
        m = TrainedModel.objects.filter(id=mid, job__project_id=pk).first()
        if not m:
            return Response({'error': '模型不存在'}, status=404)
        if os.path.exists(m.file_path):
            os.remove(m.file_path)
        m.delete()
        return Response({'ok': True})
