"""Client IP extraction tolerant to malformed proxy headers."""
import ipaddress

UNKNOWN_IP = "0.0.0.0"


def parse_ip(value):
    """Return an ip_address for one header item, or None when it is not one.

    Accepts surrounding spaces, "IPv4:port", "[IPv6]" and "[IPv6]:port".
    """
    text = str(value or "").strip()
    if text.startswith("["):
        end = text.find("]")
        if end < 0:
            return None
        text = text[1:end]
    elif text.count(":") == 1:
        text = text.split(":", 1)[0]
    text = text.split("%", 1)[0]  # IPv6 zone index
    try:
        return ipaddress.ip_address(text)
    except ValueError:
        return None


def _candidates(meta):
    forwarded = meta.get("HTTP_X_FORWARDED_FOR")
    if forwarded:
        yield from str(forwarded).split(",")
    yield meta.get("HTTP_X_REAL_IP")
    yield meta.get("REMOTE_ADDR")


def client_ip(meta, ipv4_mask=32, ipv6_mask=64):
    """Masked client IP, keeping SAPL's header priority.

    X-Forwarded-For first, then X-Real-IP, then REMOTE_ADDR; invalid items are
    skipped instead of raising, so a malformed header never becomes HTTP 500.
    """
    for candidate in _candidates(meta):
        address = parse_ip(candidate)
        if address is None:
            continue
        mask = ipv6_mask if address.version == 6 else ipv4_mask
        return str(ipaddress.ip_network((address, mask), strict=False).network_address)
    return UNKNOWN_IP
