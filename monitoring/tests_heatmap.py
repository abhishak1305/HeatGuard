import json
from unittest.mock import patch

from django.core.cache import cache
from django.test import TestCase
from django.urls import reverse

from .heatmap_service import BATCH_SIZE, build_heatmap_data, sampling_points, _inside_geometry
from .heat_index import compute_nws_heat_index
from .weather_service import WeatherNetworkError


class IndiaHeatmapTests(TestCase):
    def setUp(self):
        cache.clear()

    def tearDown(self):
        cache.clear()

    def test_heatmap_page_and_nav_link(self):
        response = self.client.get(reverse('monitoring:india_heatmap'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Live India Heat Index Map')
        self.assertContains(response, reverse('monitoring:india_heatmap_data'))
        self.assertContains(response, 'Live Map')

    def test_boundary_is_geojson_and_grid_points_are_inside(self):
        from .heatmap_service import BOUNDARY_PATH
        geo = json.loads(BOUNDARY_PATH.read_text(encoding='utf-8'))
        self.assertEqual(geo['type'], 'FeatureCollection')
        points = sampling_points()
        self.assertGreater(len(points), 100)
        self.assertLess(len(points), 500)
        geometry = geo['features'][0]['geometry']
        self.assertTrue(all(_inside_geometry(p['longitude'], p['latitude'], geometry) for p in points[::max(1, len(points) // 3)]))
        self.assertFalse(_inside_geometry(60, 20, geometry))

    def test_batches_calculate_existing_heat_index_and_return_expected_structure(self):
        points = sampling_points()
        calls = []
        def fetch(batch):
            calls.append(len(batch))
            return [{'current': {
                'temperature_2m': 35, 'relative_humidity_2m': 70,
                'time': '2026-11-22T12:00',
            }} for _ in batch]

        data = build_heatmap_data(fetch_batch=fetch)
        self.assertEqual(calls[0], min(BATCH_SIZE, len(points)))
        self.assertEqual(data['valid_point_count'], len(points))
        self.assertEqual(data['valid_points'][0]['risk'], compute_nws_heat_index(35, 70)['risk'])
        self.assertTrue(0 <= data['valid_points'][0]['intensity'] <= 1)
        self.assertEqual(data['source'], 'Open-Meteo')

    def test_missing_humidity_is_unavailable_not_normal(self):
        data = build_heatmap_data(fetch_batch=lambda batch: [
            {'current': {'temperature_2m': 35, 'relative_humidity_2m': None}}
            for _ in batch
        ])
        self.assertFalse(data['success'])
        self.assertEqual(data['valid_points'], [])

    def test_partial_batch_failure_keeps_other_valid_data(self):
        points = sampling_points()
        call_count = 0
        def fetch(batch):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise WeatherNetworkError('offline')
            return [{'current': {'temperature_2m': 34, 'relative_humidity_2m': 65,
                                 'time': '2026-11-22T12:00'}} for _ in batch]
        data = build_heatmap_data(fetch_batch=fetch)
        self.assertTrue(data['success'])
        self.assertGreater(data['unavailable_point_count'], 0)
        self.assertLess(data['valid_point_count'], len(points))

    @patch('monitoring.heatmap_service._urlopen')
    def test_multi_coordinate_fetch_uses_comma_separated_batch(self, open_mock):
        from unittest.mock import MagicMock
        from .heatmap_service import _fetch_batch
        response = MagicMock()
        response.getcode.return_value = 200
        response.read.return_value = json.dumps([
            {'current': {'temperature_2m': 30, 'relative_humidity_2m': 55}},
            {'current': {'temperature_2m': 32, 'relative_humidity_2m': 60}},
        ]).encode()
        open_mock.return_value.__enter__.return_value = response
        result = _fetch_batch([{'latitude': 20, 'longitude': 75}, {'latitude': 21, 'longitude': 76}])
        self.assertEqual(len(result), 2)
        request_url = open_mock.call_args.args[0].full_url
        self.assertIn('latitude=20%2C21', request_url)
        self.assertIn('longitude=75%2C76', request_url)

    @patch('monitoring.views.build_heatmap_data')
    def test_json_endpoint_caches_successful_data_and_does_not_write_records(self, build):
        from .models import WeatherRecord
        build.return_value = {'success': True, 'valid_points': [{'latitude': 20}], 'heatmap_points': [[20,75,.5]]}
        url = reverse('monitoring:india_heatmap_data')
        first = self.client.get(url)
        second = self.client.get(url)
        self.assertEqual(first.status_code, 200)
        self.assertEqual(second.json(), first.json())
        build.assert_called_once()
        self.assertEqual(WeatherRecord.objects.count(), 0)

    @patch('monitoring.views.build_heatmap_data', side_effect=WeatherNetworkError('secret detail'))
    def test_provider_failure_returns_generic_error(self, build):
        response = self.client.get(reverse('monitoring:india_heatmap_data'))
        self.assertEqual(response.status_code, 503)
        self.assertNotIn('secret detail', response.content.decode())
