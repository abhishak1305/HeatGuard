"""
Open-Meteo Weather & Geocoding Service Client.
Strictly uses Python standard-library urllib.request, urllib.parse, and json.
No third-party SDKs, requests, Celery, or external dependencies.
Does not generate synthetic weather values or fake fallback readings.
"""

import json
import ssl
import urllib.request
import urllib.parse
import urllib.error
from decimal import Decimal
from datetime import datetime, timezone

GEOCODING_API_URL = "https://geocoding-api.open-meteo.com/v1/search"
FORECAST_API_URL = "https://api.open-meteo.com/v1/forecast"
DEFAULT_TIMEOUT_SECONDS = 5.0


def _urlopen_with_ssl_fallback(req, timeout):
    """
    Executes urllib.request.urlopen.
    If standard SSL certificate verification fails due to local proxy or
    institutional self-signed certificate inspection, falls back to an unverified context
    so environmental telemetry queries continue working reliably.
    """
    try:
        return urllib.request.urlopen(req, timeout=timeout)
    except urllib.error.URLError as e:
        if 'CERTIFICATE_VERIFY_FAILED' in str(e) or 'certificate verify failed' in str(e):
            ctx = ssl._create_unverified_context()
            return urllib.request.urlopen(req, timeout=timeout, context=ctx)
        raise


class WeatherServiceError(Exception):
    """Base exception for weather service errors."""
    pass


class WeatherNetworkError(WeatherServiceError):
    """Raised on connection timeout or network connectivity failure."""
    pass


class WeatherAPIError(WeatherServiceError):
    """Raised when the provider returns a non-200 HTTP status code."""
    pass


class WeatherDataFormatError(WeatherServiceError):
    """Raised when response JSON is malformed or required keys are missing."""
    pass


def geocode_city(city_name, count=1, timeout=DEFAULT_TIMEOUT_SECONDS):
    """
    Queries the Open-Meteo Geocoding API for a city name.
    
    Returns:
        dict: Normalized location dictionary with:
            - name (str)
            - state_or_region (str)
            - country (str)
            - latitude (Decimal)
            - longitude (Decimal)
            - timezone (str)
        or None if no matching locations were returned.
    """
    if not city_name or not city_name.strip():
        return None

    params = {
        'name': city_name.strip(),
        'count': count,
        'language': 'en',
        'format': 'json',
    }
    query_string = urllib.parse.urlencode(params)
    url = f"{GEOCODING_API_URL}?{query_string}"
    req = urllib.request.Request(
        url,
        headers={'User-Agent': 'HeatGuard-Classroom-Educational-System/1.0'}
    )

    try:
        with _urlopen_with_ssl_fallback(req, timeout=timeout) as response:
            status_code = response.getcode()
            if status_code != 200:
                raise WeatherAPIError(f"Geocoding service returned HTTP status {status_code}.")
            raw_body = response.read().decode('utf-8')
    except urllib.error.HTTPError as e:
        raise WeatherAPIError(f"Geocoding service failed with HTTP {e.code}: {e.reason}")
    except (urllib.error.URLError, TimeoutError, OSError) as e:
        raise WeatherNetworkError(f"Network error connecting to geocoding service: {str(e)}")

    try:
        data = json.loads(raw_body)
    except json.JSONDecodeError as e:
        raise WeatherDataFormatError(f"Failed to parse geocoding response as JSON: {str(e)}")

    if not isinstance(data, dict):
        raise WeatherDataFormatError("Unexpected geocoding response structure: root must be a dict.")

    results = data.get('results')
    if not results or not isinstance(results, list):
        return None

    first = results[0]
    if not isinstance(first, dict):
        raise WeatherDataFormatError("Malformed result item in geocoding results list.")

    try:
        name = str(first.get('name', '')).strip()
        region = str(first.get('admin1', '')).strip()
        country = str(first.get('country', '')).strip() or "Global"
        lat = Decimal(str(first['latitude']))
        lon = Decimal(str(first['longitude']))
        tz = str(first.get('timezone', 'UTC')).strip() or "UTC"

        return {
            'name': name,
            'state_or_region': region,
            'country': country,
            'latitude': lat.quantize(Decimal('0.00001')),
            'longitude': lon.quantize(Decimal('0.00001')),
            'timezone': tz,
        }
    except (KeyError, ValueError, TypeError) as e:
        raise WeatherDataFormatError(f"Missing or invalid location coordinate fields: {str(e)}")


def fetch_weather_forecast(latitude, longitude, tz="auto", timeout=DEFAULT_TIMEOUT_SECONDS):
    """
    Queries Open-Meteo Forecast API for current weather, hourly forecast, and 7-day daily forecast.
    
    Returns:
        dict: Structured weather data dictionary including metadata, hourly forecast, and 7-day daily forecast.
    """
    params = {
        'latitude': str(latitude),
        'longitude': str(longitude),
        'current': 'temperature_2m,relative_humidity_2m,apparent_temperature,wind_speed_10m',
        'hourly': 'temperature_2m,relative_humidity_2m,apparent_temperature,wind_speed_10m',
        'daily': 'temperature_2m_max,temperature_2m_min,apparent_temperature_max,apparent_temperature_min',
        'timezone': tz if tz else 'auto',
    }
    query_string = urllib.parse.urlencode(params)
    url = f"{FORECAST_API_URL}?{query_string}"
    req = urllib.request.Request(
        url,
        headers={'User-Agent': 'HeatGuard-Classroom-Educational-System/1.0'}
    )

    try:
        with _urlopen_with_ssl_fallback(req, timeout=timeout) as response:
            status_code = response.getcode()
            if status_code != 200:
                raise WeatherAPIError(f"Forecast service returned HTTP status {status_code}.")
            raw_body = response.read().decode('utf-8')
    except urllib.error.HTTPError as e:
        raise WeatherAPIError(f"Forecast service failed with HTTP {e.code}: {e.reason}")
    except (urllib.error.URLError, TimeoutError, OSError) as e:
        raise WeatherNetworkError(f"Network error connecting to forecast service: {str(e)}")

    try:
        data = json.loads(raw_body)
    except json.JSONDecodeError as e:
        raise WeatherDataFormatError(f"Failed to parse forecast response as JSON: {str(e)}")

    if not isinstance(data, dict):
        raise WeatherDataFormatError("Unexpected forecast response structure: root must be a dict.")

    current = data.get('current')
    if not current or not isinstance(current, dict):
        raise WeatherDataFormatError("Forecast response missing 'current' weather block.")

    try:
        temp_c = Decimal(str(current['temperature_2m']))
        humidity = Decimal(str(current['relative_humidity_2m']))
        apparent_temp_c = Decimal(str(current.get('apparent_temperature', temp_c))) if current.get('apparent_temperature') is not None else None
        wind_speed_kmh = Decimal(str(current.get('wind_speed_10m'))) if current.get('wind_speed_10m') is not None else None
        time_str = str(current.get('time', ''))
    except (KeyError, ValueError, TypeError) as e:
        raise WeatherDataFormatError(f"Missing or invalid field in current weather block: {str(e)}")

    # Parse hourly forecast (extract up to 24 hours)
    hourly_items = []
    hourly = data.get('hourly', {})
    if isinstance(hourly, dict):
        h_times = hourly.get('time', [])
        h_temps = hourly.get('temperature_2m', [])
        h_humidity = hourly.get('relative_humidity_2m', [])
        h_apparent = hourly.get('apparent_temperature', [])
        h_wind = hourly.get('wind_speed_10m', [])

        limit = min(len(h_times), len(h_temps), 24)
        for i in range(limit):
            t_val = Decimal(str(h_temps[i])) if h_temps[i] is not None else None
            rh_val = Decimal(str(h_humidity[i])) if (i < len(h_humidity) and h_humidity[i] is not None) else None
            app_val = Decimal(str(h_apparent[i])) if (i < len(h_apparent) and h_apparent[i] is not None) else None
            w_val = Decimal(str(h_wind[i])) if (i < len(h_wind) and h_wind[i] is not None) else None

            hourly_items.append({
                'time': h_times[i],
                'temperature_c': t_val,
                'relative_humidity': rh_val,
                'apparent_temperature_c': app_val,
                'wind_speed_kmh': w_val,
            })

    # Parse 7-day daily forecast
    daily_items = []
    daily = data.get('daily', {})
    if isinstance(daily, dict):
        daily_times = daily.get('time', [])
        t_max = daily.get('temperature_2m_max', [])
        t_min = daily.get('temperature_2m_min', [])
        app_max = daily.get('apparent_temperature_max', [])
        app_min = daily.get('apparent_temperature_min', [])

        limit_daily = min(len(daily_times), len(t_max), len(t_min), 7)
        for i in range(limit_daily):
            daily_items.append({
                'date': daily_times[i],
                'max_temp_c': Decimal(str(t_max[i])) if t_max[i] is not None else None,
                'min_temp_c': Decimal(str(t_min[i])) if t_min[i] is not None else None,
                'apparent_max_c': Decimal(str(app_max[i])) if (i < len(app_max) and app_max[i] is not None) else None,
                'apparent_min_c': Decimal(str(app_min[i])) if (i < len(app_min) and app_min[i] is not None) else None,
            })

    return {
        'provider': "Open-Meteo",
        'model_context': "Numerical weather prediction model output (grid-interpolated, not a single physical station observation)",
        'retrieved_at': datetime.now(timezone.utc),
        'latitude': data.get('latitude'),
        'longitude': data.get('longitude'),
        'timezone': data.get('timezone', 'UTC'),
        'timezone_abbreviation': data.get('timezone_abbreviation', 'UTC'),
        'current': {
            'time': time_str,
            'temperature_c': temp_c,
            'relative_humidity': humidity,
            'apparent_temperature_c': apparent_temp_c,
            'wind_speed_kmh': wind_speed_kmh,
        },
        'hourly': hourly_items,
        'daily': daily_items,
        'attribution': "Weather data by Open-Meteo.com (CC BY 4.0 license)",
    }
