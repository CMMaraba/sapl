"""Pillow-only image helpers, independently testable without Django."""

import io
import os

from PIL import Image, ImageOps

from .image_geometry import parse_crop_box

_RESAMPLING = getattr(getattr(Image, "Resampling", Image), "LANCZOS")


def read_source(source):
    if source is None:
        return None
    if isinstance(source, Image.Image):
        buffer = io.BytesIO()
        source.copy().save(buffer, format="PNG")
        return buffer.getvalue()
    if isinstance(source, (bytes, bytearray)):
        return bytes(source)
    if isinstance(source, (str, os.PathLike)):
        with open(os.fspath(source), "rb") as stream:
            return stream.read()

    path = getattr(source, "path", None)
    if path and not hasattr(source, "read"):
        with open(path, "rb") as stream:
            return stream.read()

    if hasattr(source, "read"):
        position = None
        try:
            position = source.tell()
            source.seek(0)
        except (AttributeError, IOError, OSError):
            pass
        data = source.read()
        if position is not None:
            try:
                source.seek(position)
            except (AttributeError, IOError, OSError):
                pass
        return data
    raise TypeError("Expected an image, path, or readable file")


def pil_image(source, exif_orientation=True):
    data = read_source(source)
    if not data:
        return None
    with io.BytesIO(data) as stream:
        image = Image.open(stream)
        image.load()
        image = image.copy()
    if exif_orientation:
        image = ImageOps.exif_transpose(image)
    return image


def render_thumbnail(source, options=None, default_size=(256, 256)):
    """Return (encoded bytes, extension) without changing the source image."""
    options = dict(options or {})
    data = read_source(source)
    if not data:
        return b"", "jpg"

    size = options.get("size") or default_size
    size = (max(1, int(size[0])), max(1, int(size[1])))
    image = pil_image(data, exif_orientation=options.get("exif_orientation", True))
    box, fullsize = parse_crop_box(options.get("box"))
    crop = bool(options.get("crop")) and not fullsize

    if crop and box:
        x1, y1, x2, y2 = box
        x1 = min(max(x1, 0), image.width)
        y1 = min(max(y1, 0), image.height)
        x2 = min(max(x2, x1 + 1), image.width)
        y2 = min(max(y2, y1 + 1), image.height)
        image = image.crop((x1, y1, x2, y2))

    if crop or options.get("detail"):
        image = ImageOps.fit(image, size, method=_RESAMPLING)
    elif not options.get("upscale"):
        image.thumbnail(size, _RESAMPLING)
    else:
        image = ImageOps.contain(image, size, method=_RESAMPLING)

    has_alpha = image.mode in ("RGBA", "LA") or (
        image.mode == "P" and "transparency" in image.info
    )
    image_format = "PNG" if has_alpha else "JPEG"
    if image_format == "JPEG" and image.mode not in ("RGB", "L"):
        image = image.convert("RGB")
    if image_format == "JPEG" and image.mode == "L":
        image = image.convert("RGB")

    output = io.BytesIO()
    image.save(output, format=image_format, quality=88, optimize=True)
    return output.getvalue(), ("png" if image_format == "PNG" else "jpg")
