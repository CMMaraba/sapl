from types import SimpleNamespace

from sapl.materia.forms import compara_tramitacoes_mat
from sapl.protocoloadm.forms import compara_tramitacoes_doc


def test_compara_tramitacoes_mat_ignora_ids_e_ordem_de_campos():
    original = SimpleNamespace(
        id=1, materia_id=10, timestamp="old", status_id=3, texto="texto")
    reordered = SimpleNamespace(
        texto="texto", timestamp="new", materia_id=20, status_id=3, id=2)

    assert compara_tramitacoes_mat(original, reordered)


def test_compara_tramitacoes_mat_detecta_alteracao_de_campo():
    original = SimpleNamespace(id=1, materia_id=10, timestamp="old", status_id=3)
    changed = SimpleNamespace(status_id=4, timestamp="new", materia_id=20, id=2)

    assert not compara_tramitacoes_mat(original, changed)


def test_compara_tramitacoes_doc_ignora_ids_e_ordem_de_campos():
    original = SimpleNamespace(
        id=1, documento_id=10, timestamp="old", ultima_edicao="old",
        status_id=3, texto="texto")
    reordered = SimpleNamespace(
        texto="texto", status_id=3, ultima_edicao="new", timestamp="new",
        documento_id=20, id=2)

    assert compara_tramitacoes_doc(original, reordered)


def test_compara_tramitacoes_doc_detecta_alteracao_de_campo():
    original = SimpleNamespace(
        id=1, documento_id=10, timestamp="old", ultima_edicao="old", status_id=3)
    changed = SimpleNamespace(
        status_id=4, ultima_edicao="new", timestamp="new", documento_id=20, id=2)

    assert not compara_tramitacoes_doc(original, changed)
