# HeatGuard

**HeatGuard** is an Extreme Heatwave Early Warning and Human Thermal Stress Monitoring System prototype built strictly using core Django features according to the classroom curriculum.

---

## Prerequisites
- Python 3.10+ (Tested on Python 3.14)
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

3. **Apply Database Migrations:**
   ```bash
   python manage.py migrate
   ```

4. **Verify System Checks & Run Tests:**
   ```bash
   python manage.py check
   python manage.py test
   ```

5. **Run the Development Server:**
   ```bash
   python manage.py runserver
   ```
   Open your browser and navigate to `http://127.0.0.1:8000/`.

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

# Create a weather observation record
record = WeatherRecord.objects.create(
    location=station,
    requested_by=user,
    recorded_at=timezone.now(),
    record_type='current',
    temperature_c=Decimal("36.50"),
    relative_humidity=Decimal("62.00"),
    heat_index_c=Decimal("47.80"),
    risk_level='DANGER',
    data_source='provider-supplied'
)

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

# Update a record's risk level
record.risk_level = 'EXTREME_DANGER'
record.save(update_fields=['risk_level'])

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
| `/search/` | `city_search_view` | `monitoring:city_search` | Public | City/station search with query validation and redirects |
| `/city/<int:location_id>/` | `city_dashboard_view` | `monitoring:city_dashboard` | Public | City dashboard displaying telemetry for location ID (or 404) |
| `/forecast/` | `forecast_view` | `monitoring:forecast` | Public | Regional multi-day heatwave forecast placeholder |
| `/comparison/` | `city_comparison_view` | `monitoring:city_comparison` | Public | Multi-city thermal stress comparison placeholder |
| `/notices/` | `notice_list_view` | `monitoring:notice_list` | Public | Official heatwave bulletins & emergency advisories placeholder |
| `/accounts/login/` | `login_placeholder_view` | `monitoring:login` | Public | Account login placeholder |
| `/accounts/register/` | `register_placeholder_view` | `monitoring:register` | Public | User registration placeholder |

---

## Architectural Notes
- Uses function-based views (FBVs) and standard Django templates.
- Explicit data provenance labels (`provider-supplied`, `user-entered`, `application-calculated`, `officially published`, `test-only`).
- Heat index calculations use the NOAA Rothfusz regression equation (distinct from WBGT).
- Weather lookups use Python's standard-library `urllib` and `json`.
- Zero heavy third-party framework dependencies (no React, Celery, Redis, DRF, or Docker).
