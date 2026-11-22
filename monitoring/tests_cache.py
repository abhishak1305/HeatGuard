from datetime import datetime, timezone as datetime_timezone
from unittest.mock import Mock

from django.core.cache import cache
from django.test import SimpleTestCase

from .weather_cache import cached_weather_forecast


class WeatherResponseCacheTests(SimpleTestCase):
    def setUp(self):
        cache.clear()

    def tearDown(self):
        cache.clear()

    def test_cache_key_uses_normalized_coordinates_and_preserves_retrieval_time(self):
        retrieved_at = datetime(2026, 11, 22, 12, tzinfo=datetime_timezone.utc)
        response = {'retrieved_at': retrieved_at, 'provider': 'Open-Meteo'}
        fetcher = Mock(return_value=response)

        first = cached_weather_forecast('28.613901', '77.209001', fetcher=fetcher)
        second = cached_weather_forecast('28.613904', '77.209004', fetcher=fetcher)

        self.assertIs(first, response)
        self.assertEqual(second, response)
        self.assertEqual(second['retrieved_at'], retrieved_at)
        fetcher.assert_called_once()

    def test_failed_provider_response_is_not_cached(self):
        fetcher = Mock(side_effect=[TimeoutError('offline'), {'provider': 'Open-Meteo'}])

        with self.assertRaises(TimeoutError):
            cached_weather_forecast(28.6, 77.2, fetcher=fetcher)
        result = cached_weather_forecast(28.6, 77.2, fetcher=fetcher)

        self.assertEqual(result, {'provider': 'Open-Meteo'})
        self.assertEqual(fetcher.call_count, 2)
