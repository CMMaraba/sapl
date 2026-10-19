"""Rate limiting policy for SAPL views."""

from ipaddress import ip_address, ip_network

from django.conf import settings

from .client_ip import client_ip


INTERNAL_NETWORK = ip_network("10.3.144.0/21")


def rate_for_request(group, request):
    """Return no limit for the internal IPv4 network, else configured rate."""
    address = ip_address(client_ip(
        request.META,
        ipv4_mask=32,
        ipv6_mask=128,
    ))
    if address.version == 4 and address in INTERNAL_NETWORK:
        return None
    return settings.RATE_LIMITER_RATE
