"""Small Django 5 compatible port of django-admin-bootstrapped template tags.
Original package is Apache-2.0; see adjacent license notice.
"""
from django import template
from django.conf import settings
from django.forms import CheckboxInput, CheckboxSelectMultiple, RadioSelect
from django.template.loader import render_to_string

register = template.Library()


@register.simple_tag(takes_context=True)
def render_with_template_if_exist(context, template_name, fallback):
    try:
        return render_to_string(template_name, context.flatten())
    except Exception:
        return fallback


@register.simple_tag(takes_context=True)
def language_selector(context):
    if not getattr(settings, "USE_I18N", False):
        return ""
    try:
        return render_to_string("admin/language_selector.html", context.flatten())
    except Exception:
        return ""


def _column_width(lines):
    try:
        return 12 // max(len(list(line)) for line in lines)
    except (ValueError, ZeroDivisionError):
        return 12


@register.filter(name="column_width")
def column_width(value):
    try:
        return 12 // len(list(value))
    except (TypeError, ValueError, ZeroDivisionError):
        return 12


@register.filter(name="form_fieldset_column_width")
def form_fieldset_column_width(form):
    return _column_width(line for fieldset in form for line in fieldset)


@register.filter(name="fieldset_column_width")
def fieldset_column_width(fieldset):
    return _column_width(fieldset)


@register.simple_tag(takes_context=True)
def render_app_name(context, app, template="/admin_app_name.html"):
    try:
        return render_to_string(app["app_label"] + template, context.flatten())
    except Exception:
        return app["name"]


@register.simple_tag(takes_context=True)
def render_app_label(context, app, fallback=""):
    try:
        return app["app_label"]
    except (KeyError, TypeError):
        return app if isinstance(app, str) else fallback


@register.simple_tag(takes_context=True)
def render_app_description(context, app, fallback="", template="/admin_app_description.html"):
    try:
        return render_to_string(app["app_label"] + template, context.flatten())
    except Exception:
        return fallback


@register.simple_tag(name="dab_field_rendering")
def custom_field_rendering(field, *args, **kwargs):
    """Render a BoundField with Bootstrap 3 classes, without external packages."""
    if not hasattr(field, "as_widget") or not hasattr(field, "field"):
        return field
    widget = field.field.widget
    attrs = dict(getattr(widget, "attrs", {}))
    if not isinstance(widget, (CheckboxInput, CheckboxSelectMultiple, RadioSelect)):
        classes = attrs.get("class", "").split()
        if "form-control" not in classes:
            classes.append("form-control")
        attrs["class"] = " ".join(classes)
    return field.as_widget(attrs=attrs)
