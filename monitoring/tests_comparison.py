"""
Tests for the city comparison feature.
Covers two-city, three-city, invalid location IDs, partial provider failure,
city name geocoding, and attribution checks.
"""

from decimal import Decimal
from datetime import datetime, timedelta, timezone as dt_timezone
from unittest.mock import patch

from django.test import TestCase, Client
from django.core.cache import cache
from django.urls import reverse
from django.utils import timezone
from django.contrib.auth.models import User

from monitoring.models import Location, WeatherRecord, OfficialNotice, SavedLocation
from monitoring.weather_service import WeatherServiceError, WeatherTLSVerificationError


def _mock_forecast(temp_c=30.0, rh=55.0):
    """Returns a realistic forecast response dict for mocking."""
    return {
        'provider': 'Open-Meteo',
        'model_context': 'Test mock data',
        'retrieved_at': datetime.now(dt_timezone.utc),
        'latitude': 28.6,
        'longitude': 77.2,
        'timezone': 'Asia/Kolkata',
        'timezone_abbreviation': 'IST',
        'current': {
            'time': '2026-11-20T12:00',
            'temperature_c': Decimal(str(temp_c)),
            'relative_humidity': Decimal(str(rh)),
            'apparent_temperature_c': Decimal(str(temp_c + 2)),
            'wind_speed_kmh': Decimal('12.5'),
        },
        'hourly': [],
        'daily': [],
        'attribution': 'Weather data by Open-Meteo.com (test)',
    }


class CityComparisonViewTestCase(TestCase):
    """Tests for the city_comparison_view."""

    def setUp(self):
        cache.clear()
        self.client = Client()
        self.url = reverse('monitoring:city_comparison')

        self.loc1 = Location.objects.create(
            name='Delhi', state_or_region='Delhi', country='India',
            latitude=Decimal('28.61390'), longitude=Decimal('77.20900'),
        )
        self.loc2 = Location.objects.create(
            name='Mumbai', state_or_region='Maharashtra', country='India',
            latitude=Decimal('19.07600'), longitude=Decimal('72.87770'),
        )
        self.loc3 = Location.objects.create(
            name='Chennai', state_or_region='Tamil Nadu', country='India',
            latitude=Decimal('13.08780'), longitude=Decimal('80.27840'),
        )

    # ------------------------------------------------------------------
    # GET — empty form
    # ------------------------------------------------------------------
    def test_get_returns_form_with_200(self):
        """GET request renders the comparison form."""
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Comparative Thermal Stress Analysis')
        self.assertIn('form', response.context)
        self.assertFalse(response.context.get('comparison_attempted'))

    # ------------------------------------------------------------------
    # Two-city comparison
    # ------------------------------------------------------------------
    @patch('monitoring.views.fetch_weather_forecast')
    def test_two_city_comparison_success(self, mock_fetch):
        """POST with two valid stations returns comparison results for both."""
        mock_fetch.side_effect = [
            _mock_forecast(35.0, 60.0),
            _mock_forecast(31.0, 75.0),
        ]
        response = self.client.post(self.url, {
            'station_1': self.loc1.pk,
            'station_2': self.loc2.pk,
        })
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context['comparison_attempted'])

        results = response.context['comparison_results']
        self.assertEqual(len(results), 2)
        self.assertIsNone(results[0]['error'])
        self.assertIsNone(results[1]['error'])
        self.assertEqual(results[0]['temperature_c'], Decimal('35.0'))
        self.assertEqual(results[1]['temperature_c'], Decimal('31.0'))

        # City names appear in table
        self.assertContains(response, 'Delhi')
        self.assertContains(response, 'Mumbai')

    # ------------------------------------------------------------------
    # Three-city comparison
    # ------------------------------------------------------------------
    @patch('monitoring.views.fetch_weather_forecast')
    def test_three_city_comparison_success(self, mock_fetch):
        """POST with three stations returns three result columns."""
        mock_fetch.side_effect = [
            _mock_forecast(35.0, 60.0),
            _mock_forecast(31.0, 75.0),
            _mock_forecast(33.0, 70.0),
        ]
        response = self.client.post(self.url, {
            'station_1': self.loc1.pk,
            'station_2': self.loc2.pk,
            'station_3': self.loc3.pk,
        })
        results = response.context['comparison_results']
        self.assertEqual(len(results), 3)
        self.assertContains(response, 'Chennai')

    # ------------------------------------------------------------------
    # Optional third slot skipped when empty
    # ------------------------------------------------------------------
    @patch('monitoring.views.fetch_weather_forecast')
    def test_optional_third_city_skipped(self, mock_fetch):
        """When the third slot is empty, only 2 results are returned."""
        mock_fetch.side_effect = [
            _mock_forecast(35.0, 60.0),
            _mock_forecast(31.0, 75.0),
        ]
        response = self.client.post(self.url, {
            'station_1': self.loc1.pk,
            'station_2': self.loc2.pk,
        })
        results = response.context['comparison_results']
        self.assertEqual(len(results), 2)

    # ------------------------------------------------------------------
    # Missing required stations shows form errors
    # ------------------------------------------------------------------
    def test_missing_required_stations(self):
        """POST without required stations shows form validation errors."""
        response = self.client.post(self.url, {})
        self.assertEqual(response.status_code, 200)
        # Form is invalid so comparison should not be attempted
        self.assertFalse(response.context.get('comparison_attempted', False))
        self.assertTrue(response.context['form'].errors)

    # ------------------------------------------------------------------
    # Invalid location ID
    # ------------------------------------------------------------------
    def test_invalid_location_id(self):
        """POST with non-existent station ID is handled via form validation."""
        response = self.client.post(self.url, {
            'station_1': 99999,
            'station_2': self.loc2.pk,
        })
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context['form'].errors)

    # ------------------------------------------------------------------
    # Partial provider failure
    # ------------------------------------------------------------------
    @patch('monitoring.views.fetch_weather_forecast')
    def test_partial_provider_failure(self, mock_fetch):
        """When one city's provider fails, the other still shows data."""
        mock_fetch.side_effect = [
            _mock_forecast(35.0, 60.0),
            WeatherServiceError("Provider timeout"),
        ]
        response = self.client.post(self.url, {
            'station_1': self.loc1.pk,
            'station_2': self.loc2.pk,
        })
        self.assertEqual(response.status_code, 200)
        results = response.context['comparison_results']
        self.assertEqual(len(results), 2)

        # First city should have data
        self.assertIsNone(results[0]['error'])
        self.assertEqual(results[0]['temperature_c'], Decimal('35.0'))

        # Second city should have error
        self.assertIsNotNone(results[1]['error'])
        self.assertIn('unavailable', results[1]['error'].lower())
        # Template shows the error indicator
        self.assertContains(response, 'Unavailable')

    # ------------------------------------------------------------------
    # City name geocoding resolution
    # ------------------------------------------------------------------
    @patch('monitoring.views.fetch_weather_forecast')
    @patch('monitoring.views.resolve_or_create_location')
    def test_city_name_geocoding(self, mock_resolve, mock_fetch):
        """City name input triggers geocoding and fetches weather."""
        mock_resolve.return_value = (self.loc1, None)
        mock_fetch.side_effect = [
            _mock_forecast(35.0, 60.0),
            _mock_forecast(31.0, 75.0),
        ]
        response = self.client.post(self.url, {
            'city_name_1': 'New Delhi',
            'station_2': self.loc2.pk,
        })
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context['comparison_attempted'])
        results = response.context['comparison_results']
        self.assertEqual(len(results), 2)
        mock_resolve.assert_called_once_with('New Delhi')

    # ------------------------------------------------------------------
    # Failed geocoding shows error for that city
    # ------------------------------------------------------------------
    @patch('monitoring.views.fetch_weather_forecast')
    @patch('monitoring.views.resolve_or_create_location')
    def test_failed_geocoding_shows_error(self, mock_resolve, mock_fetch):
        """Failed geocoding for one city still shows the other."""
        mock_resolve.return_value = (None, "No location found.")
        mock_fetch.return_value = _mock_forecast(31.0, 75.0)

        response = self.client.post(self.url, {
            'city_name_1': 'Nonexistent Place',
            'station_2': self.loc2.pk,
        })
        results = response.context['comparison_results']
        self.assertEqual(len(results), 2)
        self.assertIsNotNone(results[0]['error'])
        self.assertIsNone(results[1]['error'])

    @patch('monitoring.views.fetch_weather_forecast')
    @patch('monitoring.views.resolve_or_create_location')
    def test_city_name_provider_failure_is_rendered_without_secondary_error(self, mock_resolve, mock_fetch):
        """A provider error for a geocoded city must use the resolved location in logging."""
        mock_resolve.return_value = (self.loc1, None)
        mock_fetch.side_effect = [WeatherServiceError('provider offline'), _mock_forecast()]

        response = self.client.post(self.url, {
            'city_name_1': 'New Delhi',
            'station_2': self.loc2.pk,
        })

        self.assertEqual(response.status_code, 200)
        results = response.context['comparison_results']
        self.assertIn('currently unavailable', results[0]['error'])
        self.assertIsNone(results[1]['error'])

    @patch('monitoring.views.fetch_weather_forecast')
    @patch('monitoring.views.resolve_or_create_location')
    def test_city_name_tls_failure_is_rendered_without_secondary_error(self, mock_resolve, mock_fetch):
        mock_resolve.return_value = (self.loc1, None)
        mock_fetch.side_effect = [WeatherTLSVerificationError('certificate failure'), _mock_forecast()]

        response = self.client.post(self.url, {
            'city_name_1': 'New Delhi',
            'station_2': self.loc2.pk,
        })

        self.assertEqual(response.status_code, 200)
        results = response.context['comparison_results']
        self.assertIn('secure provider connection', results[0]['error'])
        self.assertIsNone(results[1]['error'])

    # ------------------------------------------------------------------
    # Retrieval time is recorded
    # ------------------------------------------------------------------
    @patch('monitoring.views.fetch_weather_forecast')
    def test_retrieval_time_recorded(self, mock_fetch):
        """Each successful city result includes retrieval time in ms."""
        mock_fetch.return_value = _mock_forecast(35.0, 60.0)
        response = self.client.post(self.url, {
            'station_1': self.loc1.pk,
            'station_2': self.loc2.pk,
        })
        results = response.context['comparison_results']
        for r in results:
            if not r['error']:
                self.assertIsNotNone(r['retrieval_time_ms'])
        self.assertContains(response, 'ms')

    # ------------------------------------------------------------------
    # Source attribution shown
    # ------------------------------------------------------------------
    @patch('monitoring.views.fetch_weather_forecast')
    def test_source_attribution_shown(self, mock_fetch):
        """Comparison results include Open-Meteo source attribution."""
        mock_fetch.return_value = _mock_forecast(35.0, 60.0)
        response = self.client.post(self.url, {
            'station_1': self.loc1.pk,
            'station_2': self.loc2.pk,
        })
        self.assertContains(response, 'Open-Meteo')

    # ------------------------------------------------------------------
    # Heat index and risk category displayed
    # ------------------------------------------------------------------
    @patch('monitoring.views.fetch_weather_forecast')
    def test_heat_index_and_risk_displayed(self, mock_fetch):
        """When conditions warrant, heat index and risk category are shown."""
        # 40°C + 50% RH → Rothfusz regression, should produce a risk label
        mock_fetch.return_value = _mock_forecast(40.0, 50.0)
        response = self.client.post(self.url, {
            'station_1': self.loc1.pk,
            'station_2': self.loc2.pk,
        })
        results = response.context['comparison_results']
        for r in results:
            self.assertIsNotNone(r['heat_index_c'])
            self.assertIsNotNone(r['risk_label'])
        # Risk badge partial should be rendered
        self.assertContains(response, 'risk-')

    # ------------------------------------------------------------------
    # Empty database state for comparison
    # ------------------------------------------------------------------
    def test_empty_database_state_renders_comparison_form(self):
        """When no Locations exist in DB, form renders empty choices and allows city name search."""
        Location.objects.all().delete()
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(Location.objects.count(), 0)
        self.assertContains(response, 'Comparative Thermal Stress Analysis')


class StaffSummaryDashboardTestCase(TestCase):
    """
    Tests for staff-only summary page:
    - Restricted to staff or view_officialnotice permission.
    - Public visitors and regular users receive 403 Forbidden or redirect.
    - Factual DB counts rendered (locations, weather records, published notices).
    - Empty database state displays 0 counts correctly without population exposure labels.
    """

    def setUp(self):
        self.client = Client()
        self.url = reverse('monitoring:staff_dashboard')

        # Create regular user
        self.regular_user = User.objects.create_user(
            username='citizen_user', password='Password123!'
        )

        # Create staff user
        self.staff_user = User.objects.create_user(
            username='staff_officer', password='Password123!', is_staff=True
        )

    def test_anonymous_access_redirects_to_login(self):
        """Unauthenticated user accessing staff summary is redirected to login."""
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse('monitoring:login'), response.url)

    def test_regular_user_denied_access(self):
        """Authenticated non-staff user receives 403 PermissionDenied."""
        self.client.login(username='citizen_user', password='Password123!')
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 403)

    def test_staff_user_can_access_dashboard(self):
        """Staff user can access the dashboard successfully."""
        self.client.login(username='staff_officer', password='Password123!')
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Weather Authority & Staff Overview')
        self.assertContains(response, 'Total Locations')
        self.assertContains(response, 'Published Notices')
        self.assertContains(response, 'Stored Weather Records')

    def test_empty_database_counts(self):
        """Empty database shows 0 for all factual counts."""
        Location.objects.all().delete()
        self.client.login(username='staff_officer', password='Password123!')
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['total_stations'], 0)
        self.assertEqual(response.context['total_telemetry'], 0)
        self.assertEqual(response.context['total_published_notices'], 0)
        self.assertEqual(response.context['total_saved'], 0)
        # Ensure database counts are not labelled as live population exposure
        self.assertNotContains(response, 'Live Population Exposure')
        self.assertNotContains(response, 'Affected People')

    def test_factual_counts_with_data(self):
        """Factual counts accurately reflect database records."""
        loc = Location.objects.create(
            name='Kolkata', state_or_region='West Bengal', country='India',
            latitude=Decimal('22.57260'), longitude=Decimal('88.36390')
        )
        WeatherRecord.objects.create(
            location=loc,
            recorded_at=timezone.now(),
            temperature_c=Decimal('32.0'),
            relative_humidity=Decimal('70.0'),
            risk_level='CAUTION'
        )
        now = timezone.now()
        OfficialNotice.objects.create(
            location=loc,
            title='Staff Count Test Notice',
            message='Test message',
            issuing_organization='Test Org',
            source_url='https://example.org/notice',
            valid_from=now,
            valid_until=now + timedelta(days=2),
            created_by=self.staff_user,
            is_published=True
        )

        self.client.login(username='staff_officer', password='Password123!')
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['total_stations'], 1)
        self.assertEqual(response.context['total_telemetry'], 1)
        self.assertEqual(response.context['total_published_notices'], 1)

