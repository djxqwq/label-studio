from django.urls import path, re_path
from . import api

app_name = 'training'

urlpatterns = [
    # 配置
    path('api/train/configs', api.ModelConfigListAPI.as_view(), name='train-configs'),
    re_path(r'^api/train/configs/(?P<config_id>\d+)/?$',
            api.ModelConfigDetailAPI.as_view(), name='train-config-detail'),
    # 启动训练
    path('api/train', api.TrainStartAPI.as_view(), name='train-start'),
    # 预训练权重列表（本地 + 可选尺度）
    path('api/train/weights', api.TrainWeightsAPI.as_view(), name='train-weights'),
    # 任务
    path('api/train/jobs', api.TrainJobListAPI.as_view(), name='train-jobs'),
    re_path(r'^api/train/jobs/(?P<job_id>\d+)/?$',
            api.TrainJobDetailAPI.as_view(), name='train-job-detail'),
    re_path(r'^api/train/jobs/(?P<job_id>\d+)/logs/?$',
            api.TrainJobLogsAPI.as_view(), name='train-job-logs'),
    re_path(r'^api/train/jobs/(?P<job_id>\d+)/stop/?$',
            api.TrainJobStopAPI.as_view(), name='train-job-stop'),
    re_path(r'^api/train/jobs/(?P<job_id>\d+)/models/?$',
            api.TrainJobModelsAPI.as_view(), name='train-job-models'),
    re_path(r'^api/train/jobs/(?P<job_id>\d+)/artifacts/(?P<key>[\w-]+)/?$',
            api.TrainJobArtifactAPI.as_view(), name='train-job-artifact'),
    # 模型下载（删除请走删除整个任务）
    re_path(r'^api/train/models/(?P<mid>\d+)/download/?$',
            api.TrainModelDownloadAPI.as_view(), name='train-model-download'),
]
