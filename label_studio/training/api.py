"""训练管理 API"""
import logging
import os
import threading

from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from core.permissions import all_permissions
from projects.models import Project

from .models import ModelConfig, TrainingJob
from .serializers import TrainRequestSerializer, ModelConfigSerializer
from .tasks import build_dataset, run_training

logger = logging.getLogger(__name__)


# ==================== 模型配置 CRUD（前端管理，不碰代码）====================

# 预置默认配置
_DEFAULT_CONFIGS = [
    # (name, task_type, model_yaml, model_pt, classes)
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


def _seed_defaults(request):
    """每次访问时自动同步预置模型配置到 DB"""
    if not request.user.is_authenticated:
        return
    for name, task_type, yaml, pt, classes in _DEFAULT_CONFIGS:
        ModelConfig.objects.update_or_create(
            name=name,
            defaults=dict(
                task_type=task_type, model_yaml=yaml, model_pt=pt,
                classes=classes, created_by=request.user,
            ),
        )


class ModelConfigListAPI(APIView):
    """GET /api/train/configs —— 列表   POST —— 新建"""
    permission_required = all_permissions.projects_view

    def get(self, request):
        _seed_defaults(request)
        configs = ModelConfig.objects.all()
        return Response([c.to_dict() for c in configs])

    def post(self, request):
        serializer = ModelConfigSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        config = ModelConfig.objects.create(
            created_by=request.user,
            **serializer.validated_data,
        )
        return Response(config.to_dict(), status=status.HTTP_201_CREATED)


class ModelConfigDetailAPI(APIView):
    """DELETE /api/train/configs/<id> —— 删除"""
    permission_required = all_permissions.projects_change

    def delete(self, request, config_id):
        config = ModelConfig.objects.filter(id=config_id).first()
        if not config:
            return Response({'error': '配置不存在'}, status=404)
        config.delete()
        return Response({'ok': True})


# ==================== 训练 ====================

class TrainStartAPI(APIView):
    """POST /api/projects/{pk}/train —— 启动训练"""
    permission_required = all_permissions.projects_change

    def post(self, request, pk):
        serializer = TrainRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        config_name = serializer.validated_data['config_name']

        # 从 DB 读模型配置
        config = ModelConfig.objects.filter(name=config_name).first()
        if not config:
            return Response({'error': f'未知模型: {config_name}'}, status=400)

        # 导出 YOLO 数据
        export_dir = self._do_yolo_export(request, pk)

        # 异步训练
        params = serializer.validated_data

        def _train():
            data_name = config.data_yaml or config.name
            build_dataset(export_dir, data_name, config.task_type, config.classes)
            run_training(
                model_yaml=config.model_yaml,
                model_pt=config.model_pt,
                data_yaml=data_name,
                epochs=params.get('epochs') or config.epochs,
                batch=params.get('batch') or config.batch,
                patience=params.get('patience') or config.patience,
                imgsz=params.get('imgsz') or config.imgsz,
                device=params.get('device') or config.device,
            )

        t = threading.Thread(target=_train, daemon=True)
        t.start()

        # 记录
        project = Project.objects.get(pk=pk)
        job = TrainingJob.objects.create(
            project=project,
            created_by=request.user,
            config_name=config_name,
            status='training',
            params=serializer.validated_data,
        )

        return Response({
            'job_id': job.id,
            'config_name': config_name,
            'status': 'training',
        }, status=status.HTTP_201_CREATED)

    def _do_yolo_export(self, request, pk):
        """调 Label Studio 原生导出，返回带有 images/ + labels/ 的目录"""
        import io
        import tempfile
        import zipfile
        from data_export.models import DataExport
        from data_export.serializers import ExportDataSerializer
        from tasks.models import Task
        from core.utils.common import batch

        project = Project.objects.get(pk=pk)

        tasks = []
        task_qs = Task.objects.filter(project=project, annotations__isnull=False).distinct()
        for _ids in batch(task_qs.values_list('id', flat=True), 1000):
            tasks += ExportDataSerializer(
                Task.objects.filter(id__in=_ids)
                    .select_related('project')
                    .prefetch_related('annotations', 'predictions'),
                many=True, expand=['drafts'],
            ).data

        if not tasks:
            raise ValueError('没有标注数据')

        export_file, content_type, filename = DataExport.generate_export_file(
            project, tasks, 'YOLO', download_resources=True,
            get_args=request.GET, hostname=request.build_absolute_uri('/'),
        )

        export_dir = tempfile.mkdtemp(prefix=f'ls_train_{pk}_')
        if hasattr(export_file, 'read'):
            data = export_file.read()
            export_file.close()
        elif isinstance(export_file, str) and os.path.isfile(export_file):
            with open(export_file, 'rb') as f:
                data = f.read()
        else:
            raise RuntimeError(f'无法读取导出文件，类型: {type(export_file)}')

        with zipfile.ZipFile(io.BytesIO(data)) as zf:
            zf.extractall(export_dir)

        img = os.path.join(export_dir, 'images')
        lbl = os.path.join(export_dir, 'labels')
        if not os.path.isdir(img):
            for item in os.listdir(export_dir):
                p = os.path.join(export_dir, item)
                if os.path.isdir(p) and os.path.isdir(os.path.join(p, 'images')):
                    img = os.path.join(p, 'images')
                    lbl = os.path.join(p, 'labels')
                    break

        if not os.path.isdir(img) or not os.path.isdir(lbl):
            raise RuntimeError(f'导出结构不完整: images={os.path.isdir(img)}, labels={os.path.isdir(lbl)}')

        return export_dir
