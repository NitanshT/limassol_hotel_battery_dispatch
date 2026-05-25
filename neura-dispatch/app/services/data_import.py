from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from django.conf import settings
from django.db import transaction

from app.models import DispatchInterval, TimeSeriesPoint
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

    It does not run dispatch. Dispatch comes in the next commit.
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