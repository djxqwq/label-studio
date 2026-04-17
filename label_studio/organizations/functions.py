from core.utils.common import temporary_disconnect_all_signals
from django.conf import settings
from django.db import transaction
from organizations.models import Organization, OrganizationMember
from projects.models import Project


def create_organization(title, created_by, legacy_api_tokens_enabled=False, **kwargs):
    from core.feature_flags import flag_set

    JWT_ACCESS_TOKEN_ENABLED = flag_set('fflag__feature_develop__prompts__dia_1829_jwt_token_auth')

    with transaction.atomic():
        org = Organization.objects.create(title=title, created_by=created_by, **kwargs)
        OrganizationMember.objects.create(user=created_by, organization=org)
        if JWT_ACCESS_TOKEN_ENABLED:
            # set auth tokens to new system for new users, unless specified otherwise
            org.jwt.api_tokens_enabled = True
            org.jwt.legacy_api_tokens_enabled = (
                legacy_api_tokens_enabled or settings.LABEL_STUDIO_ENABLE_LEGACY_API_TOKEN
            )
            org.jwt.save()
        return org


def destroy_organization(org):
    from data_export.models import ConvertedFormat
    from labels_manager.models import Label, LabelLink
    from ml_models.models import ModelInterface, ThirdPartyModelVersion, ModelRun
    from ml_model_providers.models import ModelProviderConnection
    from session_policy.models import SessionTimeoutPolicy
    from webhooks.models import Webhook

    with temporary_disconnect_all_signals():
        # Clean up all FK references to organization before deleting it
        OrganizationMember.objects.filter(organization=org).delete()
        Project.objects.filter(organization=org).delete()
        ConvertedFormat.objects.filter(organization=org).delete()
        Label.objects.filter(organization=org).delete()
        Webhook.objects.filter(organization=org).delete()
        ModelInterface.objects.filter(organization=org).delete()
        ThirdPartyModelVersion.objects.filter(organization=org).delete()
        ModelRun.objects.filter(organization=org).delete()
        ModelProviderConnection.objects.filter(organization=org).delete()
        SessionTimeoutPolicy.objects.filter(organization=org).delete()

        if hasattr(org, 'saml'):
            org.saml.delete()
        if hasattr(org, 'jwt'):
            org.jwt.delete()

        # Null out active_organization for users pointing to this org
        from users.models import User
        User.objects.filter(active_organization=org).update(active_organization=None)

        org.delete()
