from datetime import timedelta
from decimal import Decimal

from django.contrib.auth.models import User
from django.db.models.deletion import ProtectedError
from django.test import TestCase, Client, override_settings
from django.urls import include, path, reverse
from django.utils import timezone

from .models import Location, WeatherRecord, OfficialNotice
from .admin import WeatherRecordAdminForm
from . import views


def _raise_test_server_error(request):
    raise RuntimeError('private traceback detail')


urlpatterns = [
    path('', include('monitoring.urls')),
    path('_test-error/', _raise_test_server_error),
]
handler400 = views.bad_request_view
handler403 = views.permission_denied_view
handler404 = views.page_not_found_view
handler500 = views.server_error_view


class WeatherHistoryAndManualReportTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.location = Location.objects.create(
            name='Phase Three City', state_or_region='Test Region', country='India',
            latitude=Decimal('23.00000'), longitude=Decimal('78.00000'),
        )
        self.user = User.objects.create_user('reporter', password='SafePass123!')

    def make_record(self, source, days_ago=0, risk='CAUTION'):
        when = timezone.now() - timedelta(days=days_ago)
        return WeatherRecord.objects.create(
            location=self.location, recorded_at=when, retrieved_at=when,
            temperature_c=Decimal('34.00'), relative_humidity=Decimal('65.00'),
            heat_index_c=Decimal('42.00'), risk_level=risk, data_source=source,
            requested_by=self.user if source == 'user-entered' else None,
        )

    def test_history_filters_saved_records_and_shows_provenance_summary(self):
        self.make_record('provider-supplied', days_ago=0, risk='DANGER')
        self.make_record('user-entered', days_ago=4, risk='CAUTION')
        url = reverse('monitoring:weather_history')
        response = self.client.get(url, {
            'location': self.location.pk,
            'start_date': timezone.localdate().isoformat(),
            'end_date': timezone.localdate().isoformat(),
            'risk_level': 'DANGER',
        })
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['record_count'], 1)
        self.assertEqual(response.context['provider_count'], 1)
        self.assertEqual(response.context['user_entered_count'], 0)
        self.assertContains(response, 'Provider-Supplied')

    def test_history_pagination_preserves_active_filters(self):
        for index in range(26):
            when = timezone.now() - timedelta(seconds=index)
            WeatherRecord.objects.create(
                location=self.location, recorded_at=when, temperature_c=Decimal('30'),
                relative_humidity=Decimal('50'), risk_level='CAUTION', data_source='user-entered',
            )
        response = self.client.get(reverse('monitoring:weather_history'), {
            'location': self.location.pk, 'risk_level': 'CAUTION',
        })
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, f'location={self.location.pk}')
        self.assertContains(response, 'risk_level=CAUTION')

    def test_manual_report_requires_login_and_saves_clear_provenance(self):
        url = reverse('monitoring:manual_observation')
        self.assertEqual(self.client.get(url).status_code, 302)
        self.client.force_login(self.user)
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'csrfmiddlewaretoken')
        self.assertContains(response, 'visible to anyone in Weather History and its CSV export')
        response = self.client.post(url, {
            'location': self.location.pk, 'temperature_c': '35.2', 'relative_humidity': '70',
        })
        self.assertRedirects(response, reverse('monitoring:weather_history'))
        record = WeatherRecord.objects.get(data_source='user-entered')
        self.assertEqual(record.requested_by, self.user)
        self.assertIsNotNone(record.heat_index_c)
        self.assertEqual(record.record_type, 'current')
        self.assertEqual(WeatherRecord.objects.filter(data_source='provider-supplied').count(), 0)

    def test_manual_report_rejects_invalid_measurements(self):
        self.client.force_login(self.user)
        response = self.client.post(reverse('monitoring:manual_observation'), {
            'location': self.location.pk, 'temperature_c': '90', 'relative_humidity': '140',
        })
        self.assertEqual(response.status_code, 200)
        self.assertFalse(WeatherRecord.objects.exists())

    def test_csv_export_uses_filtered_saved_history(self):
        self.make_record('provider-supplied')
        self.make_record('user-entered', days_ago=2)
        response = self.client.get(reverse('monitoring:weather_history_export'), {'risk_level': 'CAUTION'})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'text/csv; charset=utf-8')
        self.assertTrue(response.streaming)
        content = b''.join(response.streaming_content).decode()
        self.assertIn('Heat Index (C)', content)
        self.assertEqual(content.count('Phase Three City'), 2)


class PhaseThreePaginationAndDashboardTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.staff = User.objects.create_user('phase_staff', password='SafePass123!', is_staff=True)
        self.location = Location.objects.create(
            name='Paginated City', state_or_region='Test Region', country='India',
            latitude=Decimal('24.00000'), longitude=Decimal('79.00000'),
        )

    def test_public_notice_list_paginates_active_notices(self):
        now = timezone.now()
        for index in range(16):
            OfficialNotice.objects.create(
                location=self.location, title=f'Active notice {index}', message='Message',
                severity='WARNING', issuing_organization='Test Authority',
                source_url='https://example.org/notice', issued_at=now,
                valid_from=now - timedelta(hours=1), valid_until=now + timedelta(days=1),
                created_by=self.staff,
            )
        response = self.client.get(reverse('monitoring:notice_list'), {'active_page': 2})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['active_notices'].number, 2)
        self.assertContains(response, 'Page 2 of 2')

    def test_staff_dashboard_includes_recent_records_and_notice_pagination(self):
        now = timezone.now()
        for index in range(21):
            OfficialNotice.objects.create(
                location=self.location, title=f'Staff notice {index}', message='Message',
                severity='ADVISORY', issuing_organization='Test Authority',
                source_url='https://example.org/notice', issued_at=now,
                valid_from=now, valid_until=now + timedelta(days=1), created_by=self.staff,
            )
        WeatherRecord.objects.create(
            location=self.location, recorded_at=now, temperature_c=Decimal('34.00'),
            relative_humidity=Decimal('60.00'), data_source='provider-supplied',
        )
        self.client.force_login(self.staff)
        response = self.client.get(reverse('monitoring:staff_dashboard'), {'page': 2})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['all_notices'].number, 2)
        self.assertEqual(len(response.context['recent_weather_records']), 1)
        self.assertContains(response, 'Django Admin')

    def test_location_deletion_preserves_weather_history_and_official_notices(self):
        now = timezone.now()
        record = WeatherRecord.objects.create(
            location=self.location, recorded_at=now, data_source='provider-supplied',
        )
        notice = OfficialNotice.objects.create(
            location=self.location, title='Protected notice', message='Message',
            severity='WARNING', issuing_organization='Test Authority',
            source_url='https://example.org/notice', issued_at=now,
            valid_from=now, valid_until=now + timedelta(days=1), created_by=self.staff,
        )

        with self.assertRaises(ProtectedError):
            self.location.delete()

        self.assertTrue(WeatherRecord.objects.filter(pk=record.pk).exists())
        self.assertTrue(OfficialNotice.objects.filter(pk=notice.pk).exists())

    def test_new_admin_weather_record_requires_explicit_data_provenance(self):
        form = WeatherRecordAdminForm()
        self.assertTrue(form.fields['data_source'].required)
        self.assertIn(form.fields['data_source'].initial, ('', None))
        self.assertIn('actual provenance', form.fields['data_source'].help_text)

        record = WeatherRecord.objects.create(
            location=self.location, recorded_at=timezone.now(), data_source='user-entered',
        )
        edit_form = WeatherRecordAdminForm(instance=record)
        self.assertEqual(edit_form.initial['data_source'], 'user-entered')

    def test_directory_paginates_locations(self):
        for index in range(16):
            Location.objects.create(
                name=f'Listed City {index:02}', state_or_region='Test', country='India',
                latitude=Decimal('25.00000') + Decimal(index) / 100,
                longitude=Decimal('80.00000') + Decimal(index) / 100,
            )
        response = self.client.get(reverse('monitoring:city_search'), {'directory_page': 2})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['station_page'].number, 2)
        self.assertContains(response, 'Page 2 of 2')

    def test_branded_403_and_404_pages(self):
        user = User.objects.create_user('ordinary', password='SafePass123!')
        self.client.force_login(user)
        denied = self.client.get(reverse('monitoring:staff_dashboard'))
        self.assertEqual(denied.status_code, 403)
        self.assertContains(denied, 'Access restricted', status_code=403)
        missing = self.client.get('/this-page-does-not-exist/')
        self.assertEqual(missing.status_code, 404)
        self.assertContains(missing, 'Page not found', status_code=404)

    @override_settings(DEBUG=False)
    def test_branded_400_page_hides_request_details(self):
        response = self.client.get('/', HTTP_HOST='unlisted.invalid')
        self.assertEqual(response.status_code, 400)
        self.assertContains(response, 'Bad request', status_code=400)
        self.assertNotContains(response, 'DisallowedHost', status_code=400)

    @override_settings(DEBUG=False, ROOT_URLCONF='monitoring.tests_phase3')
    def test_branded_500_page_hides_traceback(self):
        client = Client(raise_request_exception=False)
        response = client.get('/_test-error/')
        self.assertEqual(response.status_code, 500)
        self.assertContains(response, 'temporary application error', status_code=500)
        self.assertNotContains(response, 'private traceback detail', status_code=500)
