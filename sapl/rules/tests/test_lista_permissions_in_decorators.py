from django.contrib.auth import decorators as auth_decorators
from django.contrib.auth.decorators import (
    login_required,
    permission_required as require_permission,
)
from django.utils.decorators import method_decorator as decorate_method

from scripts.lista_permissions_in_decorators import (
    get_permission_requireds,
    lista_permissions_in_decorators,
)


class _PermissionDecoratorProbe:
    @require_permission(("rules.view_one", "rules.view_two"),
                        raise_exception=True)
    def direct(self, request):
        return request

    @decorate_method(
        [
            auth_decorators.permission_required(
                ["rules.change_one", False, "rules.change_two"]),
            require_permission("rules.delete_one"),
        ],
        name="dispatch",
    )
    def dispatch(self, request):
        return request

    @auth_decorators.permission_required(
        ["rules.async_one", True, "rules.async_two"])
    async def asynchronous(self, request):
        return request

    @require_permission(True)
    def boolean_only(self, request):
        return request

    @login_required
    def unrelated(self, request):
        return request

    def body_call_is_not_a_decorator(self, request):
        return require_permission("rules.body_only")(request)


@decorate_method(
    [
        require_permission("rules.class_one"),
        auth_decorators.permission_required(("rules.class_two", False)),
    ],
    name="dispatch",
)
class _ClassDecoratorProbe:
    def dispatch(self, request):
        return request


class _NegativeDecoratorProbe:
    @login_required
    def login_only(self, request):
        return request


def test_get_permission_requireds_reads_function_and_class_decorators():
    permissions = set(get_permission_requireds(_PermissionDecoratorProbe))
    permissions.update(get_permission_requireds(_ClassDecoratorProbe))

    assert permissions == {
        "rules.view_one",
        "rules.view_two",
        "rules.change_one",
        "rules.change_two",
        "rules.delete_one",
        "rules.async_one",
        "rules.async_two",
        "rules.class_one",
        "rules.class_two",
    }


def test_get_permission_requireds_ignores_non_permission_decorators():
    assert get_permission_requireds(_NegativeDecoratorProbe) == []


def test_real_url_collector_returns_permission_pairs_and_is_repeatable():
    first = lista_permissions_in_decorators()
    second = lista_permissions_in_decorators()

    assert first
    assert second == first
    assert all(isinstance(permission, str) for permission, view in first)
    assert any(
        permission == "sessao.change_expedientemateria"
        and getattr(view, "__name__", "") == "abrir_votacao"
        for permission, view in first
    )
