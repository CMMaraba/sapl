"""Preserve SAPL's historical pytz localization semantics with Django ZoneInfo."""
import pytz
from django.utils import timezone


def localize_legacy(value, tz=None):
    """Keep the old localize(is_dst=False) decision at DST transitions."""
    if timezone.is_aware(value):
        raise ValueError('Not naive datetime (tzinfo is already set)')
    if tz is None:
        tz = timezone.get_default_timezone()
    if hasattr(tz, 'localize'):
        return tz.localize(value)
    zone_name = getattr(tz, 'key', None)
    if zone_name is not None:
        return pytz.timezone(zone_name).localize(value)
    return timezone.make_aware(value, tz)
