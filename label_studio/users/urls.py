"""This file and its contents are licensed under the Apache License 2.0. Please see the included NOTICE for copyright information and LICENSE for a copy of the license.
"""
from os.path import join

from django.conf import settings
from django.conf.urls import include
from django.urls import path, re_path
from django.views.static import serve
from rest_framework import routers
from users import api, views
from users.product_tours import api as product_tours_api

router = routers.DefaultRouter()
router.register(r'users', api.UserAPI, basename='user')

urlpatterns = [
    re_path(r'^api/', include(router.urls)),
    # Authentication
    path('user/login/', views.user_login, name='user-login'),
    path('user/signup/', views.user_signup, name='user-signup'),
    path('user/account/', views.user_account, name='user-account'),
    path('user/account/<sub_path>', views.user_account, name='user-account-anything'),
    re_path(r'^logout/?$', views.logout, name='logout'),
    # Token
    path('api/current-user/reset-token/', api.UserResetTokenAPI.as_view(), name='current-user-reset-token'),
    path('api/current-user/token', api.UserGetTokenAPI.as_view(), name='current-user-token'),
    path('api/current-user/whoami', api.UserWhoAmIAPI.as_view(), name='current-user-whoami'),
    # Product tours
    path('api/current-user/product-tour', product_tours_api.ProductTourAPI.as_view(), name='product-tour'),
    path('api/current-user/hotkeys/', api.UserHotkeysAPI.as_view(), name='current-user-hotkeys'),
    # User organizations management (superuser only)
    path('api/users/<int:pk>/organizations/', api.UserOrganizationsListAPI.as_view(), name='user-organizations-list'),
    path('api/users/<int:pk>/organizations/add/', api.UserOrganizationAddAPI.as_view(), name='user-organization-add'),
    path('api/users/<int:pk>/organizations/<int:org_id>/', api.UserOrganizationRemoveAPI.as_view(), name='user-organization-remove'),
]

# When CLOUD_FILE_STORAGE_ENABLED is set, avatars are uploaded to cloud storage with a different URL pattern.
# This local serving pattern is unnecessary for environments with cloud storage enabled.
if not settings.CLOUD_FILE_STORAGE_ENABLED:
    urlpatterns += [
        # avatars
        re_path(
            r'^data/' + settings.AVATAR_PATH + '/(?P<path>.*)$',
            serve,
            kwargs={'document_root': join(settings.MEDIA_ROOT, settings.AVATAR_PATH)},
        ),
    ]
