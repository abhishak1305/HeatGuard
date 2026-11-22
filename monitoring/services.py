"""
Location resolution service connecting the search workflow to Open-Meteo geocoding and the database.
Avoids duplicates using coordinate proximity and name/region matching.
"""

import logging
from django.db import IntegrityError, transaction
from .models import Location
from .weather_service import geocode_city, WeatherServiceError, WeatherTLSVerificationError


logger = logging.getLogger(__name__)


def _local_matches(search_query):
    return list(Location.objects.filter(name__iexact=search_query).order_by('country', 'state_or_region', 'id'))


def _exact_candidate_match(candidate):
    """Return an existing location only when provider identity fields match."""
    return Location.objects.filter(
        name__iexact=candidate['name'],
        state_or_region__iexact=candidate.get('state_or_region', ''),
        country__iexact=candidate['country'],
    ).order_by('id').first()


def find_location_candidates(search_query):
    """Return exact local matches or provider choices without writing locations."""
    clean_query = ' '.join((search_query or '').split())
    if not clean_query:
        return [], [], "Please enter a valid city or station name."
    local_matches = _local_matches(clean_query)
    if local_matches:
        return local_matches, [], None
    try:
        results = geocode_city(clean_query, count=5, return_all=True)
    except WeatherTLSVerificationError:
        logger.warning("TLS verification failed for geocoding query %r", clean_query, exc_info=True)
        return [], [], "City lookup could not verify the weather provider's secure connection. Please try again later."
    except WeatherServiceError:
        logger.warning("Geocoding provider unavailable for query %r", clean_query, exc_info=True)
        return [], [], "City lookup is currently unavailable. Please try again later."
    except Exception:
        logger.exception("Unexpected error during city geocoding")
        return [], [], "An unexpected error prevented this city lookup. Please try again."
    if not results:
        return [], [], f"No location matching '{clean_query}' was found by the geocoding provider."
    return [], results, None


def create_location_from_candidate(candidate):
    """Persist a provider candidate only after an explicit user selection."""
    with transaction.atomic():
        existing = _exact_candidate_match(candidate)
        if existing:
            return existing
        lat, lon = candidate['latitude'], candidate['longitude']
        try:
            with transaction.atomic():
                return Location.objects.create(
                    name=candidate['name'], state_or_region=candidate['state_or_region'],
                    country=candidate['country'], latitude=lat, longitude=lon,
                )
        except IntegrityError:
            return Location.objects.get(
                name__iexact=candidate['name'],
                state_or_region__iexact=candidate['state_or_region'],
                country__iexact=candidate['country'],
            )


def resolve_or_create_location(search_query):
    """
    Attempts to resolve a location:
    1. Checks if an exact or close match exists in the database.
    2. If not, queries Open-Meteo Geocoding API to resolve coordinates and place name.
    3. Reuses only an existing exact city, region, and country identity. Otherwise,
       returns a temporary provider location without persisting an arbitrary search.
    
    Returns:
        tuple (Location instance or None, error_message or None)
    """
    clean_query = ' '.join((search_query or '').split())
    if not clean_query:
        return (None, "Please enter a valid city or station name.")

    local_matches, candidates, error = find_location_candidates(clean_query)
    if len(local_matches) == 1:
        return local_matches[0], None
    if len(local_matches) > 1:
        return None, "Multiple stations match that city. Select one from the station directory."
    if error:
        return None, error
    if len(candidates) != 1:
        return None, "Multiple locations were found. Select a specific location from the results."
    candidate = candidates[0]
    existing = _exact_candidate_match(candidate)
    # Comparison may use a temporary location, but search does not persist it.
    return (existing or Location(**{key: candidate[key] for key in (
        'name', 'state_or_region', 'country', 'latitude', 'longitude'
    )}), None)
