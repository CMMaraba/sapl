import pytest
from functools import lru_cache


from scripts.lista_urls import lista_urls




_lista_urls = lista_urls()


def create_perms_post_migrate(sapl_app_config):
    """Create list/detail and Django default permissions for app models."""
    from django.contrib.auth.management import _get_all_permissions
    from django.contrib.auth.models import Permission
    from django.contrib.contenttypes.models import ContentType
    from django.utils.translation import gettext_lazy as _

    searched_perms = []
    ctypes = set()
    for klass in list(sapl_app_config.get_models()):
        opts = klass._meta
        permissions = (
            ("list_" + opts.model_name, "{} {}".format(_('Visualização da lista de'), opts.verbose_name_plural)),
            ("detail_" + opts.model_name, "{} {}".format(_('Visualização dos detalhes de'), opts.verbose_name_plural)),
        )
        opts.permissions = tuple(set(list(permissions) + list(opts.permissions)))
        if opts.proxy:
            app_label, model = opts.app_label, opts.model_name
            try:
                ctype = ContentType.objects.get_by_natural_key(app_label, model)
            except ContentType.DoesNotExist:
                ctype = ContentType.objects.create(app_label=app_label, model=model)
        else:
            ctype = ContentType.objects.get_for_model(klass)
        ctypes.add(ctype)
        for perm in _get_all_permissions(klass._meta):
            searched_perms.append((ctype, perm))
    all_perms = set(Permission.objects.filter(content_type__in=ctypes).values_list("content_type", "codename"))
    perms = [
        Permission(codename=codename, name=name, content_type=ct)
        for ct, (codename, name) in searched_perms
        if (ct.pk, codename) not in all_perms
    ]
    Permission.objects.bulk_create(perms)

def _is_crudaux_list_url(url_item):
    callback = url_item[0]
    view_class = getattr(callback, 'view_class', None)
    if view_class is None or not hasattr(view_class, 'crud'):
        return False
    crud_aux = any('CrudAux' in str(base) for base in type.mro(view_class.crud))
    list_view = any('ListView' in str(base) for base in type.mro(view_class))
    return crud_aux and list_view

_crudaux_list_urls = [
    pytest.param(item, marks=pytest.mark.django_db)
    for item in _lista_urls if _is_crudaux_list_url(item)
]



@pytest.mark.parametrize('url_item', _lista_urls)
def test_crudaux_formato_inicio_urls_associadas(url_item):
    # Verifica se um crud é do tipo CrudAux, se sim, sua url deve começar
    # com /sistema/
    key, url, var, app_name = url_item
    url = '/' + (url % {v: 1 for v in var})

    view_class = None
    if hasattr(key, 'view_class'):
        view_class = key.view_class

    # se não tem view_class, possivelmente é não é uma classed base view
    if not view_class:
        return

    # se não tem atributo crud, não é será nenhum tipo de crud
    if not hasattr(view_class, 'crud'):
        return

    # se o crud da view_class relativa a url a ser testada,
    # implementa a classe CrudAux, seu link deve iniciar com /sistema
    for string_class in list(map(str, type.mro(view_class.crud))):

        if 'CrudAux' in string_class:
            assert url.startswith('/sistema'), """
                        A url (%s) foi gerada a partir de um CrudAux,
                        o que diz que está é uma implementação de uma
                        tabela auxiliar, porém a url em questão, está fora
                        do padrão, que é iniciar com /sistema.
                    """ % (url)


@pytest.mark.parametrize('url_item', _crudaux_list_urls)
def test_crudaux_list_do_crud_esta_na_pagina_sistema(url_item, request):
    admin_client = request.getfixturevalue('admin_client')
    # Verifica a url é de um CrudAux e, se for, testa se está
    # na página Tabelas Auxiliares
    key, url, var, app_name = url_item
    url = '/' + (url % {v: 1 for v in var})

    view_class = None
    if hasattr(key, 'view_class'):
        view_class = key.view_class

    # se não tem view_class, possivelmente não é uma classed base view
    if not view_class:
        return

    # se não tem atributo crud, não é será nenhum tipo de crud
    if not hasattr(view_class, 'crud'):
        return

    herancas_crud = list(map(str, type.mro(view_class.crud)))
    for string_class in herancas_crud:
        if 'CrudAux' in string_class:

            herancas_view = list(map(str, type.mro(view_class)))

            for string_view_class in herancas_view:
                # verifica se o link para manutenção do crud está em /sistema
                if 'ListView' in string_view_class:
                    response = admin_client.get('/sistema', {}, follow=True)
                    assert url in str(response.content), """
                        A url (%s) não consta nas Tabelas Auxiliares,
                        porem é uma implementação de ListView de CrudAux.
                        Se encontra em %s.urls
                    """ % (url, app_name)


apps_url_patterns_prefixs_and_users = {
    'audiencia': {
        'prefixs': [
            '/audiencia',
        ]},
    'api': {
        'prefixs': [
            '/api/',
        ]},
    'base': {
        'users': {'operador_geral': ['/sistema']},
        'prefixs': [
            '/sistema',
            '/login',
            '/logout',
            '/ajuda',
            '/email',
            '/recuperar-senha',
            '/sapl',
            '/XSLT',
        ],
        'exact': ['/']
    },
    'comissoes': {
        'users': {'operador_geral': ['/sistema', '/comissao'],
                  'operador_comissoes': ['/comissao']},
        'prefixs': [
            '/comissao',
            '/sistema'
        ]},
    'compilacao': {
        'prefixs': [
            '/ta',
            '/sistema/ta',
        ]},
    'redireciona_urls': {
        'prefixs': [
            '/default_index_html',
            '/consultas/parlamentar/parlamentar_',
            '/consultas/comissao/comissao_',
            '/consultas/pauta_sessao/pauta_sessao_',
            '/consultas/sessao_plenaria/',

            '/relatorios_administrativos/'
            'relatorios_administrativos_index_html',

            '/tramitacaoMaterias/tramitacaoMaterias',
            '/tramitacaoMaterias/materia_mostrar_proc',
            '/generico/materia_pesquisar_',
            '/consultas/mesa_diretora/mesa_diretora_index_html',
            '/consultas/mesa_diretora/parlamentar/parlamentar_',
            '/generico/norma_juridica_pesquisar_',
            '/consultas/norma_juridica/norma_juridica_mostrar_proc',
            '/historicoTramitacoes/historicoTramitacoes',
            '/atasSessao',
            '/presencaSessao',
            '/resumoPropositurasAutor',
            '/propositurasAnoAutorTipo',
        ]},
    'lexml': {
        'prefixs': [
            '/lexml',
            '/sistema'
        ]},
    'materia': {
        'users': {'operador_geral': ['/sistema', '/materia'],
                  'operador_autor': ['/proposicao'],
                  'operador_materia': ['/materia']},
        'prefixs': [
            '/materia',
            '/proposicao',
            '/sistema'
        ]},
    'norma': {
        'users': {'operador_geral': ['/sistema', '/norma'],
                  'operador_norma': ['/norma']},
        'prefixs': [
            '/norma',
            '/sistema'
        ]},
    'painel': {
        'users': {'operador_geral': ['/sistema', '/painel'],
                  'operador_painel': ['/painel']},
        'prefixs': [
            '/painel',
            '/sistema',
            '/voto-individual'
        ]},
    'parlamentares': {
        'users': {'operador_geral': ['/sistema',
                                     '/mesa-diretora',
                                     '/parlamentar']},
        'prefixs': [
            '/parlamentar',
            '/mesa-diretora',
            '/sistema'
        ]},
    'protocoloadm': {
        'users': {'operador_geral': ['/sistema',
                                     '/docadm',
                                     '/protocoloadm'],
                  'operador_administrativo': ['/docadm'],
                  'operador_protocoloadm': ['/protocoloadm']},
        'prefixs': [
            '/protocoloadm',
            '/docadm',
            '/sistema'
        ]},
    'relatorios': {
        'prefixs': [
            '/relatorios',
            "/sistema/relatorios",
        ]},
    'sessao': {
        'users': {'operador_geral': ['/sistema', 'sessao'],
                  'operador_sessao': ['/sessao']},
        'prefixs': [
            '/sessao',
            '/sistema',
        ]},
}


@pytest.mark.parametrize('url_item', _lista_urls)
def test_urlpatterns(url_item):
    key, url, var, app_name = url_item
    url = '/' + (url % {v: 1 for v in var})

    assert '\n' not in url, """
        A url (%s) da app (%s) está mal formada.
    """ % (app_name, url)

    app_name = app_name[5:]
    if app_name != 'redireciona_urls':
        assert app_name in apps_url_patterns_prefixs_and_users, """
            A app (%s) da url (%s) não consta na lista de prefixos do teste
        """ % (app_name, url)

        if app_name in apps_url_patterns_prefixs_and_users:
            prefixs = apps_url_patterns_prefixs_and_users[app_name]['prefixs']
            exacts = apps_url_patterns_prefixs_and_users[app_name].get(
                'exact', [])

            isvalid = False
            for prefix in prefixs:
                if url.startswith(prefix):
                    isvalid = True
                    break
            if not isvalid:
                for exact in exacts:
                    if url == exact:
                        isvalid = True
                        break

            assert isvalid, """
                O prefixo da url (%s) não está no padrão de sua app (%s).
                Os prefixos permitidos são:
                %s
                """ % (url, app_name, prefixs)
    else:
        # ignorando app de redirecionamento de urls no padrão do SAPL 2.5
        pass





def _sample_value(converter):
    name = type(converter).__name__ if converter is not None else ""
    if converter is None:
        return 1
    if name == "UUIDConverter":
        return "00000000-0000-4000-8000-000000000001"
    if name == "IntConverter":
        return 1
    if name == "FloatConverter":
        return 1.5
    if name == "PathConverter":
        return "sample/path"
    return "sample"


def _declared_function_methods(callback):
    import inspect

    methods = set()
    current = callback
    valid = {"GET", "POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS", "TRACE"}
    while callable(current):
        for cell in getattr(current, "__closure__", ()) or ():
            try:
                value = cell.cell_contents
            except ValueError:
                continue
            if isinstance(value, (tuple, list)) and value and all(
                isinstance(item, str) and item.upper() in valid for item in value
            ):
                methods.update(item.upper() for item in value)
        current = getattr(current, "__wrapped__", None)
    return methods


def _bypass_outer_atomic(callback):
    from django.db.transaction import Atomic

    cells = getattr(callback, "__closure__", ()) or ()
    for cell in cells:
        try:
            if isinstance(cell.cell_contents, Atomic):
                return getattr(callback, "__wrapped__", callback)
        except ValueError:
            continue
    return callback


def _route_request(callback, url, variables):
    from django.urls import get_resolver

    converters = {}
    try:
        candidates = get_resolver().reverse_dict[callback]
        if candidates:
            converters = candidates[0][3]
    except (KeyError, TypeError, IndexError):
        pass
    kwargs = {name: _sample_value(converters.get(name)) for name in variables}
    if "sign" in kwargs:
        kwargs["sign"] = "vigencia:abc"
    if "uidb64" in kwargs:
        kwargs["uidb64"] = "MQ"
    if "token" in kwargs:
        kwargs["token"] = "abc-123"
    return "/" + (url % kwargs), kwargs


@lru_cache(maxsize=None)
def _auth_metadata(callback):
    from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
    from scripts.lista_permissions_in_decorators import (
        get_decorators,
        get_permission_requireds,
    )
    from sapl.crud.base import (
        PermissionRequiredContainerCrudMixin,
        PermissionRequiredForAppCrudMixin,
    )
    import inspect

    view = getattr(callback, "view_class", getattr(callback, "cls", callback))
    if isinstance(view, type):
        mro = view.mro()
        if any(
            "dispatch" in candidate.__dict__
            and (
                candidate.__module__.startswith("sapl.")
                and candidate.__module__ != "sapl.crud.base"
                or _bypass_outer_atomic(candidate.__dict__["dispatch"])
                    is not candidate.__dict__["dispatch"]
            )
            for candidate in mro
        ):
            return "dynamic-data-guard", ("dispatch", view)
        if any(issubclass(base, PermissionRequiredForAppCrudMixin) for base in mro):
            base = PermissionRequiredForAppCrudMixin
            if any(
                ("has_permission" in candidate.__dict__ or "dispatch" in candidate.__dict__)
                and candidate.__module__.startswith("sapl.")
                and candidate.__module__ != "sapl.crud.base"
                for candidate in mro[:mro.index(base)]
            ):
                return "dynamic-data-guard", ("app", view)
            if any("has_permission" in candidate.__dict__ for candidate in mro[:mro.index(base)]):
                return "dynamic-data-guard", ("app", view)
            return "app-permission", view
        if any(issubclass(base, PermissionRequiredContainerCrudMixin) for base in mro):
            base = PermissionRequiredContainerCrudMixin
            if any(
                ("has_permission" in candidate.__dict__ or "dispatch" in candidate.__dict__)
                and candidate.__module__.startswith("sapl.")
                and candidate.__module__ != "sapl.crud.base"
                for candidate in mro[:mro.index(base)]
            ):
                return "dynamic-data-guard", ("container", view)
            if any("has_permission" in candidate.__dict__ for candidate in mro[:mro.index(base)]):
                return "dynamic-data-guard", ("container", view)
            return "container-permission", view
        if any(issubclass(base, PermissionRequiredMixin) for base in mro):
            base = PermissionRequiredMixin
            if any(
                ("has_permission" in candidate.__dict__ or "dispatch" in candidate.__dict__)
                and candidate.__module__.startswith("sapl.")
                and candidate.__module__ != "sapl.crud.base"
                for candidate in mro[:mro.index(base)]
            ):
                return "dynamic-data-guard", ("permission", view)
            if any("has_permission" in candidate.__dict__ for candidate in mro[:mro.index(base)]):
                return "dynamic-data-guard", ("permission", view)
            return "permission", view
        method_contracts = {}
        for method_name in getattr(view, "http_method_names", ()):
            method_view = getattr(view, method_name, None)
            if not callable(method_view):
                continue
            method_permissions = get_permission_requireds(method_view)
            if method_permissions:
                method_contracts[method_name.upper()] = ("permission", tuple(dict.fromkeys(method_permissions)))
                continue
            try:
                method_decorators = get_decorators(inspect.unwrap(method_view))
            except (OSError, TypeError, SyntaxError):
                method_decorators = {}
            method_names = {name for values in method_decorators.values() for name in values}
            if "login_required" in method_names:
                method_contracts[method_name.upper()] = ("login", ())
        if method_contracts:
            return "method-decorators", (view, method_contracts)
        if getattr(view, "permission_classes", None) is not None:
            classes = tuple(view.permission_classes)
            if any(
                "has_permission" in permission.__dict__
                and not permission.__module__.startswith("rest_framework.permissions")
                for permission in classes
            ):
                return "dynamic-data-guard", ("drf", classes)
            return "drf", view
    permissions = get_permission_requireds(view)
    if permissions:
        return "decorator-permission", (view, tuple(dict.fromkeys(permissions)))
    try:
        decorators = get_decorators(inspect.unwrap(view))
    except (OSError, TypeError, SyntaxError):
        decorators = {}
    decorator_names = {name for values in decorators.values() for name in values}
    if "login_required" in decorator_names:
        return "decorator-login", view
    return "undeclared", view


class _PermissionProbe:
    def __init__(self, *, authenticated, permissions=(), apps=(), grant_all=False, staff=False):
        self.is_authenticated = authenticated
        self.is_anonymous = not authenticated
        self.permissions = set(permissions)
        self.apps = set(apps)
        self.grant_all = grant_all
        self.pk = 1
        self.username = "url-auth-probe"
        self.is_active = True
        self.is_staff = staff
        self.is_superuser = staff
        self.groups = ()

    def has_perm(self, permission, obj=None):
        return self.grant_all or permission in self.permissions

    def has_perms(self, permissions, obj=None):
        return all(self.has_perm(permission, obj) for permission in permissions)

    def has_module_perms(self, app_label):
        return self.grant_all or app_label in self.apps

    def __str__(self):
        return self.username


def _replace_function_body(callback, handler):
    chain = [callback]
    while callable(getattr(chain[-1], "__wrapped__", None)):
        chain.append(chain[-1].__wrapped__)
    if len(chain) < 2:
        raise AssertionError("A declared function auth gate has no wrapped handler")
    for wrapper, child in reversed(list(zip(chain[:-1], chain[1:]))):
        for cell in getattr(wrapper, "__closure__", ()) or ():
            try:
                current = cell.cell_contents
            except ValueError:
                continue
            if current is child:
                cell.cell_contents = handler
                return lambda: setattr(cell, "cell_contents", child)
    raise AssertionError("Could not isolate the wrapped function handler")


def _assert_callback_gate(callback, path, kwargs, user, method, expected, policy, monkeypatch, request_fixture, drf=False, container=False, supported=True):
    from django.core.exceptions import PermissionDenied
    from django_ratelimit.exceptions import Ratelimited
    from django.db.models.query import QuerySet
    from types import SimpleNamespace
    from sapl.base.models import AppConfig
    from django.http import HttpResponse
    from django.test import RequestFactory
    from rest_framework.test import force_authenticate

    reached = []

    def handler(request, *args, **view_kwargs):
        reached.append(method)
        return HttpResponse(status=204)

    view_class = getattr(callback, "view_class", getattr(callback, "cls", None))
    if path == "/materia/recuperar-materia":
        request_fixture.getfixturevalue("db")
        probe_callback = callback
    else:
        probe_callback = _bypass_outer_atomic(callback) if view_class is None else callback
    restore = None
    handler_name = method.lower()
    if view_class is not None:
        if drf and hasattr(callback, "actions"):
            handler_name = callback.actions.get(method.lower())
            view_method = getattr(view_class, handler_name, None) if handler_name else None
            allowed = getattr(view_class, "http_method_names", ())
            supported = bool(handler_name) and method.lower() in allowed
        else:
            view_method = getattr(view_class, method.lower(), None)
            allowed = getattr(view_class, "http_method_names", ())
            supported = method.lower() in allowed and callable(view_method)
        if drf and supported:
            from rest_framework.response import Response

            original_initial = view_class.initial

            def gate_then_sentinel(self, request, *args, **view_kwargs):
                original_initial(self, request, *args, **view_kwargs)

                def handler(*handler_args, **handler_kwargs):
                    reached.append(method)
                    return Response(status=204)

                setattr(self, method.lower(), handler)

            monkeypatch.setattr(view_class, "initial", gate_then_sentinel)
        elif (
            supported
            and policy == "method-decorators"
            and callable(getattr(view_method, "__wrapped__", None))
        ):
            restore = _replace_function_body(view_method, handler)
        elif supported:
            monkeypatch.setattr(view_class, handler_name, handler, raising=False)
    else:
        restore = _replace_function_body(probe_callback, handler)

    request = RequestFactory().generic(method, path)
    import hashlib
    import ipaddress

    probe_identity = "|".join((
        path, method, str(user.is_authenticated), str(user.is_staff),
        str(user.grant_all), ",".join(sorted(user.permissions)),
        ",".join(sorted(user.apps)),
    ))
    probe_digest = hashlib.sha256(probe_identity.encode()).hexdigest()
    request.META["REMOTE_ADDR"] = str(ipaddress.IPv6Address(int(probe_digest[:32], 16)))
    user.username = f"url-auth-probe-{probe_digest[:12]}"
    user.pk = int(probe_digest[:8], 16) + 1
    request._dont_enforce_csrf_checks = True
    request.user = user
    if drf:
        force_authenticate(request, user=user if user.is_authenticated else None)
    if container:
        view_class = getattr(callback, "view_class", getattr(callback, "cls", None))
        if view_class is not None:
            original_dispatch = view_class.dispatch
            def dispatch_without_ownership_filter(self, *args, **view_kwargs):
                self.crud.container_field = ""
                assert self.container_field == "", (type(self), self.crud, self.container_field)
                return original_dispatch(self, *args, **view_kwargs)
            monkeypatch.setattr(view_class, "dispatch", dispatch_without_ownership_filter)
    config_probe = SimpleNamespace(documentos_administrativos="R")
    monkeypatch.setattr(AppConfig.objects, "last", lambda: config_probe)
    if drf:
        # Auth probes use static model metadata and never evaluate data querysets.
        monkeypatch.setattr(QuerySet, "first", lambda self: None)
        monkeypatch.setattr(AppConfig.objects, "first", lambda: config_probe)
        monkeypatch.setattr(AppConfig.objects, "last", lambda: config_probe)
        monkeypatch.setattr(
            AppConfig, "attr",
            classmethod(lambda cls, name: getattr(config_probe, name)),
        )
        if view_class is not None and getattr(view_class, "queryset", None) is not None:
            monkeypatch.setattr(
                view_class, "get_queryset", lambda self: self.queryset, raising=False
            )

    denial_reason = None
    try:
        try:
            response = probe_callback(request, **kwargs)
            denied = response.status_code in (302, 401, 403)
        except Ratelimited:
            raise
        except PermissionDenied as exc:
            response = None
            denied = True
            denial_reason = f"{type(exc).__name__}: {exc}"
        if not supported:
            assert not reached, f"{method} {path} alcançou handler inexistente"
            assert response is None or response.status_code in (302, 401, 403, 405), path
        elif expected:
            assert not denied, (
                f"{method} {path} negou perfil autorizado "
                f"(status={getattr(response, 'status_code', None)}, denial={denial_reason}, "
                f"view={getattr(view_class, '__name__', None)}, "
                f"declared={getattr(view_class, 'permission_required', None)})"
            )
            assert reached == [method], f"{method} {path} não alcançou handler sentinela (status={getattr(response, 'status_code', None)})"
            assert response is not None and response.status_code == 204, path
        else:
            assert denied, f"{method} {path} aceitou perfil sem acesso"
            assert not reached, f"{method} {path} alcançou handler antes da negação"
    finally:
        if restore is not None:
            restore()


@pytest.mark.parametrize("url_item", _lista_urls)
def test_sapl_url_resolution_and_declared_auth(url_item, monkeypatch, request):
    """Resolve every route and probe only detectable access contracts.

    Known Django mixins, permission decorators, and standard DRF permission
    classes run through their real callback for GET and POST. Synthetic users
    and handler sentinels isolate the gate. Generic container ownership filters
    and database-backed application configuration are fixed to a restrictive
    mode. Custom data-dependent permission overrides are resolution-only and
    recorded as dynamic-data-guard. Unsupported methods are checked for a
    non-success denial or 405 without claiming auth coverage. This does not
    validate endpoint data, persistence, response content, real group membership,
    object-level get_object/has_object_permission, or PATCH/PUT/DELETE behavior.
    Routes without a detectable contract are resolution-only and are not counted
    as functional authorization coverage. Unsupported HTTP methods are checked
    for a safe denial or 405 only. API/domain behavior needs separate endpoint tests.
    """
    from django.urls import resolve

    callback, url, variables, app_name = url_item
    path, kwargs = _route_request(callback, url, variables)
    match = resolve(path)
    expected_view = getattr(callback, "view_class", getattr(callback, "cls", callback))
    actual_view = getattr(match.func, "view_class", getattr(match.func, "cls", match.func))
    def view_identity(view):
        return (
            getattr(view, '__module__', None),
            getattr(view, '__qualname__', getattr(view, '__name__', None)),
            tuple(sorted(getattr(view, 'actions', {}).items()))
            if isinstance(getattr(view, 'actions', None), dict) else None,
        )

    def view_signature(view):
        if not isinstance(view, type):
            return (
                "function", getattr(view, "__module__", None),
                getattr(view, "__qualname__", getattr(view, "__name__", None)),
            )
        crud = getattr(view, "crud", None)
        model = getattr(view, "model", None) or getattr(crud, "model", None)
        label = getattr(getattr(model, "_meta", None), "label_lower", None)
        crud_name = (
            f"{getattr(crud, '__module__', '')}.{getattr(crud, '__qualname__', '')}"
            if crud is not None else None
        )
        mro_names = {base.__name__.lower() for base in view.mro()}
        action = next((name for name in ("create", "update", "delete", "detail", "list")
                       if any(name in item for item in mro_names)), None)
        return (
            label, crud_name,
            getattr(crud, "parent_field", None),
            getattr(crud, "container_field", None),
            tuple(getattr(view, "permission_required", ()) or ()),
            tuple(getattr(view, "http_method_names", ())),
            getattr(view, "action", None), action,
        )

    expected_signature = view_signature(expected_view)
    actual_signature = view_signature(actual_view)
    same_view = view_identity(actual_view) == view_identity(expected_view)
    if not same_view and isinstance(actual_view, type) and isinstance(expected_view, type):
        same_view = actual_signature == expected_signature
        if not same_view:
            expected_crud = getattr(expected_view, "crud", None)
            expected_model = getattr(expected_crud, "model", None)
            specialized_multicreate = (
                expected_model is not None
                and expected_signature[7] == "create"
                and actual_signature[7] == "create"
                and actual_view.__name__.startswith(expected_model.__name__)
                and actual_view.__name__.endswith("MultiCreateView")
                and getattr(actual_view, "app_label", None) == expected_model._meta.app_label
                and actual_signature[5] == expected_signature[5]
                and any(base.__name__ == "PermissionRequiredForAppCrudMixin"
                        for base in actual_view.mro())
            )
            same_view = specialized_multicreate
    assert same_view, (
        f"{app_name}: {path} resolveu para outra view "
        f"(actual={actual_view!r}, expected={expected_view!r}, "
        f"actual_signature={actual_signature!r}, "
        f"expected_signature={expected_signature!r}, "
        f"initkwargs={getattr(match.func, 'view_initkwargs', None)!r})"
    )

    callback = match.func
    policy, subject = _auth_metadata(callback)
    container = policy == "container-permission"
    if policy == "undeclared":
        return

    profiles = []
    drf = policy == "drf"
    if policy == "container-permission":
        declared = getattr(subject, "permission_required", None)
        assert declared is not None, f"{subject.__name__} não declara permission_required"
        permissions = (declared,) if isinstance(declared, str) else tuple(declared)
        profiles = [
            (_PermissionProbe(authenticated=False), not permissions),
            (_PermissionProbe(authenticated=True), not permissions),
            (_PermissionProbe(authenticated=True, permissions=permissions, grant_all=True), True),
        ]
    if policy == "dynamic-data-guard":
        kind, declared = subject
        if kind in ("container", "permission", "app", "dispatch"):
            if kind == "container":
                required = getattr(declared, "permission_required", None)
                assert required is not None, f"{declared.__name__} não declara permission_required"
            return
        else:
            assert declared and all(callable(getattr(permission, "has_permission", None)) for permission in declared)
        return
    if policy in ("permission", "container-permission"):
        declared = getattr(subject, "permission_required", None)
        assert declared is not None, f"{subject.__name__} não declara permission_required"
        permissions = (declared,) if isinstance(declared, str) else tuple(declared)
        public = not permissions
        profiles = [
            (_PermissionProbe(authenticated=False), public),
            (_PermissionProbe(authenticated=True), public),
            (_PermissionProbe(authenticated=True, permissions=permissions, grant_all=True), True),
        ]
    elif policy == "app-permission":
        apps_required = getattr(subject, "app_label", None)
        if apps_required is None:
            model = getattr(subject, "model", None)
            crud = getattr(subject, "crud", None)
            if crud is not None:
                model = getattr(crud, "model", model)
            assert model is not None, f"{subject.__name__} não declara app_label ou model"
            apps_required = model._meta.app_label
        if isinstance(apps_required, str):
            apps_required = (apps_required,)
        public = not apps_required
        profiles = [
            (_PermissionProbe(authenticated=False), public),
            (_PermissionProbe(authenticated=True), public),
            (_PermissionProbe(authenticated=True, apps=apps_required, grant_all=True), True),
        ]
    elif policy == "decorator-permission":
        view, permissions = subject
        profiles = [
            (_PermissionProbe(authenticated=False), False),
            (_PermissionProbe(authenticated=True), False),
            (_PermissionProbe(authenticated=True, permissions=permissions, grant_all=True), True),
        ]
    elif policy in ("login", "decorator-login"):
        profiles = [
            (_PermissionProbe(authenticated=False), False),
            (_PermissionProbe(authenticated=True), True),
        ]
    elif policy in ("drf", "method-decorators"):
        profiles = None


    for method in ("GET", "POST"):
        method_profiles = profiles
        if policy == "method-decorators":
            contract = subject[1].get(method)
            if contract is None:
                continue
            contract_kind, contract_permissions = contract
            if contract_kind == "permission":
                method_profiles = [
                    (_PermissionProbe(authenticated=False), False),
                    (_PermissionProbe(authenticated=True), False),
                    (_PermissionProbe(authenticated=True, permissions=contract_permissions, grant_all=True), True),
                ]
            else:
                method_profiles = [
                    (_PermissionProbe(authenticated=False), False),
                    (_PermissionProbe(authenticated=True), True),
                ]
        view_class = getattr(callback, "view_class", getattr(callback, "cls", None))
        if drf and hasattr(callback, "actions"):
            supported = (
                bool(callback.actions.get(method.lower()))
                and method.lower() in getattr(view_class, "http_method_names", ())
            )
        elif view_class is not None:
            supported = method.lower() in getattr(view_class, "http_method_names", ()) and callable(getattr(view_class, method.lower(), None))
        else:
            declared_methods = _declared_function_methods(callback)
            supported = not declared_methods or method in declared_methods
        if drf and not supported:
            method_profiles = [(_PermissionProbe(authenticated=False), False)]
        elif drf:
            from rest_framework.permissions import (
                AllowAny, DjangoModelPermissions, DjangoModelPermissionsOrAnonReadOnly,
                IsAdminUser, IsAuthenticated, IsAuthenticatedOrReadOnly,
            )
            from sapl.rules.map_rules import rules_patterns_public

            permission_classes = tuple(getattr(subject, "permission_classes", ()))
            names = {permission.__name__ for permission in permission_classes}
            safe = method in ("GET", "HEAD", "OPTIONS")
            model = getattr(getattr(subject, "queryset", None), "model", None)
            required = set()
            public = False
            sapl_permissions = any(issubclass(pc, DjangoModelPermissions) for pc in permission_classes)
            if model is not None and sapl_permissions:
                mapping = getattr(permission_classes[0], "perms_map", {})
                required = {
                    template % {"app_label": model._meta.app_label,
                                "model_name": model._meta.model_name}
                    for template in mapping.get(method, ())
                }
                key = f"{model._meta.app_label}:{model._meta.model_name}"
                public = bool(required) and required.issubset(rules_patterns_public.get(key, set()))
            ignored = bool(getattr(subject, "_ignore_model_permissions", False))
            public_get_override = method == "GET" and any(
                permission.__name__ in {"ProposicaoPermission", "ParlamentarPermission"}
                for permission in permission_classes
            )
            if public_get_override or ignored or not names or names <= {AllowAny.__name__}:
                method_profiles = [(_PermissionProbe(authenticated=False), True),
                                   (_PermissionProbe(authenticated=True), True)]
            elif IsAdminUser.__name__ in names:
                method_profiles = [(_PermissionProbe(authenticated=False), False),
                                   (_PermissionProbe(authenticated=True), False),
                                   (_PermissionProbe(authenticated=True, grant_all=True, staff=True), True)]
            elif IsAuthenticatedOrReadOnly.__name__ in names and safe:
                method_profiles = [(_PermissionProbe(authenticated=False), True),
                                   (_PermissionProbe(authenticated=True), True)]
            elif DjangoModelPermissionsOrAnonReadOnly.__name__ in names and safe and public:
                method_profiles = [(_PermissionProbe(authenticated=False), True),
                                   (_PermissionProbe(authenticated=True), True)]
            elif sapl_permissions and public and safe:
                method_profiles = [(_PermissionProbe(authenticated=False), True),
                                   (_PermissionProbe(authenticated=True), True),
                                   (_PermissionProbe(authenticated=True, grant_all=True), True)]
            elif sapl_permissions or DjangoModelPermissions.__name__ in names or DjangoModelPermissionsOrAnonReadOnly.__name__ in names:
                if safe and not sapl_permissions:
                    method_profiles = [(_PermissionProbe(authenticated=False), False),
                                       (_PermissionProbe(authenticated=True), True)]
                else:
                    method_profiles = [(_PermissionProbe(authenticated=False), False),
                                       (_PermissionProbe(authenticated=True), False),
                                       (_PermissionProbe(authenticated=True, grant_all=True), True)]
            elif IsAuthenticated.__name__ in names:
                method_profiles = [(_PermissionProbe(authenticated=False), False),
                                   (_PermissionProbe(authenticated=True), True)]
            else:
                method_profiles = [(_PermissionProbe(authenticated=False), False),
                                   (_PermissionProbe(authenticated=True), False),
                                   (_PermissionProbe(authenticated=True, grant_all=True, staff=True), True)]
        for user, expected in method_profiles:
            _assert_callback_gate(
                callback, path, kwargs, user, method, expected, policy, monkeypatch, request,
                drf=drf, container=container, supported=supported,
            )



@pytest.mark.django_db
def test_robots_txt_get(admin_client):
    response = admin_client.get("/robots.txt")

    assert response.status_code == 200
    assert response["content-type"] == "text/plain"

    lines = response.content.decode().splitlines()
    assert lines[0] == "User-agent: semrushbot"
