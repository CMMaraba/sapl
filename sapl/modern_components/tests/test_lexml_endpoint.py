import unittest
from unittest.mock import patch

from django.test import RequestFactory


class LexmlEndpointTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        import django
        from django.conf import settings
        settings.LOGGING_CONFIG = None
        django.setup()

    def test_endpoint_uses_django_absolute_uri_api(self):
        import django
        from django.conf import settings
        settings.LOGGING_CONFIG = None
        django.setup()
        from sapl.lexml.views import lexml_request

        request = RequestFactory().get(
            "/sistema/lexml/oai?verb=Identify", secure=True, HTTP_HOST="localhost"
        )
        with patch("sapl.lexml.views.get_config", return_value={}) as get_config, \
             patch("sapl.lexml.views.OAIServerFactory") as factory:
            factory.return_value.handleRequest.return_value = b"<OAI-PMH/>"
            response = lexml_request(request)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "text/xml")
        self.assertEqual(response.content, b"<OAI-PMH/>")
        get_config.assert_called_once_with(
            "https://localhost/sistema/lexml/oai?verb=Identify", 10
        )

    def test_internal_failure_is_generic_503_with_retry_after(self):
        from sapl.lexml.views import lexml_request
        from sapl.modern_components.oai_protocol import OAIServiceError
        request = RequestFactory().get("/sistema/lexml/oai?verb=Identify", HTTP_HOST="localhost")
        with patch("sapl.lexml.views.get_config", return_value={}), \
             patch("sapl.lexml.views.OAIServerFactory") as factory, \
             patch("sapl.lexml.views.logger.exception"):
            factory.return_value.handleRequest.side_effect = OAIServiceError("private diagnostic")
            response = lexml_request(request)
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response["Retry-After"], "60")
        self.assertNotIn(b"private diagnostic", response.content)
        self.assertNotIn(b"<Identify", response.content)

    def test_invalid_or_unbounded_batch_size_is_400_without_query(self):
        from sapl.lexml.views import lexml_request
        for query in ("text", "0", "-1", "1001", "1.5", "", "1&batch_size=2"):
            with self.subTest(query=query):
                request = RequestFactory().get(
                    "/sistema/lexml/oai?verb=ListRecords&batch_size=" + query, HTTP_HOST="localhost")
                with patch("sapl.lexml.views.get_config") as get_config:
                    response = lexml_request(request)
                self.assertEqual(response.status_code, 400)
                get_config.assert_not_called()

    def test_batch_size_boundaries_remain_supported(self):
        from sapl.lexml.views import lexml_request
        for size in (1, 1000):
            with self.subTest(size=size):
                request = RequestFactory().get(
                    "/sistema/lexml/oai?verb=Identify&batch_size=" + str(size), HTTP_HOST="localhost")
                with patch("sapl.lexml.views.get_config", return_value={}) as get_config, \
                     patch("sapl.lexml.views.OAIServerFactory") as factory:
                    factory.return_value.handleRequest.return_value = b"<OAI-PMH/>"
                    response = lexml_request(request)
                self.assertEqual(response.status_code, 200)
                self.assertEqual(get_config.call_args.args[1], size)
                self.assertNotIn("batch_size", factory.return_value.handleRequest.call_args.args[0])


if __name__ == "__main__":
    unittest.main()
