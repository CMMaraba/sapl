import ast
import inspect
import os

if __name__ == '__main__':

    import django

    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "sapl.settings")
    django.setup()

if True:
    from scripts.lista_urls import lista_urls


def get_decorators(cls):
    target = cls
    decorators = {}

    def visit_functionDef(node):
        decorators[node.name] = []
        for n in node.decorator_list:
            name = ''
            if isinstance(n, ast.Call):
                name = n.func.attr if isinstance(
                    n.func, ast.Attribute) else n.func.id
            else:
                name = n.attr if isinstance(n, ast.Attribute) else n.id

            decorators[node.name].append(name)

    node_iter = ast.NodeVisitor()
    node_iter.visit_functionDef = visit_functionDef
    node_iter.visit(ast.parse(inspect.getsource(target)))
    return decorators


def get_permission_requireds(cls):
    from django.contrib.auth.decorators import permission_required
    from django.utils.decorators import method_decorator
    import textwrap

    from pathlib import Path

    target = cls
    if not (inspect.isclass(target) or inspect.isfunction(target)
            or inspect.ismethod(target)):
        target = type(target)

    module = inspect.getmodule(target)
    namespace = vars(module) if module is not None else {}
    try:
        tree = ast.parse(textwrap.dedent(inspect.getsource(target)))
    except (OSError, TypeError) as source_error:
        module_path = getattr(module, "__file__", None)
        if not module_path:
            raise source_error
        module_tree = ast.parse(
            Path(module_path).read_text(encoding="utf-8")
        )
        target_name = getattr(target, "__name__", "")
        candidates = [
            node for node in ast.walk(module_tree)
            if isinstance(node, (ast.ClassDef, ast.FunctionDef,
                                 ast.AsyncFunctionDef))
            and node.name == target_name
        ]
        if len(candidates) == 1:
            tree = ast.Module(body=candidates, type_ignores=[])
        elif inspect.isclass(target):
            source_nodes = []
            for member in vars(target).values():
                if isinstance(member, (classmethod, staticmethod)):
                    member = member.__func__
                if not inspect.isfunction(member):
                    continue
                member = inspect.unwrap(member)
                if not getattr(member, "__module__", "").startswith("sapl."):
                    continue
                try:
                    member_source = textwrap.dedent(inspect.getsource(member))
                    source_nodes.extend(ast.parse(member_source).body)
                except (OSError, TypeError) as member_error:
                    line = getattr(getattr(member, "__code__", None),
                                   "co_firstlineno", None)
                    matches = [
                        node for node in ast.walk(module_tree)
                        if isinstance(node, (ast.FunctionDef,
                                             ast.AsyncFunctionDef))
                        and node.name == getattr(member, "__name__", "")
                        and node.lineno == line
                    ]
                    if len(matches) == 1:
                        source_nodes.extend(matches)
                    else:
                        raise member_error
            if not source_nodes:
                raise source_error
            tree = ast.Module(body=source_nodes, type_ignores=[])
        else:
            raise source_error
    decorators = []

    def resolve(expression):
        if isinstance(expression, ast.Name):
            return namespace.get(expression.id)
        if isinstance(expression, ast.Attribute):
            owner = resolve(expression.value)
            return getattr(owner, expression.attr, None)
        return None

    def string_values(expression):
        if isinstance(expression, ast.Constant):
            return [expression.value] if isinstance(expression.value, str) else []
        if isinstance(expression, (ast.Tuple, ast.List)):
            values = []
            for element in expression.elts:
                values.extend(string_values(element))
            return values
        return []

    def permission_values(call):
        if call.args:
            argument = call.args[0]
        else:
            argument = next(
                (keyword.value for keyword in call.keywords
                 if keyword.arg == "perm"),
                None
            )
        return string_values(argument) if argument is not None else []

    def collect_decorator(expression):
        if isinstance(expression, (ast.Tuple, ast.List)):
            for element in expression.elts:
                collect_decorator(element)
            return
        if not isinstance(expression, ast.Call):
            return
        resolved = resolve(expression.func)
        if resolved is permission_required:
            decorators.extend(permission_values(expression))
        elif resolved is method_decorator:
            if expression.args:
                collect_decorator(expression.args[0])
            else:
                decorator_arg = next(
                    (keyword.value for keyword in expression.keywords
                     if keyword.arg == "decorator"),
                    None
                )
                if decorator_arg is not None:
                    collect_decorator(decorator_arg)

    class PermissionDecoratorVisitor(ast.NodeVisitor):
        def visit_ClassDef(self, node):
            for decorator in node.decorator_list:
                collect_decorator(decorator)
            self.generic_visit(node)

        def visit_FunctionDef(self, node):
            for decorator in node.decorator_list:
                collect_decorator(decorator)
            self.generic_visit(node)

        visit_AsyncFunctionDef = visit_FunctionDef

    PermissionDecoratorVisitor().visit(tree)
    return decorators


class ListaPermissionInDecorators:
    def __init__(self):
        self.decorators = []

    def lista_permissions_in_decorators(self):
        self.decorators = []
        urls = lista_urls()

        for url_item in urls:
            key, url, var, app_name = url_item
            if hasattr(key, 'view_class'):
                view = key.view_class
            elif hasattr(key, 'cls'):
                view = key.cls
            else:
                view = key

            if not getattr(view, '__module__', '').startswith('sapl.'):
                continue

            self.decorators.extend(
                (permission, view)
                for permission in get_permission_requireds(view)
            )
        return self.decorators

    def __call__(self):
        return self.lista_permissions_in_decorators()


lista_permissions_in_decorators = ListaPermissionInDecorators()

if __name__ == '__main__':
    _lista_permissions_in_decorators = lista_permissions_in_decorators()
    print(_lista_permissions_in_decorators)
