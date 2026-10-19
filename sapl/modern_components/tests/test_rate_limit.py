import unittest

from django.core.cache import caches
from django.http import HttpResponse
from django.test import RequestFactory, SimpleTestCase, override_settings
from django_ratelimit.decorators import ratelimit
from django_ratelimit.exceptions import Ratelimited

from sapl.modern_components.client_ip import client_ip
from sapl.modern_components.rate_limit import rate_for_request


def request_ip(group, request):
    return client_ip(request.META, ipv4_mask=32, ipv6_mask=128)


def endpoint(request):
    return HttpResponse("ok")


@override_settings(
    CACHES={
        "default": {
            "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
            "LOCATION": "sapl-rate-limit-tests",
        }
    },
    RATELIMIT_ENABLE=True,
    RATE_LIMITER_RATE="35/m",
)
class RateLimitTests(SimpleTestCase):
    def setUp(self):
        caches["default"].clear()
        self.factory = RequestFactory()
        self.limited_endpoint = ratelimit(
            key=request_ip,
            rate=rate_for_request,
            block=True,
        )(endpoint)

    def request(self, ip, **meta):
        return self.factory.get("/rate-limit-test/", REMOTE_ADDR=ip, **meta)

    def test_internal_ipv4_boundaries_are_exempt(self):
        for ip in ("10.3.144.0", "10.3.146.200", "10.3.151.255"):
            with self.subTest(ip=ip):
                self.assertIsNone(rate_for_request("group", self.request(ip)))

    def test_panel_ip_forwarded_by_proxy_is_exempt(self):
        request = self.request("127.0.0.1", HTTP_X_FORWARDED_FOR="10.3.146.200")
        self.assertIsNone(rate_for_request("group", request))

    @override_settings(RATELIMIT_IPV4_MASK=16)
    def test_network_membership_uses_unmasked_client_address(self):
        self.assertIsNone(rate_for_request("group", self.request("10.3.146.200")))
        self.assertEqual(rate_for_request("group", self.request("10.3.152.1")), "35/m")

    def test_external_ipv4_boundaries_and_public_ip_use_configured_rate(self):
        for ip in ("10.3.143.255", "10.3.152.0", "203.0.113.10"):
            with self.subTest(ip=ip):
                self.assertEqual(
                    rate_for_request("group", self.request(ip)), "35/m"
                )

    def test_more_than_35_internal_requests_are_not_limited(self):
        request = self.request("10.3.144.1")
        for _ in range(40):
            self.assertEqual(self.limited_endpoint(request).status_code, 200)

    def test_36th_external_request_is_limited(self):
        request = self.request("10.3.143.255")
        for _ in range(35):
            self.assertEqual(self.limited_endpoint(request).status_code, 200)
        with self.assertRaises(Ratelimited):
            self.limited_endpoint(request)

    def test_ipv6_never_matches_internal_ipv4_network(self):
        request = self.request("::ffff:10.3.144.1")
        self.assertEqual(rate_for_request("group", request), "35/m")

    def test_invalid_forwarded_header_fails_closed(self):
        request = self.request(
            "203.0.113.20",
            HTTP_X_FORWARDED_FOR="not-an-ip",
        )
        self.assertEqual(rate_for_request("group", request), "35/m")

    def test_invalid_all_ip_sources_use_limited_unknown_address(self):
        request = self.request(
            "invalid-remote-address",
            HTTP_X_FORWARDED_FOR="not-an-ip",
            HTTP_X_REAL_IP="also-invalid",
        )
        self.assertEqual(rate_for_request("group", request), "35/m")
        for _ in range(35):
            self.assertEqual(self.limited_endpoint(request).status_code, 200)
        with self.assertRaises(Ratelimited):
            self.limited_endpoint(request)

    @override_settings(RATE_LIMITER_RATE="2/m")
    def test_external_rate_remains_configurable(self):
        request = self.request("203.0.113.30")
        self.assertEqual(rate_for_request("group", request), "2/m")
        for _ in range(2):
            self.assertEqual(self.limited_endpoint(request).status_code, 200)
        with self.assertRaises(Ratelimited):
            self.limited_endpoint(request)


if __name__ == "__main__":
    unittest.main()
