"""Compatibility template tag for the former image-cropping package."""
import logging

from django import template
from django.conf import settings

from sapl.modern_components.images import get_backend

register = template.Library()
logger = logging.getLogger(__name__)


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
        box = getattr(instance, str(ratio_field), None)
        if getattr(ratio, "free_crop", False):
            # Free crop keeps the selection's own size, as image_cropping did.
            options = {"free_crop": True, "scale": scale, "box": box, "crop": True}
        else:
            options = {
                "size": (
                    max(1, int(round(ratio.width * scale))),
                    max(1, int(round(ratio.height * scale))),
                ),
                "box": box,
                "crop": True,
            }
    except (AttributeError, TypeError, ValueError, OverflowError):
        return ""
    try:
        return get_backend().get_thumbnail_url(image, options)
    except Exception:
        # Like the former tag: a broken image must not break the page.
        if getattr(settings, "THUMBNAIL_DEBUG", False):
            raise
        logger.warning("Falha ao gerar miniatura de %s", image, exc_info=True)
        return ""
