"""Pillow-only image helpers, independently testable without Django."""

import io
import os

from PIL import Image, ImageOps

from .image_geometry import normalize_orientation, parse_crop_box

_RESAMPLING = getattr(getattr(Image, "Resampling", Image), "LANCZOS")
_TRANSPOSE = getattr(Image, "Transpose", Image)
_ORIENTATION_TRANSPOSE = {
    2: _TRANSPOSE.FLIP_LEFT_RIGHT,
    3: _TRANSPOSE.ROTATE_180,
    4: _TRANSPOSE.FLIP_TOP_BOTTOM,
    5: _TRANSPOSE.TRANSPOSE,
    6: _TRANSPOSE.ROTATE_270,
    7: _TRANSPOSE.TRANSVERSE,
    8: _TRANSPOSE.ROTATE_90,
}
_EXIF_ORIENTATION = 0x0112


def _read_stream(source):
    position = None
    try:
        position = source.tell()
        source.seek(0)
    except (AttributeError, OSError):
        pass
    data = source.read()
    if position is not None:
        try:
            source.seek(position)
        except (AttributeError, OSError):
            pass
    return data


def _read_from_storage(source):
    with source.storage.open(source.name, "rb") as stream:
        return stream.read()


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

    # Committed FieldFile: read through a short-lived handle instead of
    # opening (and keeping) the FieldFile's own cached file.
    stored = (
        getattr(source, "storage", None) is not None
        and getattr(source, "name", None)
        and getattr(source, "_committed", False)
    )
    if stored:
        current = getattr(source, "_file", None)
        if current is None or getattr(current, "closed", False):
            return _read_from_storage(source)

    path = getattr(source, "path", None)
    if path and not hasattr(source, "read"):
        with open(path, "rb") as stream:
            return stream.read()

    if hasattr(source, "read"):
        try:
            return _read_stream(source)
        except ValueError:
            # The cached handle was closed elsewhere in the request.
            if stored:
                return _read_from_storage(source)
            raise
    raise TypeError("Expected an image, path, or readable file")


def exif_orientation(image):
    try:
        return normalize_orientation(image.getexif().get(_EXIF_ORIENTATION, 1))
    except Exception:
        return 1


def orient(image, orientation):
    method = _ORIENTATION_TRANSPOSE.get(normalize_orientation(orientation))
    return image.transpose(method) if method is not None else image


def _open(data):
    """Return (detached image, EXIF orientation) without transposing it."""
    with io.BytesIO(data) as stream:
        with Image.open(stream) as image:
            orientation = exif_orientation(image)
            image.load()
            return image.copy(), orientation


def image_info(source):
    """Return (stored width, stored height, EXIF orientation)."""
    data = read_source(source)
    if not data:
        return None
    with io.BytesIO(data) as stream:
        with Image.open(stream) as image:
            return image.width, image.height, exif_orientation(image)


def pil_image(source, exif_orientation=True):
    data = read_source(source)
    if not data:
        return None
    image, orientation = _open(data)
    if exif_orientation:
        image = orient(image, orientation)
    return image


def render_thumbnail(source, options=None, default_size=(256, 256)):
    """Return (encoded bytes, extension) without changing the source image.

    The crop box is applied in stored pixels and the EXIF orientation only
    afterwards, so persisted boxes keep selecting the same region as before.
    """
    options = dict(options or {})
    data = read_source(source)
    if not data:
        return b"", "jpg"

    size = options.get("size") or default_size
    size = (max(1, int(size[0])), max(1, int(size[1])))
    image, orientation = _open(data)
    if not options.get("exif_orientation", True):
        orientation = 1
    box, fullsize = parse_crop_box(options.get("box"))
    crop = bool(options.get("crop")) and not fullsize

    if crop and box:
        x1, y1, x2, y2 = box
        x1 = min(max(x1, 0), image.width - 1)
        y1 = min(max(y1, 0), image.height - 1)
        x2 = min(max(x2, x1 + 1), image.width)
        y2 = min(max(y2, y1 + 1), image.height)
        image = image.crop((x1, y1, x2, y2))
    image = orient(image, orientation)

    if options.get("free_crop"):
        # Former image_cropping free crop: natural size of the selection,
        # optionally reduced by scale, never enlarged.
        scale = float(options.get("scale") or 1)
        if 0 < scale < 1:
            image = image.resize(
                (max(1, round(image.width * scale)), max(1, round(image.height * scale))),
                _RESAMPLING,
            )
    elif crop or options.get("detail"):
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
