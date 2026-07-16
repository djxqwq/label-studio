from django.conf.urls import include
from django.urls import path, re_path
from . import api

app_name = 'training'

_project_urlpatterns = [
    re_path(r'^api/projects/(?P<pk>[^/]+)/train/?$',
            api.TrainStartAPI.as_view(), name='train-start'),
]

_train_urlpatterns = [
    path('api/train/configs', api.ModelConfigListAPI.as_view(), name='train-configs'),
    re_path(r'^api/train/configs/(?P<config_id>\d+)/?$',
            api.ModelConfigDetailAPI.as_view(), name='train-config-detail'),
]

urlpatterns = _project_urlpatterns + _train_urlpatterns
