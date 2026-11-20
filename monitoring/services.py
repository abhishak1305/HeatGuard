"""
Location resolution service connecting the search workflow to Open-Meteo geocoding and the database.
Avoids duplicates using coordinate proximity and name/region matching.
"""

from decimal import Decimal
from .models import Location
from .weather_service import geocode_city, WeatherServiceError


def resolve_or_create_location(search_query):
    """
    Attempts to resolve a location:
    1. Checks if an exact or close match exists in the database.
    2. If not, queries Open-Meteo Geocoding API to resolve coordinates and place name.
    3. Finds an existing Location within ~1km coordinate distance or creates a new normalized record.
    
    Returns:
        tuple (Location instance or None, error_message or None)
    """
    clean_query = search_query.strip()
    if not clean_query:
        return (None, "Please enter a valid city or station name.")

    # Check local database first: exact match or substring match
    local_match = Location.objects.filter(name__iexact=clean_query).first()
    if not local_match:
        local_match = Location.objects.filter(name__icontains=clean_query).first()
    if local_match:
        return (local_match, None)

    # Query Open-Meteo Geocoding
    try:
        geo_result = geocode_city(clean_query)
    except WeatherServiceError as e:
        return (None, str(e))
    except Exception as e:
        return (None, f"Unexpected error during geocoding: {str(e)}")

    if not geo_result:
        return (None, f"No location matching '{clean_query}' was found by the geocoding provider.")

    lat = geo_result['latitude']
    lon = geo_result['longitude']
    name = geo_result['name']
    region = geo_result['state_or_region']
    country = geo_result['country']

    # Coordinate deduplication (within ~0.02 degrees ≈ 2km)
    existing = Location.objects.filter(
        latitude__gte=lat - Decimal('0.02'),
        latitude__lte=lat + Decimal('0.02'),
        longitude__gte=lon - Decimal('0.02'),
        longitude__lte=lon + Decimal('0.02')
    ).first()

    if existing:
        return (existing, None)

    # Create new normalized Location
    new_loc = Location.objects.create(
        name=name,
        state_or_region=region,
        country=country,
        latitude=lat,
        longitude=lon
    )
    return (new_loc, None)
