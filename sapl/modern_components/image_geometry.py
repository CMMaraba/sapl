"""Pure helpers for the persisted SAPL crop-box format.

Persisted boxes use the stored file pixels, before EXIF orientation, as the
former django-image-cropping and easy-thumbnails pipeline did.
"""


def max_cropping(width, height, image_width, image_height, free_crop=False):
    image_width, image_height = int(image_width), int(image_height)
    if image_width <= 0 or image_height <= 0:
        return [0, 0, max(image_width, 0), max(image_height, 0)]
    if free_crop or width <= 0 or height <= 0:
        return [0, 0, image_width, image_height]

    ratio = float(width) / float(height)
    if image_width < image_height * ratio:
        offset = int(round((image_height - image_width / ratio) / 2.0))
        return [0, offset, image_width, image_height - offset]
    offset = int(round((image_width - image_height * ratio) / 2.0))
    return [offset, 0, image_width - offset, image_height]


def parse_crop_box(value):
    """Return ((x1,y1,x2,y2) or None, fullsize_marker)."""
    if value is None:
        return None, False
    if isinstance(value, (tuple, list)):
        parts, fullsize = list(value), False
    else:
        text = str(value).strip()
        fullsize = text.startswith("-")
        if fullsize:
            text = text[1:]
        parts = text.split(",")
    try:
        coords = [int(part) for part in parts]
    except (TypeError, ValueError):
        return None, fullsize
    if len(coords) != 4:
        return None, fullsize
    x1, y1, x2, y2 = coords
    if x1 < 0 or y1 < 0 or x2 <= x1 or y2 <= y1:
        return None, fullsize
    return (x1, y1, x2, y2), fullsize


def serialize_crop_box(box, fullsize=False):
    if box is None or len(box) != 4:
        return ""
    text = ",".join(str(int(value)) for value in box)
    return "-" + text if fullsize else text


# EXIF orientations 5 to 8 swap width and height when displayed.
_SWAPS_AXES = frozenset((5, 6, 7, 8))


def normalize_orientation(value):
    try:
        value = int(value)
    except (TypeError, ValueError):
        return 1
    return value if 1 <= value <= 8 else 1


def oriented_size(width, height, orientation):
    if normalize_orientation(orientation) in _SWAPS_AXES:
        return height, width
    return width, height


def _to_oriented(x, y, width, height, orientation):
    """Map a point from stored pixels to displayed (EXIF oriented) pixels."""
    return {
        2: (width - x, y),
        3: (width - x, height - y),
        4: (x, height - y),
        5: (y, x),
        6: (height - y, x),
        7: (height - y, width - x),
        8: (y, width - x),
    }.get(orientation, (x, y))


def _to_stored(x, y, width, height, orientation):
    """Inverse of _to_oriented; width and height are the stored dimensions."""
    return {
        2: (width - x, y),
        3: (width - x, height - y),
        4: (x, height - y),
        5: (y, x),
        6: (y, height - x),
        7: (width - y, height - x),
        8: (width - y, x),
    }.get(orientation, (x, y))


def _map_box(mapper, box, width, height, orientation):
    if box is None:
        return None
    x1, y1, x2, y2 = box
    ax, ay = mapper(x1, y1, width, height, normalize_orientation(orientation))
    bx, by = mapper(x2, y2, width, height, normalize_orientation(orientation))
    return [min(ax, bx), min(ay, by), max(ax, bx), max(ay, by)]


def box_to_oriented(box, width, height, orientation):
    """Convert a persisted box (stored pixels) to displayed coordinates."""
    return _map_box(_to_oriented, box, width, height, orientation)


def box_to_stored(box, width, height, orientation):
    """Convert a displayed box to persisted stored-pixel coordinates."""
    return _map_box(_to_stored, box, width, height, orientation)
