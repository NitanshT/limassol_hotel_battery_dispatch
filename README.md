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

## Run dispatch

After bootstrapping the input time series, run the greedy battery dispatch:

```powershell
python manage.py run_dispatch
```

Or create the input series and dispatch outputs in one command:

```powershell
python manage.py bootstrap_demo --force --with-dispatch
```

The dispatch results are stored in:

```text
app_dispatchinterval
```

Dispatch is derived data. It can be deleted and regenerated from the stored input series.

## Dispatch policy

The dispatch policy is intentionally greedy and explainable:

1. Solar serves hotel load first.
2. Surplus solar charges the battery if there is available SoC room.
3. If load remains and the tariff is day-rate, the battery discharges.
4. Remaining load is imported from the grid.
5. Solar that cannot be used or stored is curtailed.
6. Grid export is not allowed.

Battery assumptions:

```text
capacity: 400 kWh
max charge power: 200 kW
max discharge power: 200 kW
minimum SoC: 10%
maximum SoC: 95%
initial SoC: 50%
round-trip efficiency: 88%
interval length: 15 minutes
```

Efficiency convention:

```text
charge_efficiency = sqrt(0.88)
discharge_efficiency = sqrt(0.88)
```

This keeps charge and discharge values as AC-side kW while tracking SoC as internal battery energy.