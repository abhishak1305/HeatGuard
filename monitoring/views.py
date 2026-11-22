import logging
import time
from decimal import Decimal
from datetime import datetime, timedelta, timezone as datetime_timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.utils import timezone
from django.utils.http import url_has_allowed_host_and_scheme
from django.core.paginator import Paginator
from django.db.models import Avg, Max
from django.http import HttpResponse, StreamingHttpResponse
from django.http import JsonResponse
from django.core.cache import cache
from urllib.parse import urlencode
from django.views.decorators.http import require_GET, require_POST, require_http_methods

from django.contrib.auth import login, logout
from .models import Location, WeatherRecord, OfficialNotice, SavedLocation
from .forms import (
    CitySearchForm,
    CityComparisonForm,
    OfficialNoticeForm,
    HeatGuardRegistrationForm,
    HeatGuardLoginForm,
    WeatherHistoryFilterForm,
    ManualObservationForm,
)
from .services import resolve_or_create_location, find_location_candidates, create_location_from_candidate
from .weather_service import fetch_weather_forecast, WeatherServiceError, WeatherTLSVerificationError
from .heat_index import compute_nws_heat_index
from .permissions import user_can, can_manage_notices
from .weather_cache import cached_weather_forecast
from .heatmap_service import build_heatmap_data
from .safety_guidance import (
    CATEGORY_SAFETY_GUIDANCE,
    GROUP_SAFETY_GUIDANCE,
    OFFICIAL_HEALTH_RESOURCES,
    get_safety_guidance_for_risk,
)


logger = logging.getLogger(__name__)


def _query_without(querydict, key):
    params = querydict.copy()
    params.pop(key, None)
    return urlencode(params, doseq=True)


def bad_request_view(request, exception=None):
    return render(request, 'errors/400.html', status=400)


def permission_denied_view(request, exception=None):
    return render(request, 'errors/403.html', status=403)


def page_not_found_view(request, exception=None):
    return render(request, 'errors/404.html', status=404)


def server_error_view(request):
    return render(request, 'errors/500.html', status=500)


@require_GET
def set_temperature_unit_view(request):
    """
    Preference endpoint that sets the non-sensitive temperature display unit preference ('C' or 'F')
    in a client cookie.
    Accepts GET with ?unit=C or ?unit=F and redirects safely to a whitelisted URL.
    """
    unit = request.GET.get('unit', 'C').upper()
    if unit not in ('C', 'F'):
        unit = 'C'
    
    redirect_url = request.META.get('HTTP_REFERER') or reverse('monitoring:home')
    # Validate redirect URL to prevent open redirect attacks
    safe_redirect = redirect_url or reverse('monitoring:home')
    if redirect_url and not url_has_allowed_host_and_scheme(
        redirect_url, allowed_hosts={request.get_host()}
    ):
        safe_redirect = reverse('monitoring:home')

    response = redirect(safe_redirect)
    response.set_cookie('heatguard_temp_unit', unit, max_age=30 * 86400, samesite='Lax')
    return response


@require_GET
def home_view(request):
    """
    Renders the public HeatGuard landing page.
    """
    form = CitySearchForm()
    context = {
        'form': form,
    }
    return render(request, 'monitoring/home.html', context)


@require_GET
def india_heatmap_view(request):
    return render(request, 'monitoring/india_heatmap.html')


@require_GET
def india_heatmap_data_view(request):
    """Return cached, model-based India Heat Index samples; never writes records."""
    cache_key = 'heatguard:india-heatmap:v1:grid1.0:nws-v1'
    data = cache.get(cache_key)
    if data is not None:
        return JsonResponse(data)
    try:
        data = build_heatmap_data()
    except Exception:
        logger.exception('India heatmap data generation failed')
        return JsonResponse({
            'success': False,
            'error': 'Heatmap weather data is temporarily unavailable. Please try again later.',
        }, status=503)
    if data.get('success') and data.get('valid_points'):
        cache.set(cache_key, data, 600)
    return JsonResponse(data, status=200 if data.get('success') else 503)


@require_http_methods(['GET', 'POST'])
def city_search_view(request):
    """
    Handles city/station search via HTTP GET.
    """
    form = CitySearchForm(request.GET or None)
    search_attempted = 'city' in request.GET
    error_message = None
    searched_city = ""
    location_candidates = []
    matching_locations = []

    if request.method == 'POST' and request.POST.get('action') == 'select_location':
        pending = request.session.get('location_candidates', [])
        try:
            selected_index = int(request.POST.get('candidate_index', ''))
            candidate = pending[selected_index]
        except (ValueError, TypeError, IndexError):
            candidate = None
        if candidate:
            location = create_location_from_candidate({
                **candidate,
                'latitude': Decimal(candidate['latitude']),
                'longitude': Decimal(candidate['longitude']),
            })
            request.session.pop('location_candidates', None)
            return redirect('monitoring:city_dashboard', location_id=location.id)
        error_message = "That location selection has expired. Search again to choose a location."

    if search_attempted:
        if form.is_valid():
            normalized_city = form.cleaned_data['city']
            searched_city = normalized_city

            local_matches, candidates, err = find_location_candidates(normalized_city)
            if len(local_matches) == 1:
                location = local_matches[0]
                # Store non-sensitive recent search query in session for user convenience
                recent_searches = request.session.get('recent_searches', [])
                search_item = {
                    'id': location.id,
                    'name': location.name,
                    'country': location.country,
                }
                # Keep items unique and keep at most the last 5 searches
                recent_searches = [s for s in recent_searches if s.get('id') != location.id]
                recent_searches.insert(0, search_item)
                request.session['recent_searches'] = recent_searches[:5]
                request.session.modified = True

                return redirect('monitoring:city_dashboard', location_id=location.id)
            elif len(local_matches) > 1:
                matching_locations = local_matches
                error_message = "Multiple stations match that city. Select the correct station below."
            elif candidates:
                location_candidates = candidates
                request.session['location_candidates'] = [
                    {**candidate, 'latitude': str(candidate['latitude']), 'longitude': str(candidate['longitude'])}
                    for candidate in candidates
                ]
            else:
                error_message = err
        else:
            searched_city = request.GET.get('city', '').strip()

    station_page = Paginator(Location.objects.all().order_by('name', 'country'), 15).get_page(request.GET.get('directory_page'))
    session_searches = request.session.get('recent_searches', [])

    context = {
        'form': form,
        'search_attempted': search_attempted,
        'error_message': error_message,
        'searched_city': searched_city,
        'all_stations': station_page,
        'station_page': station_page,
        'station_query': _query_without(request.GET, 'directory_page'),
        'session_searches': session_searches,
        'location_candidates': location_candidates,
        'matching_locations': matching_locations,
    }
    return render(request, 'monitoring/city_search.html', context)


@require_http_methods(['GET', 'POST'])
def city_dashboard_view(request, location_id):
    """
    Displays the city monitoring dashboard.
    Shows Application-generated forecast advisory and Location-specific Official Notices.
    """
    location = get_object_or_404(Location, pk=location_id)
    save_reading = request.method == 'POST' and request.POST.get('action') == 'save_reading'
    weather_error = None
    live_weather = None
    hi_result = None

    try:
        live_weather = cached_weather_forecast(
            location.latitude, location.longitude, fetcher=fetch_weather_forecast
        )
        
        current_data = live_weather.get('current', {})
        temp_c = current_data.get('temperature_c')
        rh = current_data.get('relative_humidity')
        apparent_temp_c = current_data.get('apparent_temperature_c')
        wind_speed_kmh = current_data.get('wind_speed_kmh')

        if temp_c is not None and rh is not None:
            try:
                hi_result = compute_nws_heat_index(temp_c, rh)
            except ValueError:
                logger.warning("Heat Index inputs were outside supported ranges for location %s", location.pk)
                hi_result = None
        if save_reading:
            observed_at = _provider_observation_time(
                current_data.get('time'), live_weather.get('timezone')
            )
            if observed_at is None:
                messages.error(request, "This provider response has no valid observation time and cannot be saved.")
            else:
                record, created = WeatherRecord.objects.get_or_create(
                    location=location,
                    recorded_at=observed_at,
                    record_type='current',
                    data_source='provider-supplied',
                    defaults={
                        'requested_by': request.user if request.user.is_authenticated else None,
                        'retrieved_at': live_weather.get('retrieved_at') or timezone.now(),
                        'temperature_c': temp_c,
                        'relative_humidity': rh,
                        'provider_apparent_temp_c': apparent_temp_c,
                        'wind_speed_kmh': wind_speed_kmh,
                        'heat_index_c': hi_result['heat_index_c'] if hi_result else None,
                        'risk_level': hi_result['risk']['category'] if hi_result else None,
                    },
                )
                if created:
                    messages.success(request, "This provider reading was saved to the location history.")
                else:
                    messages.info(request, "This provider observation is already in the location history.")
            return redirect('monitoring:city_dashboard', location_id=location.pk)

    except WeatherTLSVerificationError:
        logger.warning("Provider TLS verification failed for location %s", location.pk, exc_info=True)
        weather_error = "Weather data could not be received because the provider's secure connection could not be verified. Please try again later."
    except WeatherServiceError:
        logger.warning("Weather provider unavailable for location %s", location.pk, exc_info=True)
        weather_error = "Weather telemetry is currently unavailable. Please try again later."
    except Exception:
        # Log the technical detail server-side; never show it to visitors.
        logger.exception("Unexpected error while loading live weather")
        weather_error = "Unexpected error while processing live weather data. Please try again."

    # Check if user has bookmarked this location
    is_saved = False
    if request.user.is_authenticated:
        is_saved = SavedLocation.objects.filter(user=request.user, location=location).exists()

    recent_records = location.weather_records.all().order_by('-recorded_at')[:10]
    
    # Official notices for this location (only published notices shown publicly)
    notices = location.notices.filter(is_published=True).order_by('-valid_from')

    # Retrieve specific safety guidance relevant to current risk category
    risk_category = hi_result['risk']['category'] if hi_result else None
    safety_guidance = get_safety_guidance_for_risk(risk_category)

    context = {
        'location': location,
        'live_weather': live_weather,
        'weather_error': weather_error,
        'hi_result': hi_result,
        'is_saved': is_saved,
        'safety_guidance': safety_guidance,
        'recent_records': recent_records,
        'notices': notices,
    }
    return render(request, 'monitoring/city_dashboard.html', context)


def _provider_observation_time(value, timezone_name):
    """Parse Open-Meteo's local observation timestamp as an aware datetime."""
    if not value:
        return None
    try:
        observed_at = value if isinstance(value, datetime) else datetime.fromisoformat(value)
        if timezone.is_naive(observed_at):
            try:
                provider_timezone = ZoneInfo(timezone_name) if timezone_name else timezone.get_current_timezone()
            except (ValueError, ZoneInfoNotFoundError):
                logger.warning("Invalid provider timezone %r; cannot save observation", timezone_name)
                return None
            observed_at = observed_at.replace(tzinfo=provider_timezone)
        return observed_at
    except (TypeError, ValueError):
        return None


@require_GET
def forecast_view(request):
    """
    Renders regional multi-day and hourly forecast outlook.
    """
    location_id = request.GET.get('location_id')
    location = None
    forecast_data = None
    forecast_error = None
    hottest_hour = None
    peak_heat_index_hour = None
    hottest_day = None
    processed_hourly = []
    processed_daily = []

    all_stations = Location.objects.all().order_by('name')

    if location_id and location_id.isdigit():
        location = Location.objects.filter(pk=int(location_id)).first()

    if not location and all_stations.exists():
        location = all_stations.first()

    if location:
        try:
            forecast_data = cached_weather_forecast(
                location.latitude, location.longitude, fetcher=fetch_weather_forecast
            )
            
            raw_hourly = forecast_data.get('hourly', [])
            provider_tz = forecast_data.get('timezone')
            provider_now = _provider_observation_time(
                (forecast_data.get('current') or {}).get('time'), provider_tz
            )
            if provider_now is None:
                provider_now = timezone.now()
                logger.warning(
                    "Forecast response for location %s had no valid current timestamp; using retrieval time",
                    location.pk,
                )
            start_utc = provider_now.astimezone(datetime_timezone.utc)
            end_utc = start_utc + timedelta(hours=24)
            dated_hourly = []
            for item in raw_hourly:
                hour_at = _provider_observation_time(item.get('time'), provider_tz)
                if hour_at is None:
                    continue
                hour_utc = hour_at.astimezone(datetime_timezone.utc)
                if start_utc <= hour_utc < end_utc:
                    dated_hourly.append((hour_utc, item))
            dated_hourly.sort(key=lambda pair: pair[0])
            raw_hourly = [item for _, item in dated_hourly]
            max_hourly_temp = None
            max_heat_index = None
            peak_heat_index_hour = None

            for item in raw_hourly:
                t_val = item.get('temperature_c')
                rh_val = item.get('relative_humidity')
                hi_item = None

                if t_val is not None and rh_val is not None:
                    try:
                        hi_item = compute_nws_heat_index(t_val, rh_val)
                    except ValueError:
                        hi_item = None

                bar_height = 0
                if t_val is not None:
                    bar_height = max(5, min(100, int((float(t_val) / 50.0) * 100)))

                entry = {
                    'time': item.get('time'),
                    'temperature_c': t_val,
                    'relative_humidity': rh_val,
                    'apparent_temperature_c': item.get('apparent_temperature_c'),
                    'wind_speed_kmh': item.get('wind_speed_kmh'),
                    'heat_index': hi_item,
                    'bar_height': bar_height,
                }
                processed_hourly.append(entry)

                if t_val is not None and (max_hourly_temp is None or t_val > max_hourly_temp):
                    max_hourly_temp = t_val
                    hottest_hour = entry
                if (
                    hi_item is not None
                    and (max_heat_index is None or hi_item['heat_index_c'] > max_heat_index)
                ):
                    max_heat_index = hi_item['heat_index_c']
                    peak_heat_index_hour = entry

            raw_daily = forecast_data.get('daily', [])
            max_daily_temp = None

            for day in raw_daily:
                t_max = day.get('max_temp_c')
                t_min = day.get('min_temp_c')

                bar_width = 0
                if t_max is not None:
                    bar_width = max(5, min(100, int((float(t_max) / 50.0) * 100)))

                day_entry = {
                    'date': day.get('date'),
                    'max_temp_c': t_max,
                    'min_temp_c': t_min,
                    'apparent_max_c': day.get('apparent_max_c'),
                    'apparent_min_c': day.get('apparent_min_c'),
                    'bar_width': bar_width,
                }
                processed_daily.append(day_entry)

                if t_max is not None and (max_daily_temp is None or t_max > max_daily_temp):
                    max_daily_temp = t_max
                    hottest_day = day_entry

        except WeatherTLSVerificationError:
            logger.warning("Provider TLS verification failed for forecast location %s", location.pk, exc_info=True)
            forecast_error = "Forecast data could not be received because the provider's secure connection could not be verified. Please try again later."
        except WeatherServiceError:
            logger.warning("Forecast provider unavailable for location %s", location.pk, exc_info=True)
            forecast_error = "Forecast telemetry is currently unavailable. Please try again later."
        except Exception:
            logger.exception("Unexpected error while loading forecast data")
            forecast_error = "Unexpected error while processing forecast data. Please try again."

    # Hottest hour safety guidance
    hottest_risk_cat = (
        peak_heat_index_hour['heat_index']['risk']['category']
        if peak_heat_index_hour else None
    )
    peak_safety_guidance = get_safety_guidance_for_risk(hottest_risk_cat)

    context = {
        'location': location,
        'forecast_data': forecast_data,
        'forecast_error': forecast_error,
        'processed_hourly': processed_hourly,
        'processed_daily': processed_daily,
        'hottest_hour': hottest_hour,
        'peak_heat_index_hour': peak_heat_index_hour,
        'hottest_day': hottest_day,
        'peak_safety_guidance': peak_safety_guidance,
        'all_stations': all_stations,
    }
    return render(request, 'monitoring/forecast.html', context)


@require_GET
def safety_guidance_view(request):
    """
    Renders the public heat safety and health guidance resource page.
    Includes general precautions, vulnerable group guidance, and official health links.
    """
    context = {
        'category_guidance': CATEGORY_SAFETY_GUIDANCE,
        'group_guidance': GROUP_SAFETY_GUIDANCE,
        'health_resources': OFFICIAL_HEALTH_RESOURCES,
    }
    return render(request, 'monitoring/safety_guidance.html', context)


@require_http_methods(['GET', 'POST'])
def city_comparison_view(request):
    """
    Compares live weather conditions and heat index estimates for 2 or 3 cities.
    Uses CityComparisonForm for input validation.
    Fetches real provider data with timeouts and proper error handling.
    """
    comparison_results = []
    comparison_attempted = False

    if request.method == 'POST':
        form = CityComparisonForm(request.POST)
        if form.is_valid():
            comparison_attempted = True

            for i in range(1, 4):
                station = form.cleaned_data.get(f'station_{i}')
                city_name = (form.cleaned_data.get(f'city_name_{i}') or '').strip()

                # Slot 3 is optional — skip if empty
                if i == 3 and not station and not city_name:
                    continue

                result = {
                    'slot': i,
                    'location': None,
                    'temperature_c': None,
                    'relative_humidity': None,
                    'apparent_temperature_c': None,
                    'wind_speed_kmh': None,
                    'heat_index_c': None,
                    'heat_index_f': None,
                    'risk_label': None,
                    'risk_badge_class': None,
                    'risk_description': None,
                    'retrieval_time_ms': None,
                    'source': None,
                    'error': None,
                }

                # --- Resolve location ---
                # Prioritize explicitly entered city search name over dropdown selection
                if city_name:
                    location, err = resolve_or_create_location(city_name)
                    if location:
                        result['location'] = location
                    else:
                        result['error'] = err or f"Could not resolve location '{city_name}'."
                        comparison_results.append(result)
                        continue
                elif station:
                    result['location'] = station
                else:
                    result['error'] = f"No station selected or city name entered for slot {i}."
                    comparison_results.append(result)
                    continue

                # --- Fetch live weather with timing ---
                try:
                    start_time = time.perf_counter()
                    weather = cached_weather_forecast(
                        result['location'].latitude,
                        result['location'].longitude,
                        fetcher=fetch_weather_forecast,
                    )
                    elapsed_ms = (time.perf_counter() - start_time) * 1000
                    result['retrieval_time_ms'] = round(elapsed_ms, 1)
                    result['source'] = weather.get('provider', 'Open-Meteo')

                    current = weather.get('current', {})
                    result['temperature_c'] = current.get('temperature_c')
                    result['relative_humidity'] = current.get('relative_humidity')
                    result['apparent_temperature_c'] = current.get('apparent_temperature_c')
                    result['wind_speed_kmh'] = current.get('wind_speed_kmh')

                    # Compute heat index if inputs are available
                    temp = result['temperature_c']
                    rh = result['relative_humidity']
                    if temp is not None and rh is not None:
                        try:
                            hi = compute_nws_heat_index(temp, rh)
                            result['heat_index_c'] = hi['heat_index_c']
                            result['heat_index_f'] = hi['heat_index_f']
                            result['risk_label'] = hi['risk']['label']
                            result['risk_badge_class'] = hi['risk']['badge_class']
                            result['risk_description'] = hi['risk']['description']
                        except ValueError:
                            pass  # Heat index not applicable for these conditions

                except WeatherTLSVerificationError:
                    logger.warning(
                        "Provider TLS verification failed while comparing location %s",
                        result['location'].pk,
                        exc_info=True,
                    )
                    result['error'] = "Weather data is unavailable because a secure provider connection could not be verified."
                except WeatherServiceError:
                    logger.warning(
                        "Weather provider unavailable while comparing location %s",
                        result['location'].pk,
                        exc_info=True,
                    )
                    result['error'] = "Weather data is currently unavailable for this location."
                except Exception:
                    logger.exception("Unexpected error while comparing cities")
                    result['error'] = "Unexpected error while loading this city's data."

                comparison_results.append(result)
    else:
        form = CityComparisonForm()

    context = {
        'form': form,
        'comparison_results': comparison_results,
        'comparison_attempted': comparison_attempted,
    }
    return render(request, 'monitoring/city_comparison.html', context)


# ==============================================================================
# OFFICIAL NOTICE VIEWS (PUBLIC BULLETIN & STAFF MANAGEMENT)
# ==============================================================================

@require_GET
def notice_list_view(request):
    """
    Public bulletin board displaying published Official Notices.
    Separates notices into Active, Upcoming, and Expired based on validity dates.
    Shows empty states appropriately.
    """
    now = timezone.now()
    published_qs = OfficialNotice.objects.filter(is_published=True).select_related('location')

    active_notices = Paginator(
        published_qs.filter(valid_from__lte=now, valid_until__gte=now).order_by('-valid_from'), 15
    ).get_page(request.GET.get('active_page'))
    upcoming_notices = Paginator(
        published_qs.filter(valid_from__gt=now).order_by('valid_from'), 15
    ).get_page(request.GET.get('upcoming_page'))
    expired_notices = Paginator(
        published_qs.filter(valid_until__lt=now).order_by('-valid_until'), 15
    ).get_page(request.GET.get('expired_page'))

    context = {
        'active_notices': active_notices,
        'upcoming_notices': upcoming_notices,
        'expired_notices': expired_notices,
        'total_published': published_qs.count(),
        'active_query': _query_without(request.GET, 'active_page'),
        'upcoming_query': _query_without(request.GET, 'upcoming_page'),
        'expired_query': _query_without(request.GET, 'expired_page'),
    }
    return render(request, 'monitoring/notice_list.html', context)


@login_required
@require_http_methods(['GET', 'POST'])
def notice_create_view(request):
    """
    Staff / Authority view to publish an official heat advisory bulletin.
    Enforces strict server-side permission checks using Django permissions:
    user.is_staff or user.has_perm('monitoring.add_officialnotice').
    Uses POST-redirect-GET pattern with CSRF protection.
    """
    if not user_can(request.user, 'monitoring.add_officialnotice'):
        raise PermissionDenied("Only authorized staff members can publish official notices.")

    if request.method == 'POST':
        form = OfficialNoticeForm(request.POST)
        if form.is_valid():
            notice = form.save(commit=False)
            notice.created_by = request.user
            notice.save()
            messages.success(request, f"Official Notice '{notice.title}' has been successfully published.")
            return redirect('monitoring:notice_list')
    else:
        form = OfficialNoticeForm()

    context = {
        'form': form,
        'action_title': "Publish New Official Notice",
        'is_edit': False,
    }
    return render(request, 'monitoring/notice_form.html', context)


@login_required
@require_http_methods(['GET', 'POST'])
def notice_edit_view(request, notice_id):
    """
    Staff / Authority view to edit an existing official notice.
    Enforces strict server-side permission checks using Django permissions:
    user.is_staff or user.has_perm('monitoring.change_officialnotice').
    """
    if not user_can(request.user, 'monitoring.change_officialnotice'):
        raise PermissionDenied("Only authorized staff members can edit official notices.")

    notice = get_object_or_404(OfficialNotice, pk=notice_id)

    if request.method == 'POST':
        form = OfficialNoticeForm(request.POST, instance=notice)
        if form.is_valid():
            form.save()
            messages.success(request, f"Official Notice '{notice.title}' has been updated.")
            return redirect('monitoring:notice_list')
    else:
        form = OfficialNoticeForm(instance=notice)

    context = {
        'form': form,
        'notice': notice,
        'action_title': f"Edit Notice: {notice.title}",
        'is_edit': True,
    }
    return render(request, 'monitoring/notice_form.html', context)


@login_required
@require_GET
def staff_dashboard_view(request):
    """
    Simple staff/authority summary page listing all notices (published & drafts),
    total monitoring stations, and telemetry summary.
    Protected strictly via user.is_staff or user.has_perm('monitoring.view_officialnotice').
    """
    if not can_manage_notices(request.user):
        raise PermissionDenied("Access restricted to authorized weather authority staff.")

    all_notices = Paginator(
        OfficialNotice.objects.select_related('location', 'created_by').order_by('-valid_from'), 20
    ).get_page(request.GET.get('page'))
    recent_notices = OfficialNotice.objects.select_related('location', 'created_by').order_by('-created_at')[:10]
    recent_weather_records = WeatherRecord.objects.select_related('location', 'requested_by').order_by('-recorded_at')[:10]
    total_stations = Location.objects.count()
    total_telemetry = WeatherRecord.objects.count()
    provider_record_count = WeatherRecord.objects.filter(data_source='provider-supplied').count()
    user_report_count = WeatherRecord.objects.filter(data_source='user-entered').count()
    total_saved = SavedLocation.objects.count()
    total_published_notices = OfficialNotice.objects.filter(is_published=True).count()
    dashboard_now = timezone.now()
    active_notice_count = OfficialNotice.objects.filter(
        is_published=True, valid_from__lte=dashboard_now, valid_until__gte=dashboard_now
    ).count()

    context = {
        'all_notices': all_notices,
        'recent_notices': recent_notices,
        'notice_query': _query_without(request.GET, 'page'),
        'recent_weather_records': recent_weather_records,
        'total_stations': total_stations,
        'total_telemetry': total_telemetry,
        'provider_record_count': provider_record_count,
        'user_report_count': user_report_count,
        'active_notice_count': active_notice_count,
        'total_saved': total_saved,
        'total_published_notices': total_published_notices,
    }
    return render(request, 'monitoring/staff_dashboard.html', context)


def _filtered_history(request):
    form = WeatherHistoryFilterForm(request.GET or None)
    records = WeatherRecord.objects.select_related('location', 'requested_by').order_by('-recorded_at', '-created_at')
    if not form.is_valid():
        return form, records.none()
    filters = form.cleaned_data
    if filters['location']:
        records = records.filter(location=filters['location'])
    if filters['start_date']:
        records = records.filter(recorded_at__date__gte=filters['start_date'])
    if filters['end_date']:
        records = records.filter(recorded_at__date__lte=filters['end_date'])
    if filters['risk_level']:
        records = records.filter(risk_level=filters['risk_level'])
    return form, records


@require_GET
def weather_history_view(request):
    """Browse actual persisted readings with filters, statistics, and pagination."""
    form, records = _filtered_history(request)
    summary = records.aggregate(
        average_temperature=Avg('temperature_c'),
        maximum_temperature=Max('temperature_c'),
        maximum_heat_index=Max('heat_index_c'),
    )
    page = Paginator(records, 25).get_page(request.GET.get('page'))
    return render(request, 'monitoring/weather_history.html', {
        'form': form,
        'records': page,
        'page_obj': page,
        'page_query': _query_without(request.GET, 'page'),
        'record_count': records.count(),
        'provider_count': records.filter(data_source='provider-supplied').count(),
        'user_entered_count': records.filter(data_source='user-entered').count(),
        **summary,
    })


@require_GET
def weather_history_export_view(request):
    """Export the currently filtered history as CSV using the standard library."""
    import csv

    _, records = _filtered_history(request)
    class Echo:
        def write(self, value):
            return value

    writer = csv.writer(Echo())

    def rows():
        yield writer.writerow([
            'Location', 'Recorded at', 'Temperature (C)', 'Humidity (%)',
            'Heat Index (C)', 'Risk', 'Data source',
        ])
        for record in records.iterator(chunk_size=1000):
            yield writer.writerow([
                safe_csv_text(record.location.name), timezone.localtime(record.recorded_at).isoformat(),
                record.temperature_c, record.relative_humidity, record.heat_index_c,
                record.get_risk_level_display() if record.risk_level else 'Not assessed',
                record.get_data_source_display(),
            ])

    response = StreamingHttpResponse(rows(), content_type='text/csv; charset=utf-8')
    response['Content-Disposition'] = 'attachment; filename="heatguard-weather-history.csv"'

    def safe_csv_text(value):
        value = str(value or '')
        if value.lstrip().startswith(('=', '+', '-', '@')):
            return "'" + value
        return value
    return response


@login_required
@require_http_methods(['GET', 'POST'])
def manual_observation_view(request):
    """Accept an authenticated, clearly labeled user report, separate from provider data."""
    if request.method == 'POST':
        form = ManualObservationForm(request.POST)
        if form.is_valid():
            record = form.save(commit=False)
            record.requested_by = request.user
            record.record_type = 'current'
            record.data_source = 'user-entered'
            record.recorded_at = timezone.now()
            record.retrieved_at = record.recorded_at
            assessment = compute_nws_heat_index(record.temperature_c, record.relative_humidity)
            record.heat_index_c = assessment['heat_index_c']
            record.risk_level = assessment['risk']['category']
            record.save()
            messages.success(request, 'Your observation was saved as an unverified user report.')
            return redirect('monitoring:weather_history')
    else:
        form = ManualObservationForm()
    return render(request, 'monitoring/manual_observation_form.html', {'form': form})


# ==============================================================================
# AUTHENTICATION & USER PROFILE VIEWS
# ==============================================================================

@require_http_methods(['GET', 'POST'])
def register_view(request):
    """
    Handles user registration using Django's UserCreationForm.
    Redirects authenticated users to their profile.
    """
    if request.user.is_authenticated:
        return redirect('monitoring:profile')

    if request.method == 'POST':
        form = HeatGuardRegistrationForm(request.POST)
        if form.is_valid():
            user = form.save()
            messages.success(request, f"Welcome to HeatGuard, {user.username}! Your account has been created. Please sign in.")
            return redirect('monitoring:login')
    else:
        form = HeatGuardRegistrationForm()

    context = {
        'form': form,
    }
    return render(request, 'monitoring/register.html', context)


@require_http_methods(['GET', 'POST'])
def login_view(request):
    """
    Handles session-based user authentication using Django's AuthenticationForm.
    Redirects authenticated users or preserves 'next' parameter.
    """
    if request.user.is_authenticated:
        return redirect('monitoring:profile')

    redirect_to = request.POST.get('next') or request.GET.get('next') or ''
    # Validate redirect target to prevent open redirect attacks
    if redirect_to and not url_has_allowed_host_and_scheme(
        redirect_to, allowed_hosts={request.get_host()}
    ):
        redirect_to = ''
    if not redirect_to:
        redirect_to = 'monitoring:profile'

    if request.method == 'POST':
        form = HeatGuardLoginForm(request, data=request.POST)
        if form.is_valid():
            user = form.get_user()
            login(request, user)
            messages.success(request, f"Welcome back, {user.username}!")
            return redirect(redirect_to)
    else:
        form = HeatGuardLoginForm()

    context = {
        'form': form,
    }
    return render(request, 'monitoring/login.html', context)


@login_required
@require_http_methods(['GET', 'POST'])
def logout_view(request):
    """
    Handles user logout via POST request with CSRF protection.
    Clears the session and redirects to home.
    """
    if request.method == 'POST':
        logout(request)
        messages.info(request, "You have been successfully signed out.")
        return redirect('monitoring:home')
    # If accessed via GET, redirect to profile
    return redirect('monitoring:profile')


@login_required
@require_GET
def profile_view(request):
    """
    Displays the authenticated user's profile, saved locations, and query history.
    Strictly protected with @login_required.
    """
    saved_locations = request.user.saved_locations.select_related('location').order_by('-created_at')
    query_history = WeatherRecord.objects.filter(requested_by=request.user).select_related('location').order_by('-recorded_at')[:15]
    session_searches = request.session.get('recent_searches', [])

    context = {
        'saved_locations': saved_locations,
        'query_history': query_history,
        'session_searches': session_searches,
    }
    return render(request, 'monitoring/profile.html', context)


@login_required
@require_POST
def save_location_view(request, location_id):
    """
    Allows authenticated users to bookmark a station.
    Accepts POST requests and redirects back to dashboard.
    """
    location = get_object_or_404(Location, pk=location_id)
    SavedLocation.objects.get_or_create(user=request.user, location=location)
    messages.success(request, f"Station '{location.name}' has been added to your favorites.")
    return redirect('monitoring:city_dashboard', location_id=location_id)


@login_required
@require_POST
def remove_saved_location_view(request, location_id):
    """
    Allows authenticated users to remove only their own station bookmarks.
    Accepts POST requests.
    """
    location = get_object_or_404(Location, pk=location_id)
    # Strictly delete records belonging ONLY to request.user
    deleted_count, _ = SavedLocation.objects.filter(user=request.user, location=location).delete()
    if deleted_count > 0:
        messages.info(request, f"Station '{location.name}' was removed from your favorites.")
    else:
        messages.warning(request, f"Station '{location.name}' was not in your saved list.")
    
    # Redirect back to where the request came from (dashboard or profile)
    referer = request.META.get('HTTP_REFERER')
    if referer and 'profile' in referer:
        return redirect('monitoring:profile')
    return redirect('monitoring:city_dashboard', location_id=location_id)
