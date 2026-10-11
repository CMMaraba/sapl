import unittest


class LegacyAtasRedirectTests(unittest.TestCase):
    def test_redirect_resolves_to_relatorios_namespace(self):
        import django
        from django.conf import settings
        settings.LOGGING_CONFIG = None
        django.setup()
        from django.test import Client
        response = Client().get('/atasSessao')
        self.assertEqual(response.status_code, 301)
        self.assertTrue(response['Location'].startswith('/sistema/relatorios/atas'))


if __name__ == '__main__':
    unittest.main()
