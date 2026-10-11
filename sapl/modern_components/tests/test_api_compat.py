import json
import os
import unittest
from unittest.mock import patch

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'sapl.settings')
import django
django.setup()

from django.conf import settings
from django.contrib.contenttypes.models import ContentType
from rest_framework import serializers
from rest_framework.authentication import SessionAuthentication, TokenAuthentication
from rest_framework.generics import GenericAPIView
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.schemas.openapi import SchemaGenerator

from sapl.api.schema import Schema
from sapl.api.serializers import SaplSerializerMixin
from sapl.api.system_schema import (
    JSONSchemaRenderer, YAMLValidatorRenderer, NativeSchemaGenerator, NativeSchemaView,
)


class APICompatibilityTests(unittest.TestCase):
    def test_content_type_public_label_matches_legacy(self):
        content_type = ContentType(app_label='parlamentares', model='parlamentar')
        serializer = SaplSerializerMixin()
        self.assertEqual(serializer.get___str__(content_type), str(content_type.name))
        self.assertNotIn(' | ', serializer.get___str__(content_type))

    def test_filter_contract_does_not_expose_new_unsupported_lookups(self):
        import sapl.api.urls
        from drfautoapi.drfautoapi import ApiViewSetConstrutor
        from django_filters.rest_framework import DjangoFilterBackend
        from sapl.materia.models import MateriaLegislativa
        view = ApiViewSetConstrutor.get_viewset_for_model(MateriaLegislativa)()
        filterset = DjangoFilterBackend().get_filterset_class(view, view.queryset)
        names = set(filterset.base_filters)
        self.assertIn('ementa__icontains', names)
        self.assertFalse(any('trigram' in name or 'iso_week_day' in name for name in names))

    def test_other_public_labels_keep_model_string(self):
        self.assertEqual(SaplSerializerMixin().get___str__('legacy label'), 'legacy label')

    def test_legacy_json_format_is_supported(self):
        renderer = JSONSchemaRenderer()
        self.assertEqual(renderer.format, 'json')
        self.assertEqual(json.loads(renderer.render({'openapi': '3.0.2'})), {'openapi': '3.0.2'})

    def test_legacy_yaml_format_is_supported(self):
        renderer = YAMLValidatorRenderer()
        self.assertEqual(renderer.format, 'yaml')
        self.assertIn(b'openapi:', renderer.render({'openapi': '3.0.2'}))

    def test_documentation_retains_project_metadata(self):
        view = NativeSchemaView.as_view()
        generator = view.initkwargs['schema_generator']
        self.assertEqual(generator.title, settings.SPECTACULAR_SETTINGS['TITLE'])
        self.assertEqual(generator.version, settings.SPECTACULAR_SETTINGS['VERSION'])
        self.assertEqual(generator.description, settings.SPECTACULAR_SETTINGS['DESCRIPTION'])

    def test_schema_documents_token_cookie_and_its_own_endpoint(self):
        with patch.object(SchemaGenerator, 'get_schema', return_value={'paths': {}}):
            schema = NativeSchemaGenerator().get_schema(public=True)
        schemes = schema['components']['securitySchemes']
        self.assertEqual(schemes['tokenAuth']['name'], 'Authorization')
        self.assertEqual(schemes['cookieAuth']['name'], settings.SESSION_COOKIE_NAME)
        self.assertIn('/api/schema/', schema['paths'])

    def _operation(self, permission):
        class ExampleSerializer(serializers.Serializer):
            name = serializers.CharField()

        class ExampleView(GenericAPIView):
            serializer_class = ExampleSerializer
            authentication_classes = [TokenAuthentication, SessionAuthentication]
            permission_classes = [permission]
            filter_backends = []

        view = ExampleView()
        view.request = None
        view.format_kwarg = None
        view.kwargs = {}
        schema = Schema()
        schema.view = view
        return schema.get_operation('/api/example/', 'POST')

    def test_protected_operation_documents_both_auth_methods(self):
        self.assertEqual(self._operation(IsAuthenticated)['security'],
                         [{'tokenAuth': []}, {'cookieAuth': []}])

    def test_public_operation_documents_anonymous_access(self):
        self.assertIn({}, self._operation(AllowAny)['security'])


if __name__ == '__main__':
    unittest.main()
