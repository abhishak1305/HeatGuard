import io
import json
import urllib.error
import ssl
from decimal import Decimal
from unittest.mock import patch, MagicMock
from django.test import TestCase, Client
from django.core.cache import cache
from django.urls import reverse
from django.contrib.auth.models import User
from django.utils import timezone

from .models import Location, WeatherRecord
from .forms import CitySearchForm
from .weather_service import (
    geocode_city,
    fetch_weather_forecast,
    WeatherNetworkError,
    WeatherAPIError,
    WeatherDataFormatError,
    WeatherTLSVerificationError,
)
from .utils import calculate_heat_index


class WeatherServiceMockedTestCase(TestCase):
    """
    Unit tests for weather_service.py using unittest.mock.
    Does not require an active internet connection.
    """

    @patch('urllib.request.urlopen')
    def test_geocode_city_success(self, mock_urlopen):
        sample_geo_json = {
            "results": [
                {
                    "id": 1850147,
                    "name": "Tokyo",
                    "latitude": 35.6895,
                    "longitude": 139.69171,
                    "admin1": "Tokyo",
                    "country": "Japan",
                    "timezone": "Asia/Tokyo"
                }
            ]
        }
        mock_response = MagicMock()
        mock_response.getcode.return_value = 200
        mock_response.read.return_value = json.dumps(sample_geo_json).encode('utf-8')
        mock_urlopen.return_value.__enter__.return_value = mock_response

        result = geocode_city("Tokyo")
        self.assertIsNotNone(result)
        self.assertEqual(result['name'], "Tokyo")
        self.assertEqual(result['country'], "Japan")
        self.assertEqual(result['latitude'], Decimal("35.68950"))
        self.assertEqual(result['longitude'], Decimal("139.69171"))

    @patch('urllib.request.urlopen')
    def test_geocode_city_no_results(self, mock_urlopen):
        mock_response = MagicMock()
        mock_response.getcode.return_value = 200
        mock_response.read.return_value = json.dumps({"results": []}).encode('utf-8')
        mock_urlopen.return_value.__enter__.return_value = mock_response

        result = geocode_city("NonexistentPlaceXYZ")
        self.assertIsNone(result)

    @patch('urllib.request.urlopen')
    def test_geocode_city_network_timeout(self, mock_urlopen):
        mock_urlopen.side_effect = TimeoutError("Connection timed out")

        with self.assertRaises(WeatherNetworkError):
            geocode_city("London")

    @patch('urllib.request.urlopen')
    def test_geocode_tls_failure_is_not_retried_insecurely(self, mock_urlopen):
        mock_urlopen.side_effect = urllib.error.URLError(ssl.SSLCertVerificationError("bad certificate"))
        with self.assertRaises(WeatherTLSVerificationError):
            geocode_city("London")
        mock_urlopen.assert_called_once()

    @patch('urllib.request.urlopen')
    def test_forecast_tls_failure_is_not_retried_insecurely(self, mock_urlopen):
        mock_urlopen.side_effect = urllib.error.URLError(ssl.SSLCertVerificationError("bad certificate"))
        with self.assertRaises(WeatherTLSVerificationError):
            fetch_weather_forecast(Decimal('28.61390'), Decimal('77.20900'))
        mock_urlopen.assert_called_once()

    @patch('urllib.request.urlopen')
    def test_geocode_city_http_error(self, mock_urlopen):
        mock_urlopen.side_effect = urllib.error.HTTPError(
            url="https://geocoding-api.open-meteo.com/v1/search",
            code=500,
            msg="Internal Server Error",
            hdrs={},
            fp=io.BytesIO(b"Server Error")
        )

        with self.assertRaises(WeatherAPIError):
            geocode_city("Paris")

    @patch('urllib.request.urlopen')
    def test_geocode_city_invalid_json(self, mock_urlopen):
        mock_response = MagicMock()
        mock_response.getcode.return_value = 200
        mock_response.read.return_value = b"<html>Not JSON</html>"
        mock_urlopen.return_value.__enter__.return_value = mock_response

        with self.assertRaises(WeatherDataFormatError):
            geocode_city("Berlin")

    @patch('urllib.request.urlopen')
    def test_fetch_weather_forecast_success(self, mock_urlopen):
        sample_forecast_json = {
            "latitude": 35.6895,
            "longitude": 139.69171,
            "timezone": "Asia/Tokyo",
            "current": {
                "time": "2026-11-20T12:00",
                "temperature_2m": 31.5,
                "relative_humidity_2m": 65,
                "apparent_temperature": 37.2,
                "wind_speed_10m": 12.4
            },
            "daily": {
                "time": ["2026-11-20", "2026-11-21"],
                "temperature_2m_max": [33.0, 34.0],
                "temperature_2m_min": [24.0, 25.0]
            }
        }
        mock_response = MagicMock()
        mock_response.getcode.return_value = 200
        mock_response.read.return_value = json.dumps(sample_forecast_json).encode('utf-8')
        mock_urlopen.return_value.__enter__.return_value = mock_response

        data = fetch_weather_forecast(Decimal("35.6895"), Decimal("139.69171"))
        self.assertEqual(data['provider'], "Open-Meteo")
        self.assertEqual(data['current']['temperature_c'], Decimal("31.5"))
        self.assertEqual(data['current']['relative_humidity'], Decimal("65"))
        self.assertIn("Open-Meteo.com", data['attribution'])

    @patch('urllib.request.urlopen')
    def test_fetch_weather_forecast_missing_current_block(self, mock_urlopen):
        mock_response = MagicMock()
        mock_response.getcode.return_value = 200
        mock_response.read.return_value = json.dumps({"latitude": 10.0}).encode('utf-8')
        mock_urlopen.return_value.__enter__.return_value = mock_response

        with self.assertRaises(WeatherDataFormatError):
            fetch_weather_forecast(Decimal("10.0"), Decimal("20.0"))

    @patch('urllib.request.urlopen')
    def test_fetch_weather_forecast_keeps_temperature_when_humidity_is_missing(self, mock_urlopen):
        for humidity_field in ('missing', None):
            with self.subTest(humidity_field=humidity_field):
                current = {
                    'time': '2026-11-20T12:00',
                    'temperature_2m': 31.5,
                }
                if humidity_field is None:
                    current['relative_humidity_2m'] = None
                mock_response = MagicMock()
                mock_response.getcode.return_value = 200
                mock_response.read.return_value = json.dumps({
                    'timezone': 'Asia/Kolkata',
                    'current': current,
                }).encode('utf-8')
                mock_urlopen.return_value.__enter__.return_value = mock_response

                result = fetch_weather_forecast(Decimal('28.6'), Decimal('77.2'))

                self.assertEqual(result['current']['temperature_c'], Decimal('31.5'))
                self.assertIsNone(result['current']['relative_humidity'])


class HeatIndexCalculationTestCase(TestCase):
    def test_heat_index_high_stress(self):
        # 35°C and 70% humidity produces Danger level heat index
        hi_val, risk, note = calculate_heat_index(Decimal("35.0"), Decimal("70.0"))
        self.assertIsNotNone(hi_val)
        self.assertIn(risk, ['DANGER', 'EXTREME_DANGER'])

    def test_heat_index_below_threshold(self):
        # 20°C is below the 26.7°C (80°F) threshold, uses simple Steadman equation
        hi_val, risk, note = calculate_heat_index(Decimal("20.0"), Decimal("50.0"))
        self.assertAlmostEqual(float(hi_val), 20.0, delta=1.5)
        self.assertEqual(risk, 'NORMAL')


class CityDashboardWorkflowTestCase(TestCase):
    def setUp(self):
        cache.clear()
        self.client = Client()
        self.location = Location.objects.create(
            name="Test City",
            state_or_region="Test Region",
            country="Testland",
            latitude=Decimal("28.61390"),
            longitude=Decimal("77.20900")
        )

    @patch('monitoring.views.fetch_weather_forecast')
    def test_city_dashboard_success_flow(self, mock_fetch):
        mock_fetch.return_value = {
            'provider': "Open-Meteo",
            'model_context': "Numerical weather prediction model output",
            'retrieved_at': timezone.now(),
            'latitude': 28.61,
            'longitude': 77.21,
            'timezone': "Asia/Kolkata",
            'current': {
                'time': "2026-11-20T12:00",
                'temperature_c': Decimal("32.0"),
                'relative_humidity': Decimal("60.0"),
                'apparent_temperature_c': Decimal("37.0"),
                'wind_speed_kmh': Decimal("10.0"),
            },
            'daily': [],
            'attribution': "Weather data by Open-Meteo.com",
        }

        url = reverse('monitoring:city_dashboard', kwargs={'location_id': self.location.id})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "32.0 °C")
        self.assertContains(response, "Weather data by Open-Meteo.com")
        self.assertContains(response, "Numerical weather prediction model output")

        # A dashboard GET displays data but never writes a history record.
        self.assertFalse(WeatherRecord.objects.filter(location=self.location, data_source='provider-supplied').exists())

    @patch('monitoring.views.fetch_weather_forecast')
    def test_city_dashboard_weather_provider_failure_honest_error(self, mock_fetch):
        mock_fetch.side_effect = WeatherNetworkError("Gateway Timeout")

        url = reverse('monitoring:city_dashboard', kwargs={'location_id': self.location.id})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Live Telemetry Unavailable")
        self.assertContains(response, "HeatGuard does not synthesize fallback values")
        self.assertNotContains(response, "Gateway Timeout")
        self.assertContains(response, "Please try again later")

    @patch('monitoring.views.fetch_weather_forecast')
    def test_city_dashboard_unexpected_error_does_not_expose_exception(self, mock_fetch):
        mock_fetch.side_effect = RuntimeError("private upstream traceback detail")
        url = reverse('monitoring:city_dashboard', kwargs={'location_id': self.location.id})

        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Unexpected error while processing live weather data")
        self.assertNotContains(response, "private upstream traceback detail")

    @patch('monitoring.services.geocode_city')
    def test_city_search_does_not_show_raw_provider_exception(self, mock_geocode):
        mock_geocode.side_effect = WeatherNetworkError("internal proxy token")
        url = reverse('monitoring:city_search') + '?city=Unlisted+Town'

        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "City lookup is currently unavailable")
        self.assertNotContains(response, "internal proxy token")
