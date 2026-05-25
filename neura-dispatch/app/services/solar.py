from __future__ import annotations

import csv
import math
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

CYPRUS_TZ = ZoneInfo("Asia/Nicosia")

PV_SYSTEM_KWP = 200.0
INTERVALS_PER_HOUR = 4
HOURS_PER_WEEK = 7 * 24
POINTS_PER_WEEK = HOURS_PER_WEEK * INTERVALS_PER_HOUR


@dataclass(frozen=True)
class SolarSeries:
    values_kw: list[float]
    source_label: str


def load_hourly_solar_from_renewables_ninja_csv(csv_path: Path) -> list[float]:
    """
    Load hourly PV production from a renewables.ninja CSV export.

    Expected common renewables.ninja shape:
        time,electricity

    This parser is intentionally tolerant because CSV exports can include metadata
    rows or slightly different timestamp column names.

    Assumption:
        The electricity column is interpreted as AC power in kW for the configured
        200 kWp PV system.
    """
    if not csv_path.exists():
        raise FileNotFoundError(f"Solar CSV not found: {csv_path}")

    lines = csv_path.read_text(encoding="utf-8").splitlines()
    header_index = _find_csv_header_index(lines)

    if header_index is None:
        raise ValueError(
            "Could not find a CSV header containing a time column and a solar value column."
        )

    relevant_lines = lines[header_index:]
    reader = csv.DictReader(relevant_lines)

    if reader.fieldnames is None:
        raise ValueError("CSV file has no header row.")

    timestamp_column = _find_column(
        reader.fieldnames,
        candidates=("time", "datetime", "timestamp", "date", "local_time"),
    )
    value_column = _find_column(
        reader.fieldnames,
        candidates=("electricity", "solar_kw", "pv_kw", "generation_kw", "power"),
    )

    if timestamp_column is None:
        raise ValueError(f"Could not find timestamp column in {reader.fieldnames}")

    if value_column is None:
        raise ValueError(f"Could not find solar value column in {reader.fieldnames}")

    parsed_rows: list[tuple[datetime, float]] = []

    for row in reader:
        raw_timestamp = row.get(timestamp_column)
        raw_value = row.get(value_column)

        if not raw_timestamp or raw_value in (None, ""):
            continue

        timestamp = _parse_timestamp(raw_timestamp)
        value_kw = max(0.0, min(float(raw_value), PV_SYSTEM_KWP))

        parsed_rows.append((timestamp, value_kw))

    if not parsed_rows:
        raise ValueError(f"No usable solar rows found in {csv_path}")

    parsed_rows.sort(key=lambda item: item[0])

    return [value_kw for _, value_kw in parsed_rows]


def resample_hourly_to_15min_step(hourly_kw: list[float]) -> list[float]:
    """
    Convert hourly solar power to 15-minute power values.

    Resampling choice:
        Repeat each hourly kW value for four 15-minute intervals.

    Why:
        renewables.ninja hourly output is treated as an hourly average power value.
        Repeating it preserves hourly energy exactly:
            hourly_kw * 1 hour
        equals:
            hourly_kw * 0.25 hour * 4
    """
    if len(hourly_kw) < HOURS_PER_WEEK:
        raise ValueError(
            f"Need at least {HOURS_PER_WEEK} hourly solar values, got {len(hourly_kw)}"
        )

    values_15min: list[float] = []

    for value_kw in hourly_kw[:HOURS_PER_WEEK]:
        values_15min.extend([round(value_kw, 3)] * INTERVALS_PER_HOUR)

    return values_15min[:POINTS_PER_WEEK]


def fallback_solar_15min_kw(timestamps: list[datetime]) -> list[float]:
    """
    Deterministic fallback PV profile.

    This is not a replacement for renewables.ninja. It exists so the project can
    run locally without an API token or committed CSV file.

    Shape:
    - zero at night
    - smooth summer PV curve
    - peak below 200 kW due to inverter/weather/temperature losses
    - mild deterministic day-to-day cloud variation
    """
    values: list[float] = []

    for timestamp in timestamps:
        hour = timestamp.hour + timestamp.minute / 60.0
        day_index = timestamp.weekday()

        sunrise = 5.45
        sunset = 20.10

        if hour < sunrise or hour > sunset:
            values.append(0.0)
            continue

        daylight_fraction = (hour - sunrise) / (sunset - sunrise)
        solar_shape = math.sin(math.pi * daylight_fraction)

        # Hot Cyprus summer roof: do not expect 200 kW AC continuously.
        temperature_and_inverter_derate = 0.88

        # Deterministic cloud factor. Slightly weaker midweek, stronger weekend.
        cloud_factor = 0.92 + 0.06 * math.sin((day_index + 1) * 1.7)

        value_kw = (
            PV_SYSTEM_KWP
            * temperature_and_inverter_derate
            * cloud_factor
            * max(0.0, solar_shape) ** 1.35
        )

        values.append(round(max(0.0, min(value_kw, PV_SYSTEM_KWP)), 3))

    return values


def get_solar_15min_series(
    timestamps: list[datetime],
    csv_path: Path | None = None,
) -> SolarSeries:
    """
    Return 15-minute solar values for the representative week.

    Priority:
    1. If csv_path exists, load renewables.ninja hourly CSV and resample to 15 min.
    2. Otherwise, use deterministic fallback profile.
    """
    if csv_path is not None and csv_path.exists():
        hourly_kw = load_hourly_solar_from_renewables_ninja_csv(csv_path)
        return SolarSeries(
            values_kw=resample_hourly_to_15min_step(hourly_kw),
            source_label=f"renewables.ninja CSV: {csv_path}",
        )

    return SolarSeries(
        values_kw=fallback_solar_15min_kw(timestamps),
        source_label="deterministic fallback solar profile",
    )


def _find_csv_header_index(lines: list[str]) -> int | None:
    for index, line in enumerate(lines):
        lower = line.lower()
        if "time" in lower and (
            "electricity" in lower
            or "solar" in lower
            or "pv" in lower
            or "power" in lower
        ):
            return index

    return None


def _find_column(fieldnames: list[str], candidates: tuple[str, ...]) -> str | None:
    normalized = {field.strip().lower(): field for field in fieldnames}

    for candidate in candidates:
        if candidate in normalized:
            return normalized[candidate]

    return None


def _parse_timestamp(raw_timestamp: str) -> datetime:
    cleaned = raw_timestamp.strip().replace("Z", "+00:00")

    try:
        parsed = datetime.fromisoformat(cleaned)
    except ValueError:
        parsed = datetime.strptime(cleaned, "%Y-%m-%d %H:%M:%S")

    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=CYPRUS_TZ)

    return parsed.astimezone(CYPRUS_TZ)