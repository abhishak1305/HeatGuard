# HeatGuard

**HeatGuard** is an Extreme Heatwave Early Warning and Human Thermal Stress Monitoring System prototype built strictly using core Django features according to the classroom curriculum.

## Demo Accounts

Create the `demouser`, `staffuser`, and Weather Authority Staff permission group with:

```powershell
python manage.py setup_roles
```

New accounts have unusable passwords until an operator sets them explicitly. For local demos, use `python manage.py changepassword demouser` and `python manage.py changepassword staffuser`. Existing passwords are never reset by a normal rerun. For automated provisioning, provide `HEATGUARD_DEMO_USER_PASSWORD` and `HEATGUARD_STAFF_USER_PASSWORD`; resetting existing demo passwords requires `python manage.py setup_roles --force`. Passwords are never printed. Do not use shared demo accounts in a public deployment.

---

## Prerequisites
- Python 3.12+ (verified here with Python 3.14.5)
- Django 6.1.3 (pinned in `requirements.txt`)
- SQLite3 (included with Python)

---

## Setup Instructions

1. **Activate the Virtual Environment:**
   - **Windows:**
     ```powershell
     .\venv\Scripts\Activate.ps1
     ```
   - **macOS / Linux:**
     ```bash
     source venv/bin/activate
     ```

2. **Install Dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

3. **Configure local settings:**
   Django does not load `.env` files by itself. `.env.example` documents the supported variable names but is not automatically read. Settings default to `DEBUG=False`; explicitly set `DJANGO_DEBUG=1` for local development. When `DJANGO_SECRET_KEY` is not set in local debug mode, Django generates a temporary random key for that process. Set a stable development key if you need sessions to survive server restarts.

   PowerShell:
   ```powershell
   $env:DJANGO_DEBUG = "1"
   $env:DJANGO_SECRET_KEY = (& python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())")
   ```

   Bash:
   ```bash
   export DJANGO_DEBUG=1
   export DJANGO_SECRET_KEY="$(python -c 'from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())')"
   ```

   For a deployment, set `DJANGO_DEBUG=0`, provide a securely generated persistent `DJANGO_SECRET_KEY`, and set `DJANGO_ALLOWED_HOSTS` to the deployment host names. Production defaults enable SSL redirects, one year of HSTS, and secure session/CSRF cookies. Configure `DJANGO_SECURE_SSL_REDIRECT`, `DJANGO_SECURE_HSTS_SECONDS`, `DJANGO_SESSION_COOKIE_SECURE`, and `DJANGO_CSRF_COOKIE_SECURE` explicitly when your deployment topology requires different values. Settings refuse to start with debug disabled when the secret key or allowed hosts are missing. HTTPS redirects are off by default in local development.

4. **Apply Database Migrations:**
   ```bash
   python manage.py migrate
   ```

5. **Verify System Checks & Run Tests:**
   ```bash
   python manage.py check
   python manage.py test
   ```

6. **Run the Development Server:**
   ```bash
   python manage.py runserver
   ```
   Open your browser and navigate to `http://127.0.0.1:8000/`.

## Production Deployment Checklist

The `runserver` command above is for local development only. Deploy through a production WSGI/ASGI server provided by the hosting environment, and configure that environment before starting Django:

- Set `DJANGO_DEBUG=0`, a unique persistent `DJANGO_SECRET_KEY`, and the exact `DJANGO_ALLOWED_HOSTS` values. Do not copy secrets into this repository or rely on `.env.example` being loaded.
- Run `python manage.py check --deploy` with the production environment. Decide whether HSTS should include subdomains or be preload eligible only after confirming every affected domain is HTTPS-capable; those options are intentionally not enabled by default.
- Set `DJANGO_SECURE_HSTS_INCLUDE_SUBDOMAINS=1` or `DJANGO_SECURE_HSTS_PRELOAD=1` only after confirming the whole domain/subdomain deployment is HTTPS-only; these options are intentionally off by default.
- If TLS terminates at a reverse proxy, configure Django's trusted HTTPS proxy header only after verifying the proxy removes client-supplied copies and sets the header itself. Otherwise, keep the default unset and perform HTTPS redirects at the trusted edge.
- Run migrations as a deployment step, run `python manage.py collectstatic --noinput`, and configure the host to serve the collected `staticfiles/` directory.
- Keep `db.sqlite3` on persistent storage and establish tested backups and restores. The application does not create backups automatically.
- Apply request limits at the hosting edge to public city search and comparison endpoints, which can initiate Open-Meteo requests, and to login attempts. Keep an eye on provider availability and quotas.
- Staff must verify the issuing authority and publication URL before publishing an Official Notice. The form validates URL syntax but cannot independently prove that a source is an official issuer.

---

## Django ORM: Shell Operations Guide

You can interact with HeatGuard's data layer using the Django interactive shell (`python manage.py shell`). Below is an end-to-end demonstration of standard Create, Read, Update, and Delete (CRUD) operations via the Django ORM:

```python
# 1. Start the shell
# python manage.py shell

from decimal import Decimal
from django.utils import timezone
from datetime import timedelta
from django.contrib.auth.models import User
from monitoring.models import Location, WeatherRecord, OfficialNotice, SavedLocation

# --- CREATE (C) ---
# Create a user and a monitoring location
user, _ = User.objects.get_or_create(username="officer_jane", email="jane@heatguard.local")
station = Location.objects.create(
    name="Central Urban Core",
    state_or_region="Capital District",
    country="Country A",
    latitude=Decimal("28.61390"),
    longitude=Decimal("77.20900")
)

# In the normal application flow, provider records are saved through the
# explicit dashboard action and manual submissions are labeled user-entered.
# Do not label hand-entered example values as provider-supplied observations.

# Bookmark the station for the user
bookmark = SavedLocation.objects.create(user=user, location=station)

# --- READ (R) ---
# Query all stations
all_locations = Location.objects.all()
print("Locations:", all_locations)

# Filter weather records with high risk
high_heat = WeatherRecord.objects.filter(risk_level='DANGER', location=station)
print("Danger records:", high_heat.count())

# Query reverse relations
user_bookmarks = user.saved_locations.all()
station_records = station.weather_records.all()
print(f"Station records count: {station_records.count()}")

# --- UPDATE (U) ---
# Update a location's region
station.state_or_region = "National Capital Region"
station.save(update_fields=['state_or_region'])

# --- DELETE (D) ---
# Remove bookmark
bookmark.delete()

# Check that bookmark was removed
print("Remaining bookmarks:", user.saved_locations.count())
```

---

## Route Table

| URL Pattern | View Function | Named Pattern | Access | Description |
|---|---|---|---|---|
| `/` | `home_view` | `monitoring:home` | Public | Main landing page & heat monitoring overview |
| `/admin/` | Django Admin | `admin:app_list` and model admin routes | Staff with model permissions | Manage Django users and HeatGuard records |
| `/search/` | `city_search_view` | `monitoring:city_search` | Public | City/station search with query validation and redirects |
| `/city/<int:location_id>/` | `city_dashboard_view` | `monitoring:city_dashboard` | Public | City dashboard displaying telemetry for location ID (or 404) |
| `/forecast/` | `forecast_view` | `monitoring:forecast` | Public | Live hourly and daily weather forecast with heat-risk estimates |
| `/history/` | `weather_history_view` | `monitoring:weather_history` | Public | Filterable, paginated saved readings and summary statistics |
| `/history/export.csv` | `weather_history_export_view` | `monitoring:weather_history_export` | Public | CSV export for the current history filters |
| `/observations/report/` | `manual_observation_view` | `monitoring:manual_observation` | Login required; GET/POST | Submit an unverified, user-entered observation |
| `/comparison/` | `city_comparison_view` | `monitoring:city_comparison` | Public | Multi-city weather and heat-index comparison |
| `/safety-guidance/` | `safety_guidance_view` | `monitoring:safety_guidance` | Public | Heat safety recommendations and health resources |
| `/notices/` | `notice_list_view` | `monitoring:notice_list` | Public | Published official notices and advisories |
| `/notices/create/` | `notice_create_view` | `monitoring:notice_create` | Notice add permission | Create sourced official notices |
| `/notices/<int:notice_id>/edit/` | `notice_edit_view` | `monitoring:notice_edit` | Notice change permission | Edit official notices |
| `/staff/dashboard/` | `staff_dashboard_view` | `monitoring:staff_dashboard` | Staff or notice management permission | Database-backed operational summary |
| `/preferences/unit/` | `set_temperature_unit_view` | `monitoring:set_temperature_unit` | Public | Set Celsius/Fahrenheit preference cookie |
| `/accounts/login/` | `login_view` | `monitoring:login` | Public | User login |
| `/accounts/register/` | `register_view` | `monitoring:register` | Public | User registration |
| `/accounts/logout/` | `logout_view` | `monitoring:logout` | Login required; POST | Sign out |
| `/accounts/profile/` | `profile_view` | `monitoring:profile` | Login required | Saved locations, own weather records, and session searches |
| `/locations/<int:location_id>/save/` | `save_location_view` | `monitoring:save_location` | Login required; POST | Save a location |
| `/locations/<int:location_id>/remove/` | `remove_saved_location_view` | `monitoring:remove_saved_location` | Login required; POST | Remove own saved location |

---

## Architectural Notes
- Uses function-based views (FBVs) and standard Django templates.
- Explicit data provenance labels (`provider-supplied`, `user-entered`, `application-calculated`, `officially published`, `test-only`).
- Heat Index calculations use the NOAA preliminary method and conditional Rothfusz regression (distinct from WBGT).
- Weather lookups use Python's standard-library `urllib` and `json`.
- Weather history contains explicitly saved provider readings and user-entered reports; page views do not create records. Manual reports are not used by live forecast or official notice workflows.
- CSV export uses Python's standard-library `csv` module. Password reset is not enabled because no email delivery backend is configured. Registration email remains optional and is not unique.
- Zero heavy third-party framework dependencies (no React, Celery, Redis, DRF, or Docker).
- The syllabus-aligned project blueprint and coding prompts are in [`docs/heatguard_django_syllabus_prompts.md`](docs/heatguard_django_syllabus_prompts.md).
