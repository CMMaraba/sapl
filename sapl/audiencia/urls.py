from django.urls import include, re_path as url
from sapl.audiencia.views import (index, AudienciaCrud, AnexoAudienciaPublicaCrud)

from .apps import AppConfig

app_name = AppConfig.name

urlpatterns = [
    url(r'^audiencia/', include(AudienciaCrud.get_urls() + AnexoAudienciaPublicaCrud.get_urls())),
]