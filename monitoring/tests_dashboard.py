import json
from decimal import Decimal
from unittest.mock import patch
from django.test import TestCase, Client
from django.core.cache import cache
from django.urls import reverse
from django.contrib.auth.models import User
from django.utils import timezone
from datetime import timedelta
from datetime import datetime
from zoneinfo import ZoneInfo

from monitoring.models import Location, WeatherRecord, OfficialNotice
from monitoring.weather_service import WeatherNetworkError


class CityDashboardComprehensiveTestCase(TestCase):
    """
    Comprehensive tests for the working City Monitoring Dashboard:
    - Valid location telemetry rendering
    - Missing optional provider fields (apparent temp, wind speed) showing 'Not available' without substituting zero
    - Provider failure rendering an honest error panel
    - Single WeatherRecord creation tied to correct Location and user/anonymous
    """

    def setUp(self):
        cache.clear()
        self.client = Client()
        self.user = User.objects.create_user(
            username="analyst_bob",
            email="bob@example.com",
            password="securepassword123"
        )
        self.location = Location.objects.create(
            name="Ahmedabad Station",
            state_or_region="Gujarat",
            country="India",
            latitude=Decimal("23.02250"),
            longitude=Decimal("72.57140")
        )
        # Add an official notice for this location
        now = timezone.now()
        OfficialNotice.objects.create(
            location=self.location,
            title="Orange Heat Warning for Central Ahmedabad",
            message="Severe afternoon heat conditions expected. Drink ORS, water, and buttermilk.",
            severity="WARNING",
            issuing_organization="Ahmedabad Municipal Corporation / IMD",
            source_url="https://example.gov/advisory/101",
            valid_from=now,
            valid_until=now + timedelta(days=1),
            created_by=self.user,
            is_published=True
        )

    @patch('monitoring.views.fetch_weather_forecast')
    def test_dashboard_valid_location_data(self, mock_fetch):
        """Test full dashboard rendering with all provider fields and heat index calculation."""
        mock_fetch.return_value = {
            'provider': "Open-Meteo",
            'model_context': "Numerical weather prediction model output (grid-interpolated)",
            'retrieved_at': timezone.now(),
            'latitude': 23.02,
            'longitude': 72.57,
            'timezone': "Asia/Kolkata",
            'current': {
                'time': "2026-11-20T12:00",
                'temperature_c': Decimal("36.5"),
                'relative_humidity': Decimal("55.0"),
                'apparent_temperature_c': Decimal("43.2"),
                'wind_speed_kmh': Decimal("14.5"),
            },
            'daily': [],
            'attribution': "Weather data by Open-Meteo.com (CC BY 4.0 license)",
        }

        url = reverse('monitoring:city_dashboard', kwargs={'location_id': self.location.id})
        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)
        # Location info
        self.assertContains(response, "Ahmedabad Station")
        self.assertContains(response, "Gujarat, India")
        # Telemetry metrics with units
        self.assertContains(response, "36.5 °C")
        self.assertContains(response, "55.0%")
        self.assertContains(response, "43.2 °C")
        self.assertContains(response, "14.5 km/h")
        # Heat Index and assessment
        self.assertContains(response, "Human Thermal Stress Assessment")
        self.assertContains(response, "Heat Index-based estimate")
        self.assertContains(response, "DANGER")
        self.assertContains(response, "Recommended Precautions")
        self.assertContains(response, "Detailed Forecast")
        # Official notice section
        self.assertContains(response, "Orange Heat Warning for Central Ahmedabad")
        self.assertContains(response, "Ahmedabad Municipal Corporation / IMD")
        # Source attribution
        self.assertContains(response, "Weather data by Open-Meteo.com")
        self.assertContains(response, "Numerical weather prediction model output")

        # Dashboard reads must not write history.
        self.assertFalse(WeatherRecord.objects.filter(location=self.location).exists())

    @patch('monitoring.views.fetch_weather_forecast')
    def test_explicit_post_saves_provider_observation_and_retrieval_times(self, mock_fetch):
        retrieved_at = timezone.now()
        mock_fetch.return_value = {
            'provider': 'Open-Meteo',
            'retrieved_at': retrieved_at,
            'timezone': 'Asia/Kolkata',
            'current': {
                'time': '2026-11-20T12:00',
                'temperature_c': Decimal('36.5'),
                'relative_humidity': Decimal('55'),
                'apparent_temperature_c': Decimal('43.2'),
                'wind_speed_kmh': Decimal('14.5'),
            },
            'attribution': 'Weather data by Open-Meteo.com',
        }
        self.client.force_login(self.user)
        url = reverse('monitoring:city_dashboard', kwargs={'location_id': self.location.pk})

        response = self.client.post(url, {'action': 'save_reading'})

        self.assertRedirects(response, url, fetch_redirect_response=False)
        record = WeatherRecord.objects.get(location=self.location)
        self.assertEqual(
            record.recorded_at,
            datetime(2026, 11, 20, 12, 0, tzinfo=ZoneInfo('Asia/Kolkata')),
        )
        self.assertEqual(record.retrieved_at, retrieved_at)
        self.assertEqual(record.temperature_c, Decimal('36.5'))
        self.assertEqual(record.requested_by, self.user)

    @patch('monitoring.views.fetch_weather_forecast')
    def test_repeated_post_and_refresh_do_not_duplicate_observation(self, mock_fetch):
        mock_fetch.return_value = {
            'retrieved_at': timezone.now(),
            'timezone': 'Asia/Kolkata',
            'current': {
                'time': '2026-11-20T12:00',
                'temperature_c': Decimal('36.5'),
                'relative_humidity': Decimal('55'),
            },
        }
        url = reverse('monitoring:city_dashboard', kwargs={'location_id': self.location.pk})

        self.client.post(url, {'action': 'save_reading'})
        self.client.post(url, {'action': 'save_reading'})
        self.client.get(url)

        self.assertEqual(WeatherRecord.objects.filter(location=self.location).count(), 1)

    @patch('monitoring.views.fetch_weather_forecast')
    def test_saved_observation_without_humidity_has_no_risk_assessment(self, mock_fetch):
        mock_fetch.return_value = {
            'retrieved_at': timezone.now(),
            'timezone': 'Asia/Kolkata',
            'current': {
                'time': '2026-11-20T12:00',
                'temperature_c': Decimal('36.5'),
                'relative_humidity': None,
            },
        }
        url = reverse('monitoring:city_dashboard', kwargs={'location_id': self.location.pk})

        self.client.post(url, {'action': 'save_reading'})

        record = WeatherRecord.objects.get(location=self.location)
        self.assertIsNone(record.heat_index_c)
        self.assertIsNone(record.risk_level)

    @patch('monitoring.views.fetch_weather_forecast')
    def test_fahrenheit_preference_converts_dashboard_temperatures(self, mock_fetch):
        mock_fetch.return_value = {
            'retrieved_at': timezone.now(),
            'timezone': 'Asia/Kolkata',
            'current': {
                'time': '2026-11-20T12:00',
                'temperature_c': Decimal('36.5'),
                'relative_humidity': Decimal('55'),
                'apparent_temperature_c': Decimal('43.2'),
                'wind_speed_kmh': Decimal('14.5'),
            },
        }
        self.client.cookies['heatguard_temp_unit'] = 'F'
        url = reverse('monitoring:city_dashboard', kwargs={'location_id': self.location.pk})

        response = self.client.get(url)

        self.assertContains(response, '97.7 °F')
        self.assertContains(response, '109.8 °F')
        self.assertNotContains(response, '36.5 °C')
        self.assertFalse(WeatherRecord.objects.filter(location=self.location).exists())

    @patch('monitoring.views.fetch_weather_forecast')
    def test_missing_humidity_renders_assessment_unavailable_without_empty_labels(self, mock_fetch):
        mock_fetch.return_value = {
            'current': {
                'time': '2026-11-20T12:00',
                'temperature_c': Decimal('36.5'),
                'relative_humidity': None,
            },
            'timezone': 'Asia/Kolkata',
        }
        url = reverse('monitoring:city_dashboard', kwargs={'location_id': self.location.pk})

        response = self.client.get(url)

        self.assertContains(response, 'Heat Index assessment is unavailable')
        self.assertContains(response, 'Not available')
        self.assertNotContains(response, 'Why this category was assigned:')
        self.assertNotContains(response, '<strong>Assessment:</strong>')
        self.assertNotContains(response, 'Method:  • Adjustment:')

    @patch('monitoring.views.fetch_weather_forecast')
    def test_save_reading_post_requires_csrf_token(self, mock_fetch):
        mock_fetch.return_value = {
            'retrieved_at': timezone.now(),
            'timezone': 'Asia/Kolkata',
            'current': {'time': '2026-11-20T12:00', 'temperature_c': Decimal('30'), 'relative_humidity': Decimal('50')},
        }
        csrf_client = Client(enforce_csrf_checks=True)
        url = reverse('monitoring:city_dashboard', kwargs={'location_id': self.location.pk})

        page = csrf_client.get(url)
        rejected = csrf_client.post(url, {'action': 'save_reading'})

        self.assertContains(page, 'csrfmiddlewaretoken')
        self.assertEqual(rejected.status_code, 403)
        self.assertFalse(WeatherRecord.objects.filter(location=self.location).exists())

    @patch('monitoring.views.fetch_weather_forecast')
    def test_dashboard_authenticated_user_sets_requested_by(self, mock_fetch):
        """Test that authenticated user sets requested_by on the saved WeatherRecord."""
        mock_fetch.return_value = {
            'provider': "Open-Meteo",
            'model_context': "Numerical model output",
            'retrieved_at': timezone.now(),
            'latitude': 23.02,
            'longitude': 72.57,
            'timezone': "Asia/Kolkata",
            'current': {
                'time': "2026-11-20T12:00",
                'temperature_c': Decimal("30.0"),
                'relative_humidity': Decimal("50.0"),
                'apparent_temperature_c': Decimal("32.0"),
                'wind_speed_kmh': Decimal("8.0"),
            },
            'daily': [],
            'attribution': "Weather data by Open-Meteo.com",
        }

        self.client.force_login(self.user)
        url = reverse('monitoring:city_dashboard', kwargs={'location_id': self.location.id})
        response = self.client.post(url, {'action': 'save_reading'})
        self.assertEqual(response.status_code, 302)

        record = WeatherRecord.objects.filter(location=self.location).latest('recorded_at')
        self.assertEqual(record.requested_by, self.user)

    @patch('monitoring.views.fetch_weather_forecast')
    def test_dashboard_missing_optional_provider_fields(self, mock_fetch):
        """
        Verify that missing optional fields (apparent temperature, wind speed)
        display 'Not available' and do NOT substitute zero.
        """
        mock_fetch.return_value = {
            'provider': "Open-Meteo",
            'model_context': "Model output",
            'retrieved_at': timezone.now(),
            'latitude': 23.02,
            'longitude': 72.57,
            'timezone': "Asia/Kolkata",
            'current': {
                'time': "2026-11-20T12:00",
                'temperature_c': Decimal("28.0"),
                'relative_humidity': Decimal("60.0"),
                'apparent_temperature_c': None,  # Absent optional field
                'wind_speed_kmh': None,          # Absent optional field
            },
            'daily': [],
            'attribution': "Weather data by Open-Meteo.com",
        }

        url = reverse('monitoring:city_dashboard', kwargs={'location_id': self.location.id})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

        content = response.content.decode('utf-8')
        self.assertIn("Not available", content)
        # Ensure zero was not substituted as wind speed or apparent temp
        self.assertNotIn("0.0 km/h", content)
        self.assertNotIn("0 km/h", content)

    @patch('monitoring.views.fetch_weather_forecast')
    def test_dashboard_provider_failure_renders_honest_error_panel(self, mock_fetch):
        """Verify that provider failure displays honest error panel and avoids saving WeatherRecord."""
        initial_record_count = WeatherRecord.objects.count()
        mock_fetch.side_effect = WeatherNetworkError("Connection timed out after 5.0 seconds")

        url = reverse('monitoring:city_dashboard', kwargs={'location_id': self.location.id})
        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Live Telemetry Unavailable")
        self.assertNotContains(response, "Connection timed out after 5.0 seconds")
        self.assertContains(response, "Please try again later")
        self.assertContains(response, "HeatGuard does not synthesize fallback values")

        # Verify NO new record was created during a failed provider call
        self.assertEqual(WeatherRecord.objects.count(), initial_record_count)
