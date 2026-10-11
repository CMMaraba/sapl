import unittest
from types import SimpleNamespace
from unittest.mock import patch


class OAIPerRecordIdentifierTests(unittest.TestCase):
    def test_get_record_accepts_charfield_number_component(self):
        import django
        from django.conf import settings
        settings.LOGGING_CONFIG = None
        django.setup()
        from sapl.lexml.OAIServer import OAIServer

        institution = SimpleNamespace(endereco_web="www.example.org", sigla="camara")
        norma = SimpleNamespace(
            numero="123-A", ano=2024, timestamp=None,
            tipo=SimpleNamespace(equivalente_lexml="lei"),
        )
        provider = OAIServer({})
        identifier = "camara.example.org:sapl/lei;2024;123-A"
        with patch("sapl.lexml.OAIServer.casa_legislativa", return_value=institution), \
             patch("sapl.lexml.OAIServer.casa", institution), \
             patch.object(provider, "get_esfera_federacao", return_value="M"), \
             patch("sapl.lexml.OAIServer.NormaJuridica.objects.select_related") as select_related, \
             patch.object(provider, "monta_urn", return_value="urn:example"), \
             patch.object(provider, "monta_xml", return_value=None):
            select_related.return_value.filter.return_value.first.return_value = norma
            result = provider.get_oai_record("oai:" + identifier)

        self.assertIsNotNone(result)
        self.assertEqual(result["record"]["id"], identifier)
        select_related.return_value.filter.assert_called_once_with(
            data__isnull=False, esfera_federacao__isnull=False,
            timestamp__isnull=False, tipo__equivalente_lexml="lei",
            ano=2024, numero="123-A", esfera_federacao="M",
        )


if __name__ == "__main__":
    unittest.main()
