"""Django integration for SAPL image cropping and thumbnail generation.

Crop values remain "x1,y1,x2,y2" in the stored file's pixels, before EXIF
orientation, as in the former django-image-cropping pipeline.
"""
import hashlib
import json
import logging

from django import forms
from django.conf import settings
from django.contrib.admin.widgets import AdminFileWidget
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from django.db import models, transaction
from django.db.models import signals
from django.templatetags.static import static

from .image_geometry import (box_to_stored, max_cropping, oriented_size,
                             serialize_crop_box)
from .image_processing import image_info, read_source, render_thumbnail

logger = logging.getLogger(__name__)

THUMBNAIL_ROOT = "sapl-thumbnails"
# Bump when rendering semantics change so stale cache files are not reused.
THUMBNAIL_VERSION = 2


def _setting(name, default):
    try:
        return getattr(settings, name, default)
    except Exception:
        return default


def _storage_for(source):
    return getattr(source, "storage", None) or default_storage


def thumbnail_folder(source_name):
    """Per-source cache folder, so thumbnails can be removed with the source."""
    digest = hashlib.sha256(str(source_name).encode("utf-8")).hexdigest()
    return "{}/{}/{}".format(THUMBNAIL_ROOT, digest[:2], digest)


def delete_thumbnails(source_name, storage=None):
    """Remove every cached thumbnail generated from source_name."""
    if not source_name:
        return
    storage = storage or default_storage
    folder = thumbnail_folder(source_name)
    try:
        _dirs, files = storage.listdir(folder)
    except (OSError, NotImplementedError):
        return
    for filename in files:
        try:
            storage.delete("{}/{}".format(folder, filename))
        except OSError:
            logger.warning("Falha ao remover miniatura %s/%s", folder, filename)


def _source_identity(source, storage):
    """Return (cache folder, cache identity, bytes or None).

    Committed files are identified by name, size and modification time, so a
    cached thumbnail is found without reading the source image.
    """
    name = getattr(source, "name", None)
    if name and getattr(source, "_committed", False):
        try:
            size = storage.size(name)
            modified = storage.get_modified_time(name).timestamp()
        except (AttributeError, NotImplementedError, OSError, ValueError):
            pass
        else:
            return thumbnail_folder(name), "{}|{}|{}".format(name, size, modified), None
    data = read_source(source)
    if not data:
        return None, None, None
    digest = hashlib.sha256(data).hexdigest()
    return thumbnail_folder("sha256:" + digest), digest, data


class PillowImageBackend:
    def __init__(self, **kwargs):
        self.kwargs = kwargs

    def get_source_info(self, image):
        """Return (stored width, stored height, EXIF orientation)."""
        return image_info(image)

    def get_size(self, image):
        """Displayed (EXIF oriented) size."""
        width, height, orientation = image_info(image)
        return oriented_size(width, height, orientation)

    def get_thumbnail_url(self, image_path, thumbnail_options):
        options = dict(thumbnail_options or {})
        default_size = _setting("IMAGE_CROPPING_THUMB_SIZE", (256, 256))
        size = options.get("size") or default_size
        options["size"] = (max(1, int(size[0])), max(1, int(size[1])))
        storage = _storage_for(image_path)
        folder, identity, data = _source_identity(image_path, storage)
        if identity is None:
            return ""
        signature = hashlib.sha256()
        signature.update(identity.encode("utf-8"))
        signature.update(json.dumps(
            {"options": options, "version": THUMBNAIL_VERSION},
            sort_keys=True, default=str,
        ).encode("utf-8"))
        names = {}
        # Probe both supported formats without decoding or resizing the source.
        for extension in ("jpg", "png"):
            candidate = signature.copy()
            candidate.update(extension.encode("ascii"))
            name = "{}/{}.{}".format(folder, candidate.hexdigest(), extension)
            names[extension] = name
            if storage.exists(name):
                return storage.url(name)
        if data is None:
            data = read_source(image_path)
        rendered, extension = render_thumbnail(data, options, default_size)
        name = names[extension]
        saved = storage.save(name, ContentFile(rendered))
        if saved != name:
            # A concurrent request stored the same thumbnail first.
            storage.delete(saved)
        return storage.url(name)


_BACKEND = None


def get_backend():
    global _BACKEND
    if _BACKEND is None:
        _BACKEND = PillowImageBackend()
    return _BACKEND


def _crop_media():
    return forms.Media(
        css={"all": [static("modern_components/crop.css")]},
        js=[static("modern_components/crop.js")],
    )


class CropMediaMixin:
    @property
    def media(self):
        return _crop_media()


class CropWidget(CropMediaMixin, forms.TextInput):
    """Ratio-field widget carrying the native crop UI."""


def _image_widget_attrs(image, field_name):
    try:
        width, height, orientation = get_backend().get_source_info(image)
        width, height = oriented_size(width, height, orientation)
        attrs = {
            "class": "sapl-crop-source",
            "data-field-name": field_name,
            "data-org-width": str(width),
            "data-org-height": str(height),
            "data-exif-orientation": str(orientation),
        }
        try:
            attrs["data-image-url"] = image.url
        except (AttributeError, ValueError, OSError):
            pass
        return attrs
    except (OSError, ValueError, TypeError, AttributeError):
        return {}


class ImageCropWidget(CropMediaMixin, AdminFileWidget):
    def render(self, name, value, attrs=None, renderer=None):
        attrs = dict(attrs or {})
        classes = attrs.get("class", "").split()
        if "sapl-crop-source" not in classes:
            classes.append("sapl-crop-source")
        attrs["class"] = " ".join(classes)
        if value:
            attrs.update(_image_widget_attrs(value, name))
        if renderer is None:
            return super().render(name, value, attrs)
        return super().render(name, value, attrs, renderer=renderer)


class ImageCropField(models.ImageField):
    def formfield(self, **kwargs):
        kwargs.setdefault("widget", ImageCropWidget)
        return super().formfield(**kwargs)


class ImageRatioField(models.CharField):
    def __init__(
        self,
        image_field,
        size="0x0",
        free_crop=False,
        adapt_rotation=False,
        allow_fullsize=False,
        verbose_name=None,
        help_text=None,
        hide_image_field=False,
        size_warning=None,
        **kwargs
    ):
        if "__" in image_field:
            self.image_field, self.image_fk_field = image_field.split("__", 1)
        else:
            self.image_field, self.image_fk_field = image_field, None
        try:
            self.width, self.height = [int(value) for value in size.split("x", 1)]
        except (AttributeError, TypeError, ValueError):
            raise ValueError("size must be expressed as WIDTHxHEIGHT")
        self.free_crop = bool(free_crop)
        self.adapt_rotation = bool(adapt_rotation)
        self.allow_fullsize = bool(allow_fullsize)
        self.size_warning = bool(_setting("IMAGE_CROPPING_SIZE_WARNING", True) if size_warning is None else size_warning)
        self.hide_image_field = bool(hide_image_field)
        thumb_size = _setting("IMAGE_CROPPING_THUMB_SIZE", (300, 300))
        self.box_max_width, self.box_max_height = thumb_size
        max_length = kwargs.pop("max_length", 255)
        default = kwargs.pop("default", "")
        blank = kwargs.pop("blank", True)
        super().__init__(
            max_length=max_length,
            default=default,
            blank=blank,
            verbose_name=verbose_name,
            help_text=help_text,
            **kwargs
        )

    def deconstruct(self):
        name, path, _args, kwargs = super().deconstruct()
        kwargs.update({
            "free_crop": self.free_crop,
            "adapt_rotation": self.adapt_rotation,
            "allow_fullsize": self.allow_fullsize,
            "hide_image_field": self.hide_image_field,
            "size_warning": self.size_warning,
        })
        args = (
            self.image_field,
            "{}x{}".format(self.width, self.height),
        )
        return name, path, args, kwargs

    def contribute_to_class(self, cls, name, **kwargs):
        super().contribute_to_class(cls, name, **kwargs)
        if cls._meta.abstract:
            return
        if "crop_fields" not in cls.__dict__:
            cls.add_to_class("crop_fields", {})
        cls.crop_fields[self.image_field] = {
            "fk_field": self.image_fk_field,
            "hidden": self.hide_image_field,
        }
        if "ratio_fields" not in cls.__dict__:
            cls.add_to_class("ratio_fields", [])
        cls.ratio_fields.append(name)
        signals.pre_save.connect(self.initial_cropping, sender=cls, weak=False)
        if not self.image_fk_field:
            signals.pre_save.connect(self.discard_stale_thumbnails, sender=cls, weak=False)

    def discard_stale_thumbnails(self, sender, instance, raw=False, **kwargs):
        """Drop cached thumbnails when the crop or the source image changes."""
        if raw or instance.pk is None:
            return
        previous = sender._default_manager.filter(pk=instance.pk).values_list(
            self.image_field, self.name
        ).first()
        if not previous:
            return
        old_image, old_box = previous
        image = getattr(instance, self.image_field, None)
        current_image = getattr(image, "name", None) or ""
        current_box = getattr(instance, self.name, "") or ""
        if not old_image or (old_image == current_image and (old_box or "") == current_box):
            return
        storage = sender._meta.get_field(self.image_field).storage
        transaction.on_commit(lambda: delete_thumbnails(old_image, storage))

    def initial_cropping(self, sender, instance, *args, **kwargs):
        for ratiofieldname in getattr(instance, "ratio_fields", ()):
            if getattr(instance, ratiofieldname, ""):
                continue
            ratiofield = instance._meta.get_field(ratiofieldname)
            image = getattr(instance, ratiofield.image_field, None)
            if ratiofield.image_fk_field and image:
                image = getattr(image, ratiofield.image_fk_field, None)
            if not image:
                continue
            try:
                width, height, orientation = get_backend().get_source_info(image)
            except (AttributeError, ValueError, OSError, TypeError):
                try:
                    width, height, orientation = image.width, image.height, 1
                except (AttributeError, ValueError, OSError, TypeError):
                    continue
            # Centre the default box on the displayed image, then persist it
            # in stored pixels like every other box.
            display_width, display_height = oriented_size(width, height, orientation)
            box = max_cropping(
                ratiofield.width,
                ratiofield.height,
                display_width,
                display_height,
                free_crop=ratiofield.free_crop,
            )
            box = box_to_stored(box, width, height, orientation)
            setattr(instance, ratiofieldname, serialize_crop_box(box))

    def formfield(self, *args, **kwargs):
        ratio = float(self.width) / self.height if self.height and not self.free_crop else 0
        attrs = {
            "data-min-width": self.width,
            "data-min-height": self.height,
            "data-box-max-width": self.box_max_width,
            "data-box-max-height": self.box_max_height,
            "data-ratio": ratio,
            "data-image-field": self.image_field,
            "data-my-name": self.name,
            "data-adapt-rotation": str(self.adapt_rotation).lower(),
            "data-allow-fullsize": str(self.allow_fullsize).lower(),
            "data-size-warning": str(self.size_warning).lower(),
            "data-hide-image-field": str(self.hide_image_field).lower(),
            "class": "image-ratio",
        }
        kwargs["widget"] = CropWidget(attrs=attrs)
        return super().formfield(*args, **kwargs)
