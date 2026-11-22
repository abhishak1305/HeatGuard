"""Short-lived caching for successful Open-Meteo forecast responses."""

import hashlib
from decimal import Decimal

from django.core.cache import cache

from .weather_service import fetch_weather_forecast


CACHE_TIMEOUT_SECONDS = 7 * 60


def cached_weather_forecast(latitude, longitude, tz='auto', fetcher=None):
    """Fetch or return a cached provider response, retaining its source timestamp."""
    lat_key = Decimal(str(latitude)).quantize(Decimal('0.00001'))
    lon_key = Decimal(str(longitude)).quantize(Decimal('0.00001'))
    raw_key = f"v1:{lat_key}:{lon_key}:{tz or 'auto'}"
    cache_key = 'heatguard:weather:' + hashlib.sha256(raw_key.encode('utf-8')).hexdigest()
    result = cache.get(cache_key)
    if result is not None:
        return result

    provider_fetcher = fetcher or fetch_weather_forecast
    result = provider_fetcher(latitude, longitude, tz=tz or 'auto')
    cache.set(cache_key, result, CACHE_TIMEOUT_SECONDS)
    return result
