import pytest
from django.contrib.auth import get_user_model
from django.core.cache import cache
from rest_framework.authtoken.models import Token
from rest_framework.test import APIClient

from sapl.base.models import AppConfig, DOC_ADM_RESTRITIVO


@pytest.mark.django_db

def test_api_permissions_for_public_and_restricted_models():
    user_model = get_user_model()
    ordinary = user_model.objects.create_user(
        username='api-matrix-user', password='test-only-password')
    admin = user_model.objects.create_superuser(
        username='api-matrix-admin', email='api-matrix@example.invalid',
        password='test-only-password')
    token = Token.objects.get_or_create(user=admin)[0]

    anonymous_client = APIClient()
    ordinary_client = APIClient()
    ordinary_client.force_authenticate(user=ordinary)
    admin_client = APIClient()
    admin_client.force_authenticate(user=admin)
    token_client = APIClient()
    token_client.credentials(HTTP_AUTHORIZATION=f'Token {token.key}')

    cache_key = 'sapl_documentos_administrativos'
    missing = object()
    previous_cached_setting = cache.get(cache_key, missing)
    config = AppConfig.objects.first()
    created_config = config is None
    if created_config:
        config = AppConfig.objects.create(documentos_administrativos=DOC_ADM_RESTRITIVO)
    else:
        previous_db_setting = config.documentos_administrativos
        config.documentos_administrativos = DOC_ADM_RESTRITIVO
        config.save(update_fields=['documentos_administrativos'])
    cache.set(cache_key, DOC_ADM_RESTRITIVO, 600)

    try:
        public_list = '/api/materia/proposicao/'
        private_list = '/api/protocoloadm/documentoadministrativo/'
        assert anonymous_client.get(public_list).status_code == 200
        assert ordinary_client.get(public_list).status_code == 200

        assert anonymous_client.get(private_list).status_code == 401
        assert ordinary_client.get(private_list).status_code == 403
        assert admin_client.get(private_list).status_code == 200
        assert token_client.get(private_list).status_code == 200

        for client in (anonymous_client, ordinary_client):
            expected_denied = 401 if client is anonymous_client else 403
            assert client.post(
                public_list, {}, format='json').status_code == expected_denied
            for method in ('put', 'patch', 'delete'):
                response = getattr(client, method)(
                    public_list + '2147483647/', {}, format='json')
                assert response.status_code == expected_denied

        assert admin_client.post(public_list, {}, format='json').status_code == 400
        for method in ('put', 'patch', 'delete'):
            response = getattr(admin_client, method)(
                public_list + '2147483647/', {}, format='json')
            assert response.status_code == 404

        csrf_client = APIClient(enforce_csrf_checks=True)
        assert csrf_client.login(
            username='api-matrix-admin', password='test-only-password')
        csrf_client.get('/login/', HTTP_X_FORWARDED_PROTO='https', HTTP_HOST='10.3.150.110')
        csrf_token = csrf_client.cookies['csrftoken'].value
        csrf_kwargs = {
            'HTTP_X_FORWARDED_PROTO': 'https',
            'HTTP_ORIGIN': 'https://10.3.150.110',
            'HTTP_HOST': '10.3.150.110',
        }
        assert csrf_client.post(
            public_list, {}, format='json', **csrf_kwargs).status_code == 403
        csrf_kwargs['HTTP_X_CSRFTOKEN'] = csrf_token
        valid_csrf_response = csrf_client.post(
            public_list, {}, format='json', **csrf_kwargs)
        assert valid_csrf_response.status_code == 400, valid_csrf_response.content[:300]
        csrf_kwargs['HTTP_ORIGIN'] = 'https://external.invalid'
        assert csrf_client.post(
            public_list, {}, format='json', **csrf_kwargs).status_code == 403
    finally:
        if previous_cached_setting is missing:
            cache.delete(cache_key)
        else:
            cache.set(cache_key, previous_cached_setting, 600)
        if created_config:
            config.delete()
        else:
            config.documentos_administrativos = previous_db_setting
            config.save(update_fields=['documentos_administrativos'])
