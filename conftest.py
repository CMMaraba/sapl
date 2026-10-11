import pytest
from django.test import override_settings
from django_webtest import DjangoTestApp, WebTestMixin


@pytest.fixture(autouse=True)
def isolate_test_media_root(tmp_path):
    """Keep test uploads out of the cloned application media."""
    media_root = tmp_path / "media"
    media_root.mkdir()
    with override_settings(MEDIA_ROOT=str(media_root)):
        yield


class OurTestApp(DjangoTestApp):

    def __init__(self, *args, **kwargs):
        self.default_user = kwargs.pop('default_user', None)
        super(OurTestApp, self).__init__(*args, **kwargs)

    def get(self, *args, **kwargs):
        kwargs.setdefault('user', self.default_user)
        kwargs.setdefault('auto_follow', True)
        return super(OurTestApp, self).get(*args, **kwargs)


@pytest.fixture(scope='function')
def app(request, admin_user):
    """WebTest's TestApp.

    Patch and unpatch settings before and after each test.

    WebTestMixin, when used in a unittest.TestCase, automatically calls
    _patch_settings() and _unpatchsettings.

    source: https://gist.github.com/magopian/6673250
    """
    wtm = WebTestMixin()
    wtm._patch_settings()
    request.addfinalizer(wtm._unpatch_settings)
    # XXX change this admin user to "saploper"
    return OurTestApp(default_user=admin_user.username)
