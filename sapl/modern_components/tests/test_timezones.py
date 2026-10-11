from datetime import datetime, timedelta, timezone as fixed_timezone
from zoneinfo import ZoneInfo

import pytz
from django.test import SimpleTestCase, override_settings

from sapl.modern_components.timezones import localize_legacy


class LegacyTimezoneTests(SimpleTestCase):
    def test_named_zones_match_original_localize_including_dst_boundaries(self):
        cases = [
            ('America/Sao_Paulo', datetime(2018, 2, 17, 23, 30)),
            ('America/Sao_Paulo', datetime(2018, 11, 4, 0, 30)),
            ('America/Sao_Paulo', datetime(2026, 10, 11, 12, 30)),
            ('America/New_York', datetime(2025, 11, 2, 1, 30)),
            ('Europe/London', datetime(2025, 10, 26, 1, 30)),
            ('UTC', datetime(2026, 10, 11, 12, 30)),
        ]
        for name, value in cases:
            with self.subTest(zone=name, value=value):
                expected = pytz.timezone(name).localize(value)
                self.assertEqual(localize_legacy(value, ZoneInfo(name)), expected)

    def test_sao_paulo_ambiguous_hour_keeps_standard_time(self):
        value = datetime(2018, 2, 17, 23, 30)
        result = localize_legacy(value, ZoneInfo('America/Sao_Paulo'))
        self.assertEqual(result.utcoffset(), timedelta(hours=-3))

    @override_settings(TIME_ZONE='America/Sao_Paulo')
    def test_default_django_zone_is_supported(self):
        result = localize_legacy(datetime(2018, 2, 17, 23, 30))
        self.assertEqual(result.utcoffset(), timedelta(hours=-3))

    def test_explicit_pytz_zone_is_supported(self):
        value = datetime(2018, 2, 17, 23, 30)
        tz = pytz.timezone('America/Sao_Paulo')
        self.assertEqual(localize_legacy(value, tz), tz.localize(value))

    def test_fixed_offset_is_preserved(self):
        value = datetime(2026, 10, 11, 12, 30)
        tz = fixed_timezone(timedelta(hours=-3))
        self.assertEqual(localize_legacy(value, tz), value.replace(tzinfo=tz))

    def test_already_aware_is_rejected_like_production(self):
        with self.assertRaises(ValueError):
            localize_legacy(datetime.now(fixed_timezone.utc))
