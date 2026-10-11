"""OpenAPI documentation using the distribution's DRF and bundled assets."""
from django.conf import settings
from django.urls import reverse
from django.views.generic import TemplateView
from rest_framework.authentication import SessionAuthentication, TokenAuthentication
from rest_framework.permissions import AllowAny
from rest_framework.renderers import JSONOpenAPIRenderer, OpenAPIRenderer
from rest_framework.schemas import get_schema_view
from rest_framework.schemas.openapi import SchemaGenerator


class JSONSchemaRenderer(JSONOpenAPIRenderer):
    format = 'json'


class YAMLValidatorRenderer(OpenAPIRenderer):
    format = 'yaml'


class ApplicationJSONSchemaRenderer(JSONSchemaRenderer):
    media_type = 'application/json'


class ApplicationYAMLSchemaRenderer(YAMLValidatorRenderer):
    media_type = 'application/yaml'


class NativeSchemaGenerator(SchemaGenerator):
    def get_schema(self, request=None, public=False):
        schema = super().get_schema(request=request, public=public)
        schema.setdefault('components', {}).setdefault('securitySchemes', {}).update({
            'tokenAuth': {'type': 'apiKey', 'in': 'header', 'name': 'Authorization',
                          'description': 'Token-based authentication with required prefix "Token"'},
            'cookieAuth': {'type': 'apiKey', 'in': 'cookie',
                           'name': settings.SESSION_COOKIE_NAME},
        })
        # The schema endpoint itself was present in the production documentation.
        schema['paths'][reverse('sapl.api:schema_api')] = {'get': {
            'operationId': 'get_api_schema',
            'description': 'OpenAPI schema. Choose JSON or YAML by format or Accept header.',
            'parameters': [
                {'in': 'query', 'name': 'format', 'schema': {'type': 'string', 'enum': ['json', 'yaml']}},
                {'in': 'query', 'name': 'lang', 'schema': {'type': 'string', 'enum': ['pt-br']}},
            ],
            'security': [{'tokenAuth': []}, {'cookieAuth': []}, {}],
            'responses': {'200': {'description': 'OpenAPI schema', 'content': {
                media: {'schema': {'type': 'object', 'additionalProperties': {}}}
                for media in ('application/vnd.oai.openapi', 'application/yaml',
                              'application/vnd.oai.openapi+json', 'application/json')
            }}},
        }}
        response_contracts = (
            '/api/auth/token',
            '/api/recriar-token/{id}',
            '/api/materia/tipomaterialegislativa/{id}/change_position/',
        )
        for path in response_contracts:
            operation = schema.get('paths', {}).get(path, {}).get('post')
            if operation is None:
                continue
            responses = operation.setdefault('responses', {})
            if '201' in responses and '200' not in responses:
                responses['200'] = responses.pop('201')
        recreate_token = schema.get('paths', {}).get('/api/recriar-token/{id}', {}).get('post')
        if recreate_token is not None:
            recreate_token.pop('requestBody', None)
        return schema


class NativeSchemaView:
    @classmethod
    def as_view(cls, **kwargs):
        info = settings.SPECTACULAR_SETTINGS
        return get_schema_view(
            title=info['TITLE'], description=info['DESCRIPTION'], version=info['VERSION'],
            public=True, permission_classes=[AllowAny], generator_class=NativeSchemaGenerator,
            renderer_classes=[YAMLValidatorRenderer, JSONSchemaRenderer,
                              ApplicationJSONSchemaRenderer, ApplicationYAMLSchemaRenderer,
                              OpenAPIRenderer, JSONOpenAPIRenderer],
        )


class SwaggerView(TemplateView):
    template_name = 'api/system_swagger.html'
    url_name = 'sapl.api:schema_api'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['schema_url'] = reverse(self.url_name)
        return context


class RedocView(SwaggerView):
    template_name = 'api/system_redoc.html'
