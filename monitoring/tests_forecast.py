import json
from decimal import Decimal
from unittest.mock import patch
from django.test import TestCase, Client
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
