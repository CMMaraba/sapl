"""Normalize webpack-bundle-tracker 1.x chunks for the APT loader 0.6."""

from webpack_loader import utils
from webpack_loader.exceptions import WebpackLoaderBadStatsError
from webpack_loader.loader import WebpackLoader
from webpack_loader.templatetags import webpack_loader as apt_tags


class SaplWebpackLoader(WebpackLoader):
    _assets = {}

    def filter_chunks(self, chunks):
        assets = self.get_assets().get("assets", {})
        for chunk in chunks:
            if isinstance(chunk, str):
                chunk = assets.get(chunk)
                if not isinstance(chunk, dict):
                    raise WebpackLoaderBadStatsError(
                        "Webpack chunk has no asset metadata."
                    )
                chunk = dict(chunk)
            elif isinstance(chunk, dict):
                chunk = dict(chunk)
            else:
                raise WebpackLoaderBadStatsError(
                    "Webpack chunks must be asset names or objects."
                )

            if not isinstance(chunk.get("name"), str):
                raise WebpackLoaderBadStatsError(
                    "Webpack chunk metadata must include a name."
                )
            ignore = any(regex.match(chunk["name"]) for regex in self.config["ignores"])
            if not ignore:
                chunk["url"] = self.get_chunk_url(chunk)
                yield chunk


_loaders = {}


def get_loader(config_name):
    if config_name not in _loaders:
        _loaders[config_name] = SaplWebpackLoader(config_name)
    return _loaders[config_name]


# Keep the APT package's template-tag implementations and their edge cases.
utils.get_loader = get_loader
register = apt_tags.register
render_bundle = apt_tags.render_bundle
webpack_static = apt_tags.webpack_static
get_files = apt_tags.get_files
