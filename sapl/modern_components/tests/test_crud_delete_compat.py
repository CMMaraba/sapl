from types import SimpleNamespace
from unittest.mock import Mock, patch

from django.db.models import ProtectedError
from django.test import RequestFactory

from sapl.crud.base import CrudDeleteView


class CustomDeleteView(CrudDeleteView):
    def delete(self, request, *args, **kwargs):
        return "custom-delete"


def test_form_valid_routes_custom_delete_handler():
    view = CustomDeleteView()
    view.request = RequestFactory().post("/delete")
    view.args = ()
    view.kwargs = {"pk": 7}

    assert view.form_valid(object()) == "custom-delete"


def test_form_valid_preserves_protected_error_handling():
    view = CrudDeleteView()
    view.request = SimpleNamespace(user=SimpleNamespace(username="test"))
    view.args = ()
    view.kwargs = {"pk": 7}
    protected = SimpleNamespace(delete=Mock(side_effect=ProtectedError("blocked", [])))
    view.get_object = Mock(return_value=protected)
    view.get_success_url = Mock(return_value="/list")
    view.get_context_data = Mock(return_value={})
    view.render_to_response = Mock(return_value="protected-error")

    with patch("sapl.crud.base.messages.add_message") as add_message:
        assert view.form_valid(object()) == "protected-error"

    protected.delete.assert_called_once_with()
    add_message.assert_called_once()
    assert "Registro não pode ser removido" in str(add_message.call_args.args[2])


def test_invalid_delete_form_does_not_call_custom_delete():
    class InvalidForm:
        def is_valid(self):
            return False

    view = CustomDeleteView()
    view.request = RequestFactory().post("/delete")
    view.get_object = Mock(return_value=SimpleNamespace(delete=Mock()))
    view.get_form = Mock(return_value=InvalidForm())
    view.form_invalid = Mock(return_value="invalid-form")

    assert view.post(view.request) == "invalid-form"
    view.form_invalid.assert_called_once()
    assert not view.get_object.return_value.delete.called
