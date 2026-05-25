# Neura Dispatch Take-Home

Small Django service for a behind-the-meter battery dispatch scenario for a Cyprus hotel.

## Scenario

A hotel in Limassol has:

- 200 kWp rooftop PV
- 400 kWh / 200 kW LFP battery
- 15-minute dispatch intervals
- stylised two-rate tariff

The goal is to estimate weekly battery savings, show the dispatch schedule, and generate a simple financier-facing weekly report.

## Current implementation status

This first commit contains:

- Django project scaffold
- SQLite-backed data models
- `/reports/weekly/` route placeholder
- Django admin registration

The dispatch, data generation, reporting service, chart, and tests are implemented in later commits.

## Local setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python manage.py migrate
python manage.py runserver

Then open:

```text
http://127.0.0.1:8000/reports/weekly/
```

## Architecture direction

The app intentionally keeps Django views thin. Energy data generation, tariff logic, dispatch logic, and reporting live in:

```text
app/services/
```

This keeps the code easy to test and avoids hiding business logic inside:

```text
views.py
```

The intended separation is:

```text
app/
├── models.py              # database models only
├── views.py               # thin HTTP rendering layer
├── services/
│   ├── load_profile.py    # synthetic hotel load generation
│   ├── tariff.py          # time-of-use tariff logic
│   ├── solar.py           # solar import and resampling
│   ├── dispatch.py        # battery dispatch policy
│   └── reporting.py       # weekly metrics and chart data
```

## Create migrations and test the scaffold

After editing the models, create and apply migrations:

```powershell
python manage.py makemigrations
python manage.py migrate
```

Run Django's project checks:

```powershell
python manage.py check
```

Start the server:

```powershell
python manage.py runserver
```

Open:

```text
http://127.0.0.1:8000/reports/weekly/
```

Expected scaffold response:

```text
Weekly report endpoint is wired. Reporting implementation comes in a later commit.
```

Stop the server with:

```text
Ctrl+C
```

## Demo data bootstrap

The project stores the required 15-minute input series in SQLite.

To create one representative week:

```powershell
python manage.py bootstrap_demo --force
```

This creates:

- `solar_kw`
- `load_kw`
- `grid_price_eur_per_kwh`

for 672 intervals:

```text
7 days × 24 hours × 4 intervals per hour = 672 rows
```

### Solar data

The preferred solar source is a renewables.ninja hourly CSV for Limassol and a 200 kWp PV system.

Expected CSV location:

```text
data/renewables_ninja_limassol_hourly.csv
```

Expected common columns:

```text
time,electricity
```

If the CSV exists, the app loads the hourly renewables.ninja values and resamples them to 15-minute intervals by repeating each hourly average power value four times.

That preserves hourly energy:

```text
hourly_kw × 1 hour = hourly_kw × 0.25 hour × 4
```

If the CSV is not present, the app uses a deterministic fallback solar profile so the reviewer can still run the project locally. The fallback is only a run-local convenience, not a replacement for renewables.ninja in the final submitted analysis.