"""This file and its contents are licensed under the Apache License 2.0. Please see the included NOTICE for copyright information and LICENSE for a copy of the license.
"""
import json

from core.settings.base import *  # noqa
from core.utils.secret_key import generate_secret_key_if_missing

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = generate_secret_key_if_missing(BASE_DATA_DIR)

DJANGO_DB = get_env('DJANGO_DB', DJANGO_DB_SQLITE)
DATABASES = {'default': DATABASES_ALL[DJANGO_DB]}

MIDDLEWARE.append('organizations.middleware.DummyGetSessionMiddleware')
MIDDLEWARE.append('core.middleware.UpdateLastActivityMiddleware')
if INACTIVITY_SESSION_TIMEOUT_ENABLED:
    MIDDLEWARE.append('core.middleware.InactivitySessionTimeoutMiddleWare')

ADD_DEFAULT_ML_BACKENDS = False

LOGGING['root']['level'] = get_env('LOG_LEVEL', 'WARNING')

DEBUG = get_bool_env('DEBUG', False)

DEBUG_PROPAGATE_EXCEPTIONS = get_bool_env('DEBUG_PROPAGATE_EXCEPTIONS', False)

SESSION_COOKIE_SECURE = get_bool_env('SESSION_COOKIE_SECURE', False)

SESSION_ENGINE = 'django.contrib.sessions.backends.signed_cookies'

# Redis / RQ — opensource 默认连本地 Redis；无 Redis 时训练可回退本机线程
REDIS_HOST = get_env('REDIS_HOST', 'localhost')
REDIS_PORT = int(get_env('REDIS_PORT', 6379))
REDIS_DB = int(get_env('REDIS_DB', 0))
_REDIS_PASSWORD = get_env('REDIS_PASSWORD', None)

_rq_base = {
    'HOST': REDIS_HOST,
    'PORT': REDIS_PORT,
    'DB': REDIS_DB,
    'DEFAULT_TIMEOUT': int(get_env('RQ_DEFAULT_TIMEOUT', 180)),
}
if _REDIS_PASSWORD:
    _rq_base['PASSWORD'] = _REDIS_PASSWORD

TRAINING_QUEUE = get_env('TRAINING_QUEUE', 'training')
TRAINING_JOB_TIMEOUT = int(get_env('TRAINING_JOB_TIMEOUT', 48 * 3600))  # 48h
# rq：入队由 GPU 机 rqworker 消费；local：本机 threading（无 Redis/调试）
TRAINING_EXECUTOR = get_env('TRAINING_EXECUTOR', 'rq')
# shared：两边挂同一盘；ssh：训练服 scp 拉包/回传（双机无共享盘推荐）；http：备选
TRAINING_DATA_MODE = get_env('TRAINING_DATA_MODE', 'shared')
TRAINING_WORKER_TOKEN = get_env('TRAINING_WORKER_TOKEN', '')
TRAINING_ANNOTATION_URL = get_env('TRAINING_ANNOTATION_URL', '')
TRAINING_SSH_HOST = get_env('TRAINING_SSH_HOST', '')
TRAINING_SSH_USER = get_env('TRAINING_SSH_USER', 'root')
TRAINING_SSH_PORT = get_env('TRAINING_SSH_PORT', '22')
TRAINING_SSH_KEY = get_env('TRAINING_SSH_KEY', '')
# 标注服宿主机 mydata 绝对路径，如 /opt/label-studio/mydata
TRAINING_SSH_REMOTE_DATA = get_env('TRAINING_SSH_REMOTE_DATA', '')
# 标注服容器内数据根，写入 DB 供下载 API 使用
TRAINING_ANNOTATION_DATA_DIR = get_env('TRAINING_ANNOTATION_DATA_DIR', '/label-studio/data')

RQ_QUEUES = {
    'critical': dict(_rq_base),
    'high': dict(_rq_base),
    'default': dict(_rq_base),
    'low': dict(_rq_base),
    TRAINING_QUEUE: {
        **_rq_base,
        'DEFAULT_TIMEOUT': TRAINING_JOB_TIMEOUT,
    },
}

SENTRY_DSN = get_env('SENTRY_DSN', 'https://68b045ab408a4d32a910d339be8591a4@o227124.ingest.sentry.io/5820521')
SENTRY_ENVIRONMENT = get_env('SENTRY_ENVIRONMENT', 'opensource')

FRONTEND_SENTRY_DSN = get_env(
    'FRONTEND_SENTRY_DSN', 'https://5f51920ff82a4675a495870244869c6b@o227124.ingest.sentry.io/5838868'
)
FRONTEND_SENTRY_ENVIRONMENT = get_env('FRONTEND_SENTRY_ENVIRONMENT', 'opensource')

EDITOR_KEYMAP = json.dumps(get_env('EDITOR_KEYMAP'))

from label_studio import __version__
from label_studio.core.utils import sentry

sentry.init_sentry(release_name='label-studio', release_version=__version__)

# we should do it after sentry init
from label_studio.core.utils.common import collect_versions

versions = collect_versions()

# in Label Studio Community version, feature flags are always ON
FEATURE_FLAGS_DEFAULT_VALUE = True
# or if file is not set, default is using offline mode
FEATURE_FLAGS_OFFLINE = get_bool_env('FEATURE_FLAGS_OFFLINE', True)

FEATURE_FLAGS_FILE = get_env('FEATURE_FLAGS_FILE', 'feature_flags.json')
FEATURE_FLAGS_FROM_FILE = True
try:
    from core.utils.io import find_node

    find_node('label_studio', FEATURE_FLAGS_FILE, 'file')
except IOError:
    FEATURE_FLAGS_FROM_FILE = False

STORAGE_PERSISTENCE = get_bool_env('STORAGE_PERSISTENCE', True)
