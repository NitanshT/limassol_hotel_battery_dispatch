from __future__ import annotations

from dataclasses import dataclass

from app.models import TimeSeriesPoint
from app.services.dispatch import BatteryConfig, DispatchInput, run_greedy_dispatch


BASELINE_PV_KWP = 200.0
BASELINE_BATTERY_KWH = 400.0
BASELINE_BATTERY_KW = 200.0
INTERVAL_HOURS = 0.25


class WhatIfUnavailableError(RuntimeError):
    pass


@dataclass(frozen=True)
class WhatIfInputs:
    pv_kwp: float
    battery_kwh: float


@dataclass(frozen=True)
class WhatIfResult:
    pv_kwp: float
    battery_kwh: float
    battery_power_kw: float
    grid_spend_with_battery_eur: float
    grid_spend_without_battery_eur: float
    savings_eur: float
    total_battery_charged_kwh: float
    total_battery_discharged_kwh: float
    total_solar_kwh: float
    curtailed_solar_kwh: float
    solar_self_consumption_pct: float
    final_soc_pct: float


def run_what_if_scenario(inputs: WhatIfInputs) -> WhatIfResult:
    """
    Run an in-memory what-if scenario using the stored representative week.

    PV scaling:
        Stored solar profile is treated as the 200 kWp baseline.
        New solar_kw = stored solar_kw * (pv_kwp / 200)

    Battery scaling:
        Capacity is user-controlled.
        Power scales with the same C-rate as the baseline battery:
            400 kWh / 200 kW = 2-hour battery
            max power = battery_kwh / 2

    This keeps the form small while avoiding unrealistic cases where a tiny
    battery has the original 200 kW inverter.
    """
    _validate_inputs(inputs)

    points = list(TimeSeriesPoint.objects.order_by("timestamp"))

    if not points:
        raise WhatIfUnavailableError(
            "No input time-series rows found. Run `python manage.py bootstrap_demo --force --with-dispatch` first."
        )

    pv_scale = inputs.pv_kwp / BASELINE_PV_KWP
    battery_power_kw = inputs.battery_kwh / 2.0

    dispatch_inputs = [
        DispatchInput(
            timestamp=point.timestamp,
            solar_kw=point.solar_kw * pv_scale,
            load_kw=point.load_kw,
            price_eur_per_kwh=point.grid_price_eur_per_kwh,
        )
        for point in points
    ]

    config = BatteryConfig(
        capacity_kwh=inputs.battery_kwh,
        max_charge_kw=battery_power_kw,
        max_discharge_kw=battery_power_kw,
        min_soc_pct=10.0,
        max_soc_pct=95.0,
        initial_soc_pct=10.0,
    )

    results = run_greedy_dispatch(dispatch_inputs, config=config)

    grid_spend_with_battery_eur = 0.0
    grid_spend_without_battery_eur = 0.0
    total_battery_charged_kwh = 0.0
    total_battery_discharged_kwh = 0.0
    total_solar_kwh = 0.0
    curtailed_solar_kwh = 0.0

    for result in results:
        solar_kwh = result.solar_kw * INTERVAL_HOURS
        load_kwh = result.load_kw * INTERVAL_HOURS

        grid_import_with_battery_kwh = result.grid_import_kw * INTERVAL_HOURS
        grid_import_without_battery_kwh = max(0.0, load_kwh - solar_kwh)

        grid_spend_with_battery_eur += (
            grid_import_with_battery_kwh * result.price_eur_per_kwh
        )
        grid_spend_without_battery_eur += (
            grid_import_without_battery_kwh * result.price_eur_per_kwh
        )

        total_battery_charged_kwh += result.battery_charge_kw * INTERVAL_HOURS
        total_battery_discharged_kwh += result.battery_discharge_kw * INTERVAL_HOURS
        total_solar_kwh += solar_kwh
        curtailed_solar_kwh += result.curtailed_solar_kw * INTERVAL_HOURS

    solar_self_consumption_pct = (
        ((total_solar_kwh - curtailed_solar_kwh) / total_solar_kwh) * 100.0
        if total_solar_kwh > 0
        else 0.0
    )

    savings_eur = grid_spend_without_battery_eur - grid_spend_with_battery_eur
    final_soc_pct = results[-1].soc_pct if results else 0.0

    return WhatIfResult(
        pv_kwp=round(inputs.pv_kwp, 1),
        battery_kwh=round(inputs.battery_kwh, 1),
        battery_power_kw=round(battery_power_kw, 1),
        grid_spend_with_battery_eur=round(grid_spend_with_battery_eur, 2),
        grid_spend_without_battery_eur=round(grid_spend_without_battery_eur, 2),
        savings_eur=round(savings_eur, 2),
        total_battery_charged_kwh=round(total_battery_charged_kwh, 1),
        total_battery_discharged_kwh=round(total_battery_discharged_kwh, 1),
        total_solar_kwh=round(total_solar_kwh, 1),
        curtailed_solar_kwh=round(curtailed_solar_kwh, 1),
        solar_self_consumption_pct=round(solar_self_consumption_pct, 1),
        final_soc_pct=round(final_soc_pct, 1),
    )


def run_default_comparison_scenarios() -> list[WhatIfResult]:
    """
    Small fixed comparison table for the report page.

    This gives reviewers immediate signal without requiring them to type values.
    """
    scenarios = [
        WhatIfInputs(pv_kwp=150.0, battery_kwh=300.0),
        WhatIfInputs(pv_kwp=200.0, battery_kwh=400.0),
        WhatIfInputs(pv_kwp=250.0, battery_kwh=500.0),
        WhatIfInputs(pv_kwp=300.0, battery_kwh=600.0),
    ]

    return [run_what_if_scenario(scenario) for scenario in scenarios]


def _validate_inputs(inputs: WhatIfInputs) -> None:
    if inputs.pv_kwp <= 0:
        raise ValueError("PV size must be positive.")

    if inputs.battery_kwh <= 0:
        raise ValueError("Battery capacity must be positive.")

    if inputs.pv_kwp > 1000:
        raise ValueError("PV size is too large for this simple what-if form.")

    if inputs.battery_kwh > 2000:
        raise ValueError("Battery capacity is too large for this simple what-if form.")