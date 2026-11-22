import json
from decimal import Decimal
from unittest.mock import patch
from django.test import TestCase, Client
from django.core.cache import cache
from django.urls import reverse
from django.utils import timezone

from monitoring.models import Location
from monitoring.weather_service import WeatherNetworkError


class ForecastPageTestCase(TestCase):
    """
    Tests for the HeatGuard forecast page:
    - Rendering hourly (next-24-hour) and daily (7-day) forecast arrays.
    - Confirming missing humidity does NOT produce a fabricated Heat Index.
    - Confirming local timezone and issue/retrieval time metadata are rendered.
    - Confirming forecast wording is explicitly distinct from official government notices.
    """

    def setUp(self):
        cache.clear()
        self.client = Client()
        self.location = Location.objects.create(
            name="Jaipur Observatory",
            state_or_region="Rajasthan",
            country="India",
            latitude=Decimal("26.91240"),
            longitude=Decimal("75.78730")
        )

    @patch('monitoring.views.fetch_weather_forecast')
    def test_forecast_page_renders_hourly_and_daily_arrays(self, mock_fetch):
        """Verify that 24-hour hourly items and 7-day daily forecast arrays render properly."""
        mock_fetch.return_value = {
            'provider': "Open-Meteo",
            'model_context': "Numerical weather prediction model output",
            'retrieved_at': timezone.now(),
            'latitude': 26.91,
            'longitude': 75.79,
            'timezone': "Asia/Kolkata",
            'timezone_abbreviation': "IST",
            'current': {
                'time': "2026-11-20T12:00",
                'temperature_c': Decimal("32.0"),
                'relative_humidity': Decimal("45.0"),
                'apparent_temperature_c': Decimal("33.5"),
                'wind_speed_kmh': Decimal("12.0"),
            },
            'hourly': [
                {
                    'time': "2026-11-20T12:00",
                    'temperature_c': Decimal("32.0"),
                    'relative_humidity': Decimal("45.0"),
                    'apparent_temperature_c': Decimal("33.5"),
                    'wind_speed_kmh': Decimal("12.0"),
                },
                {
                    'time': "2026-11-20T13:00",
                    'temperature_c': Decimal("35.0"),
                    'relative_humidity': Decimal("50.0"),
                    'apparent_temperature_c': Decimal("39.0"),
                    'wind_speed_kmh': Decimal("10.0"),
                }
            ],
            'daily': [
                {
                    'date': "2026-11-20",
                    'max_temp_c': Decimal("36.0"),
                    'min_temp_c': Decimal("22.0"),
                    'apparent_max_c': Decimal("38.0"),
                    'apparent_min_c': Decimal("21.0"),
                },
                {
                    'date': "2026-11-21",
                    'max_temp_c': Decimal("37.5"),
                    'min_temp_c': Decimal("23.0"),
                    'apparent_max_c': Decimal("40.0"),
                    'apparent_min_c': Decimal("22.0"),
                }
            ],
            'attribution': "Weather data by Open-Meteo.com (CC BY 4.0 license)",
        }

        url = reverse('monitoring:forecast') + f'?location_id={self.location.id}'
        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)
        # Location, Provider, and Timezone
        self.assertContains(response, "Jaipur Observatory")
        self.assertContains(response, "Asia/Kolkata")
        self.assertContains(response, "IST")
        self.assertContains(response, "Open-Meteo")
        # Section titles
        self.assertContains(response, "Forecast-Based Heat-Risk Outlook")
        self.assertContains(response, "Next 24-Hour Hourly Temperature")
        self.assertContains(response, "7-Day Daily Weather Outlook")
        # Peak values
        self.assertContains(response, "Peak Hottest Forecast Hour (Next 24h)")
        self.assertContains(response, "Peak Hottest Forecast Day (7-Day Horizon)")
        self.assertContains(response, "35.0 °C")  # Hottest hour
        self.assertContains(response, "37.5 °C")  # Hottest day
        # Units
        self.assertContains(response, "°C")
        self.assertContains(response, "%")
        self.assertContains(response, "km/h")

    @patch('monitoring.views.fetch_weather_forecast')
    def test_forecast_missing_humidity_does_not_produce_heat_index(self, mock_fetch):
        """
        Verify that an hourly entry with missing relative humidity renders 'Not available'
        and does NOT calculate or fabricate a Heat Index.
        """
        mock_fetch.return_value = {
            'provider': "Open-Meteo",
            'model_context': "Numerical weather prediction model output",
            'retrieved_at': timezone.now(),
            'latitude': 26.91,
            'longitude': 75.79,
            'timezone': "Asia/Kolkata",
            'timezone_abbreviation': "IST",
            'current': {
                'time': "2026-11-20T12:00",
                'temperature_c': Decimal("32.0"),
                'relative_humidity': Decimal("45.0"),
                'apparent_temperature_c': Decimal("33.5"),
                'wind_speed_kmh': Decimal("12.0"),
            },
            'hourly': [
                {
                    'time': "2026-11-20T14:00",
                    'temperature_c': Decimal("33.0"),
                    'relative_humidity': None,  # MISSING HUMIDITY
                    'apparent_temperature_c': None,
                    'wind_speed_kmh': Decimal("15.0"),
                }
            ],
            'daily': [],
            'attribution': "Weather data by Open-Meteo.com",
        }

        url = reverse('monitoring:forecast') + f'?location_id={self.location.id}'
        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)
        content = response.content.decode('utf-8')
        self.assertIn("33.0 °C", content)
        self.assertIn("Not available", content)
        # Ensure no fabricated Heat Index was computed for 14:00
        processed_hourly = response.context['processed_hourly']
        self.assertIsNone(processed_hourly[0]['heat_index'])

    @patch('monitoring.views.fetch_weather_forecast')
    def test_forecast_wording_is_distinct_from_official_notices(self, mock_fetch):
        """
        Verify that the forecast page includes explicit disclaimers and never
        describes model outlooks as official government declarations.
        """
        mock_fetch.return_value = {
            'provider': "Open-Meteo",
            'model_context': "Numerical weather prediction model output",
            'retrieved_at': timezone.now(),
            'latitude': 26.91,
            'longitude': 75.79,
            'timezone': "Asia/Kolkata",
            'timezone_abbreviation': "IST",
            'current': {
                'time': "2026-11-20T12:00",
                'temperature_c': Decimal("30.0"),
                'relative_humidity': Decimal("40.0"),
                'apparent_temperature_c': Decimal("30.0"),
                'wind_speed_kmh': Decimal("10.0"),
            },
            'hourly': [],
            'daily': [],
            'attribution': "Weather data by Open-Meteo.com",
        }

        url = reverse('monitoring:forecast') + f'?location_id={self.location.id}'
        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Forecast-Based Heat-Risk Outlook")
        self.assertContains(response, "an official government heatwave declaration")
        self.assertContains(response, "review official meteorological bulletins")

    @patch('monitoring.views.fetch_weather_forecast')
    def test_forecast_excludes_hours_before_provider_now(self, mock_fetch):
        """
        Regression test: the provider returns hours from the start of the day,
        so the page must drop past hours and only show the upcoming 24 hours.
        """
        def hourly_entry(time_str, temp, rh):
            return {
                'time': time_str,
                'temperature_c': Decimal(temp),
                'relative_humidity': Decimal(rh),
                'apparent_temperature_c': None,
                'wind_speed_kmh': None,
            }

        mock_fetch.return_value = {
            'provider': "Open-Meteo",
            'model_context': "Numerical weather prediction model output",
            'retrieved_at': timezone.now(),
            'latitude': 26.91,
            'longitude': 75.79,
            'timezone': "Asia/Kolkata",
            'timezone_abbreviation': "IST",
            'current': {
                'time': "2026-11-20T12:00",
                'temperature_c': Decimal("30.0"),
                'relative_humidity': Decimal("40.0"),
                'apparent_temperature_c': None,
                'wind_speed_kmh': None,
            },
            'hourly': [
                hourly_entry("2026-11-20T06:00", "22.0", "30.0"),  # past
                hourly_entry("2026-11-20T11:00", "28.0", "35.0"),  # past
                hourly_entry("2026-11-20T12:00", "30.0", "40.0"),  # now
                hourly_entry("2026-11-20T14:00", "36.0", "45.0"),  # future (hottest)
            ],
            'daily': [],
            'attribution': "Weather data by Open-Meteo.com",
        }

        url = reverse('monitoring:forecast') + f'?location_id={self.location.id}'
        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)
        processed = response.context['processed_hourly']
        times = [item['time'] for item in processed]
        self.assertEqual(
            times,
            ["2026-11-20T12:00", "2026-11-20T14:00"],
            "Past hourly entries must be excluded from the forecast window",
        )
        # Hottest hour must come from the remaining (future) window
        self.assertEqual(response.context['hottest_hour']['time'], "2026-11-20T14:00")
        self.assertNotContains(response, "2026-11-20T06:00")

    @patch('monitoring.views.fetch_weather_forecast')
    def test_forecast_provider_error_does_not_expose_exception(self, mock_fetch):
        mock_fetch.side_effect = WeatherNetworkError("private gateway hostname and token")
        url = reverse('monitoring:forecast') + f'?location_id={self.location.id}'

        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Forecast telemetry is currently unavailable")
        self.assertNotContains(response, "private gateway hostname and token")

    @patch('monitoring.views.fetch_weather_forecast')
    def test_forecast_window_uses_timezone_aware_instants_and_separate_peaks(self, mock_fetch):
        mock_fetch.return_value = {
            'provider': 'Open-Meteo',
            'retrieved_at': timezone.now(),
            'timezone': 'Asia/Kolkata',
            'timezone_abbreviation': 'IST',
            'current': {
                'time': '2026-11-20T12:00',
                'temperature_c': Decimal('30'),
                'relative_humidity': Decimal('50'),
            },
            'hourly': [
                {'time': '2026-11-20T06:29:00Z', 'temperature_c': Decimal('50'), 'relative_humidity': Decimal('50')},
                {'time': '2026-11-20T12:00', 'temperature_c': Decimal('35'), 'relative_humidity': Decimal('50')},
                {'time': '2026-11-20T14:00', 'temperature_c': Decimal('34'), 'relative_humidity': Decimal('100')},
                {'time': '2026-11-20T12:30', 'temperature_c': None, 'relative_humidity': Decimal('90')},
                {'time': '2026-11-21T06:30:00Z', 'temperature_c': Decimal('60'), 'relative_humidity': Decimal('90')},
                {'time': 'not-a-time', 'temperature_c': Decimal('70'), 'relative_humidity': Decimal('90')},
            ],
            'daily': [],
        }
        url = reverse('monitoring:forecast') + f'?location_id={self.location.pk}'

        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)
        hourly = response.context['processed_hourly']
        self.assertEqual(
            [item['time'] for item in hourly],
            ['2026-11-20T12:00', '2026-11-20T12:30', '2026-11-20T14:00'],
        )
        self.assertIsNone(hourly[1]['heat_index'])
        self.assertEqual(response.context['hottest_hour']['temperature_c'], Decimal('35'))
        self.assertEqual(
            response.context['peak_heat_index_hour']['temperature_c'], Decimal('34')
        )
        self.assertNotContains(response, '2026-11-20T06:29:00Z')
        self.assertNotContains(response, '2026-11-21T06:30:00Z')
        self.assertContains(response, 'Peak Heat Index:')

    @patch('monitoring.views.fetch_weather_forecast')
    def test_forecast_temperatures_use_fahrenheit_preference(self, mock_fetch):
        mock_fetch.return_value = {
            'retrieved_at': timezone.now(),
            'timezone': 'Asia/Kolkata',
            'current': {'time': '2026-11-20T12:00', 'temperature_c': Decimal('30'), 'relative_humidity': Decimal('50')},
            'hourly': [
                {'time': '2026-11-20T12:00', 'temperature_c': Decimal('30'), 'relative_humidity': Decimal('50')},
            ],
            'daily': [],
        }
        self.client.cookies['heatguard_temp_unit'] = 'F'
        url = reverse('monitoring:forecast') + f'?location_id={self.location.pk}'

        response = self.client.get(url)

        self.assertContains(response, '86.0 °F')
        self.assertNotContains(response, '30.0 °C')
