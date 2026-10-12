import importlib.util
import hashlib
import io
import json
import os
import shutil
import tempfile
import unittest
from types import SimpleNamespace

from PIL import Image

HAS_DJANGO = importlib.util.find_spec("django") is not None

if HAS_DJANGO:
    from unittest.mock import patch
    from django.core.files.storage import FileSystemStorage
    from django.db.models.fields.files import FieldFile
    from sapl.modern_components.images import (
        ImageCropField, ImageRatioField, PillowImageBackend, THUMBNAIL_VERSION,
        delete_thumbnails, thumbnail_folder,
    )
    from sapl.modern_components.image_processing import read_source, render_thumbnail


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
        # Cache filename contract for sources without a stored name.
        identity = hashlib.sha256(source).hexdigest()
        signature = hashlib.sha256(identity.encode("utf-8"))
        signature.update(json.dumps(
            {"options": options, "version": THUMBNAIL_VERSION}, sort_keys=True, default=str
        ).encode("utf-8"))
        signature.update(extension.encode("ascii"))
        name = "{}/{}.{}".format(
            thumbnail_folder("sha256:" + identity), signature.hexdigest(), extension
        )
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



@unittest.skipUnless(HAS_DJANGO, "Django integration tests run inside the SAPL venv")
class StoredThumbnailTests(unittest.TestCase):
    """Thumbnails of committed files, as rendered for parlamentares pages."""

    def setUp(self):
        self.root = tempfile.mkdtemp(prefix="sapl-thumbs-")
        self.addCleanup(shutil.rmtree, self.root, True)
        self.storage = FileSystemStorage(location=self.root, base_url="/media/")
        self.photo = self.store("fotos/a.png", image_bytes())
        self.options = {"size": (4, 4), "crop": True, "box": "1,1,7,5"}

    def store(self, name, data):
        saved = self.storage.save(name, io.BytesIO(data))
        return FieldFile(None, SimpleNamespace(storage=self.storage), saved)

    def thumbnails(self, field_file):
        folder = thumbnail_folder(field_file.name)
        try:
            return self.storage.listdir(folder)[1]
        except FileNotFoundError:
            return []

    def test_cache_hit_does_not_read_source_or_keep_it_open(self):
        backend = PillowImageBackend()
        with patch("sapl.modern_components.images.read_source", wraps=read_source) as reads:
            first = backend.get_thumbnail_url(self.photo, self.options)
            self.assertEqual(reads.call_count, 1)
            for _ in range(3):
                self.assertEqual(backend.get_thumbnail_url(self.photo, self.options), first)
        self.assertEqual(reads.call_count, 1)
        self.assertIsNone(self.photo._file)
        self.assertEqual(len(self.thumbnails(self.photo)), 1)

    def test_changed_source_file_gets_new_thumbnail(self):
        backend = PillowImageBackend()
        first = backend.get_thumbnail_url(self.photo, self.options)
        path = self.storage.path(self.photo.name)
        with open(path, "wb") as stream:
            stream.write(image_bytes(color=(200, 10, 10)))
        stat = os.stat(path)
        os.utime(path, (stat.st_atime, stat.st_mtime + 10))
        self.assertNotEqual(backend.get_thumbnail_url(self.photo, self.options), first)

    def test_read_source_recovers_from_closed_cached_handle(self):
        self.photo.open("rb")
        self.photo.file.close()
        self.assertEqual(read_source(self.photo), image_bytes())

    def test_read_source_restores_uncommitted_upload_position(self):
        upload = FieldFile(None, SimpleNamespace(storage=self.storage), "fotos/novo.png")
        upload._file = io.BytesIO(image_bytes())
        upload._committed = False
        upload._file.seek(5)
        self.assertEqual(read_source(upload), image_bytes())
        self.assertEqual(upload._file.tell(), 5)

    def test_concurrent_duplicate_is_removed(self):
        backend = PillowImageBackend()
        url = backend.get_thumbnail_url(self.photo, self.options)
        # Simulate a second request whose jpg/png probes ran before the
        # first one saved; later checks see the real storage.
        real_exists = self.storage.exists
        probes = [False, False]

        def exists(name):
            return probes.pop() if probes else real_exists(name)

        with patch.object(self.storage, "exists", side_effect=exists):
            again = backend.get_thumbnail_url(self.photo, self.options)
        self.assertEqual(again, url)
        self.assertEqual(len(self.thumbnails(self.photo)), 1)

    def test_delete_thumbnails_only_touches_its_source(self):
        other = self.store("fotos/b.png", image_bytes(color=(1, 2, 3)))
        backend = PillowImageBackend()
        backend.get_thumbnail_url(self.photo, self.options)
        backend.get_thumbnail_url(self.photo, {"size": (8, 8), "crop": True, "box": "1,1,7,5"})
        backend.get_thumbnail_url(other, self.options)
        self.assertEqual(len(self.thumbnails(self.photo)), 2)
        delete_thumbnails(self.photo.name, self.storage)
        self.assertEqual(self.thumbnails(self.photo), [])
        self.assertEqual(len(self.thumbnails(other)), 1)
        delete_thumbnails("fotos/inexistente.png", self.storage)


@unittest.skipUnless(HAS_DJANGO, "Django integration tests run inside the SAPL venv")
class RatioFieldSignalTests(unittest.TestCase):
    def ratio_field(self, size="128x128"):
        field = ImageRatioField("fotografia", size)
        field.set_attributes_from_name("cropping")
        return field

    def sender(self, previous):
        query = SimpleNamespace(values_list=lambda *names: SimpleNamespace(first=lambda: previous))
        storage = SimpleNamespace(name="storage")
        return SimpleNamespace(
            _default_manager=SimpleNamespace(filter=lambda **kwargs: query),
            _meta=SimpleNamespace(get_field=lambda name: SimpleNamespace(storage=storage)),
        ), storage

    def instance(self, image_name, box):
        return SimpleNamespace(pk=1, fotografia=SimpleNamespace(name=image_name), cropping=box)

    def run_discard(self, previous, instance):
        sender, storage = self.sender(previous)
        with patch("sapl.modern_components.images.transaction.on_commit", side_effect=lambda fn: fn()), \
                patch("sapl.modern_components.images.delete_thumbnails") as delete:
            self.ratio_field().discard_stale_thumbnails(sender, instance)
        return delete, storage

    def test_changed_crop_discards_cached_thumbnails(self):
        delete, storage = self.run_discard(("fotos/a.jpg", "0,0,10,10"), self.instance("fotos/a.jpg", "1,1,9,9"))
        delete.assert_called_once_with("fotos/a.jpg", storage)

    def test_replaced_image_discards_old_image_thumbnails(self):
        delete, storage = self.run_discard(("fotos/a.jpg", "0,0,10,10"), self.instance("fotos/b.jpg", "0,0,10,10"))
        delete.assert_called_once_with("fotos/a.jpg", storage)

    def test_unchanged_record_keeps_thumbnails(self):
        delete, _storage = self.run_discard(("fotos/a.jpg", "0,0,10,10"), self.instance("fotos/a.jpg", "0,0,10,10"))
        delete.assert_not_called()

    def test_initial_crop_is_centred_on_displayed_image_and_stored_raw(self):
        field = self.ratio_field("200x100")
        instance = SimpleNamespace(
            ratio_fields=["cropping"], cropping="", fotografia=object(),
            _meta=SimpleNamespace(get_field=lambda name: field),
        )
        # Stored 300x400 with EXIF 6: displayed as 400x300.
        backend = SimpleNamespace(get_source_info=lambda image: (300, 400, 6))
        with patch("sapl.modern_components.images.get_backend", return_value=backend):
            field.initial_cropping(None, instance)
        # Displayed box 0,50,400,250 is a centred 2:1 crop of 400x300.
        self.assertEqual(instance.cropping, "50,0,250,400")


if __name__ == "__main__":
    unittest.main()
