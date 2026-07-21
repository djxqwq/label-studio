from django.apps import AppConfig


class TrainingConfig(AppConfig):
    name = 'training'
    verbose_name = 'Training'
    default_auto_field = 'django.db.models.AutoField'

    def ready(self):
        # 注册 Project 删除时清理训练任务文件
        from . import signals  # noqa: F401
