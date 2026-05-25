from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from django.conf import settings
from django.db import transaction

from app.models import DispatchInterval, TimeSeriesPoint
from app.services.dispatch import BatteryConfig, DispatchInput, run_greedy_dispatch
from app.services.load_profile import (
    generate_hotel_load_kw,
    representative_week_timestamps,
)
from app.services.solar import get_solar_15min_series
from app.services.tariff import tou_price


@dataclass(frozen=True)
class BootstrapResult:
    time_series_points: int
    solar_source: str
    min_solar_kw: float
    max_solar_kw: float
    min_load_kw: float
    max_load_kw: float


@dataclass(frozen=True)
class DispatchPersistenceResult:
    dispatch_intervals: int
    total_grid_import_kwh: float
    total_battery_charge_kwh: float
    total_battery_discharge_kwh: float
    final_soc_pct: float


def bootstrap_demo_timeseries(
    force: bool = False,
    solar_csv_path: Path | None = None,
) -> BootstrapResult:
    """
    Populate the database with one representative 15-minute week.

    This creates the three required input series:
    - solar_kw
    - load_kw
    - grid_price_eur_per_kwh
    """
    if TimeSeriesPoint.objects.exists() and not force:
        existing = TimeSeriesPoint.objects.order_by("timestamp")
        solar_values = [row.solar_kw for row in existing]
        load_values = [row.load_kw for row in existing]

        return BootstrapResult(
            time_series_points=existing.count(),
            solar_source="existing database rows",
            min_solar_kw=min(solar_values),
            max_solar_kw=max(solar_values),
            min_load_kw=min(load_values),
            max_load_kw=max(load_values),
        )

    if solar_csv_path is None:
        solar_csv_path = (
            Path(settings.BASE_DIR)
            / "data"
            / "renewables_ninja_limassol_hourly.csv"
        )

    timestamps = representative_week_timestamps()
    solar_series = get_solar_15min_series(
        timestamps=timestamps,
        csv_path=solar_csv_path,
    )
    load_values = generate_hotel_load_kw(timestamps=timestamps)

    if len(timestamps) != len(solar_series.values_kw) or len(timestamps) != len(load_values):
        raise ValueError(
            "Generated series lengths do not match: "
            f"timestamps={len(timestamps)}, "
            f"solar={len(solar_series.values_kw)}, "
            f"load={len(load_values)}"
        )

    with transaction.atomic():
        if force:
            DispatchInterval.objects.all().delete()
            TimeSeriesPoint.objects.all().delete()

        TimeSeriesPoint.objects.bulk_create(
            [
                TimeSeriesPoint(
                    timestamp=timestamp,
                    solar_kw=solar_kw,
                    load_kw=load_kw,
                    grid_price_eur_per_kwh=tou_price(timestamp),
                )
                for timestamp, solar_kw, load_kw in zip(
                    timestamps,
                    solar_series.values_kw,
                    load_values,
                    strict=True,
                )
            ],
            batch_size=500,
        )

    return BootstrapResult(
        time_series_points=len(timestamps),
        solar_source=solar_series.source_label,
        min_solar_kw=min(solar_series.values_kw),
        max_solar_kw=max(solar_series.values_kw),
        min_load_kw=min(load_values),
        max_load_kw=max(load_values),
    )


def run_and_persist_dispatch(
    config: BatteryConfig | None = None,
) -> DispatchPersistenceResult:
    """
    Run dispatch against stored TimeSeriesPoint rows and persist DispatchInterval rows.

    Existing dispatch rows are deleted first because dispatch is derived data.
    """
    points = list(TimeSeriesPoint.objects.order_by("timestamp"))

    if not points:
        raise ValueError(
            "No TimeSeriesPoint rows found. Run `python manage.py bootstrap_demo --force` first."
        )

    dispatch_inputs = [
        DispatchInput(
            timestamp=point.timestamp,
            solar_kw=point.solar_kw,
            load_kw=point.load_kw,
            price_eur_per_kwh=point.grid_price_eur_per_kwh,
        )
        for point in points
    ]

    dispatch_results = run_greedy_dispatch(
        rows=dispatch_inputs,
        config=config or BatteryConfig(),
    )

    interval_hours = (config or BatteryConfig()).interval_hours

    with transaction.atomic():
        DispatchInterval.objects.all().delete()

        DispatchInterval.objects.bulk_create(
            [
                DispatchInterval(
                    point=point,
                    solar_to_load_kw=result.solar_to_load_kw,
                    battery_charge_kw=result.battery_charge_kw,
                    battery_discharge_kw=result.battery_discharge_kw,
                    grid_import_kw=result.grid_import_kw,
                    curtailed_solar_kw=result.curtailed_solar_kw,
                    soc_kwh=result.soc_kwh,
                    soc_pct=result.soc_pct,
                )
                for point, result in zip(points, dispatch_results, strict=True)
            ],
            batch_size=500,
        )

    total_grid_import_kwh = sum(
        result.grid_import_kw * interval_hours for result in dispatch_results
    )
    total_battery_charge_kwh = sum(
        result.battery_charge_kw * interval_hours for result in dispatch_results
    )
    total_battery_discharge_kwh = sum(
        result.battery_discharge_kw * interval_hours for result in dispatch_results
    )
    final_soc_pct = dispatch_results[-1].soc_pct if dispatch_results else 0.0

    return DispatchPersistenceResult(
        dispatch_intervals=len(dispatch_results),
        total_grid_import_kwh=round(total_grid_import_kwh, 3),
        total_battery_charge_kwh=round(total_battery_charge_kwh, 3),
        total_battery_discharge_kwh=round(total_battery_discharge_kwh, 3),
        final_soc_pct=round(final_soc_pct, 3),
    )