import importlib.util
import hashlib
import io
import json
import unittest

from PIL import Image

HAS_DJANGO = importlib.util.find_spec("django") is not None

if HAS_DJANGO:
    from unittest.mock import patch
    from sapl.modern_components.images import (
        ImageCropField, ImageRatioField, PillowImageBackend,
    )
    from sapl.modern_components.image_processing import render_thumbnail


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


def image_bytes(mode="RGB", color=(20, 40, 60)):
    stream = io.BytesIO()
    Image.new(mode, (8, 6), color).save(stream, format="PNG")
    return stream.getvalue()


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

    def test_repeated_thumbnail_requests_render_only_once(self):
        storage = MemoryStorage()
        options = {"size": (4, 4), "crop": True, "box": [1, 1, 7, 5]}
        source = image_bytes()
        with patch("sapl.modern_components.images.default_storage", storage), patch(
            "sapl.modern_components.images.render_thumbnail", wraps=render_thumbnail
        ) as render:
            urls = [PillowImageBackend().get_thumbnail_url(source, options) for _ in range(3)]
        self.assertEqual(urls, [urls[0]] * 3)
        self.assertEqual(render.call_count, 1)
        self.assertEqual(len(storage.files), 1)
        self.assertEqual(options, {"size": (4, 4), "crop": True, "box": [1, 1, 7, 5]})

    def test_existing_explicit_size_thumbnail_is_reused(self):
        storage = MemoryStorage()
        source = image_bytes()
        options = {"size": (4, 4)}
        rendered, extension = render_thumbnail(source, options)
        # Cache filename contract already used by the original backend.
        signature = hashlib.sha256(source)
        signature.update(json.dumps(options, sort_keys=True, default=str).encode("utf-8"))
        signature.update(extension.encode("ascii"))
        digest = signature.hexdigest()
        name = "sapl-thumbnails/{}/{}.{}".format(digest[:2], digest, extension)
        storage.files[name] = rendered
        with patch("sapl.modern_components.images.default_storage", storage), patch(
            "sapl.modern_components.images.render_thumbnail", side_effect=AssertionError("Cached thumbnail was rasterized")
        ):
            url = PillowImageBackend().get_thumbnail_url(source, options)
        self.assertEqual(url, storage.url(name))
        self.assertEqual(len(storage.files), 1)

    def test_cache_changes_with_source_crop_size_and_options(self):
        storage = MemoryStorage()
        source = image_bytes()
        variants = [
            (source, {"size": (4, 4), "crop": True, "box": [1, 1, 7, 5]}),
            (image_bytes(color=(80, 100, 120)), {"size": (4, 4), "crop": True, "box": [1, 1, 7, 5]}),
            (source, {"size": (4, 4), "crop": True, "box": [0, 0, 6, 4]}),
            (source, {"size": (3, 3), "crop": True, "box": [1, 1, 7, 5]}),
            (source, {"size": (4, 4), "crop": False, "box": [1, 1, 7, 5]}),
        ]
        with patch("sapl.modern_components.images.default_storage", storage), patch(
            "sapl.modern_components.images.render_thumbnail", wraps=render_thumbnail
        ) as render:
            backend = PillowImageBackend()
            urls = [backend.get_thumbnail_url(data, options) for data, options in variants]
            for (data, options), url in zip(variants, urls):
                self.assertEqual(backend.get_thumbnail_url(data, options), url)
        self.assertEqual(len(set(urls)), len(variants))
        self.assertEqual(render.call_count, len(variants))
        self.assertEqual(len(storage.files), len(variants))

    def test_default_size_changes_invalidate_only_implicit_size(self):
        storage = MemoryStorage()
        source = image_bytes()
        with patch("sapl.modern_components.images.default_storage", storage), patch(
            "sapl.modern_components.images.render_thumbnail", wraps=render_thumbnail
        ) as render:
            backend = PillowImageBackend()
            with patch("sapl.modern_components.images._setting", return_value=(4, 3)):
                first = backend.get_thumbnail_url(source, {})
                explicit = backend.get_thumbnail_url(source, {"size": (2, 2)})
            with patch("sapl.modern_components.images._setting", return_value=(2, 2)):
                second = backend.get_thumbnail_url(source, {})
                unchanged = backend.get_thumbnail_url(source, {"size": (2, 2)})
        self.assertNotEqual(first, second)
        self.assertEqual(explicit, second)
        self.assertEqual(explicit, unchanged)
        self.assertEqual(render.call_count, 2)
        sizes = []
        for data in storage.files.values():
            with Image.open(io.BytesIO(data)) as thumb:
                sizes.append(thumb.size)
        self.assertCountEqual(sizes, [(4, 3), (2, 2)])

    def test_cached_png_and_jpeg_preserve_format_and_alpha(self):
        for mode, color, extension, image_format in [
            ("RGB", (20, 40, 60), ".jpg", "JPEG"),
            ("RGBA", (20, 40, 60, 64), ".png", "PNG"),
        ]:
            with self.subTest(mode=mode):
                storage = MemoryStorage()
                source = image_bytes(mode, color)
                with patch("sapl.modern_components.images.default_storage", storage), patch(
                    "sapl.modern_components.images.render_thumbnail", wraps=render_thumbnail
                ) as render:
                    backend = PillowImageBackend()
                    urls = [backend.get_thumbnail_url(source, {"size": (4, 4)}) for _ in range(3)]
                self.assertEqual(render.call_count, 1)
                self.assertEqual(urls, [urls[0]] * 3)
                self.assertTrue(urls[0].endswith(extension))
                with Image.open(io.BytesIO(next(iter(storage.files.values())))) as thumb:
                    self.assertEqual(thumb.format, image_format)
                    if mode == "RGBA":
                        self.assertEqual(thumb.getpixel((0, 0))[3], 64)

    def test_thumbnail_uses_source_storage_and_preserves_stream_position(self):
        storage = MemoryStorage()
        source = io.BytesIO(image_bytes())
        source.storage = storage
        source.seek(3)
        with patch("sapl.modern_components.images.render_thumbnail", wraps=render_thumbnail) as render:
            backend = PillowImageBackend()
            first = backend.get_thumbnail_url(source, {"size": (4, 4)})
            second = backend.get_thumbnail_url(source, {"size": (4, 4)})
        self.assertEqual(first, second)
        self.assertEqual(source.tell(), 3)
        self.assertEqual(render.call_count, 1)
        self.assertEqual(len(storage.files), 1)


if __name__ == "__main__":
    unittest.main()
