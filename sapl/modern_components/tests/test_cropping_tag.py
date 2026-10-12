from types import SimpleNamespace
from unittest.mock import patch

from django.test import SimpleTestCase

from sapl.modern_components.templatetags.cropping import cropped_thumbnail


class CroppedThumbnailTagTests(SimpleTestCase):
    def setUp(self):
        self.image = object()
        self.ratio = SimpleNamespace(
            image_field="fotografia", image_fk_field=None, width=128, height=128
        )
        self.instance = SimpleNamespace(
            _meta=SimpleNamespace(get_field=lambda _name: self.ratio),
            fotografia=self.image,
            cropping="10,20,110,120",
        )
        self.backend = SimpleNamespace(get_thumbnail_url=lambda image, options: (image, options))

    @patch("sapl.modern_components.templatetags.cropping.get_backend")
    def test_xyxy_crop_and_default_dimensions(self, get_backend):
        get_backend.return_value = self.backend
        image, options = cropped_thumbnail(self.instance, "cropping")
        self.assertIs(image, self.image)
        self.assertEqual(options, {"size": (128, 128), "box": "10,20,110,120", "crop": True})

    @patch("sapl.modern_components.templatetags.cropping.get_backend")
    def test_scale_two_doubles_ratio_dimensions(self, get_backend):
        get_backend.return_value = self.backend
        _image, options = cropped_thumbnail(self.instance, "cropping", scale=2)
        self.assertEqual(options["size"], (256, 256))

    @patch("sapl.modern_components.templatetags.cropping.get_backend")
    def test_fullsize_marker_is_preserved_for_backend(self, get_backend):
        get_backend.return_value = self.backend
        self.instance.cropping = "-10,20,110,120"
        _image, options = cropped_thumbnail(self.instance, "cropping", scale=2)
        self.assertEqual(options["box"], "-10,20,110,120")
        self.assertTrue(options["crop"])

    @patch("sapl.modern_components.templatetags.cropping.get_backend")
    def test_related_image_field_is_resolved(self, get_backend):
        get_backend.return_value = self.backend
        related = SimpleNamespace(fotografia=self.image)
        self.ratio.image_field = "anexo"
        self.ratio.image_fk_field = "fotografia"
        self.instance.anexo = related
        image, _options = cropped_thumbnail(self.instance, "cropping")
        self.assertIs(image, self.image)

    @patch("sapl.modern_components.templatetags.cropping.get_backend")
    def test_free_crop_uses_selection_size(self, get_backend):
        get_backend.return_value = self.backend
        self.ratio.free_crop = True
        self.ratio.width = self.ratio.height = 100
        _image, options = cropped_thumbnail(self.instance, "cropping")
        self.assertEqual(
            options, {"free_crop": True, "scale": 1.0, "box": "10,20,110,120", "crop": True}
        )

    @patch("sapl.modern_components.templatetags.cropping.get_backend")
    def test_backend_failure_renders_empty_url(self, get_backend):
        get_backend.return_value.get_thumbnail_url.side_effect = ValueError(
            "I/O operation on closed file"
        )
        with self.assertLogs("sapl.modern_components.templatetags.cropping", "WARNING"):
            self.assertEqual(cropped_thumbnail(self.instance, "cropping"), "")

    @patch("sapl.modern_components.templatetags.cropping.get_backend")
    def test_thumbnail_debug_reraises(self, get_backend):
        get_backend.return_value.get_thumbnail_url.side_effect = OSError("broken")
        with self.settings(THUMBNAIL_DEBUG=True), self.assertRaises(OSError):
            cropped_thumbnail(self.instance, "cropping")
