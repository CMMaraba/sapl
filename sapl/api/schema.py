import re

from django import forms
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.schemas.openapi import AutoSchema


class Schema(AutoSchema):
    def get_component_name(self, serializer):
        model = getattr(getattr(serializer, 'Meta', None), 'model', None)
        name = super().get_component_name(serializer)
        if model is not None:
            return f'{model._meta.app_label}_{model._meta.object_name}_{name}'
        return name

    def get_operation_id(self, path, method):
        # Generated serializers share class names; use the unique HTTP route.
        route = re.sub(r'[^A-Za-z0-9_]+', '_', path).strip('_')
        return f'{method.lower()}_{route}'

    def get_filter_parameters(self, path, method):
        # django-filter no longer provides the deprecated DRF schema hook.
        if not self.allows_filters(path, method):
            return []
        parameters = []
        for backend_class in self.view.filter_backends:
            backend = backend_class()
            hook = getattr(backend, 'get_schema_operation_parameters', None)
            if hook is not None:
                parameters.extend(hook(self.view))
                continue
            if not isinstance(backend, DjangoFilterBackend):
                continue
            filterset = backend.get_filterset_class(
                self.view, getattr(self.view, 'queryset', None))
            if filterset is None:
                continue
            for name, filter_ in filterset.base_filters.items():
                field = filter_.field
                schema = {'type': 'string'}
                if isinstance(field, forms.BooleanField):
                    schema = {'type': 'boolean'}
                elif isinstance(field, (forms.IntegerField, forms.ModelChoiceField)):
                    schema = {'type': 'integer'}
                elif isinstance(field, (forms.DecimalField, forms.FloatField)):
                    schema = {'type': 'number'}
                elif isinstance(field, forms.DateTimeField):
                    schema['format'] = 'date-time'
                elif isinstance(field, forms.DateField):
                    schema['format'] = 'date'
                if isinstance(field, forms.MultipleChoiceField):
                    schema = {'type': 'array', 'items': schema}
                parameters.append({
                    'name': name, 'in': 'query', 'required': bool(filter_.extra.get('required', False)),
                    'description': str(filter_.label or name), 'schema': schema,
                })
        return parameters
