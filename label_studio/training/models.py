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
    created_by = models.ForeignKey(User, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return self.name

    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'task_type': self.task_type,
            'model_yaml': self.model_yaml,
            'model_pt': self.model_pt,
            'classes': self.classes,
            'epochs': self.epochs,
            'batch': self.batch,
            'patience': self.patience,
            'imgsz': self.imgsz,
            'device': self.device,
        }


class TrainingJob(models.Model):
    """训练任务记录"""
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('building', 'Building Dataset'),
        ('training', 'Training'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
        ('stopped', 'Stopped'),
    ]

    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name='training_jobs')
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
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def to_dict(self):
        return {
            'id': self.id,
            'config_name': self.config_name,
            'status': self.status,
            'progress': self.progress,
            'current_epoch': self.current_epoch,
            'total_epochs': self.total_epochs,
            'params': self.params,
            'result': self.result,
            'error_message': self.error_message,
            'created_at': self.created_at.strftime('%Y-%m-%d %H:%M'),
        }


class TrainingLog(models.Model):
    """训练日志行"""
    job = models.ForeignKey(TrainingJob, on_delete=models.CASCADE, related_name='logs')
    level = models.CharField(max_length=10, default='INFO')
    message = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['created_at']


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
            'metrics': self.metrics,
            'created_at': self.created_at.strftime('%Y-%m-%d %H:%M'),
        }
