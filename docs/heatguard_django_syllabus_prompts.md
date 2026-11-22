# HeatGuard — Django Syllabus-Aligned Project Blueprint and Agentic Coding Prompts

## Project title
**HeatGuard: Extreme Heatwave Early Warning and Human Thermal Stress Monitoring System**

## Purpose of this document
This document contains a practical project definition and a sequential set of ready-to-copy prompts for an AI coding agent such as Cursor Agent, Claude Code, or Windsurf. The project is deliberately designed around the supplied Django syllabus. The coding agent must not introduce frameworks or advanced infrastructure that are outside that syllabus.

---

# Part 1 — Revised project idea

## 1.1 Project overview

HeatGuard is a Django-based web application that helps users understand current heat conditions, view short-term weather forecasts, estimate heat-related discomfort using temperature and relative humidity, and access heat-safety guidance. It also provides a simple administrative workflow for publishing and managing official heat-related notices.

A user can search for a city, view its available weather information, see an explainable heat-index estimate and risk category, review upcoming forecast conditions, and read practical precautions. Logged-in users can save locations and review their own recent searches. Authorized staff can manage location records and publish official notices through protected Django views and the Django admin site.

The application is intended as an educational and public-information tool. It is not an official meteorological warning authority, a medical diagnosis system, or a certified occupational heat-stress instrument.

## 1.2 What the project should answer

1. What are the current reported weather conditions for a selected city?
2. How do temperature and relative humidity combine to affect apparent temperature?
3. What heat-risk category does the application's documented screening rule assign?
4. What do the available hourly and daily forecasts suggest for the next few days?
5. Are there official notices entered by an authorized administrator for this location?
6. What sensible heat-safety precautions should a member of the public consider?
7. How have the weather records saved by this application changed over time?

## 1.3 Scope and scientific wording

Use the phrase **“Heat Index-based Heat Stress Estimate”** in the interface and documentation. The project title can retain “Human Thermal Stress Index,” but explain that the implemented indicator is an estimate based on air temperature and relative humidity.

Do not call the estimate WBGT. Do not claim that the application measures a person's body temperature, diagnoses heat illness, or calculates a certified workplace exposure limit. The Heat Index calculation is a shade-oriented apparent-temperature estimate and does not fully account for direct solar radiation, clothing, workload, acclimatization, or individual health conditions. Refer to the National Weather Service methodology when implementing the Rothfusz calculation: https://www.wpc.ncep.noaa.gov/html/heatindex_equation.shtml

Keep three different concepts visibly separate:

- **Weather provider data:** current-condition and forecast values returned by the selected provider. Display provider, units, and retrieval time.
- **Application estimate:** the Heat Index and risk category calculated by HeatGuard from provider values. Label it as an estimate.
- **Official notice:** a notice manually entered or verified by an authorized staff member, with its issuing organization, source link, issue time, and validity period. Never imply that an application-generated estimate is an official government warning.

The initial provider can be Open-Meteo. Its forecast documentation describes current, hourly, and daily weather variables, including temperature and relative humidity: https://open-meteo.com/en/docs

## 1.4 Main user journeys

### Public visitor
1. Opens the home page.
2. Enters a city name in a Django search form.
3. Sees matching locations or a clear validation message.
4. Opens the city's monitoring page.
5. Reviews current weather, the Heat Index-based estimate, forecast information, and safety guidance.
6. Checks whether an official notice is listed for that location.

### Registered user
1. Registers or logs in using Django authentication.
2. Searches for a city.
3. Saves a location to a personal list.
4. Views saved locations and recent searches.
5. Logs out securely.

### Authorized staff member
1. Logs in using a staff account.
2. Opens a protected notice-management page.
3. Creates or updates an official notice using a validated Django ModelForm.
4. Provides source organization, source URL, issue time, and validity dates.
5. Uses Django admin to manage locations, records, notices, and users where appropriate.

## 1.5 Recommended feature scope

### Core features — implement first

- Professional home page explaining the platform and its limitations.
- City search using a Django GET form.
- City name and coordinate lookup through a simple weather/geocoding provider integration.
- Current weather display.
- Hourly and daily forecast display when the provider returns those fields.
- Heat Index-based estimate using temperature and relative humidity.
- Clearly explained risk category and public safety suggestions.
- Recent weather records saved in the database.
- Location-specific official notice listing.
- Django admin registration for project models.
- Registration, login, logout, sessions, and protected views.
- Forms with server-side validation and CSRF protection.
- Error, loading, empty, and no-data states.
- Tests for views, forms, models, and the calculation function.

### Useful features — add after the core works

- Save and remove favourite locations.
- Recent search history for logged-in users.
- Compare two or three cities in a simple table.
- Staff-managed official heat notices.
- Date-filtered history of records collected by this application.
- CSV download of the application's saved records, only if time permits and the instructor approves this small Python standard-library addition.
- Staff dashboard showing counts of saved locations, records, and active notices.

### Features deliberately excluded from the syllabus-aligned build

Do not add React, Vue, Angular, Next.js, Django REST Framework, GraphQL, FastAPI, PostgreSQL/PostGIS, Redis, Celery, Docker, Kubernetes, microservices, machine learning, deep learning, satellite image processing, GIS heat layers, real-time WebSockets, complex notification gateways, or a third-party charting framework.

Do not build a complicated multi-tenant government command centre. A Django staff dashboard, tables, filters, and the Django admin site are sufficient for this version.

An interactive map can be considered only as an optional extension after the syllabus-aligned application is complete and the instructor approves additional JavaScript or mapping-library work. The core version should use city search, location cards, and comparison tables instead.

## 1.6 Recommended technology stack

| Area | Use | Reason |
|---|---|---|
| Language | Python | Required for Django and calculation logic |
| Backend | Django | Directly covers the course syllabus |
| Frontend | HTML, CSS, small amounts of vanilla JavaScript | Keeps rendering inside Django templates |
| Templates | Django Template Language (DTL) | Covers variables, tags, loops, conditions, and inheritance |
| Forms | Django Forms and ModelForms | Covers GET, POST, validation, and CSRF |
| Database | SQLite | Default Django database; straightforward for coursework |
| Data access | Django ORM | Covers create, read, update, delete, and ForeignKey relationships |
| User accounts | Django built-in authentication | Covers users, login, logout, groups, and permissions |
| Administration | Django admin | Covers staff data management |
| Weather source | Open-Meteo through Python standard-library `urllib` and `json` | Provides real weather data without adding an API framework or API SDK |
| Tests | Django test framework and Python `unittest` assertions | Covers debugging and testing in the syllabus |

Use a currently supported Python and Django version compatible with the lab environment. Do not install packages just because an AI agent prefers them. Before adding any package, explain why it is required and verify that it does not take the project outside the syllabus.

---

# Part 2 — Simple Django architecture

## 2.1 Suggested project structure

Use one Django project and one main Django app to keep the coursework understandable. A separate accounts app is not required; use Django's built-in authentication views and the main app's templates.

```text
heatguard_project/
│
├── manage.py
├── requirements.txt
├── README.md
│
├── heatguard_project/
│   ├── __init__.py
│   ├── settings.py
│   ├── urls.py
│   ├── asgi.py
│   └── wsgi.py
│
├── monitoring/
│   ├── migrations/
│   ├── templates/
│   │   └── monitoring/
│   │       ├── base.html
│   │       ├── home.html
│   │       ├── dashboard.html
│   │       ├── forecast.html
│   │       ├── compare.html
│   │       ├── history.html
│   │       ├── notices.html
│   │       ├── login.html
│   │       ├── register.html
│   │       ├── profile.html
│   │       ├── notice_form.html
│   │       ├── 400.html
│   │       ├── 403.html
│   │       ├── 404.html
│   │       └── 500.html
│   ├── static/
│   │   └── monitoring/
│   │       ├── css/
│   │       │   └── style.css
│   │       └── js/
│   │           └── main.js
│   ├── __init__.py
│   ├── admin.py
│   ├── apps.py
│   ├── forms.py
│   ├── models.py
│   ├── tests.py
│   ├── urls.py
│   ├── views.py
│   ├── weather_service.py
│   └── heat_index.py
│
└── db.sqlite3
```

The agent may adjust filenames slightly if that makes the implementation clearer, but it must explain the change and preserve a simple structure. Do not create unnecessary layers, packages, or apps.

## 2.2 Suggested database models

Keep the database small and explainable.

### Location

- `name`
- `state_or_region`
- `country`
- `latitude`
- `longitude`
- `created_at`

### WeatherRecord

- ForeignKey to `Location`
- Optional nullable ForeignKey to Django User named `requested_by` (use `SET_NULL`; anonymous provider searches may have no user)
- `recorded_at`
- `record_type` (for example, current or forecast; do not mix them without labelling)
- `temperature_c`
- `relative_humidity`
- `feels_like_c` if supplied by the provider
- `wind_speed`
- `heat_index_c` (calculated by HeatGuard where valid)
- `risk_level`
- `data_source`
- `retrieved_at`

Store only real provider data or clearly identified user-entered values. Never seed invented live readings. If sample fixtures are needed for testing, label them as test data and keep them out of the normal live dashboard.

### OfficialNotice

- ForeignKey to `Location` (allow a documented all-locations option only if implemented simply)
- `title`
- `message`
- `severity`
- `issuing_organization`
- `source_url`
- `issued_at`
- `valid_from`
- `valid_until`
- `created_by` ForeignKey to Django User
- `created_at`
- `is_published`

### SavedLocation (optional core extension)

- ForeignKey to Django User
- ForeignKey to `Location`
- `created_at`

Add a uniqueness rule so that the same user cannot save the same location twice.

Use Django migrations for all schema changes. Do not edit the SQLite database directly.

## 2.3 URL plan

Use normal Django URL patterns and named routes. Suggested routes:

| URL | View | Method / purpose |
|---|---|---|
| `/` | `home` | Landing page |
| `/search/` | `search_city` | GET city search |
| `/city/<int:location_id>/` | `city_dashboard` | City dashboard |
| `/forecast/<int:location_id>/` | `city_forecast` | Forecast view |
| `/compare/` | `compare_cities` | GET comparison form and results |
| `/history/` | `weather_history` | Logged-in user's history |
| `/notices/` | `notice_list` | Published notices |
| `/notices/create/` | `notice_create` | Staff-only POST form |
| `/accounts/register/` | `register` | Registration |
| `/accounts/login/` | Django login view | Login |
| `/accounts/logout/` | Django logout view | Logout |
| `/saved/` | `saved_locations` | Logged-in user's saved locations |

The agent can add detail or edit routes when needed, but must document every route and its access rule.

---

# Part 3 — Shared instruction to give the coding agent

Paste this instruction before starting the prompts below. It applies to every phase.

```text
You are my Django development assistant. Build HeatGuard according to the supplied Django course syllabus and the project specification.

STRICT SYLLABUS LIMIT:
Use Python, Django, Django project/app structure, function-based views, URL routing, HTTP GET/POST, Django templates and DTL, template inheritance, Django forms and ModelForms, CSRF protection, redirects, Django models, migrations, ORM, ForeignKey relationships, Django admin, built-in users, groups, permissions, cookies, sessions, login, logout, debugging, and Django tests.

Use SQLite, HTML, CSS, and only small amounts of vanilla JavaScript. Use Python's standard-library urllib and json for the optional real weather-provider request. Do not introduce React, Vue, Angular, Django REST Framework, FastAPI, GraphQL, PostgreSQL, PostGIS, Redis, Celery, Docker, Kubernetes, microservices, machine learning, WebSockets, or third-party chart/map frameworks.

Do not generate fake live weather, fake official warnings, fake station observations, or fake historical climate data. Clearly label data as provider-supplied, user-entered, application-calculated, test-only, or officially published. A failed weather request must show an honest error state, not fabricated fallback values.

Keep the Heat Index calculation distinct from WBGT. Describe it as an estimate based on temperature and relative humidity. Document the formula source, units, applicability, and limitations. Do not claim that this educational project is an official warning service or medical diagnostic tool.

Work only on the phase requested in the current prompt. First inspect the current repository and summarize relevant files. Then implement that phase. Do not silently rewrite unrelated files. Preserve working functionality. After implementation, run the appropriate Django checks and tests, report the exact commands and results, list changed files, and identify any limitations.

Do not proceed to the next phase automatically. Stop and wait for my review. If a requirement is ambiguous, choose the simplest syllabus-compliant interpretation and state the assumption instead of adding advanced technology.

Write beginner-readable code with clear names and comments where helpful. Prefer simple function-based views over advanced abstractions. Avoid overengineering.
```

---

# Part 4 — Sequential ready-to-copy coding prompts

Execute these prompts one at a time. Review the result and test it before moving to the next prompt.

## Prompt 0 — Confirm requirements and prepare the Django-only architecture

```text
Before writing any code, inspect the repository (or confirm that it is empty) and prepare a concise implementation plan for HeatGuard.

The application is a Django-based Extreme Heatwave Early Warning and Human Thermal Stress Monitoring System. It must stay within this syllabus: Django setup and apps; views and URLs; HTTP requests and responses; templates and DTL; template inheritance; forms; GET and POST; validation; CSRF; redirects; models and migrations; ORM and ForeignKey; Django admin; users, groups and permissions; cookies and sessions; login/logout; debugging and testing.

Use one Django project, one main app named monitoring, SQLite, function-based views, Django templates, HTML/CSS, and minimal vanilla JavaScript. Weather data may be retrieved from Open-Meteo through Python's standard-library urllib and json. No React, DRF, third-party API framework, GIS package, chart package, background-job system, or production infrastructure stack.

Prepare:
1. A simple architecture description.
2. A folder structure.
3. A small database model proposal: Location, WeatherRecord, OfficialNotice, and optionally SavedLocation.
4. A named URL list with the intended view and access rule.
5. A list of public, registered-user, and staff features.
6. A phase-by-phase implementation plan that maps directly to the syllabus.
7. A list of out-of-scope technologies that you will not introduce.

Do not create or modify code in this phase. Identify any requirement that needs an explicit assumption. Wait for approval.
```

## Prompt 1 — Install Django and create the project and app

```text
Initialize the HeatGuard Django project using the approved architecture.

Tasks:
1. Check the installed Python version and whether a virtual environment exists.
2. Create or use a virtual environment and install a compatible supported Django release.
3. Create a Django project named heatguard_project.
4. Create one Django app named monitoring.
5. Add monitoring to INSTALLED_APPS.
6. Keep SQLite as the database.
7. Configure basic template and static-file settings correctly.
8. Create the initial monitoring URL configuration and include it in the project URL configuration.
9. Create a simple home view and a placeholder home template so that the app runs.
10. Keep settings readable and suitable for a classroom project. Do not add Docker, environment-management libraries, or deployment packages.

Deliverables:
- Working project and app structure.
- requirements.txt containing only the required dependency or dependencies.
- Initial README with setup and run commands.

Verification:
- Run `python manage.py check`.
- Run `python manage.py migrate`.
- Run `python manage.py runserver` and verify the home page loads.
- Explain the role of manage.py, settings.py, project urls.py, app urls.py, views.py, and apps.py.

Do not build the full UI yet. Stop after verification.
```

## Prompt 2 — Implement views, URLs, HTTP requests, responses, and error handling

```text
Implement the basic navigation and function-based views for HeatGuard using Django views and URL patterns.

Create named routes and simple placeholder pages for:
- Home
- City search
- City dashboard
- Forecast
- City comparison
- Notice list
- Login and registration placeholders (Django authentication integration will be completed later)

Requirements:
1. Use function-based views.
2. Use `render()` for HTML responses and `redirect()` where appropriate.
3. Demonstrate a simple URL parameter using an integer location ID for the city dashboard.
4. Use named URL patterns and Django's `reverse` or `{% url %}` rather than hardcoding internal links.
5. Return an appropriate 404 response when a requested location does not exist.
6. Add a clear 400-style response or form error for malformed search input.
7. Do not place database or external API logic in this phase.
8. Keep view functions short and beginner-readable.

Deliverables:
- monitoring/urls.py and updated project urls.py.
- Placeholder function-based views.
- Simple templates sufficient to verify routing.
- A route table in README.

Verification:
- Test every route in the browser.
- Test a valid and invalid location ID.
- Run `python manage.py check`.
- Add basic Django tests verifying that the home and placeholder pages return the expected HTTP status.

Stop after verification.
```

## Prompt 3 — Build the base template and reusable DTL layout

```text
Create the shared frontend structure using Django templates and Django Template Language only.

Design direction:
- Product name: HeatGuard.
- Visual identity: professional environmental monitoring platform.
- Use a calm deep-navy/charcoal base with restrained orange, amber, and red risk accents, plus readable neutral backgrounds.
- Avoid excessive gradients, glowing cards, distracting animations, oversized empty hero areas, and generic AI dashboard decoration.
- Use semantic HTML, responsive CSS, accessible contrast, and clear typography.

Tasks:
1. Create `base.html` with the page shell, header, navigation, main content block, footer, and static CSS inclusion.
2. Create reusable navigation links for Home, Monitor, Forecast, Compare, Notices, and account actions.
3. Use DTL template inheritance with `{% extends %}` and `{% block %}`.
4. Demonstrate DTL variables, `if/else`, loops, and URL tags with simple page data.
5. Add CSS for buttons, form fields, cards, tables, badges, alert panels, and responsive layout.
6. Add a consistent risk-color system: low, moderate, high, very high, and extreme. Do not assign scientific meaning to thresholds in this phase.
7. Include reusable UI patterns for loading, error, empty, and no-data states.
8. Do not add a frontend framework or charting library.

Deliverables:
- base.html.
- static CSS file.
- Any small reusable partial templates that genuinely reduce duplication.
- Updated placeholder pages using template inheritance.

Verification:
- Check that navigation works.
- Inspect desktop and mobile widths.
- Confirm that static CSS loads.
- Confirm that child templates extend the base template.
- Run Django checks.

Stop after verification.
```

## Prompt 4 — Create the professional landing page

```text
Build the public HeatGuard landing page using Django templates, DTL, and CSS.

The landing page should explain the product in plain language and guide visitors to monitor a city.

Sections:
1. Header with HeatGuard identity and clear navigation.
2. Hero section with the heading “Understand Heat. Prepare Earlier.” and a city-search form.
3. Short explanation of current conditions, forecast-based estimates, and official notices.
4. Feature cards: City Monitoring, Heat Index Estimate, Forecast Outlook, Safety Guidance, and Official Notices.
5. “How it works” section showing the flow from weather data to an application estimate and guidance.
6. A clear methodology disclaimer: HeatGuard is an educational information tool; its estimate is not a medical diagnosis or official government declaration.
7. Data-source attribution area.
8. Footer with About, Methodology, and Data Sources links.

Functional requirements:
- The search form submits to the named city-search URL using GET.
- Validate that the city input is not blank.
- Preserve the user's entered city if validation fails.
- Use real navigation links, not decorative buttons.
- Do not display fake current temperature, fake warning counts, fake user counts, or fake live statistics on the landing page.

Deliverables:
- Complete landing page template.
- Updated home view and search form markup.
- Responsive styling.

Acceptance criteria:
- A visitor understands what the application does within a few seconds.
- The search form works.
- Every navigation link points to a real route or a clearly marked section.
- The disclaimer and data-source attribution are visible.
- The page works on mobile and desktop.

Stop after verification.
```

## Prompt 5 — Create models, migrations, ORM operations, and Django admin

```text
Implement the initial database layer using Django models, migrations, ORM, ForeignKey relationships, and Django admin.

Create these models unless the approved architecture contains a justified simpler alternative:

1. Location:
   - name, state_or_region, country
   - latitude and longitude (decimal fields with sensible validation)
   - created_at
   - a readable `__str__` method

2. WeatherRecord:
   - ForeignKey to Location
   - Optional nullable ForeignKey to Django User named requested_by (use SET_NULL; anonymous searches may have no user)
   - recorded_at and retrieved_at
   - record_type (current or forecast)
   - temperature_c and relative_humidity
   - optional provider apparent temperature and wind speed
   - calculated heat_index_c, where valid
   - risk_level
   - data_source
   - created_at
   - sensible ordering and readable `__str__`

3. OfficialNotice:
   - ForeignKey to Location
   - title, message, severity
   - issuing_organization and source_url
   - issued_at, valid_from, valid_until
   - created_by ForeignKey to Django User
   - created_at and is_published
   - validate that valid_until is later than valid_from

4. SavedLocation (optional, if it can be implemented simply):
   - ForeignKey to Django User
   - ForeignKey to Location
   - created_at
   - unique constraint for user and location

Tasks:
- Add the models in monitoring/models.py.
- Create and apply migrations.
- Register relevant models in monitoring/admin.py.
- Add useful list displays, search fields, filters, and date hierarchy in admin where appropriate.
- Use Django ORM for all data operations.
- Do not use raw SQL or edit the SQLite database manually.

Demonstrate in the README or a short notes file how to use Django shell for create, read, update, and delete operations.

Testing:
- Test model creation and string representations.
- Test ForeignKey relationships.
- Test important validation and uniqueness rules.
- Run `makemigrations`, `migrate`, `python manage.py check`, and the tests.

Do not create fake weather records as normal production seed data. Test fixtures must be clearly identified as test-only.

Stop after verification.
```

## Prompt 6 — Implement city search with Django Forms, GET, validation, and redirects

```text
Implement a proper city-search workflow using Django Forms and HTTP GET.

Requirements:
1. Create a CitySearchForm in monitoring/forms.py.
2. Include a required city field with whitespace trimming and reasonable maximum length.
3. Use GET for a read-only city search.
4. Validate blank, too-short, and excessively long input.
5. Show field-level errors in the template.
6. Preserve the submitted value after validation errors.
7. After a valid city lookup, redirect to or render the matching city dashboard using a named URL.
8. Avoid putting business logic directly into the template.
9. If the same city is searched with different capitalization or surrounding spaces, normalize it before lookup.
10. Show a clear “location not found” message if no result is available.

If the weather/geocoding provider has not yet been integrated, create a temporary clearly labelled placeholder lookup function that will be replaced in Prompt 7. Do not invent coordinates or weather values.

Deliverables:
- CitySearchForm.
- Updated search view and URL.
- Search result or validation template state.
- Django tests for valid, blank, and invalid search input.

Verification:
- Test using browser and Django test client.
- Confirm the request uses GET.
- Confirm invalid input never triggers an external request.
- Run Django checks and tests.

Stop after verification.
```

## Prompt 7 — Integrate real weather and geocoding data

```text
Integrate a real weather provider into HeatGuard while keeping the implementation inside the Django syllabus.

Use Open-Meteo as the initial provider. Read its current official documentation before selecting endpoint parameters:
- Forecast documentation: https://open-meteo.com/en/docs
- Geocoding documentation: https://open-meteo.com/en/docs/geocoding-api

Implementation constraints:
- Use Python standard-library `urllib.request`, `urllib.parse`, `json`, and exception handling.
- Do not install an API SDK, Django REST Framework, Celery, Redis, or another service framework.
- Keep provider requests in a small module named `weather_service.py`, not scattered across templates or views.

Tasks:
1. Implement a function that searches the provider's geocoding endpoint for a city name.
2. Parse the returned location name, region/country, latitude, and longitude safely.
3. Implement a function that requests current, hourly, and daily forecast variables needed by the project, including temperature and relative humidity where available.
4. Request metric units and the appropriate local timezone supported by the API.
5. Add a short, explicit network timeout.
6. Handle invalid city, no results, HTTP errors, timeouts, malformed JSON, missing keys, and unexpected response structures.
7. Return a consistent Python dictionary or a simple documented result structure to the Django view.
8. Never return invented weather values when a provider call fails.
9. Display source attribution, the provider retrieval time, and the provider's data/model context where documented.
10. Do not label provider model output as a direct observation from a physical weather station unless the provider explicitly identifies it as such.

When a city is successfully resolved, create or reuse its Location record with normalized identifying fields. Avoid duplicates for the same city/coordinates using a sensible lookup strategy.

Testing:
- Mock the provider response in Django tests; do not depend on a live internet connection for automated tests.
- Test successful geocoding and forecast parsing.
- Test no-result, timeout, HTTP error, invalid JSON, and missing-field cases.
- Verify that an API failure produces an honest user-facing error state.

Deliverables:
- weather_service.py.
- Updated search workflow.
- Provider attribution in the relevant template.
- Tests for provider parsing and failures.

Stop after verification.
```

## Prompt 8 — Implement the Heat Index and risk classification

```text
Implement the HeatGuard Heat Index calculation as a small, independently testable Python module.

Important terminology:
- The implemented measure is a Heat Index-based apparent-temperature estimate.
- It is not WBGT and must not be labelled as a certified Human Thermal Stress measurement.
- The interface may call the overall section “Human Thermal Stress Assessment” only if it clearly states “Heat Index-based estimate.”

Methodology:
1. Use temperature and relative humidity from the provider.
2. Implement the National Weather Service Heat Index method, including the preliminary/simple calculation and the Rothfusz regression and applicable humidity adjustments as described in the official methodology: https://www.wpc.ncep.noaa.gov/html/heatindex_equation.shtml
3. Convert Celsius inputs to Fahrenheit for the published equation and convert the final result back to Celsius for display/storage.
4. Validate temperature and humidity ranges and handle missing inputs.
5. Follow the published method's applicability conditions. Where the regression is not appropriate, use the documented preliminary method or mark the estimate as unavailable; do not force a misleading value.
6. Keep the calculation separate from the risk category mapping.
7. Put risk category boundaries in one clearly documented configuration/constants location. Do not claim that generic Heat Index bands are Indian IMD heatwave declaration criteria. State that the project screening bands are educational and should be reviewed against locally approved guidance before real operational use.
8. Return the calculated value, display unit, risk category, and a short explanation.

Add unit tests for:
- Typical lower-heat conditions.
- High temperature and high humidity.
- Low-humidity adjustment conditions.
- High-humidity adjustment conditions.
- Boundary and invalid inputs.
- Celsius/Fahrenheit conversion consistency.

Update the methodology page or section to explain assumptions and limitations in plain language.

Do not modify the formula or thresholds merely to make a dashboard look more dramatic.

Stop after the tests pass.
```

## Prompt 9 — Build the city monitoring dashboard

```text
Build the working city monitoring dashboard using the data returned by the weather service and the Heat Index module.

The dashboard should include:
1. City name, region, country, and last retrieved time.
2. Current temperature.
3. Relative humidity.
4. Provider apparent temperature if available.
5. Wind speed if available.
6. Heat Index-based estimate.
7. Risk category with text and color, not color alone.
8. A short explanation of why the category was assigned.
9. A safety-guidance summary.
10. A link to the detailed forecast.
11. A section showing relevant published official notices, if any.
12. Visible source attribution and disclaimer.

Requirements:
- Use Django templates and DTL loops/conditions.
- Use responsive cards and simple CSS layout.
- Use proper units: °C, %, and provider-specified wind units.
- Do not show zero as a substitute for missing data.
- Display “Not available” when a provider field is absent.
- Display a clear error panel if the live provider request fails.
- Save a WeatherRecord only after a valid provider response. Avoid saving duplicate records repeatedly during one request.
- Set `requested_by` to the authenticated user when available; leave it null for anonymous searches.
- Make clear whether a value is provider-supplied or calculated by HeatGuard.

Testing:
- Test dashboard response for valid location data.
- Test missing optional provider fields.
- Test provider failure.
- Test that the stored record belongs to the correct Location.

Stop after verification.
```

## Prompt 10 — Add hourly and daily forecast with forecast-based heat assessment

```text
Build the forecast page using the hourly and daily forecast arrays returned by Open-Meteo.

Requirements:
1. Display a readable next-24-hour forecast table or compact hourly cards.
2. Display a daily forecast table for the provider's available forecast period (normally seven days unless the request specifies otherwise).
3. Include date/time, temperature, relative humidity when available, and relevant weather details.
4. Calculate a Heat Index-based estimate for forecast hours only when the required inputs are present and within the method's applicability.
5. Identify the hottest forecast hours and days using actual returned forecast values.
6. Display a “Forecast-based heat-risk outlook” label.
7. Never describe the generated outlook as an official heatwave declaration.
8. Clearly show forecast issue/retrieval time, timezone, units, and provider.
9. Explain missing or unavailable forecast data without inserting fake values.
10. Use DTL loops and conditions to render the data.

Do not add a JavaScript chart library. If a visual summary is useful, build a simple accessible CSS bar display from the actual forecast values, with a table or text alternative. Do not create a visual for missing data.

Tests:
- Verify hourly and daily arrays render.
- Verify missing humidity does not produce a Heat Index value.
- Verify dates and times use the requested location's timezone.
- Verify forecast wording is distinct from official notices.

Stop after verification.
```

## Prompt 11 — Add heat-risk notices and a staff notice workflow

```text
Implement two clearly separated types of information:

A. Application-generated forecast advisory
- Generated from provider forecast values and the project's documented screening categories.
- Must be labelled “HeatGuard forecast-based advisory.”
- Must never be represented as an official government alert.

B. Official notice
- Entered or verified by an authorized staff member.
- Must include issuing organization, source URL, issue time, validity period, location, severity, and message.
- Must be labelled “Official notice” only when the staff workflow has required source details.

Tasks:
1. Create or complete OfficialNotice model and validation.
2. Create a ModelForm for notice creation/editing.
3. Create staff-protected function-based views.
4. Use login and permission checks; do not rely on hiding a button in the template as security.
5. Accept POST for create/update and use CSRF protection.
6. Use POST-redirect-GET after successful save.
7. Add a public notice list and location-specific notices on the city dashboard.
8. Show active, upcoming, and expired status based on validity dates.
9. Add an empty state when no official notices exist.
10. Register OfficialNotice in Django admin.

Testing:
- Anonymous user cannot create a notice.
- Normal authenticated user without the required permission cannot create a notice.
- Authorized staff can create and edit a notice.
- Invalid validity dates are rejected.
- Unpublished notices are not shown publicly.
- Expired notices are clearly labelled and not shown as active.

Do not scrape official bulletins or invent notices. Use source links and entries supplied by staff.

Stop after verification.
```

## Prompt 12 — Add public safety recommendations

```text
Create a practical safety-guidance section based on the application's risk categories.

Requirements:
1. Create a small, maintainable Python data structure or simple model-backed table for general recommendations.
2. Provide clear advice on hydration, shade, rest, reducing strenuous outdoor activity during hot periods, checking vulnerable people, and recognizing possible heat-illness warning signs.
3. Use cautious, non-diagnostic wording.
4. Do not personalize medical advice or claim to replace local health authorities.
5. Show the recommendations relevant to the current risk category on the city dashboard and forecast page.
6. Add a general safety page with guidance for outdoor workers, older adults, children, and people who may be more vulnerable to heat.
7. Include a clear message to seek urgent local medical help for suspected severe heat illness.
8. Add links to reliable official public-health guidance. Do not copy large sections of external content.

Testing:
- Each risk category displays the intended guidance.
- Missing/unknown risk does not display a falsely reassuring message.
- All safety text remains readable on mobile.

Stop after verification.
```

## Prompt 13 — Implement Django authentication, registration, login, and logout

```text
Implement user management using Django's built-in authentication system.

Requirements:
1. Use Django's built-in User model unless there is a strong syllabus-compliant reason not to.
2. Implement registration with Django's UserCreationForm or a small subclass.
3. Implement login using Django's authentication views or the standard authenticate/login functions.
4. Implement logout using Django's supported logout flow.
5. Configure named login and logout URLs.
6. Use session-based authentication.
7. Protect the user's history and saved-location views with login_required.
8. Show clear login errors and success messages.
9. Redirect users appropriately after login and logout.
10. Do not store plain-text passwords or create a custom password system.
11. Use CSRF protection on every state-changing form.

Templates:
- register.html
- login.html
- profile.html or account page

Testing:
- Registration success and duplicate username handling.
- Invalid password handling.
- Login success/failure.
- Logout clears the authenticated session.
- Protected page redirects anonymous users to login.

Explain how Django stores authentication state in the session.

Stop after verification.
```

## Prompt 14 — Add groups, permissions, user sessions, saved locations, and search history

```text
Complete the role and session features using Django's built-in groups, permissions, cookies, and sessions.

Roles:
- Public visitor: can search and view public weather information and published notices.
- Registered user: can save locations and view their own recent search/history pages.
- Staff/authority: can manage official notices and access the simple staff summary page.

Tasks:
1. Use Django Groups and permissions for staff capabilities. Document the required group and permission setup.
2. Do not treat a user's submitted role field as authorization.
3. Add SavedLocation if it has not already been created.
4. Ensure a user can add and remove only their own saved locations.
5. Store a small amount of non-sensitive recent-search information in the session for anonymous visitors if useful.
6. For logged-in users, store persistent search/record relationships through the database where appropriate.
7. Use cookies only for appropriate non-sensitive preferences, such as display unit, if implemented.
8. Never put passwords, secrets, or sensitive personal information in cookies or session values.
9. Set sensible session and cookie options supported by Django settings.
10. Show role-appropriate navigation without relying on the template for authorization.

Testing:
- Users cannot access another user's saved locations.
- Anonymous users cannot access private history.
- Non-staff users cannot create official notices.
- Staff permissions work as expected.
- Session history behaves correctly and does not contain sensitive data.

Stop after verification.
```

## Prompt 15 — Add city comparison and simple monitoring summary

```text
Create a city comparison feature using ordinary Django forms, views, ORM, and templates.

Requirements:
1. Allow the user to select two or three existing Location records or search for city names using the existing weather-service functions.
2. Fetch real provider data for selected cities, with timeouts and proper error handling.
3. Compare temperature, humidity, Heat Index-based estimate, and risk category in a responsive HTML table.
4. Show each city's provider retrieval time and source.
5. Clearly identify unavailable data; do not omit a failed city silently.
6. Do not build a GIS map or use a third-party visualization library.
7. Add a staff-only summary page showing factual database counts, such as total locations, number of stored weather records, and number of currently published notices.
8. Do not label database counts as live population exposure or real-world affected people.

Testing:
- Two-city and three-city comparison.
- Invalid location IDs.
- Partial provider failure.
- Staff-only summary access.
- Empty database state.

Stop after verification.
```

## Prompt 16 — Add historical records and simple analytics

```text
Implement a modest historical monitoring page using only records actually stored by HeatGuard.

Important:
This page is an application record history, not a complete historical climate archive. Do not imply that records collected since deployment represent long-term local climate history. Do not fill missing dates with fabricated values.

Requirements:
1. Query WeatherRecord through the Django ORM.
2. Provide simple filters for location and date range using a Django GET form.
3. Show recorded temperature, humidity, calculated Heat Index, risk category, record type, source, and timestamp.
4. Add simple summary values calculated from the filtered records, such as highest recorded value in the selected saved records and number of records.
5. Add a simple CSS-based visual summary only if it uses actual records and has an accessible table/text alternative.
6. Make clear whether records are current provider responses or forecast records.
7. Restrict a personal history view to the logged-in user's own activity if the design stores user ownership. Public/shared system history must be clearly distinguished.

Tests:
- Date and location filtering.
- Empty history state.
- Records from different locations do not get mixed.
- User privacy rules are enforced.
- Summary calculations use only filtered database records.

Stop after verification.
```

## Prompt 17 — Add a useful staff dashboard and improve Django admin

```text
Create a simple staff dashboard using Django views, ORM queries, templates, groups, and permissions.

The dashboard is for managing the application's data, not a simulated government command centre.

Show:
- Total locations stored.
- Total WeatherRecord entries.
- Number of published active notices.
- Recently added notices.
- Recently stored weather records.
- Links to manage locations, notices, and records through protected pages or Django admin.

Requirements:
1. Restrict the page to authorized staff.
2. Calculate all counts using Django ORM.
3. Use clear labels and a timestamp for the summary.
4. Do not display fake impact estimates, exposed-population counts, hospital capacity, or emergency response statistics.
5. Improve Django admin list_display, search_fields, list_filter, date_hierarchy, and ordering for the models.
6. Ensure only appropriate staff can change or delete records.

Testing:
- Access rules for anonymous, regular, and staff users.
- Correct database counts.
- Empty database state.

Stop after verification.
```

## Prompt 18 — Add optional CSV export using the standard library

```text
If the instructor approves a small export utility, add CSV export for the user's permitted WeatherRecord history. Otherwise, skip this prompt and document the feature as out of scope.

Requirements:
1. Use a Django function-based view and Python's built-in csv module.
2. Require login for a user's private history export, or use a staff permission for a system-wide export.
3. Query records through Django ORM.
4. Include column headers, units, source, record type, and timestamp.
5. Respect location and date filters.
6. Set a correct CSV content type and a safe download filename.
7. Prevent users from exporting another user's private records.
8. Do not export passwords, session values, or unnecessary personal information.

Testing:
- Correct CSV headers and values.
- Empty export behavior.
- Access control.
- Filters are respected.

Stop after verification.
```

## Prompt 19 — Debugging, Django tests, and end-to-end verification

```text
Perform a structured debugging and testing pass using Django's built-in testing tools.

Do not add a new testing framework unless the instructor explicitly approves it.

Create or complete tests for:
1. Home page and URL routing.
2. URL parameters and invalid IDs.
3. CitySearchForm validation.
4. Model creation, ForeignKey relations, and constraints.
5. Weather provider response parsing using mocked responses.
6. Provider timeout, HTTP error, and invalid JSON handling.
7. Heat Index calculation and edge cases.
8. Dashboard display for available and missing values.
9. Forecast rendering and time labels.
10. Notice creation, publication, expiration, and permissions.
11. Registration, login, logout, and protected views.
12. Saved-location ownership and session behavior.
13. History filters and export permissions if export exists.

Also:
- Run `python manage.py check`.
- Run `python manage.py makemigrations --check --dry-run`.
- Run `python manage.py test`.
- Review terminal errors and Django logs.
- Fix root causes rather than hiding errors with broad exception handling.
- Check browser pages for missing templates, static files, broken links, CSRF failures, and incorrect redirects.

Produce a test summary with passed/failed counts and any known limitations. Do not claim a test passed unless it was actually run.

Stop after verification.
```

## Prompt 20 — Security, code quality, and syllabus compliance review

```text
Review the entire HeatGuard codebase for security, code quality, and strict syllabus compliance.

Security checks:
1. Ensure every state-changing form uses POST and `{% csrf_token %}`.
2. Validate all user input in Django forms or model validation.
3. Use ORM queries rather than unsafe SQL string construction.
4. Escape untrusted text in templates; do not mark provider/user text as safe without a compelling reason.
5. Protect private pages with login_required and permission checks.
6. Verify users cannot edit or delete another user's records.
7. Use Django's password hashing and authentication.
8. Ensure DEBUG is not presented as a production setting. Explain that the development server is not for production deployment.
9. Ensure secret values are not committed to source control. Keep classroom settings simple and explain how to change SECRET_KEY and ALLOWED_HOSTS before a public deployment.
10. Do not expose stack traces or internal error details to visitors.

Code quality:
- Remove unused imports, dead code, duplicate functions, and unnecessary packages.
- Keep views readable and move only genuinely reusable provider/calculation functions into their own small modules.
- Add comments for non-obvious logic.
- Check model and form validation.
- Check all links, URL names, template blocks, and static paths.

Syllabus audit:
Create a checklist mapping the implementation to each supplied syllabus unit: Django setup/apps; views/URLs; HTTP requests/responses; templates/DTL; debugging/testing; forms/GET/POST/CSRF/validation; models/migrations/ORM/ForeignKey/admin; cookies/sessions; users/authentication/login/logout.

List any feature that goes beyond the syllabus and explain whether it is optional. Do not add advanced technology during this review.

Run Django checks and tests again. Report only verified results.

Stop after verification.
```

## Prompt 21 — Final UI/UX polish and accessibility

```text
Perform a final visual and usability improvement pass without changing the technology stack or business logic unnecessarily.

Design goals:
- Professional environmental monitoring appearance.
- Consistent typography, spacing, colors, borders, buttons, and card styles.
- Calm neutral surfaces with restrained heat-risk colors.
- Clear hierarchy: city and timestamp first, current conditions second, heat assessment third, forecast and notices next, safety guidance after that.
- Responsive navigation and layouts.
- Accessible labels, keyboard focus, readable contrast, meaningful headings, and text descriptions for risk colors.
- Useful loading, error, empty, no-search-result, and no-history states.
- No fake live counters or decorative charts containing invented values.
- Avoid excessive animations, glassmorphism, glowing effects, and oversized empty sections.

Pages to review:
- Home.
- Search and validation results.
- City dashboard.
- Forecast.
- Comparison.
- Notices.
- Login and registration.
- Saved locations and history.
- Staff dashboard.
- Methodology and safety information.

Use existing HTML/CSS and minimal vanilla JavaScript only. Do not add a new UI framework or chart package.

Deliver:
- Updated styles and templates.
- A page-by-page UI review checklist.
- Any remaining accessibility or responsive limitations.

Verify at mobile, tablet, and desktop viewport sizes. Run Django checks and tests after changes.

Stop after verification.
```

## Prompt 22 — Documentation, local run instructions, and final demonstration

```text
Prepare HeatGuard for academic demonstration and handover while staying within the syllabus.

Create a clear README with:
1. Project title and purpose.
2. Feature list grouped by public user, registered user, and staff.
3. Technology stack restricted to the implemented Django syllabus.
4. Project folder structure and explanation of important files.
5. Python/Django installation and virtual-environment steps.
6. Commands to run migrations, create a superuser, and start the development server.
7. Explanation of each model and ForeignKey relationship.
8. URL/view summary.
9. Forms and validation summary.
10. Authentication, session, group, and permission summary.
11. Weather provider endpoints and attribution.
12. Heat Index method, units, source, assumptions, and limitations.
13. Explanation of the difference between provider forecast, HeatGuard estimate, and official notice.
14. Test commands and the actual test results.
15. Screenshots of the main pages (only real screenshots from the implemented project).
16. Known limitations and future improvements that do not misrepresent the current system.

Also prepare a short demonstration sequence:
- Open the home page.
- Search for a city.
- Open its monitoring dashboard.
- Explain temperature and humidity values.
- Explain the Heat Index-based estimate and why it is not WBGT.
- Review the forecast-based outlook.
- Open public safety guidance.
- Log in as a normal user and save a location.
- Log in as authorized staff and publish a sourced notice.
- Show the Django admin and relevant models.
- Show the history page and explain that it contains only records actually stored by the application.

Do not claim production readiness merely because `runserver` works. Provide a separate short note describing that a real public deployment requires production hosting, HTTPS, secure settings, database backups, and operational monitoring. Do not add Docker or cloud deployment automation as part of this syllabus-limited build.

Run the final Django checks and tests. Report exact commands, results, known issues, and the final folder structure.

Stop after documentation and verification.
```

---

# Part 5 — How to use the prompts

1. Open the project folder in Cursor, Claude Code, or Windsurf.
2. Paste the **Shared instruction** from Part 3 into the agent's project rules or the beginning of the conversation.
3. Run Prompt 0 and review the plan before permitting code changes.
4. Run one numbered prompt at a time, in order.
5. After each prompt, read the agent's changed-file list and test report. Run the commands yourself where possible.
6. Do not continue when migrations, tests, or the current page are broken. Fix the current phase first.
7. Keep a backup or Git commit after each accepted milestone.
8. If the agent suggests React, DRF, PostgreSQL, Redis, Celery, Docker, AI/ML, or another excluded technology, ask it to provide the same functionality using the approved Django features instead.

## Suggested milestones

| Milestone | Prompts | Expected result |
|---|---|---|
| Django foundation | 0–3 | Running Django project with routes and reusable templates |
| Basic application | 4–6 | Landing page, database models, admin, validated city search |
| Working monitoring | 7–10 | Real weather data, Heat Index estimate, dashboard, forecast |
| User and notice workflows | 11–14 | Notices, safety guidance, login, roles, sessions, saved cities |
| Reporting and administration | 15–18 | City comparison, application-record history, staff summary, optional CSV |
| Quality and handover | 19–22 | Tested, secured, polished, documented project |

## Final scope statement

The finished coursework version of HeatGuard should demonstrate the Django syllabus through a meaningful environmental-monitoring use case. Its strength should come from correct use of Django views, URLs, templates, forms, validation, models, ORM, migrations, admin, sessions, authentication, permissions, debugging, and testing—not from adding technologies outside the course.

A successful submission is a clean, working Django website that uses real weather-provider data where available, explains its Heat Index-based estimate honestly, distinguishes forecast advisories from sourced official notices, protects staff actions, and provides a professional user experience.
