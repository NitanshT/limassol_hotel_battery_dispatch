# Limassol Hotel Battery Dispatch

Small Django service for a behind-the-meter battery dispatch scenario for a Cyprus hotel.

The project models one representative week for a hotel in Limassol with:

- 200 kWp rooftop PV
- 400 kWh / 200 kW LFP battery
- 15-minute dispatch intervals
- stylised two-rate electricity tariff
- SQLite persistence
- Django weekly report at `/reports/weekly/`

The goal is to estimate weekly battery savings, show the dispatch schedule, and generate a simple financier-facing weekly report.

---

## What the app does

The app creates and stores one representative 15-minute week of:

- `solar_kw`
- `load_kw`
- `grid_price_eur_per_kwh`

It then runs a greedy battery dispatch policy and stores one dispatch row per interval.

The report shows:

- grid spend with battery
- grid spend without battery
- weekly savings
- total battery charged kWh
- total battery discharged kWh
- solar self-consumption percentage
- total solar generation
- curtailed solar
- battery SoC curve
- scrollable 15-minute dispatch schedule

---

## Local setup on Windows PowerShell

Create and activate a virtual environment:

```powershell
py -3.14 -m venv .venv
.\.venv\Scripts\Activate.ps1
```

Install dependencies:

```powershell
pip install -r requirements.txt
```

Run database migrations:

```powershell
python manage.py migrate
```

Create demo data and run dispatch:

```powershell
python manage.py bootstrap_demo --force --with-dispatch
```

Start the development server:

```powershell
python manage.py runserver
```

Open:

```text
http://127.0.0.1:8000/reports/weekly/
```

---

## Local setup on macOS/Linux

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python manage.py migrate
python manage.py bootstrap_demo --force --with-dispatch
python manage.py runserver
```

Then open:

```text
http://127.0.0.1:8000/reports/weekly/
```

---

## One-command project check

After setup, this should pass:

```powershell
python manage.py check
python manage.py test
python manage.py bootstrap_demo --force --with-dispatch
```

Expected shape:

```text
System check identified no issues
...
OK
...
Demo time series bootstrap complete.
Rows: 672
Dispatch run complete.
Dispatch rows: 672
```

---

## Architecture

The app intentionally keeps Django views thin.

```text
app/
├── models.py
├── views.py
├── urls.py
├── services/
│   ├── load_profile.py
│   ├── tariff.py
│   ├── solar.py
│   ├── dispatch.py
│   ├── data_import.py
│   └── reporting.py
├── management/
│   └── commands/
│       ├── bootstrap_demo.py
│       └── run_dispatch.py
└── tests/
    ├── test_dispatch.py
    ├── test_reporting.py
    └── test_views.py
```

Responsibilities:

| Layer | Responsibility |
|---|---|
| `models.py` | SQLite persistence for input time series and dispatch outputs |
| `load_profile.py` | deterministic synthetic hotel load |
| `tariff.py` | two-rate time-of-use tariff |
| `solar.py` | renewables.ninja CSV parsing, hourly-to-15-minute resampling, fallback solar |
| `dispatch.py` | pure greedy battery dispatch policy |
| `data_import.py` | database bootstrap and dispatch persistence |
| `reporting.py` | weekly financial and energy metrics |
| `views.py` | HTTP rendering only |

This separation keeps business logic out of Django views and makes the dispatch policy testable without the database.

---

## Data model

The app uses two main tables.

### `TimeSeriesPoint`

One row per 15-minute input interval.

Fields:

- `timestamp`
- `solar_kw`
- `load_kw`
- `grid_price_eur_per_kwh`

The three input series are stored together because dispatch and reporting always consume them together. For this take-home, that is simpler and more pragmatic than three separate time-series tables.

### `DispatchInterval`

One row per 15-minute dispatch result.

Fields:

- `solar_to_load_kw`
- `battery_charge_kw`
- `battery_discharge_kw`
- `grid_import_kw`
- `curtailed_solar_kw`
- `soc_kwh`
- `soc_pct`

Dispatch rows are derived data. They can be deleted and regenerated from `TimeSeriesPoint`.

---

## Representative week

The representative week starts on:

```text
Monday 2025-07-07 00:00 Asia/Nicosia
```

It contains:

```text
7 days × 24 hours × 4 intervals/hour = 672 rows
```

July was selected because the scenario is a Cyprus hotel with hot-afternoon cooling peaks.

---

## Load profile assumptions

There is no clean public 15-minute load dataset for a Cyprus hotel, so the hotel load is synthetic and deterministic.

The generated load includes:

- non-zero baseload from rooms, pumps, refrigeration, kitchen prep, lighting, and common areas
- lower overnight demand
- breakfast activity bump
- housekeeping/laundry bump around late morning
- hot afternoon cooling spike
- dinner/evening guest activity
- slightly higher weekend activity
- deterministic noise using a fixed random seed
- final scaling so the weekly peak is approximately 200 kW

The default generated profile has:

```text
672 points
weekly peak: 200 kW
```

This is intentionally not a full building simulation. It is a defensible synthetic profile for a short take-home assignment.

---

## Solar data

The intended solar source is renewables.ninja hourly PV data for Limassol using a 200 kWp PV system.

Expected CSV path:

```text
data/renewables_ninja_limassol_hourly.csv
```

Expected common CSV columns:

```text
time,electricity
```

The app parses the hourly CSV and resamples to 15-minute intervals by repeating each hourly average value four times.

This preserves hourly energy:

```text
hourly_kw × 1 hour = hourly_kw × 0.25 hour × 4
```

If the CSV is not present, the app uses a deterministic fallback solar profile so the reviewer can run the project locally without an API token or committed data file.

The fallback is only a run-local convenience. In a production or final analytical workflow, the renewables.ninja CSV should be used.

---

## Tariff

The tariff is a stylised two-rate time-of-use tariff:

| Period | Time | Price |
|---|---:|---:|
| Day | 09:00–23:00 | €0.30/kWh |
| Night | 23:00–09:00 | €0.15/kWh |

The tariff is implemented in:

```text
app/services/tariff.py
```

Timestamps are handled in Cyprus local time:

```text
Asia/Nicosia
```

---

## Battery assumptions

| Parameter | Value |
|---|---:|
| Capacity | 400 kWh |
| Max charge power | 200 kW |
| Max discharge power | 200 kW |
| Minimum SoC | 10% |
| Maximum SoC | 95% |
| Initial SoC | 50% |
| Round-trip efficiency | 88% |
| Dispatch interval | 15 minutes |

Efficiency convention:

```text
charge_efficiency = sqrt(0.88)
discharge_efficiency = sqrt(0.88)
```

This keeps charge and discharge values as AC-side kW while tracking SoC as internal battery energy.

---

## Dispatch policy

The dispatch policy is intentionally greedy and explainable.

For each 15-minute interval:

1. Solar serves hotel load first.
2. Surplus solar charges the battery if there is available SoC room.
3. If load remains and the tariff is day-rate, the battery discharges.
4. Remaining load is imported from the grid.
5. Solar that cannot be used or stored is curtailed.
6. Grid export is not allowed.

This is not a mathematical optimizer. That is intentional. For this take-home, the priority is a working, defensible, testable dispatch slice rather than a full linear-programming-based energy management system.

---

## Weekly report

The weekly report is available at:

```text
http://127.0.0.1:8000/reports/weekly/
```

The view delegates metric calculation to:

```text
app/services/reporting.py
```

The no-battery counterfactual assumes:

- same hotel load
- same PV generation
- solar still serves load first
- no grid export
- surplus solar is curtailed
- no battery charge/discharge

Savings are calculated as:

```text
grid spend without battery - grid spend with battery
```

Solar self-consumption is calculated as:

```text
(total solar generation - curtailed solar) / total solar generation
```

---

## Management commands

Create input data only:

```powershell
python manage.py bootstrap_demo --force
```

Create input data and dispatch results:

```powershell
python manage.py bootstrap_demo --force --with-dispatch
```

Run dispatch against existing input data:

```powershell
python manage.py run_dispatch
```

Use a specific renewables.ninja CSV:

```powershell
python manage.py bootstrap_demo --force --with-dispatch --solar-csv data\renewables_ninja_limassol_hourly.csv
```

---

## Tests

Run:

```powershell
python manage.py test
```

The tests focus on high-signal business logic:

- dispatch respects SoC limits
- dispatch respects charge/discharge power limits
- dispatch does not discharge during night-rate periods
- dispatch charges from surplus solar
- dispatch rejects invalid negative inputs
- reporting calculates grid spend, savings, charged/discharged energy, and solar self-consumption correctly
- weekly report route returns a useful unavailable-state page if dispatch has not been generated

The tests intentionally avoid over-testing HTML styling or Chart.js behavior.

---

## Dependencies

The project intentionally keeps dependencies minimal:

```text
Django
requests
```

Chart.js is loaded from CDN in the report template.

SQLite is used because it is sufficient for a local take-home submission and requires no extra services.

---

## Known tradeoffs

### Greedy dispatch instead of optimization

A greedy policy is easier to explain and test in a short take-home. A production system would likely use an optimization approach with forecasts, tariff windows, degradation costs, and operational constraints.

### Fallback solar profile

The fallback profile exists so the app runs locally without external credentials. The intended analytical source is renewables.ninja hourly data.

### Single representative week

The project models one representative summer week. A production system would ingest continuous measured data and produce rolling reports.

### Simplified tariff

The tariff is a stylised two-rate tariff. A production version should support real commercial tariff components, demand charges, VAT, fixed charges, and site-specific contract details.

### No battery degradation model

The dispatch does not account for cycle degradation or warranty constraints. That is acceptable for this slice but important in production.

---

## What I would build next

With another day, I would add:

1. Real renewables.ninja CSV committed to the repo or reproducible API pull instructions.
2. A what-if form to vary PV size, battery capacity, and tariff assumptions.
3. A real EAC commercial tariff parser or manually encoded commercial tariff.
4. Exportable weekly PDF report.
5. Battery degradation cost per kWh cycled.
6. Forecast-aware dispatch rather than purely greedy dispatch.
7. Basic validation charts for solar, load, grid import, and curtailment.
8. Admin action or UI button to regenerate demo data and dispatch.
9. Separate service-level tests for solar resampling and tariff boundaries.
10. Clear comparison of savings under fallback solar versus renewables.ninja data.

---

## AI usage

AI was used as a senior-engineering accelerator for:

- project decomposition
- Django scaffold planning
- service-layer design
- synthetic load shaping
- dispatch algorithm drafting
- README wording
- test case selection

I kept the architecture intentionally lean and reviewed the outputs against the take-home requirements. The main value of AI here was speed: turning the brief into a working, documented, testable slice while still making explicit engineering tradeoffs.

---

## Submission notes

This project is intentionally scoped to the requested 2–3 hour take-home.

It prioritizes:

- working local setup
- clear assumptions
- stored input data
- dispatch outside views
- simple report
- meaningful tests
- readable code

It does not try to look like an enterprise platform. That is deliberate.