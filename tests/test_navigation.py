"""Navigation and URL routing — ensure UI never resolves to DRF API paths."""
import pytest
from django.test import Client
from django.urls import reverse

from tests.factories import UserFactory


@pytest.mark.django_db
class TestHrisUrlRouting:
    def test_employee_detail_reverses_to_ui_path(self):
        pk = 'f808577c-e06e-4999-906a-25a76e5f5518'
        url = reverse('hris-employee-detail', args=[pk])
        assert url == f'/employees/{pk}/'
        assert not url.startswith('/api/')

    def test_api_employee_detail_is_namespaced(self):
        pk = 'f808577c-e06e-4999-906a-25a76e5f5518'
        url = reverse('api:employee-detail', args=[pk])
        assert url == f'/api/v1/employees/{pk}/'

    def test_profile_dropdown_target_is_ui(self, client):
        user = UserFactory(is_hr_admin=True)
        client.force_login(user)
        response = client.get(reverse('hris-dashboard'))
        assert response.status_code == 200
        profile_url = reverse('hris-my-profile')
        assert profile_url in response.content.decode()

    def test_browser_api_employee_redirects_to_ui(self, client):
        user = UserFactory()
        client.force_login(user)
        pk = str(user.profile.id)
        response = client.get(
            f'/api/v1/employees/{pk}/',
            HTTP_ACCEPT='text/html,application/xhtml+xml',
        )
        assert response.status_code == 302
        assert response.url == f'/employees/{pk}/'

    def test_employee_profile_page_renders_html(self, client):
        user = UserFactory()
        profile = user.profile
        client.force_login(user)
        response = client.get(reverse('hris-employee-detail', args=[profile.pk]))
        assert response.status_code == 200
        content = response.content.decode()
        assert 'Employee Profile' in content or profile.user.get_full_name() in content
        assert 'Django REST framework' not in content

    def test_api_json_still_works(self, client):
        user = UserFactory()
        client.force_login(user)
        pk = str(user.profile.id)
        response = client.get(
            f'/api/v1/employees/{pk}/',
            HTTP_ACCEPT='application/json',
        )
        assert response.status_code == 200
        assert response['Content-Type'].startswith('application/json')
