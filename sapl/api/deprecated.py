from django.http import HttpResponseRedirect
from django.urls import reverse
from django_filters import rest_framework as filters
from django_filters.rest_framework.backends import DjangoFilterBackend
from rest_framework.mixins import ListModelMixin, RetrieveModelMixin
from rest_framework.permissions import AllowAny
from rest_framework.viewsets import GenericViewSet

from sapl.api.serializers import SessaoPlenariaECidadaniaSerializer
from sapl.sessao.models import SessaoPlenaria


class SessaoPlenariaFilter(filters.FilterSet):
    data_inicio = filters.DateFilter(input_formats=('%d/%m/%Y', '%Y-%m-%d'))
    data_fim = filters.DateFilter(input_formats=('%d/%m/%Y', '%Y-%m-%d'))
    interativa = filters.BooleanFilter()

    class Meta:
        model = SessaoPlenaria
        fields = ('data_inicio', 'data_fim', 'interativa')


class SessaoPlenariaViewSet(ListModelMixin,
                            RetrieveModelMixin,
                            GenericViewSet):
    """
    Deprecated - Será eliminado na versão 3.2

    * TODO: 
        * eliminar endpoint, transferido para SaplApiViewSetConstrutor
            * /api/sessao-planaria -> /api/sessao/sessaoplenaria/ecidadania
            * /api/sessao-planaria/{pk} -> /api/sessao/sessaoplenaria/{pk}/ecidadania
        * verificar se ainda permanece necessidade desses endpoint's
    """

    permission_classes = (AllowAny,)
    serializer_class = SessaoPlenariaECidadaniaSerializer
    queryset = SessaoPlenaria.objects.all()
    filter_backends = (DjangoFilterBackend,)
    filterset_class = SessaoPlenariaFilter

    def list(self, request, *args, **kwargs):
        if (request.query_params.get('data_inicio') and
                request.query_params.get('get_all', '').lower() == 'true'):
            queryset = self.filter_queryset(self.get_queryset())
            session_id = queryset.order_by(
                'data_inicio', 'hora_inicio', 'pk').values_list('pk', flat=True).first()
            if session_id is not None:
                url = reverse('sapl.api:sessao_plenaria_old-detail',
                              kwargs={'pk': session_id})
                return HttpResponseRedirect(url + '?format=json')
        return super().list(request, *args, **kwargs)
