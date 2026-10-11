import pytest

from sapl.crispy_layout_mixin import CrispyLayoutFormMixin


class ParentWithoutGetForm:
    pass


class ViewWithoutGetForm(CrispyLayoutFormMixin, ParentWithoutGetForm):
    layout_key = None


class ParentWithFailingGetForm:
    def get_form(self, form_class=None):
        raise AttributeError('form constructor failure')


class ViewWithFailingGetForm(CrispyLayoutFormMixin, ParentWithFailingGetForm):
    layout_key = None


def test_missing_parent_get_form_returns_none():
    assert ViewWithoutGetForm().get_form() is None


def test_parent_form_constructor_attribute_error_is_not_swallowed():
    with pytest.raises(AttributeError, match='form constructor failure'):
        ViewWithFailingGetForm().get_form()
