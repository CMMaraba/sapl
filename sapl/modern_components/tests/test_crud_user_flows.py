"""Exercise real HTML CRUD and uploads with application operator permissions."""
from datetime import date
from io import BytesIO

import pytest
from django.apps import apps
from django.contrib.auth.models import Group
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse
from model_bakery import baker
from reportlab.pdfgen import canvas

from sapl.base.models import AppConfig, CasaLegislativa
from sapl.rules import (
    SAPL_GROUP_ADMINISTRATIVO, SAPL_GROUP_AUDIENCIA, SAPL_GROUP_MATERIA, SAPL_GROUP_NORMA,
    SAPL_GROUP_PROTOCOLO, SAPL_GROUP_SESSAO,
)

CASES = [
    ('materia', 'MateriaLegislativa', 'materialegislativa', SAPL_GROUP_MATERIA,
     'ementa', 'texto_original'),
    ('norma', 'NormaJuridica', 'normajuridica', SAPL_GROUP_NORMA,
     'ementa', 'texto_integral'),
    ('protocoloadm', 'DocumentoAdministrativo', 'documentoadministrativo',
     SAPL_GROUP_PROTOCOLO, 'assunto', 'texto_integral'),
    ('sessao', 'SessaoPlenaria', 'sessaoplenaria', SAPL_GROUP_SESSAO,
     'hora_inicio', 'upload_pauta'),
    ('audiencia', 'AudienciaPublica', 'audienciapublica', SAPL_GROUP_AUDIENCIA,
     'tema', 'upload_pauta'),
]


def pdf_upload():
    buffer = BytesIO()
    document = canvas.Canvas(buffer)
    document.drawString(40, 800, 'SAPL automated test document')
    document.save()
    return SimpleUploadedFile('sapl-test.pdf', buffer.getvalue(),
                              content_type='application/pdf')


def payload_for(app_label):
    if app_label == 'materia':
        tipo = baker.make('materia.TipoMateriaLegislativa',
                          sigla='PL', descricao='Projeto de Lei')
        regime = baker.make('materia.RegimeTramitacao', descricao='Ordinario')
        return dict(tipo=tipo.pk, regime_tramitacao=regime.pk, numero=1,
                    ano=2026, data_apresentacao='2026-05-15', em_tramitacao='True',
                    ementa='Teste de cadastro de materia')
    if app_label == 'norma':
        tipo = baker.make('norma.TipoNormaJuridica', sigla='L', descricao='Lei')
        return dict(tipo=tipo.pk, numero='1', ano=2026, data='2026-05-15',
                    esfera_federacao='M', ementa='Teste de cadastro de norma')
    if app_label == 'protocoloadm':
        tipo = baker.make('protocoloadm.TipoDocumentoAdministrativo',
                          sigla='OF', descricao='Oficio')
        return dict(tipo=tipo.pk, numero=1, ano=2026, data='2026-05-15',
                    assunto='Teste de cadastro de documento',
                    tramitacao='True', restrito='False',
                    numero_protocolo='', ano_protocolo='', complemento='')
    if app_label == 'sessao':
        legislatura = baker.make('parlamentares.Legislatura', numero=1,
                                 data_inicio=date(2025, 1, 1),
                                 data_fim=date(2028, 12, 31),
                                 data_eleicao=date(2024, 10, 6))
        legislativa = baker.make('parlamentares.SessaoLegislativa',
                                 legislatura=legislatura, numero=1,
                                 data_inicio=date(2026, 1, 1),
                                 data_fim=date(2026, 12, 31))
        tipo = baker.make('sessao.TipoSessaoPlenaria', nome='Ordinaria')
        return dict(tipo=tipo.pk, legislatura=legislatura.pk,
                    sessao_legislativa=legislativa.pk, numero=1,
                    data_inicio='2026-05-15', hora_inicio='10:00')
    tipo = baker.make('audiencia.TipoAudienciaPublica', nome='Audiencia Publica',
                      tipo='A')
    return dict(tipo=tipo.pk, numero=1, ano=2026, nome='Audiencia de teste',
                tema='Teste de cadastro de audiencia', data='2026-05-15',
                hora_inicio='10:00', audiencia_cancelada='False')


@pytest.fixture
def crud_config(db):
    AppConfig.objects.get_or_create(pk=1)
    if not CasaLegislativa.objects.exists():
        baker.make(CasaLegislativa, nome='Casa de teste', sigla='CT')


def assert_saved_response(response):
    errors = None
    if getattr(response, 'context_data', None):
        form = response.context_data.get('form')
        errors = form.errors if form is not None else None
    assert response.status_code == 302, (response.status_code, errors)


@pytest.mark.django_db
@pytest.mark.parametrize('case', CASES, ids=[c[0] for c in CASES])
@pytest.mark.parametrize('with_upload', [False, True], ids=['text', 'pdf'])
def test_operator_creates_edits_reads_and_deletes(
        case, with_upload, client, django_user_model, crud_config):
    app_label, model_name, route, group_name, changed_field, upload_field = case
    model = apps.get_model(app_label, model_name)
    user = django_user_model.objects.create_user(username='crud_operator')
    user.groups.add(Group.objects.get(name=str(group_name)))
    assert not user.is_superuser
    client.force_login(user)
    data = payload_for(app_label)
    url_name = 'sapl.{}:{}'.format(app_label, route)
    create_url = reverse(url_name + '_create')
    assert client.get(create_url).status_code == 200
    if with_upload:
        data[upload_field] = pdf_upload()
    before = set(model.objects.values_list('pk', flat=True))
    response = client.post(create_url, data)
    assert_saved_response(response)
    created = model.objects.exclude(pk__in=before).get()
    assert getattr(created, changed_field) == data[changed_field]
    if with_upload:
        uploaded = getattr(created, upload_field)
        assert uploaded.name
        with uploaded.open('rb') as stream:
            assert stream.read(4) == b'%PDF'
    detail_url = reverse(url_name + '_detail', kwargs={'pk': created.pk})
    assert client.get(detail_url).status_code == 200
    update_url = reverse(url_name + '_update', kwargs={'pk': created.pk})
    assert client.get(update_url).status_code == 200
    changed = dict(data)
    changed.pop(upload_field, None)
    changed[changed_field] = ('11:00' if changed_field == 'hora_inicio'
                              else 'Texto alterado pelo operador')
    response = client.post(update_url, changed)
    assert_saved_response(response)
    created.refresh_from_db()
    assert getattr(created, changed_field) == changed[changed_field]
    if with_upload:
        with getattr(created, upload_field).open('rb') as stream:
            assert stream.read(4) == b'%PDF'
    delete_url = reverse(url_name + '_delete', kwargs={'pk': created.pk})
    if app_label == 'protocoloadm':
        # Original rules permit protocol operators to add/change, not delete.
        for method in (client.get, client.post):
            assert method(delete_url).status_code == 403
            assert model.objects.filter(pk=created.pk).exists()
        user.groups.add(Group.objects.get(name=str(SAPL_GROUP_ADMINISTRATIVO)))
        client.force_login(user)
    assert client.get(delete_url).status_code == 200
    response = client.post(delete_url, {})
    assert_saved_response(response)
    assert not model.objects.filter(pk=created.pk).exists()


@pytest.mark.django_db
@pytest.mark.parametrize('case', CASES, ids=[c[0] for c in CASES])
@pytest.mark.parametrize('identity', ['anonymous', 'no_permissions'])
def test_unauthorized_user_cannot_create(
        case, identity, client, django_user_model, crud_config):
    app_label, model_name, route, *_ = case
    model = apps.get_model(app_label, model_name)
    if identity == 'no_permissions':
        user = django_user_model.objects.create_user(username='without_permissions')
        client.force_login(user)
    url = reverse('sapl.{}:{}_create'.format(app_label, route))
    data = payload_for(app_label)
    before = model.objects.count()
    for response in [client.get(url), client.post(url, data)]:
        assert response.status_code in (302, 403)
        if response.status_code == 302:
            assert '/login' in response['Location']
    assert model.objects.count() == before
