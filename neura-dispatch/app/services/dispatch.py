from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import datetime

from app.services.tariff import is_day_rate


@dataclass(frozen=True)
class BatteryConfig:
    """
    Battery parameters for the Limassol hotel scenario.

    Efficiency convention:
        The round-trip efficiency is split symmetrically:

            charge_efficiency = sqrt(round_trip_efficiency)
            discharge_efficiency = sqrt(round_trip_efficiency)

        This means all charge/discharge kW values are AC-side values, while SoC
        is tracked as internal battery energy.

    Example:
        round_trip_efficiency = 0.88
        charge_efficiency ~= 0.938
        discharge_efficiency ~= 0.938
    """

    capacity_kwh: float = 400.0
    max_charge_kw: float = 200.0
    max_discharge_kw: float = 200.0

    min_soc_pct: float = 10.0
    max_soc_pct: float = 95.0
    initial_soc_pct: float = 10.0

    round_trip_efficiency: float = 0.88
    interval_hours: float = 0.25

    @property
    def charge_efficiency(self) -> float:
        return math.sqrt(self.round_trip_efficiency)

    @property
    def discharge_efficiency(self) -> float:
        return math.sqrt(self.round_trip_efficiency)

    @property
    def min_soc_kwh(self) -> float:
        return self.capacity_kwh * self.min_soc_pct / 100.0

    @property
    def max_soc_kwh(self) -> float:
        return self.capacity_kwh * self.max_soc_pct / 100.0

    @property
    def initial_soc_kwh(self) -> float:
        return self.capacity_kwh * self.initial_soc_pct / 100.0


@dataclass(frozen=True)
class DispatchInput:
    timestamp: datetime
    solar_kw: float
    load_kw: float
    price_eur_per_kwh: float


@dataclass(frozen=True)
class DispatchResult:
    timestamp: datetime
    solar_kw: float
    load_kw: float
    price_eur_per_kwh: float

    solar_to_load_kw: float
    battery_charge_kw: float
    battery_discharge_kw: float
    grid_import_kw: float
    curtailed_solar_kw: float

    soc_kwh: float
    soc_pct: float


def run_greedy_dispatch(
    rows: list[DispatchInput],
    config: BatteryConfig | None = None,
) -> list[DispatchResult]:
    """
    Run a simple behind-the-meter greedy dispatch policy.

    Policy:
    1. Use solar to serve load first.
    2. If there is surplus solar, charge the battery subject to power and SoC limits.
    3. If remaining load exists and the tariff is day-rate, discharge the battery.
    4. Import whatever remains from the grid.
    5. Never export to the grid.
    6. Curtail surplus solar that cannot be used or stored.

    This is intentionally not an optimizer. It is the right level of complexity for
    a 2-3 hour take-home: explainable, deterministic, and easy to test.
    """
    cfg = config or BatteryConfig()

    if cfg.interval_hours <= 0:
        raise ValueError("interval_hours must be positive")

    if cfg.capacity_kwh <= 0:
        raise ValueError("capacity_kwh must be positive")

    if not 0 <= cfg.min_soc_pct <= cfg.initial_soc_pct <= cfg.max_soc_pct <= 100:
        raise ValueError(
            "Expected SoC percentages to satisfy: "
            "0 <= min_soc_pct <= initial_soc_pct <= max_soc_pct <= 100"
        )

    if not 0 < cfg.round_trip_efficiency <= 1:
        raise ValueError("round_trip_efficiency must be in the interval (0, 1]")

    interval_hours = cfg.interval_hours
    soc_kwh = cfg.initial_soc_kwh

    results: list[DispatchResult] = []

    for row in rows:
        if row.solar_kw < 0 or row.load_kw < 0 or row.price_eur_per_kwh < 0:
            raise ValueError("Dispatch inputs must be non-negative")

        # 1. Solar serves load first.
        solar_to_load_kw = min(row.solar_kw, row.load_kw)

        remaining_load_kwh = max(0.0, row.load_kw - solar_to_load_kw) * interval_hours
        surplus_solar_kwh = max(0.0, row.solar_kw - solar_to_load_kw) * interval_hours

        # 2. Charge from surplus solar only.
        available_soc_room_kwh = max(0.0, cfg.max_soc_kwh - soc_kwh)

        max_charge_ac_kwh_by_power = cfg.max_charge_kw * interval_hours
        max_charge_ac_kwh_by_soc = (
            available_soc_room_kwh / cfg.charge_efficiency
            if cfg.charge_efficiency > 0
            else 0.0
        )

        charge_ac_kwh = min(
            surplus_solar_kwh,
            max_charge_ac_kwh_by_power,
            max_charge_ac_kwh_by_soc,
        )

        soc_kwh += charge_ac_kwh * cfg.charge_efficiency

        curtailed_solar_kwh = max(0.0, surplus_solar_kwh - charge_ac_kwh)

        # 3. Discharge only during expensive/day-rate periods.
        discharge_ac_kwh = 0.0

        if remaining_load_kwh > 0 and is_day_rate(row.price_eur_per_kwh):
            available_internal_energy_kwh = max(0.0, soc_kwh - cfg.min_soc_kwh)

            max_discharge_ac_kwh_by_power = cfg.max_discharge_kw * interval_hours
            max_discharge_ac_kwh_by_soc = (
                available_internal_energy_kwh * cfg.discharge_efficiency
            )

            discharge_ac_kwh = min(
                remaining_load_kwh,
                max_discharge_ac_kwh_by_power,
                max_discharge_ac_kwh_by_soc,
            )

            soc_kwh -= discharge_ac_kwh / cfg.discharge_efficiency

        # 4. Grid supplies whatever remains.
        grid_import_kwh = max(0.0, remaining_load_kwh - discharge_ac_kwh)

        # Numerical guardrail against tiny floating point drift.
        soc_kwh = min(max(soc_kwh, cfg.min_soc_kwh), cfg.max_soc_kwh)

        results.append(
            DispatchResult(
                timestamp=row.timestamp,
                solar_kw=round(row.solar_kw, 6),
                load_kw=round(row.load_kw, 6),
                price_eur_per_kwh=round(row.price_eur_per_kwh, 6),
                solar_to_load_kw=round(solar_to_load_kw, 6),
                battery_charge_kw=round(charge_ac_kwh / interval_hours, 6),
                battery_discharge_kw=round(discharge_ac_kwh / interval_hours, 6),
                grid_import_kw=round(grid_import_kwh / interval_hours, 6),
                curtailed_solar_kw=round(curtailed_solar_kwh / interval_hours, 6),
                soc_kwh=round(soc_kwh, 6),
                soc_pct=round((soc_kwh / cfg.capacity_kwh) * 100.0, 6),
            )
        )

    return results