from django.conf.urls import include
from django.urls import path, re_path
from . import api

app_name = 'training'

_project_urlpatterns = [
    # 训练操作
    re_path(r'^api/projects/(?P<pk>[^/]+)/train/?$',
            api.TrainStartAPI.as_view(), name='train-start'),
    re_path(r'^api/projects/(?P<pk>[^/]+)/train/status/?$',
            api.TrainStatusAPI.as_view(), name='train-status'),
    re_path(r'^api/projects/(?P<pk>[^/]+)/train/logs/?$',
            api.TrainLogsAPI.as_view(), name='train-logs'),
    re_path(r'^api/projects/(?P<pk>[^/]+)/train/stop/?$',
            api.TrainStopAPI.as_view(), name='train-stop'),
    # 模型管理
    re_path(r'^api/projects/(?P<pk>[^/]+)/train/models/?$',
            api.ModelListAPI.as_view(), name='train-models'),
    re_path(r'^api/projects/(?P<pk>[^/]+)/train/models/(?P<mid>\d+)/download/?$',
            api.ModelDownloadAPI.as_view(), name='train-model-download'),
    re_path(r'^api/projects/(?P<pk>[^/]+)/train/models/(?P<mid>\d+)/?$',
            api.ModelDeleteAPI.as_view(), name='train-model-delete'),
]

_train_urlpatterns = [
    path('api/train/configs', api.ModelConfigListAPI.as_view(), name='train-configs'),
    re_path(r'^api/train/configs/(?P<config_id>\d+)/?$',
            api.ModelConfigDetailAPI.as_view(), name='train-config-detail'),
]

urlpatterns = _project_urlpatterns + _train_urlpatterns
