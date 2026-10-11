import unittest
from types import SimpleNamespace
from unittest.mock import patch


class CapaProcessoNumeracaoTests(unittest.TestCase):
    def test_uses_numeracao_model_field_names(self):
        import django
        from django.conf import settings
        settings.LOGGING_CONFIG = None
        django.setup()
        from sapl.relatorios.views import get_capa_processo

        protocolo = SimpleNamespace(
            numero=10, ano=2024, data='2024-01-02', hora='10:00',
            assunto_ementa='Assunto', interessado='Interessado', autor=None,
            tipo_processo=1, tipo_materia='PL', tipo_documento=None,
            anulado=0,
        )
        materia = SimpleNamespace(numero=7, ano=2024)
        numeracao = SimpleNamespace(numero_materia='5', ano_materia=2020)
        with patch('sapl.relatorios.views.MateriaLegislativa.objects.filter',
                   side_effect=[[materia], [materia]]), \
             patch('sapl.relatorios.views.DocumentoAdministrativo.objects.filter',
                   return_value=[]), \
             patch('sapl.relatorios.views.Numeracao.objects.filter',
                   return_value=[numeracao]):
            result = get_capa_processo([protocolo])
        self.assertEqual(result[0]['numeracao'], 'PROCESSO N&#176; 5/2020')


if __name__ == '__main__':
    unittest.main()
