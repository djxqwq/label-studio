"""This file and its contents are licensed under the Apache License 2.0. Please see the included NOTICE for copyright information and LICENSE for a copy of the license.
"""
import pytest
from organizations.models import Organization, OrganizationMember
from tasks.models import Task
from tests.utils import make_annotation
from users.models import User


@pytest.mark.django_db
def test_active_organization_filled(business_client):
    response = business_client.get('/api/users/')
    response_data = response.json()
    assert response_data[0]['active_organization'] == business_client.organization.id


@pytest.mark.django_db
def test_user_list_only_returns_current_user_for_non_superuser(business_client):
    other_user = User.objects.create(email='other_user@pytest.net')
    OrganizationMember.objects.create(user=other_user, organization=business_client.organization)

    response = business_client.get('/api/users/')
    response_data = response.json()

    assert response.status_code == 200
    assert len(response_data) == 1
    assert response_data[0]['id'] == business_client.user.id


@pytest.mark.django_db
def test_user_organizations_self_access_allowed_for_non_superuser(business_client):
    response = business_client.get(f'/api/users/{business_client.user.id}/organizations/')
    response_data = response.json()

    assert response.status_code == 200
    assert len(response_data) == 1
    assert response_data[0]['id'] == business_client.organization.id


@pytest.mark.django_db
def test_user_organizations_other_user_forbidden_for_non_superuser(business_client):
    other_user = User.objects.create(email='other_user@pytest.net')
    OrganizationMember.objects.create(user=other_user, organization=business_client.organization)

    response = business_client.get(f'/api/users/{other_user.id}/organizations/')

    assert response.status_code == 403


@pytest.mark.django_db
def test_user_can_update_own_active_organization(business_client):
    other_owner = User.objects.create(email='owner2@pytest.net')
    other_organization = Organization.create_organization(created_by=other_owner, title='Second Team')
    OrganizationMember.objects.create(user=business_client.user, organization=other_organization)

    response = business_client.patch(
        f'/api/organizations/user/{business_client.user.id}/active-organization',
        data={'active_organization': other_organization.id},
        content_type='application/json',
    )

    business_client.user.refresh_from_db()

    assert response.status_code == 200
    assert response.json()['active_organization'] == other_organization.id
    assert business_client.user.active_organization_id == other_organization.id


@pytest.mark.django_db
def test_user_cannot_update_own_active_organization_to_unassigned_team(business_client):
    other_owner = User.objects.create(email='owner3@pytest.net')
    other_organization = Organization.create_organization(created_by=other_owner, title='Forbidden Team')

    response = business_client.patch(
        f'/api/organizations/user/{business_client.user.id}/active-organization',
        data={'active_organization': other_organization.id},
        content_type='application/json',
    )

    business_client.user.refresh_from_db()

    assert response.status_code == 404
    assert business_client.user.active_organization_id == business_client.organization.id


@pytest.mark.django_db
def test_api_list_organizations(business_client):
    response = business_client.get('/api/organizations/')
    response_data = response.json()
    assert len(response_data) == 1
    assert response_data[0]['id'] == business_client.organization.id


@pytest.mark.django_db
def test_organization_member_retrieve_same_user(business_client, configured_project):
    user = business_client.user
    organization = business_client.organization
    task = Task.objects.filter(project=configured_project).first()
    make_annotation({'completed_by': user}, task_id=task.id)
    response = business_client.get(f'/api/organizations/{organization.id}/memberships/{user.id}/')
    response_data = response.json()
    assert response_data['user'] == user.id
    assert response_data['organization'] == organization.id
    assert response_data['annotations_count'] == 1
    assert response_data['contributed_projects_count'] == 1


@pytest.mark.django_db
def test_organization_member_retrieve_other_user_in_org(business_client):
    organization = business_client.organization
    other_user = User.objects.create(email='other_user@pytest.net')
    OrganizationMember.objects.create(user=other_user, organization=organization)
    response = business_client.get(f'/api/organizations/{organization.id}/memberships/{other_user.id}/')
    response_data = response.json()
    print(response_data)
    assert response_data['user'] == other_user.id
    assert response_data['organization'] == organization.id
    assert response_data['annotations_count'] == 0
    assert response_data['contributed_projects_count'] == 0


@pytest.mark.django_db
def test_organization_member_retrieve_not_active_org(business_client):
    user = business_client.user
    other_user = User.objects.create(email='other_user@pytest.net')
    other_organization = Organization.create_organization(created_by=other_user)
    OrganizationMember.objects.create(user=user, organization=other_organization)
    response = business_client.get(f'/api/organizations/{other_organization.id}/memberships/{user.id}/')
    assert response.status_code == 403
