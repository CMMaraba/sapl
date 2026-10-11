import io
import unittest

from PIL import Image

from sapl.modern_components.image_processing import pil_image, render_thumbnail


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


if __name__ == "__main__":
    unittest.main()
