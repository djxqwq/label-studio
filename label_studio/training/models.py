"""训练任务数据库模型"""
import uuid
from django.db import models
from django.contrib.auth import get_user_model
from projects.models import Project

User = get_user_model()


class ModelConfig(models.Model):
    """用户创建的模型配置（前端可增删，不碰代码）"""
    TASK_CHOICES = [
        ('obb', 'OBB 旋转检测'),
        ('detect', '目标检测'),
        ('cls', '分类'),
        ('seg', '分割'),
    ]

    name = models.CharField(max_length=255, unique=True)
    task_type = models.CharField(max_length=20, choices=TASK_CHOICES, default='obb')
    model_yaml = models.CharField(max_length=255, default='yolov8x-obb')
    model_pt = models.CharField(max_length=255, default='yolov8x-obb')
    data_yaml = models.CharField(max_length=255, default='')  # 留空自动生成
    classes = models.JSONField(help_text="类别列表，如 ['apple', 'banana']")
    epochs = models.IntegerField(default=1000)
    batch = models.IntegerField(default=16)
    patience = models.IntegerField(default=200)
    imgsz = models.IntegerField(default=640)
    device = models.CharField(max_length=64, default='0')
    train_params = models.JSONField(default=dict, blank=True, help_text="完整 YOLO 训练超参")
    created_by = models.ForeignKey(User, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return self.name

    def resolved_train_params(self):
        from .params import extract_train_params_from_config
        return extract_train_params_from_config(self)

    def to_dict(self):
        train_params = self.resolved_train_params()
        return {
            'id': self.id,
            'name': self.name,
            'task_type': self.task_type,
            'model_yaml': self.model_yaml,
            'model_pt': self.model_pt,
            'data_yaml': self.data_yaml,
            'classes': self.classes,
            'epochs': train_params.get('epochs', self.epochs),
            'batch': train_params.get('batch', self.batch),
            'patience': train_params.get('patience', self.patience),
            'imgsz': train_params.get('imgsz', self.imgsz),
            'device': train_params.get('device', self.device),
            'train_params': train_params,
        }


class TrainingJob(models.Model):
    """训练任务记录（支持单项目或多项目合并训练集）"""
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('building', 'Building Dataset'),
        ('training', 'Training'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
        ('stopped', 'Stopped'),
    ]

    # 旧单项目外键：保留兼容历史数据，新任务以 projects M2M 为准
    project = models.ForeignKey(
        Project, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='training_jobs',
    )
    projects = models.ManyToManyField(Project, related_name='training_jobs_multi', blank=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    config_name = models.CharField(max_length=255)
    task_id = models.CharField(max_length=64, unique=True, default=uuid.uuid4, editable=False)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    progress = models.IntegerField(default=0, help_text="0-100")
    current_epoch = models.IntegerField(default=0)
    total_epochs = models.IntegerField(default=0)
    params = models.JSONField(default=dict)
    result = models.JSONField(default=dict, null=True, blank=True)
    error_message = models.TextField(blank=True, default='')
    stop_requested = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def get_projects(self):
        """返回关联项目 queryset（优先 M2M，回退旧 FK）"""
        qs = self.projects.all()
        if qs.exists():
            return qs
        if self.project_id:
            return Project.objects.filter(pk=self.project_id)
        return Project.objects.none()

    def to_dict(self, detail=False):
        project_list = [
            {'id': p.id, 'title': p.title}
            for p in self.get_projects()
        ]
        data = {
            'id': self.id,
            'task_id': str(self.task_id),
            'config_name': self.config_name,
            'status': self.status,
            'progress': self.progress,
            'current_epoch': self.current_epoch,
            'total_epochs': self.total_epochs,
            'params': self.params,
            'result': self.result,
            'error_message': self.error_message,
            'stop_requested': self.stop_requested,
            'projects': project_list,
            'project_ids': [p['id'] for p in project_list],
            'project_titles': [p['title'] for p in project_list],
            'created_by': self.created_by.get_username() if self.created_by else None,
            'created_at': self.created_at.strftime('%Y-%m-%d %H:%M'),
            'updated_at': self.updated_at.strftime('%Y-%m-%d %H:%M'),
        }
        if detail:
            models = [m.to_dict() for m in self.models.all()]
            data['models'] = models
            data['model_count'] = len(models)
            data['log_count'] = self.logs.count()
        return data


class TrainingLog(models.Model):
    """训练日志行"""
    job = models.ForeignKey(TrainingJob, on_delete=models.CASCADE, related_name='logs')
    level = models.CharField(max_length=10, default='INFO')
    message = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['created_at']

    def to_dict(self):
        return {
            'id': self.id,
            'level': self.level,
            'message': self.message,
            'created_at': self.created_at.strftime('%Y-%m-%d %H:%M:%S'),
        }


class TrainedModel(models.Model):
    """训练完成的模型文件"""
    job = models.ForeignKey(TrainingJob, on_delete=models.CASCADE, related_name='models')
    name = models.CharField(max_length=255)
    file_path = models.CharField(max_length=1024)
    file_size = models.BigIntegerField(default=0)
    metrics = models.JSONField(default=dict)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'file_size': self.file_size,
            'file_size_mb': round(self.file_size / (1024 * 1024), 2) if self.file_size else 0,
            'metrics': self.metrics,
            'created_at': self.created_at.strftime('%Y-%m-%d %H:%M'),
            'job_id': self.job_id,
        }
