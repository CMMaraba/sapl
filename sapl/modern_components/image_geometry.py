"""Pure helpers for the persisted SAPL crop-box format."""

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
