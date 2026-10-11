from types import SimpleNamespace
from unittest.mock import patch

from django.forms.models import ModelChoiceIteratorValue
from django.test import SimpleTestCase

from sapl.materia.forms import TipoProposicaoSelect


class TipoProposicaoSelectTests(SimpleTestCase):
    def test_plain_and_wrapped_values_preserve_profile_attribute(self):
        for value in (7, ModelChoiceIteratorValue(7, SimpleNamespace(pk=7))):
            with self.subTest(value_type=type(value).__name__):
                with patch("sapl.materia.forms.TipoProposicao.objects.get") as get:
                    get.return_value.perfis.exists.return_value = True
                    option = TipoProposicaoSelect().create_option("tipo", value, "Tipo", False, 0)
                    get.assert_called_once_with(id=7)
                    self.assertEqual(str(option["value"]), "7")
                    self.assertEqual(option["attrs"]["data-has-perfil"], "True")

    def test_empty_choice_does_not_query(self):
        with patch("sapl.materia.forms.TipoProposicao.objects.get") as get:
            option = TipoProposicaoSelect().create_option("tipo", "", "---------", False, 0)
            get.assert_not_called()
            self.assertNotIn("data-has-perfil", option["attrs"])
