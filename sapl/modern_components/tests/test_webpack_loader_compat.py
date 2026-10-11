from django.template import Context, Engine
from django.test import SimpleTestCase
from webpack_loader.exceptions import WebpackLoaderBadStatsError

from sapl.modern_components import webpack_loader as compat


class SaplWebpackLoaderCompatTests(SimpleTestCase):
    def setUp(self):
        self.stats = {
            "status": "done",
            "publicPath": "/static/",
            "chunks": {
                "global": [
                    "js/app.js",
                    {"name": "css/app.css", "publicPath": "/assets/app.css"},
                    "js/app.js.gz",
                ]
            },
            "assets": {
                "js/app.js": {
                    "name": "js/app.js",
                    "path": "/build/js/app.js",
                    "publicPath": "/assets/app.js",
                },
                "css/app.css": {
                    "name": "css/app.css",
                    "path": "/build/css/app.css",
                    "publicPath": "/assets/app.css",
                },
                "js/app.js.gz": {
                    "name": "js/app.js.gz",
                    "path": "/build/js/app.js.gz",
                    "publicPath": "/assets/app.js.gz",
                },
            },
        }
        self.loader = compat.SaplWebpackLoader("DEFAULT")
        self.loader.config = {
            "CACHE": False,
            "STATS_FILE": "unused",
            "BUNDLE_DIR_NAME": "bundles/",
            "POLL_INTERVAL": 0.01,
            "TIMEOUT": None,
            "ignores": [],
        }
        self.loader._load_assets = lambda: self.stats
        compat._loaders["sapl-webpack-test"] = self.loader
        self.addCleanup(compat._loaders.pop, "sapl-webpack-test", None)

    def test_accepts_tracker_strings_and_legacy_asset_objects(self):
        chunks = list(self.loader.get_bundle("global"))
        self.assertEqual(
            [chunk["name"] for chunk in chunks],
            ["js/app.js", "css/app.css", "js/app.js.gz"],
        )
        self.assertEqual(chunks[0]["url"], "/assets/app.js")
        self.assertEqual(chunks[1]["url"], "/assets/app.css")
        self.assertNotIn("url", self.stats["chunks"]["global"][1])

    def test_apt_render_bundle_tag_keeps_attrs_and_gzip_behavior(self):
        template = Engine.get_default().from_string(
            "{% load render_bundle from webpack_loader %}"
            "{% render_bundle 'global' config='sapl-webpack-test' attrs='defer' %}"
        )
        rendered = str(template.render(Context({})))
        self.assertIn('src="/assets/app.js" defer', rendered)
        self.assertIn('href="/assets/app.css" rel="stylesheet" defer', rendered)
        self.assertIn('src="/assets/app.js.gz" defer', rendered)

    def test_apt_get_files_extension_and_webpack_static_contract(self):
        template = Engine.get_default().from_string(
            "{% load get_files webpack_static from webpack_loader %}"
            "{% get_files 'global' 'js' 'sapl-webpack-test' as files %}"
            "{{ files|length }}|{{ files.0.publicPath }}|"
            "{% webpack_static 'img/logo.png' 'sapl-webpack-test' %}"
        )
        self.assertEqual(
            str(template.render(Context({}))),
            "1|/assets/app.js|/static/img/logo.png",
        )

    def test_missing_tracker_asset_fails_with_loader_error(self):
        self.stats["chunks"]["global"] = ["js/missing.js"]
        with self.assertRaisesRegex(WebpackLoaderBadStatsError, "no asset metadata"):
            list(self.loader.get_bundle("global"))

    def test_unknown_chunk_shape_is_rejected(self):
        self.stats["chunks"]["global"] = [42]
        with self.assertRaisesRegex(WebpackLoaderBadStatsError, "asset names or objects"):
            list(self.loader.get_bundle("global"))
