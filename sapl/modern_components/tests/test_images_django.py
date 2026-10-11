import importlib.util
import io
import unittest

from PIL import Image

HAS_DJANGO = importlib.util.find_spec("django") is not None

if HAS_DJANGO:
    from unittest.mock import patch
    from sapl.modern_components.images import (
        ImageCropField, ImageRatioField, PillowImageBackend,
    )


@unittest.skipUnless(HAS_DJANGO, "Django integration tests run inside the SAPL venv")
class DjangoImageFieldTests(unittest.TestCase):
    def test_migration_deconstruction_uses_local_component(self):
        field = ImageRatioField("fotografia", "128x128")
        self.assertEqual(
            field.deconstruct()[1],
            "sapl.modern_components.images.ImageRatioField",
        )
        clone = field.clone()
        self.assertEqual(clone.max_length, field.max_length)
        self.assertEqual(clone.default, field.default)
        self.assertEqual(clone.blank, field.blank)
        image_field = ImageCropField()
        self.assertEqual(
            image_field.deconstruct()[1],
            "sapl.modern_components.images.ImageCropField",
        )

    def test_ratio_form_widget_preserves_crop_metadata(self):
        field = ImageRatioField("fotografia", "128x128")
        field.set_attributes_from_name("cropping")
        form_field = field.formfield()
        self.assertEqual(form_field.widget.attrs["data-image-field"], "fotografia")
        self.assertEqual(form_field.widget.attrs["data-ratio"], 1.0)
        self.assertIn("image-ratio", form_field.widget.attrs["class"])

    def test_thumbnail_backend_uses_configured_storage(self):
        class MemoryStorage:
            def __init__(self):
                self.files = {}

            def exists(self, name):
                return name in self.files

            def save(self, name, content):
                self.files[name] = content.read()
                return name

            def url(self, name):
                return "/test-media/" + name

        storage = MemoryStorage()
        png = io.BytesIO()
        Image.new("RGB", (8, 6), (20, 40, 60)).save(png, format="PNG")
        with patch("sapl.modern_components.images.default_storage", storage):
            url = PillowImageBackend().get_thumbnail_url(
                png.getvalue(), {"size": (4, 4), "crop": True, "box": [1, 1, 7, 5]}
            )
        self.assertTrue(url.startswith("/test-media/sapl-thumbnails/"))
        self.assertEqual(len(storage.files), 1)
        with Image.open(io.BytesIO(next(iter(storage.files.values())))) as thumb:
            self.assertEqual(thumb.size, (4, 4))


if __name__ == "__main__":
    unittest.main()
