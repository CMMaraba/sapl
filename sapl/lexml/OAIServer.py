import unicodedata
from datetime import datetime

from django.urls import reverse
from django.utils import timezone
from lxml import etree
from lxml.builder import ElementMaker


from sapl.base.models import AppConfig, CasaLegislativa
from sapl.lexml.models import LexmlPublicador, LexmlProvedor
from sapl.norma.models import NormaJuridica
from sapl.utils import LISTA_DE_UFS
from sapl.modern_components.oai_protocol import OAIProtocolServer


class OAIServer:
    """SAPL OAI record provider for the project-owned OAI-PMH layer."""

    XSI_NS = 'http://www.w3.org/2001/XMLSchema-instance'
    ns = {'lexml': 'http://www.lexml.gov.br/oai_lexml'}

    def __init__(self, config=None):
        self.config = config or {}

    def get_oai_record(self, identifier):
        """Look up one record by its canonical SAPL OAI identifier."""
        if not isinstance(identifier, str) or not identifier.startswith('oai:'):
            return None
        internal_id = identifier[4:]
        institution = casa_legislativa()
        domain_parts = institution.endereco_web.split('.')
        domain = '.'.join(domain_parts[1:])
        prefix = '{}.{}:sapl/'.format(institution.sigla.lower(), domain)
        if not internal_id.startswith(prefix):
            return None
        try:
            equivalent, year, number = internal_id[len(prefix):].rsplit(';', 2)
            year = int(year)
            if not number:
                return None
        except (ValueError, TypeError):
            return None

        esfera = self.get_esfera_federacao()
        filters = {
            'data__isnull': False,
            'esfera_federacao__isnull': False,
            'timestamp__isnull': False,
            'tipo__equivalente_lexml': equivalent,
            'ano': year,
            'numero': number,
        }
        if esfera:
            filters['esfera_federacao'] = esfera
        norma = NormaJuridica.objects.select_related('tipo').filter(**filters).first()
        if not norma or self.monta_id(norma) != internal_id:
            return None
        record_id = self.monta_id(norma)
        return {
            'record': {
                'id': record_id,
                'when_modified': norma.timestamp,
                'deleted': 0,
            },
            'metadata': self.monta_xml(self.monta_urn(norma, esfera), norma),
        }

    def get_esfera_federacao(self):
        appconfig = AppConfig.objects.first()
        return appconfig.esfera_federacao

    def recupera_norma(self, offset, batch_size, from_, until, identifier, esfera):
        kwargs = {'data__isnull': False,
                  'esfera_federacao__isnull': False,
                  'timestamp__isnull': False,
                  'timestamp__lte': until}
        if from_:
            kwargs['timestamp__gte'] = from_
        if identifier:
            kwargs['numero'] = identifier
        if esfera:
            kwargs['esfera_federacao'] = esfera
        return NormaJuridica.objects.select_related('tipo').filter(**kwargs)[offset:offset + batch_size]

    def monta_id(self, norma):
        if norma:
            num = len(casa.endereco_web.split('.'))
            dominio = '.'.join(casa.endereco_web.split('.')[1:num])
            prefixo_oai = '{}.{}:sapl/'.format(casa.sigla.lower(), dominio)
            numero_interno = norma.numero
            tipo_norma = norma.tipo.equivalente_lexml
            ano_norma = norma.ano
            identificador = '{}{};{};{}'.format(prefixo_oai, tipo_norma, ano_norma, numero_interno)
            return identificador
        else:
            return None

    @staticmethod
    def remove_acentos(linha):
        res = unicodedata.normalize('NFKD', linha).encode('ASCII', 'ignore')
        res = res.decode("UTF-8")
        remove_list = ["\'", "\"", "-"]
        for i in remove_list:
            res = res.replace(i, "")
        return res

    def monta_urn(self, norma, esfera):
        if norma:
            urn = 'urn:lex:br;'
            esferas = {'M': 'municipal', 'E': 'estadual'}
            municipio = self.remove_acentos(casa.municipio.lower())
            uf_map = dict(LISTA_DE_UFS)
            uf_desc = uf_map.get(casa.uf.upper(), '').lower()
            uf_desc = self.remove_acentos(uf_desc)
            for x in [' ', '.de.', '.da.', '.das.', '.do.', '.dos.']:
                municipio = municipio.replace(x, '.')
                uf_desc = uf_desc.replace(x, '.')
            if esfera == 'M':
                urn += '{};{}:'.format(uf_desc, municipio)
                if norma.tipo.equivalente_lexml == 'regimento.interno' or norma.tipo.equivalente_lexml == 'resolucao':
                    urn += 'camara.'
                urn += esferas[esfera] + ':'
            elif esfera == 'E':
                urn += '{}:{}:'.format(uf_desc, esferas[esfera])
            else:
                urn += ':'
            if norma.tipo.equivalente_lexml:
                urn += '{}:{};'.format(norma.tipo.equivalente_lexml, norma.data.isoformat())
            else:
                urn += '{};'.format(norma.data.isoformat())
            if norma.tipo.equivalente_lexml == 'lei.organica' or norma.tipo.equivalente_lexml == 'constituicao':
                urn += str(norma.ano)
            else:
                urn += str(norma.numero)
            if norma.data_vigencia and norma.data_publicacao:
                urn += '@{};publicacao;{}'.format(norma.data_vigencia.isoformat(), norma.data_publicacao.isoformat())
            elif norma.data_publicacao:
                urn += '@inicio.vigencia;publicacao;{}'.format(norma.data_publicacao.isoformat())
            return urn
        else:
            return None

    def data_por_extenso(self, data):
        data = data.strftime('%d-%m-%Y')
        if data != '':
            meses = {1: 'Janeiro', 2: 'Fevereiro', 3: 'Março', 4: 'Abril', 5: 'Maio', 6: 'Junho', 7: 'Julho',
                     8: 'Agosto', 9: 'Setembro', 10: 'Outubro', 11: 'Novembro', 12: 'Dezembro'}
            return '{} de {} de {}'.format(data[0:2], meses[int(data[3:5])], data[6:])
        else:
            return ''

    def monta_xml(self, urn, norma):
        BASE_URL_SAPL = self.config['base_url']
        BASE_URL_SAPL = BASE_URL_SAPL[:BASE_URL_SAPL.find('/', 8)]

        publicador = LexmlPublicador.objects.first()
        if norma and publicador:
            LEXML = ElementMaker(namespace=self.ns['lexml'], nsmap=self.ns)
            oai_lexml = LEXML.LexML()
            oai_lexml.attrib['{{{pre}}}schemaLocation'.format(pre=self.XSI_NS)] = '{} {}'.format(
                'http://www.lexml.gov.br/oai_lexml', 'http://projeto.lexml.gov.br/esquemas/oai_lexml.xsd')
            texto_integral = norma.texto_integral
            mime_types = {'doc': 'application/msword',
                          'docx': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
                          'odt': 'application/vnd.oasis.opendocument.text',
                          'pdf': 'application/pdf',
                          'rtf': 'application/rtf'}

            if texto_integral:
                url_conteudo = BASE_URL_SAPL + texto_integral.url
                extensao = texto_integral.url.split('.')[-1]
                formato = mime_types.get(extensao, 'application/octet-stream')
            else:
                formato = 'text/html'
                url_conteudo = BASE_URL_SAPL + reverse('sapl.norma:normajuridica_detail',
                                                                 kwargs={'pk': norma.pk})
            element_maker = ElementMaker()
            id_publicador = str(publicador.id_publicador)
            item_conteudo = element_maker.Item(url_conteudo, formato=formato, idPublicador=id_publicador,
                                               tipo='conteudo')
            oai_lexml.append(item_conteudo)
            url = BASE_URL_SAPL + reverse('sapl.norma:normajuridica_detail', kwargs={'pk': norma.pk})
            item_metadado = element_maker.Item(url, formato='text/html', idPublicador=id_publicador, tipo='metadado')
            oai_lexml.append(item_metadado)
            documento_individual = element_maker.DocumentoIndividual(urn)
            oai_lexml.append(documento_individual)
            if norma.tipo.equivalente_lexml == 'lei.organica':
                epigrafe = '{} de {} - {}, de {}'.format(norma.tipo.descricao, casa.municipio,
                                                         casa.uf, norma.ano)
            elif norma.tipo.equivalente_lexml == 'constituicao':
                epigrafe = '{} do Estado de {}, de {}'.format(norma.tipo.descricao, casa.municipio,
                                                              norma.ano)
            else:
                epigrafe = '{} n° {}, de {}'.format(norma.tipo.descricao, norma.numero,
                                                    self.data_por_extenso(norma.data))
            oai_lexml.append(element_maker.Epigrafe(epigrafe))
            oai_lexml.append(element_maker.Ementa(norma.ementa))
            indexacao = norma.indexacao
            if indexacao:
                oai_lexml.append(element_maker.Indexacao(indexacao))
            return etree.tostring(oai_lexml)
        else:
            return None

    def oai_query(self, offset=0, batch_size=10, from_=None, until=None, identifier=None):
        if from_:
            from_ = timezone.make_aware(from_)  # convert from naive to timezone aware datetime
        esfera = self.get_esfera_federacao()
        offset = 0 if offset < 0 else offset
        batch_size = 10 if batch_size < 0 else batch_size

        until = timezone.make_aware(until) \
            if until and timezone.make_aware(until) < timezone.now() \
            else timezone.now()

        normas = self.recupera_norma(offset,
                                     batch_size,
                                     from_,
                                     until,
                                     identifier,
                                     esfera)
        for norma in normas:
            resultado = {}
            identificador = self.monta_id(norma)
            urn = self.monta_urn(norma, esfera)
            xml_lexml = self.monta_xml(urn, norma)
            resultado['tx_metadado_xml'] = xml_lexml
            resultado['cd_status'] = 'N'
            resultado['id'] = identificador
            resultado['when_modified'] = norma.timestamp
            resultado['deleted'] = 0
            yield {'record': resultado,
                   'metadata': resultado['tx_metadado_xml']}


def OAIServerFactory(config=None):
    return OAIProtocolServer(OAIServer(config or {}))


casa = None


def casa_legislativa():
    global casa
    if not casa:
        casa = CasaLegislativa.objects.first()
    return casa if casa else CasaLegislativa()  # retorna objeto dummy


def get_xml_provedor():
    """ antigo get_descricao_casa() """
    descricao = ''
    provedor = LexmlProvedor.objects.first()
    if provedor:
        descricao = provedor.xml
        if descricao:
            descricao = descricao.encode('utf-8')
    return descricao


def get_config(url, batch_size):
    config = {'content_type': None,
              'delay': 0,
              'base_asset_path': None,
              'metadata_prefixes': ['oai_lexml'],
              'titulo': casa_legislativa().nome,  # Inicializa variável global casa
              'email': [casa.email],  # lista de e-mails, antigo `def get_email()`
              'base_url': url[:url.find('/', 8)] + reverse('sapl.lexml:lexml_endpoint')[:-4],  # remove '/oai' suffix
              'descricao': get_xml_provedor(),
              'batch_size': batch_size
              }
    return config


if __name__ == '__main__':
    """
        Para executar localmente (estando no diretório raiz):
        
        $ ./manage.py shell_plus
        
        Executar comando        
        %run sapl/lexml/OAIServer.py
    """
    oai_server = OAIServerFactory(get_config('http://127.0.0.1:8000/', 10))
    r = oai_server.handleRequest({'verb': 'ListRecords',
                                  'metadataPrefix': 'oai_lexml'})
    print(r.decode('UTF-8'))
