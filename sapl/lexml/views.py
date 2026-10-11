import logging

from django.http import HttpResponse, HttpResponseBadRequest
from django.shortcuts import render

from sapl.crud.base import CrudAux, Crud
from sapl.lexml.OAIServer import OAIServerFactory, get_config
from sapl.modern_components.oai_protocol import OAIServiceError
from sapl.rules import RP_DETAIL, RP_LIST

from .models import LexmlProvedor, LexmlPublicador

from .forms import LexmlProvedorForm

logger = logging.getLogger(__name__)

LexmlPublicadorCrud = CrudAux.build(LexmlPublicador, 'lexml_publicador')


class LexmlProvedorCrud(Crud):
    model = LexmlProvedor
    help_topic = 'lexml_provedor'
    public = [RP_LIST, RP_DETAIL]

    class CreateView(Crud.CreateView):
        form_class = LexmlProvedorForm

    class UpdateView(Crud.UpdateView):
        form_class = LexmlProvedorForm

    class DetailView(Crud.DetailView):
        layout_key = 'LexmlProvedorDetail'


def lexml_request(request):
    request_dict = request.GET.copy()
    batch_values = request.GET.getlist('batch_size')
    try:
        if len(batch_values) > 1:
            raise ValueError("repeated batch size")
        batch_size = int(batch_values[0]) if batch_values else 10
        if not 1 <= batch_size <= 1000:
            raise ValueError("batch size outside the supported range")
    except (TypeError, ValueError):
        return HttpResponseBadRequest("batch_size deve ser um inteiro entre 1 e 1000.")
    if 'batch_size' in request_dict:
        del request_dict['batch_size']

    config = get_config(request.build_absolute_uri(), batch_size)
    oai_server = OAIServerFactory(config)
    try:
        result = oai_server.handleRequest(request_dict)
    except OAIServiceError:
        logger.exception("Falha interna do serviço OAI.")
        response = HttpResponse("Serviço OAI temporariamente indisponível.", status=503)
        response['Retry-After'] = '60'
        return response
    return HttpResponse(result, content_type='text/xml')


def request_search(request, keyword):
    return render(request, "lexml/resultado-pesquisa.html", {"keyword": keyword})
