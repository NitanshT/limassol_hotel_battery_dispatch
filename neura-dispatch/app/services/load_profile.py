from __future__ import annotations

import math
import random
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

CYPRUS_TZ = ZoneInfo("Asia/Nicosia")

INTERVAL_MINUTES = 15
INTERVALS_PER_HOUR = 4
HOURS_PER_DAY = 24
DAYS_PER_WEEK = 7
POINTS_PER_WEEK = DAYS_PER_WEEK * HOURS_PER_DAY * INTERVALS_PER_HOUR


def representative_week_timestamps(
    start: datetime | None = None,
) -> list[datetime]:
    """
    Return one representative week of 15-minute timestamps.

    Default week:
        Monday 2025-07-07 00:00 in Cyprus local time.

    Why July:
        The take-home scenario mentions a hot summer afternoon peak. July is a
        defensible representative summer week for Limassol hotel cooling demand.
    """
    if start is None:
        start = datetime(2025, 7, 7, 0, 0, tzinfo=CYPRUS_TZ)

    return [
        start + timedelta(minutes=INTERVAL_MINUTES * index)
        for index in range(POINTS_PER_WEEK)
    ]


def _gaussian(hour: float, center: float, width: float, amplitude: float) -> float:
    """
    Smooth peak helper for shaping hotel demand.

    This keeps the synthetic profile explainable:
    - breakfast bump
    - housekeeping/laundry bump
    - afternoon cooling peak
    - evening restaurant/guest activity bump
    """
    return amplitude * math.exp(-0.5 * ((hour - center) / width) ** 2)


def generate_hotel_load_kw(
    timestamps: list[datetime],
    seed: int = 42,
    target_peak_kw: float = 200.0,
) -> list[float]:
    """
    Generate a deterministic synthetic 15-minute hotel load profile.

    Design assumptions:
    - non-zero baseload from rooms, refrigeration, pumps, lighting, kitchen prep
    - lower demand overnight
    - breakfast activity in the morning
    - housekeeping/laundry around late morning
    - strongest cooling demand in the hot afternoon
    - dinner/evening guest activity
    - weekends have slightly higher occupancy/activity
    - final profile is scaled so the weekly peak is target_peak_kw

    This is intentionally not a stochastic building simulation. It is a compact,
    defensible synthetic profile for a 2-3 hour take-home.
    """
    rng = random.Random(seed)
    raw_values: list[float] = []

    for timestamp in timestamps:
        hour = timestamp.hour + timestamp.minute / 60.0
        is_weekend = timestamp.weekday() >= 5

        baseload_kw = 72.0

        overnight_reduction_kw = -12.0 if 0 <= hour < 6 else 0.0

        breakfast_kw = _gaussian(
            hour=hour,
            center=8.0,
            width=1.1,
            amplitude=18.0,
        )

        housekeeping_laundry_kw = _gaussian(
            hour=hour,
            center=11.0,
            width=1.7,
            amplitude=12.0,
        )

        cooling_kw = _gaussian(
            hour=hour,
            center=15.75,
            width=2.6,
            amplitude=78.0,
        )

        dinner_activity_kw = _gaussian(
            hour=hour,
            center=20.0,
            width=1.8,
            amplitude=24.0,
        )

        weekend_multiplier = 1.08 if is_weekend else 1.0

        small_noise_kw = rng.uniform(-3.0, 3.0)

        load_kw = (
            baseload_kw
            + overnight_reduction_kw
            + breakfast_kw
            + housekeeping_laundry_kw
            + cooling_kw
            + dinner_activity_kw
        )

        load_kw = load_kw * weekend_multiplier + small_noise_kw

        # Keep the synthetic hotel from unrealistically dropping too low.
        raw_values.append(max(45.0, load_kw))

    if not raw_values:
        return []

    raw_peak_kw = max(raw_values)
    scale_factor = target_peak_kw / raw_peak_kw

    return [round(value * scale_factor, 3) for value in raw_values]


def generate_representative_hotel_load(
    seed: int = 42,
    target_peak_kw: float = 200.0,
) -> list[tuple[datetime, float]]:
    """
    Convenience wrapper returning timestamp/load pairs for the representative week.
    """
    timestamps = representative_week_timestamps()
    loads = generate_hotel_load_kw(
        timestamps=timestamps,
        seed=seed,
        target_peak_kw=target_peak_kw,
    )

    return list(zip(timestamps, loads, strict=True))