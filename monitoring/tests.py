from decimal import Decimal
from unittest.mock import patch
from django.test import TestCase, Client
from django.core.cache import cache
from django.urls import reverse
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.utils import IntegrityError
from django.utils import timezone
from datetime import timedelta

from .models import Location, WeatherRecord, OfficialNotice, SavedLocation
from .forms import CitySearchForm
from .services import create_location_from_candidate, resolve_or_create_location


class NavigationAndViewsTestCase(TestCase):
    def setUp(self):
        cache.clear()
        self.client = Client()
        self.location = Location.objects.create(
            name="Central Urban Core",
            state_or_region="Metro Region",
            country="Country A",
            latitude=Decimal("28.61390"),
            longitude=Decimal("77.20900")
        )
        self.coastal_location = Location.objects.create(
            name="Coastal Harbor Station",
            state_or_region="Coastal Belt",
            country="Country A",
            latitude=Decimal("18.92200"),
            longitude=Decimal("72.83470")
        )

    @patch('monitoring.services.geocode_city')
    def test_city_comparison_keeps_nearby_distinct_provider_location(self, mock_geocode):
        candidate = {
            'name': 'East Campus', 'state_or_region': 'Metro Region', 'country': 'Country A',
            'latitude': Decimal('28.61400'), 'longitude': Decimal('77.21000'),
        }
        mock_geocode.return_value = [candidate]
        before = Location.objects.count()

        resolved, error = resolve_or_create_location('East Campus')

        self.assertIsNone(error)
        self.assertEqual(resolved.name, 'East Campus')
        self.assertIsNone(resolved.pk)
        self.assertEqual(Location.objects.count(), before)

    def test_candidate_creation_deduplicates_exact_identity_but_not_nearby_other_city(self):
        exact = create_location_from_candidate({
            'name': self.location.name,
            'state_or_region': self.location.state_or_region,
            'country': self.location.country,
            'latitude': self.location.latitude,
            'longitude': self.location.longitude,
        })
        self.assertEqual(exact.pk, self.location.pk)

        nearby = create_location_from_candidate({
            'name': 'East Campus', 'state_or_region': self.location.state_or_region,
            'country': self.location.country, 'latitude': Decimal('28.61400'),
            'longitude': Decimal('77.21000'),
        })
        self.assertNotEqual(nearby.pk, self.location.pk)
        self.assertEqual(nearby.name, 'East Campus')

    def test_home_view(self):
        url = reverse('monitoring:home')
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Understand Heat. Prepare Earlier.")
        self.assertContains(response, "Thermal Stress Monitoring Framework")
        self.assertContains(response, "Methodology, Scientific Scope & Limitations")
        self.assertContains(response, "Data Sources & Attribution")
        self.assertContains(
            response,
            f'href="{reverse("monitoring:safety_guidance")}" class="btn btn-secondary" style="margin-top: 0.5rem;">View Safety Guidance',
        )
        self.assertContains(response, "Normal, Caution, Extreme Caution, Danger, and Extreme Danger")
        self.assertNotContains(response, "registered observers")
        self.assertNotContains(response, "\\(")
        self.assertNotContains(response, "\\)")
        self.assertTemplateUsed(response, 'monitoring/home.html')
        self.assertTemplateUsed(response, 'base.html')

    def test_city_search_view_get(self):
        url = reverse('monitoring:city_search')
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Monitor Station Search")
        self.assertContains(response, "Central Urban Core")

    def test_city_search_blank_input_validation(self):
        url = reverse('monitoring:city_search') + '?city='
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Please enter a city or station name.")
        self.assertFalse(response.context['form'].is_valid())

    def test_city_search_whitespace_only_validation(self):
        url = reverse('monitoring:city_search') + '?city=   '
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Please enter a city or station name.")
        self.assertFalse(response.context['form'].is_valid())

    def test_city_search_too_short_validation(self):
        url = reverse('monitoring:city_search') + '?city=A'
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Search query must be at least 2 characters long.")
        self.assertFalse(response.context['form'].is_valid())

    def test_city_search_too_long_validation(self):
        long_query = "x" * 105
        url = reverse('monitoring:city_search') + f'?city={long_query}'
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Search query cannot exceed 100 characters.")
        self.assertFalse(response.context['form'].is_valid())

    def test_city_search_preserves_submitted_value_on_error(self):
        url = reverse('monitoring:city_search') + '?city=Z'
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'value="Z"')

    def test_city_search_redirects_on_exact_match_with_spaces_and_case(self):
        # Query with extra surrounding whitespace and lowercase
        url = reverse('monitoring:city_search') + '?city=%20%20central%20urban%20core%20%20'
        response = self.client.get(url)
        expected_url = reverse('monitoring:city_dashboard', kwargs={'location_id': self.location.id})
        self.assertRedirects(response, expected_url, fetch_redirect_response=False)

    @patch('monitoring.services.geocode_city')
    def test_city_search_location_not_found_message(self, mock_geocode):
        mock_geocode.return_value = None
        url = reverse('monitoring:city_search') + '?city=NonexistentCity'
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "No location matching &#x27;NonexistentCity&#x27; was found by the geocoding provider.")

    @patch('monitoring.services.geocode_city')
    def test_city_search_only_persists_provider_location_after_selection(self, mock_geocode):
        mock_geocode.return_value = [{
            'name': 'Jaipur', 'state_or_region': 'Rajasthan', 'country': 'India',
            'latitude': Decimal('26.91240'), 'longitude': Decimal('75.78730'),
            'timezone': 'Asia/Kolkata',
        }]
        before = Location.objects.count()
        response = self.client.get(reverse('monitoring:city_search') + '?city=Jaipur')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Jaipur')
        self.assertEqual(Location.objects.count(), before)

        response = self.client.post(reverse('monitoring:city_search'), {
            'action': 'select_location', 'candidate_index': '0',
        })
        self.assertEqual(response.status_code, 302)
        self.assertEqual(Location.objects.count(), before + 1)
        self.assertEqual(Location.objects.get(name='Jaipur').country, 'India')

    @patch('monitoring.services.geocode_city', return_value=None)
    def test_city_search_does_not_match_unsafe_substrings(self, mock_geocode):
        response = self.client.get(reverse('monitoring:city_search') + '?city=Core')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'No location matching')

    @patch('monitoring.views.fetch_weather_forecast')
    def test_city_dashboard_valid_id(self, mock_fetch):
        mock_fetch.side_effect = RuntimeError('offline test stub')
        url = reverse('monitoring:city_dashboard', kwargs={'location_id': self.location.id})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Central Urban Core")

    def test_city_dashboard_invalid_id_returns_404(self):
        url = reverse('monitoring:city_dashboard', kwargs={'location_id': 99999})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 404)

    @patch('monitoring.views.fetch_weather_forecast', return_value={
        'timezone': 'Asia/Kolkata', 'current': {}, 'hourly': [], 'daily': [],
    })
    def test_forecast_view(self, mock_fetch):
        url = reverse('monitoring:forecast')
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Regional Heatwave Forecast")
        mock_fetch.assert_called_once()

    def test_city_comparison_view(self):
        url = reverse('monitoring:city_comparison')
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Comparative Thermal Stress Analysis")

    def test_notice_list_view(self):
        url = reverse('monitoring:notice_list')
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Official Heat Notices")

    def test_login_placeholder_view(self):
        url = reverse('monitoring:login')
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Account Sign In")

    def test_register_placeholder_view(self):
        url = reverse('monitoring:register')
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Create Your Account")


class CitySearchFormTestCase(TestCase):
    """
    Direct unit tests for the CitySearchForm.
    """
    def test_valid_city_search_form(self):
        form = CitySearchForm(data={'city': '  Tokyo  '})
        self.assertTrue(form.is_valid())
        self.assertEqual(form.cleaned_data['city'], 'Tokyo')

    def test_form_multi_space_normalization(self):
        form = CitySearchForm(data={'city': 'New   York   City'})
        self.assertTrue(form.is_valid())
        self.assertEqual(form.cleaned_data['city'], 'New York City')

    def test_blank_city_invalid(self):
        form = CitySearchForm(data={'city': ''})
        self.assertFalse(form.is_valid())
        self.assertIn('city', form.errors)

    def test_short_city_invalid(self):
        form = CitySearchForm(data={'city': 'A'})
        self.assertFalse(form.is_valid())
        self.assertIn('city', form.errors)


class ModelsTestCase(TestCase):
    """
    Test suite for HeatGuard models, ORM relationships, validation rules, and data provenance.
    All data created here is explicitly identified as test-only.
    """
    def setUp(self):
        self.user = User.objects.create_user(
            username="test_observer",
            email="observer@example.com",
            password="testpassword123"
        )
        self.location = Location.objects.create(
            name="Test City Station",
            state_or_region="Test Region",
            country="Testland",
            latitude=Decimal("28.61390"),
            longitude=Decimal("77.20900")
        )

    def test_location_creation_and_str(self):
        self.assertEqual(str(self.location), "Test City Station, Test Region (Testland)")
        self.assertEqual(self.location.latitude, Decimal("28.61390"))
        self.assertEqual(self.location.longitude, Decimal("77.20900"))

    def test_location_str_without_region(self):
        loc = Location.objects.create(
            name="Ocean Buoy A",
            state_or_region="",
            country="International Waters",
            latitude=Decimal("0.00000"),
            longitude=Decimal("0.00000")
        )
        self.assertEqual(str(loc), "Ocean Buoy A (International Waters)")

    def test_location_latitude_validation(self):
        invalid_loc = Location(
            name="Invalid Lat",
            country="Testland",
            latitude=Decimal("95.00000"),
            longitude=Decimal("10.00000")
        )
        with self.assertRaises(ValidationError):
            invalid_loc.full_clean()

    def test_location_case_insensitive_identity_constraint(self):
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                Location.objects.create(
                    name=self.location.name.upper(),
                    state_or_region=self.location.state_or_region.lower(),
                    country=self.location.country.upper(),
                    latitude=Decimal('40.00000'), longitude=Decimal('40.00000'),
                )

    def test_weather_record_creation_and_relationships(self):
        now = timezone.now()
        record = WeatherRecord.objects.create(
            location=self.location,
            requested_by=self.user,
            recorded_at=now,
            record_type='current',
            temperature_c=Decimal("35.50"),
            relative_humidity=Decimal("60.00"),
            heat_index_c=Decimal("45.20"),
            risk_level='DANGER',
            data_source='test-only'
        )
        self.assertEqual(record.location, self.location)
        self.assertEqual(record.requested_by, self.user)
        self.assertEqual(record.data_source, 'test-only')
        self.assertIn("Test City Station - 35.50°C", str(record))
        self.assertIn("[test-only]", str(record))

    def test_weather_record_null_requested_by_on_user_delete(self):
        now = timezone.now()
        record = WeatherRecord.objects.create(
            location=self.location,
            requested_by=self.user,
            recorded_at=now,
            temperature_c=Decimal("30.00"),
            relative_humidity=Decimal("50.00"),
            data_source='test-only'
        )
        self.user.delete()
        record.refresh_from_db()
        self.assertIsNone(record.requested_by)

    def test_official_notice_creation_and_validation(self):
        now = timezone.now()
        valid_from = now
        valid_until = now + timedelta(days=2)
        notice = OfficialNotice.objects.create(
            location=self.location,
            title="High Heat Advisory Notice",
            message="Hydrate frequently and avoid afternoon sun.",
            severity="WARNING",
            issuing_organization="Regional Meteorological Agency",
            source_url="https://example.gov/bulletin/101",
            valid_from=valid_from,
            valid_until=valid_until,
            created_by=self.user,
            is_published=True
        )
        notice.full_clean()
        self.assertIn("[WARNING] High Heat Advisory Notice", str(notice))
        self.assertEqual(notice.location.notices.count(), 1)

    def test_official_notice_invalid_dates_validation(self):
        now = timezone.now()
        invalid_notice = OfficialNotice(
            location=self.location,
            title="Invalid Notice Dates",
            message="Test message",
            severity="ADVISORY",
            issuing_organization="Test Agency",
            valid_from=now,
            valid_until=now - timedelta(hours=1),
            created_by=self.user
        )
        with self.assertRaises(ValidationError) as ctx:
            invalid_notice.full_clean()
        self.assertIn('valid_until', ctx.exception.message_dict)

    def test_saved_location_uniqueness(self):
        SavedLocation.objects.create(user=self.user, location=self.location)
        with self.assertRaises(IntegrityError):
            SavedLocation.objects.create(user=self.user, location=self.location)

    def test_saved_location_str(self):
        saved = SavedLocation.objects.create(user=self.user, location=self.location)
        self.assertEqual(str(saved), f"{self.user.username} saved {self.location.name}")
