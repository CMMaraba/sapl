from django.urls import include, re_path as url
from sapl.api.system_schema import NativeSchemaView, SwaggerView, RedocView
from rest_framework.authtoken.views import obtain_auth_token

from sapl.api.deprecated import SessaoPlenariaViewSet
from sapl.api.views import recria_token, SaplApiViewSetConstrutor

from .apps import AppConfig
from .views_health import HealthzView, ReadyzView

app_name = AppConfig.name

router = SaplApiViewSetConstrutor.router()

# TODO: eliminar endpoint, transferido para SaplApiViewSetConstrutor
# verificar se ainda permanece necessidade desses endpoint's
# /api/sessao-planaria -> /api/sessao/sessaoplenaria/ecidadania
#  /api/sessao-planaria/{pk} -> /api/sessao/sessaoplenaria/{pk}/ecidadania
router.register(r'sessao-plenaria', SessaoPlenariaViewSet,
                basename='sessao_plenaria_old')

urlpatterns_router = router.urls

urlpatterns_api_doc = [
    url('^schema/swagger-ui/',
        SwaggerView.as_view(url_name='sapl.api:schema_api'),
        name='swagger_ui_schema_api'),
    url('^schema/redoc/',
        RedocView.as_view(url_name='sapl.api:schema_api'),
        name='redoc_schema_api'),
    url('^schema/', NativeSchemaView.as_view(), name='schema_api'),
]

urlpatterns = [
    url(r'^api/', include(urlpatterns_api_doc)),
    url(r'^api/', include(urlpatterns_router)),

    url(r'^api/auth/token$', obtain_auth_token),
    url(r'^api/recriar-token/(?P<pk>\d*)$', recria_token, name="recria_token"),
]
