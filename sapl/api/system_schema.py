from django.urls import reverse
from django.views.generic import TemplateView
from rest_framework.permissions import AllowAny
from rest_framework.schemas import get_schema_view
from rest_framework.renderers import JSONOpenAPIRenderer, OpenAPIRenderer

class NativeSchemaView:
    @classmethod
    def as_view(cls, **kwargs):
        return get_schema_view(title="SAPL API", version="3.1-system", public=True,
                               permission_classes=[AllowAny],
                               renderer_classes=[JSONOpenAPIRenderer, OpenAPIRenderer])

class SwaggerView(TemplateView):
    template_name = "api/system_swagger.html"
    url_name = "sapl.api:schema_api"
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["schema_url"] = reverse(self.url_name)
        return context

class RedocView(SwaggerView):
    template_name = "api/system_redoc.html"
