import time

from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.utils import timezone
from django.utils.http import url_has_allowed_host_and_scheme

from django.contrib.auth import authenticate, login, logout
from .models import Location, WeatherRecord, OfficialNotice, SavedLocation
from .forms import (
    CitySearchForm,
    CityComparisonForm,
    OfficialNoticeForm,
    HeatGuardRegistrationForm,
    HeatGuardLoginForm,
)
from .services import resolve_or_create_location
from .weather_service import fetch_weather_forecast, WeatherServiceError
from .heat_index import compute_nws_heat_index
from .safety_guidance import (
    CATEGORY_SAFETY_GUIDANCE,
    GROUP_SAFETY_GUIDANCE,
    OFFICIAL_HEALTH_RESOURCES,
    get_safety_guidance_for_risk,
)


def is_staff_check(user):
    """
    Verifies that the user is authenticated and has staff status OR
    the explicit 'monitoring.add_officialnotice' model permission.
    """
    return user.is_authenticated and (user.is_staff or user.has_perm('monitoring.add_officialnotice'))


def set_temperature_unit_view(request):
    """
    Preference endpoint that sets the non-sensitive temperature display unit preference ('C' or 'F')
    in a client cookie.
    Accepts GET with ?unit=C or ?unit=F and redirects back to referer.
    """
    unit = request.GET.get('unit', 'C').upper()
    if unit not in ('C', 'F'):
        unit = 'C'
    
    redirect_url = request.META.get('HTTP_REFERER') or reverse('monitoring:home')
    response = redirect(redirect_url)
    response.set_cookie('heatguard_temp_unit', unit, max_age=30 * 86400, samesite='Lax')
    return response


def home_view(request):
    """
    Renders the public HeatGuard landing page.
    """
    form = CitySearchForm()
    context = {
        'form': form,
    }
    return render(request, 'monitoring/home.html', context)


def city_search_view(request):
    """
    Handles city/station search via HTTP GET.
    """
    form = CitySearchForm(request.GET or None)
    search_attempted = 'city' in request.GET
    error_message = None
    searched_city = ""

    if search_attempted:
        if form.is_valid():
            normalized_city = form.cleaned_data['city']
            searched_city = normalized_city

            location, err = resolve_or_create_location(normalized_city)
            if location:
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
            else:
                error_message = err
        else:
            searched_city = request.GET.get('city', '').strip()

    all_stations = Location.objects.all().order_by('name')[:15]
    session_searches = request.session.get('recent_searches', [])

    context = {
        'form': form,
        'search_attempted': search_attempted,
        'error_message': error_message,
        'searched_city': searched_city,
        'all_stations': all_stations,
        'session_searches': session_searches,
    }
    return render(request, 'monitoring/city_search.html', context)


def city_dashboard_view(request, location_id):
    """
    Displays the city monitoring dashboard.
    Shows Application-generated forecast advisory and Location-specific Official Notices.
    """
    location = get_object_or_404(Location, pk=location_id)
    weather_error = None
    live_weather = None
    hi_result = None

    try:
        live_weather = fetch_weather_forecast(location.latitude, location.longitude)
        
        current_data = live_weather.get('current', {})
        temp_c = current_data.get('temperature_c')
        rh = current_data.get('relative_humidity')
        apparent_temp_c = current_data.get('apparent_temperature_c')
        wind_speed_kmh = current_data.get('wind_speed_kmh')

        if temp_c is not None and rh is not None:
            hi_result = compute_nws_heat_index(temp_c, rh)
            calculated_hi = hi_result['heat_index_c']
            risk_category = hi_result['risk']['category']
        else:
            calculated_hi = None
            risk_category = 'NORMAL'

        WeatherRecord.objects.create(
            location=location,
            requested_by=request.user if request.user.is_authenticated else None,
            recorded_at=timezone.now(),
            record_type='current',
            temperature_c=temp_c,
            relative_humidity=rh,
            provider_apparent_temp_c=apparent_temp_c,
            wind_speed_kmh=wind_speed_kmh,
            heat_index_c=calculated_hi,
            risk_level=risk_category,
            data_source='provider-supplied'
        )

    except WeatherServiceError as e:
        weather_error = f"Weather telemetry currently unavailable: {str(e)}"
    except Exception as e:
        weather_error = f"Unexpected error retrieving live weather: {str(e)}"

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


def forecast_view(request):
    """
    Renders regional multi-day and hourly forecast outlook.
    """
    location_id = request.GET.get('location_id')
    location = None
    forecast_data = None
    forecast_error = None
    hottest_hour = None
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
            forecast_data = fetch_weather_forecast(location.latitude, location.longitude)
            
            raw_hourly = forecast_data.get('hourly', [])
            max_hourly_temp = None

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

        except WeatherServiceError as e:
            forecast_error = f"Forecast telemetry unavailable from provider: {str(e)}"
        except Exception as e:
            forecast_error = f"Unexpected error loading forecast data: {str(e)}"

    # Hottest hour safety guidance
    hottest_risk_cat = hottest_hour['heat_index']['risk']['category'] if (hottest_hour and hottest_hour.get('heat_index')) else None
    peak_safety_guidance = get_safety_guidance_for_risk(hottest_risk_cat)

    context = {
        'location': location,
        'forecast_data': forecast_data,
        'forecast_error': forecast_error,
        'processed_hourly': processed_hourly,
        'processed_daily': processed_daily,
        'hottest_hour': hottest_hour,
        'hottest_day': hottest_day,
        'peak_safety_guidance': peak_safety_guidance,
        'all_stations': all_stations,
    }
    return render(request, 'monitoring/forecast.html', context)


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
                    weather = fetch_weather_forecast(
                        result['location'].latitude,
                        result['location'].longitude,
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

                except WeatherServiceError as e:
                    result['error'] = f"Weather data unavailable: {e}"
                except Exception as e:
                    result['error'] = f"Unexpected error: {e}"

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

def notice_list_view(request):
    """
    Public bulletin board displaying published Official Notices.
    Separates notices into Active, Upcoming, and Expired based on validity dates.
    Shows empty states appropriately.
    """
    now = timezone.now()
    published_qs = OfficialNotice.objects.filter(is_published=True).select_related('location')

    active_notices = published_qs.filter(valid_from__lte=now, valid_until__gte=now).order_by('-valid_from')
    upcoming_notices = published_qs.filter(valid_from__gt=now).order_by('valid_from')
    expired_notices = published_qs.filter(valid_until__lt=now).order_by('-valid_until')[:10]

    context = {
        'active_notices': active_notices,
        'upcoming_notices': upcoming_notices,
        'expired_notices': expired_notices,
        'total_published': published_qs.count(),
    }
    return render(request, 'monitoring/notice_list.html', context)


@login_required
def notice_create_view(request):
    """
    Staff / Authority view to publish an official heat advisory bulletin.
    Enforces strict server-side permission checks using Django permissions:
    user.is_staff or user.has_perm('monitoring.add_officialnotice').
    Uses POST-redirect-GET pattern with CSRF protection.
    """
    if not (request.user.is_staff or request.user.has_perm('monitoring.add_officialnotice')):
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
def notice_edit_view(request, notice_id):
    """
    Staff / Authority view to edit an existing official notice.
    Enforces strict server-side permission checks using Django permissions:
    user.is_staff or user.has_perm('monitoring.change_officialnotice').
    """
    if not (request.user.is_staff or request.user.has_perm('monitoring.change_officialnotice')):
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
def staff_dashboard_view(request):
    """
    Simple staff/authority summary page listing all notices (published & drafts),
    total monitoring stations, and telemetry summary.
    Protected strictly via user.is_staff or user.has_perm('monitoring.view_officialnotice').
    """
    if not (request.user.is_staff or request.user.has_perm('monitoring.view_officialnotice')):
        raise PermissionDenied("Access restricted to authorized weather authority staff.")

    all_notices = OfficialNotice.objects.select_related('location', 'created_by').order_by('-valid_from')
    total_stations = Location.objects.count()
    total_telemetry = WeatherRecord.objects.count()
    total_saved = SavedLocation.objects.count()
    total_published_notices = OfficialNotice.objects.filter(is_published=True).count()

    context = {
        'all_notices': all_notices,
        'total_stations': total_stations,
        'total_telemetry': total_telemetry,
        'total_saved': total_saved,
        'total_published_notices': total_published_notices,
    }
    return render(request, 'monitoring/staff_dashboard.html', context)


# ==============================================================================
# AUTHENTICATION & USER PROFILE VIEWS
# ==============================================================================

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
            messages.error(request, "Invalid username or password. Please try again.")
    else:
        form = HeatGuardLoginForm()

    context = {
        'form': form,
    }
    return render(request, 'monitoring/login.html', context)


@login_required
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
def save_location_view(request, location_id):
    """
    Allows authenticated users to bookmark a station.
    Accepts POST requests and redirects back to dashboard.
    """
    if request.method == 'POST':
        location = get_object_or_404(Location, pk=location_id)
        SavedLocation.objects.get_or_create(user=request.user, location=location)
        messages.success(request, f"Station '{location.name}' has been added to your favorites.")
    return redirect('monitoring:city_dashboard', location_id=location_id)


@login_required
def remove_saved_location_view(request, location_id):
    """
    Allows authenticated users to remove only their own station bookmarks.
    Accepts POST requests.
    """
    if request.method == 'POST':
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
