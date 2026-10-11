"""Compatibility template tag for the former image-cropping package."""
from django import template

from sapl.modern_components.images import get_backend

register = template.Library()


@register.simple_tag
def cropped_thumbnail(instance, ratio_field, scale=1):
    """Return a cached thumbnail URL using a persisted XYXY crop box."""
    if instance is None:
        return ""
    try:
        ratio = instance._meta.get_field(str(ratio_field))
        image = getattr(instance, ratio.image_field, None)
        if ratio.image_fk_field and image:
            image = getattr(image, ratio.image_fk_field, None)
        if not image:
            return ""
        scale = float(scale)
        if scale <= 0:
            return ""
        size = (
            max(1, int(round(ratio.width * scale))),
            max(1, int(round(ratio.height * scale))),
        )
        options = {
            "size": size,
            "box": getattr(instance, str(ratio_field), None),
            "crop": True,
        }
    except (AttributeError, TypeError, ValueError, OverflowError):
        return ""
    return get_backend().get_thumbnail_url(image, options)
