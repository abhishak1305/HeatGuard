"""India sampling grid and batched Open-Meteo Heat Index aggregation."""
import json
import logging
import math
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request
import ssl
import urllib.error

from .heat_index import RISK_CATEGORIES, compute_nws_heat_index
from .weather_service import (
    _urlopen, WeatherServiceError, WeatherNetworkError, WeatherAPIError,
    WeatherTLSVerificationError, WeatherDataFormatError, DEFAULT_TIMEOUT_SECONDS,
)

logger = logging.getLogger(__name__)
BOUNDARY_PATH = Path(__file__).resolve().parent / 'static/monitoring/geo/india_boundary.geojson'
FORECAST_URL = 'https://api.open-meteo.com/v1/forecast'
GRID_CACHE_KEY = 'heatguard:india-heatmap:grid:v1:spacing100'
STEP = 1.0
BATCH_SIZE = 35
HEAT_MIN_F = RISK_CATEGORIES['CAUTION']['hi_min_f']
HEAT_MAX_F = RISK_CATEGORIES['EXTREME_DANGER']['hi_min_f']


def _inside_ring(lon, lat, ring):
    inside = False
    j = len(ring) - 1
    for i, point in enumerate(ring):
        xi, yi = point[0], point[1]
        xj, yj = ring[j][0], ring[j][1]
        if ((yi > lat) != (yj > lat)) and lon < (xj - xi) * (lat - yi) / ((yj - yi) or 1e-12) + xi:
            inside = not inside
        j = i
    return inside


def _inside_geometry(lon, lat, geometry):
    polygons = geometry['coordinates'] if geometry['type'] == 'MultiPolygon' else [geometry['coordinates']]
    for polygon in polygons:
        if _inside_ring(lon, lat, polygon[0]) and not any(_inside_ring(lon, lat, hole) for hole in polygon[1:]):
            return True
    return False


def _ring_intervals(ring, lat):
    crossings = []
    previous = ring[-1]
    for current in ring:
        x1, y1 = previous[0], previous[1]
        x2, y2 = current[0], current[1]
        if (y1 > lat) != (y2 > lat):
            crossings.append(x1 + (lat - y1) * (x2 - x1) / (y2 - y1))
        previous = current
    crossings.sort()
    return list(zip(crossings[::2], crossings[1::2]))


def _in_intervals(lon, intervals):
    return any(left <= lon <= right for left, right in intervals)


def sampling_points():
    from django.core.cache import cache
    points = cache.get(GRID_CACHE_KEY)
    if points is not None:
        return points
    boundary = json.loads(BOUNDARY_PATH.read_text(encoding='utf-8'))
    geometries = [feature['geometry'] for feature in boundary['features'] if feature.get('geometry')]
    if not geometries:
        raise ValueError('India boundary contains no geometry')
    coords = [coord for geometry in geometries for poly in (geometry['coordinates'] if geometry['type'] == 'MultiPolygon' else [geometry['coordinates']]) for ring in poly for coord in ring]
    min_lon, max_lon = min(c[0] for c in coords), max(c[0] for c in coords)
    min_lat, max_lat = min(c[1] for c in coords), max(c[1] for c in coords)
    points = []
    lat = math.floor(min_lat / STEP) * STEP
    while lat <= max_lat:
        polygon_intervals = []
        for geometry in geometries:
            polygons = geometry['coordinates'] if geometry['type'] == 'MultiPolygon' else [geometry['coordinates']]
            for polygon in polygons:
                outer = _ring_intervals(polygon[0], lat)
                holes = [interval for ring in polygon[1:] for interval in _ring_intervals(ring, lat)]
                polygon_intervals.append((outer, holes))
        lon = math.floor(min_lon / STEP) * STEP
        while lon <= max_lon:
            if any(_in_intervals(lon, outer) and not _in_intervals(lon, holes) for outer, holes in polygon_intervals):
                points.append({'latitude': round(lat, 2), 'longitude': round(lon, 2)})
            lon += STEP
        lat += STEP
    cache.set(GRID_CACHE_KEY, points, None)
    return points


def _fetch_batch(points, timeout=DEFAULT_TIMEOUT_SECONDS):
    params = urlencode({
        'latitude': ','.join(str(p['latitude']) for p in points),
        'longitude': ','.join(str(p['longitude']) for p in points),
        'current': 'temperature_2m,relative_humidity_2m',
        'timezone': 'Asia/Kolkata',
    })
    req = Request(f'{FORECAST_URL}?{params}', headers={'User-Agent': 'HeatGuard/1.0'})
    try:
        with _urlopen(req, timeout=timeout) as response:
            if response.getcode() != 200:
                raise WeatherAPIError('Weather provider returned an unsuccessful response.')
            payload = json.loads(response.read().decode('utf-8'))
    except urllib.error.HTTPError as exc:
        raise WeatherAPIError(f'Weather provider returned HTTP {exc.code}.') from exc
    except urllib.error.URLError as exc:
        if isinstance(exc.reason, ssl.SSLCertVerificationError):
            raise WeatherTLSVerificationError('Weather provider TLS verification failed.') from exc
        raise WeatherNetworkError('Weather provider connection failed.') from exc
    except ssl.SSLCertVerificationError as exc:
        raise WeatherTLSVerificationError('Weather provider TLS verification failed.') from exc
    except (TimeoutError, OSError) as exc:
        raise WeatherNetworkError('Weather provider connection failed.') from exc
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise WeatherDataFormatError('Weather provider response could not be parsed.') from exc
    if isinstance(payload, dict):
        payload = [payload]
    if not isinstance(payload, list):
        raise WeatherDataFormatError('Unexpected multi-location response structure.')
    return payload


def build_heatmap_data(fetch_batch=None):
    points = sampling_points()
    fetch = fetch_batch or _fetch_batch
    valid, unavailable, provider_times, retrieval_times = [], 0, [], []
    for offset in range(0, len(points), BATCH_SIZE):
        batch = points[offset:offset + BATCH_SIZE]
        try:
            responses = fetch(batch)
        except WeatherServiceError:
            logger.warning('Heatmap provider batch failed (%d points)', len(batch), exc_info=True)
            unavailable += len(batch)
            continue
        if not isinstance(responses, list):
            responses = [responses]
        for index, point in enumerate(batch):
            try:
                current = responses[index]['current']
                temp, humidity = current.get('temperature_2m'), current.get('relative_humidity_2m')
                assessment = compute_nws_heat_index(temp, humidity)
                hi_f = float(assessment['heat_index_f'])
                intensity = max(0.0, min(1.0, (hi_f - HEAT_MIN_F) / (HEAT_MAX_F - HEAT_MIN_F)))
                valid.append({
                    'latitude': point['latitude'], 'longitude': point['longitude'],
                    'temperature_c': float(temp), 'relative_humidity': float(humidity),
                    'heat_index_c': float(assessment['heat_index_c']), 'heat_index_f': hi_f,
                    'risk': assessment['risk'], 'intensity': round(intensity, 4),
                })
                timestamp = current.get('time')
                if timestamp:
                    provider_times.append(timestamp)
            except (IndexError, KeyError, TypeError, ValueError, OverflowError):
                unavailable += 1
    if not valid:
        return {'success': False, 'error': 'Heatmap weather data is temporarily unavailable.', 'valid_points': [], 'unavailable_points': len(points)}
    retrieval = datetime.now(timezone.utc).isoformat()
    return {
        'success': True, 'source': 'Open-Meteo',
        'model_context': 'Latest model-based weather estimate; not a ground-station measurement.',
        'retrieved_at': retrieval, 'provider_valid_time': max(provider_times) if provider_times else None,
        'provider_timezone': 'Asia/Kolkata',
        'valid_point_count': len(valid), 'unavailable_point_count': unavailable,
        'total_point_count': len(points), 'valid_points': valid,
        'heatmap_points': [[p['latitude'], p['longitude'], p['intensity']] for p in valid],
        'refresh_seconds': 600, 'scale_f': {'minimum': HEAT_MIN_F, 'maximum': HEAT_MAX_F},
        'legend': [{'key': key, **value} for key, value in RISK_CATEGORIES.items()],
        'boundary_source': 'Bundled India GeoJSON; original dataset attribution/license not present in repository.',
    }
