import io
import unittest

from PIL import Image, ImageOps

from sapl.modern_components.image_processing import image_info, pil_image, render_thumbnail


def png_bytes(size=(10, 8), color=(200, 40, 20)):
    output = io.BytesIO()
    Image.new("RGB", size, color).save(output, format="PNG")
    return output.getvalue()


class PillowImageTests(unittest.TestCase):
    def test_pil_image_loads_detached_source(self):
        source = io.BytesIO(png_bytes())
        image = pil_image(source)
        self.assertEqual(image.size, (10, 8))
        self.assertFalse(source.closed)

    def test_crop_box_is_applied_in_xyxy_coordinates(self):
        payload, ext = render_thumbnail(
            png_bytes(),
            {"size": (20, 10), "box": "2,1,8,7", "crop": True},
        )
        with Image.open(io.BytesIO(payload)) as result:
            self.assertEqual(ext, "jpg")
            self.assertEqual(result.size, (20, 10))

    def test_fullsize_marker_disables_crop(self):
        payload, _ = render_thumbnail(
            png_bytes(),
            {"size": (20, 20), "box": "-2,1,8,7", "crop": True, "upscale": True},
        )
        with Image.open(io.BytesIO(payload)) as result:
            self.assertEqual(result.size, (20, 16))

    def test_empty_input_is_safe(self):
        self.assertEqual(render_thumbnail(None), (b"", "jpg"))


    def test_free_crop_keeps_selection_size(self):
        payload, _ = render_thumbnail(
            png_bytes((80, 60)), {"free_crop": True, "box": "10,10,50,30", "crop": True}
        )
        with Image.open(io.BytesIO(payload)) as result:
            self.assertEqual(result.size, (40, 20))

    def test_free_crop_without_box_keeps_whole_image(self):
        payload, _ = render_thumbnail(png_bytes((80, 60)), {"free_crop": True, "crop": True})
        with Image.open(io.BytesIO(payload)) as result:
            self.assertEqual(result.size, (80, 60))

    def test_free_crop_scale_only_reduces(self):
        for scale, expected in [(0.5, (20, 10)), (2, (40, 20))]:
            payload, _ = render_thumbnail(
                png_bytes((80, 60)),
                {"free_crop": True, "scale": scale, "box": "10,10,50,30", "crop": True},
            )
            with Image.open(io.BytesIO(payload)) as result:
                self.assertEqual(result.size, expected)


def quadrant_jpeg(orientation):
    """Stored 400x300 JPEG: red, green, blue and yellow quadrants."""
    image = Image.new("RGB", (400, 300))
    colors = [(255, 0, 0), (0, 255, 0), (0, 0, 255), (255, 255, 0)]
    for (x, y), color in zip([(0, 0), (200, 0), (0, 150), (200, 150)], colors):
        image.paste(color, (x, y, x + 200, y + 150))
    exif = image.getexif()
    exif[0x0112] = orientation
    output = io.BytesIO()
    image.save(output, format="JPEG", exif=exif, quality=95)
    return output.getvalue()


def dominant(image):
    return image.convert("RGB").resize((1, 1)).getpixel((0, 0))


class ExifOrientationTests(unittest.TestCase):
    def test_legacy_box_selects_same_region_and_is_shown_upright(self):
        data = quadrant_jpeg(6)
        box = (0, 0, 200, 150)  # stored red quadrant
        with Image.open(io.BytesIO(data)) as stored:
            expected = ImageOps.exif_transpose(stored).crop((150, 0, 300, 200))
        payload, _ = render_thumbnail(data, {"size": (150, 200), "box": "0,0,200,150", "crop": True})
        with Image.open(io.BytesIO(payload)) as result:
            self.assertEqual(result.size, (150, 200))
            red, green, blue = dominant(result)
            self.assertGreater(red, 200)
            self.assertLess(green, 60)
            self.assertLess(blue, 60)
            self.assertEqual(dominant(result), dominant(expected))
        self.assertEqual(box, (0, 0, 200, 150))

    def test_image_info_reports_stored_size_and_orientation(self):
        self.assertEqual(image_info(quadrant_jpeg(6)), (400, 300, 6))
        self.assertEqual(pil_image(quadrant_jpeg(6)).size, (300, 400))

    def test_orientation_can_be_disabled(self):
        payload, _ = render_thumbnail(
            quadrant_jpeg(6), {"size": (400, 300), "exif_orientation": False}
        )
        with Image.open(io.BytesIO(payload)) as result:
            self.assertEqual(result.size, (400, 300))


if __name__ == "__main__":
    unittest.main()
