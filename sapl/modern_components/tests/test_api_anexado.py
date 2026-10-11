"""The inherited Anexado endpoint must filter both real document relations."""
from types import SimpleNamespace

import pytest
from django.contrib.auth.models import AnonymousUser, User
from model_bakery import baker

import sapl.api.urls
from drfautoapi.drfautoapi import ApiViewSetConstrutor
from sapl.protocoloadm.models import Anexado, DocumentoAdministrativo


def queryset_for(user):
    view = ApiViewSetConstrutor.get_viewset_for_model(Anexado)()
    view.request = SimpleNamespace(user=user)
    return view.get_queryset()


@pytest.mark.django_db
def test_anonymous_anexado_hides_either_restricted_document():
    public = baker.make(DocumentoAdministrativo, restrito=False, _quantity=2)
    private = baker.make(DocumentoAdministrativo, restrito=True, _quantity=2)
    visible = baker.make(Anexado, documento_principal=public[0], documento_anexado=public[1])
    baker.make(Anexado, documento_principal=public[0], documento_anexado=private[0])
    baker.make(Anexado, documento_principal=private[0], documento_anexado=public[0])
    baker.make(Anexado, documento_principal=private[0], documento_anexado=private[1])
    assert list(queryset_for(AnonymousUser()).values_list('pk', flat=True)) == [visible.pk]


@pytest.mark.django_db
def test_authenticated_anexado_keeps_existing_visibility_policy():
    public = baker.make(DocumentoAdministrativo, restrito=False)
    private = baker.make(DocumentoAdministrativo, restrito=True)
    relation = baker.make(Anexado, documento_principal=public, documento_anexado=private)
    assert queryset_for(User(username='read-only-probe')).filter(pk=relation.pk).exists()
