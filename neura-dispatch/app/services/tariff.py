from datetime import datetime

DAY_PRICE_EUR_PER_KWH = 0.30
NIGHT_PRICE_EUR_PER_KWH = 0.15

DAY_START_HOUR = 9
DAY_END_HOUR = 23


def tou_price(timestamp: datetime) -> float:
    """
    Return the stylised two-rate time-of-use tariff.

    Day rate:
        09:00 <= local time < 23:00 -> 0.30 EUR/kWh

    Night rate:
        23:00 <= local time, or local time < 09:00 -> 0.15 EUR/kWh

    The caller is responsible for passing timestamps in the intended local
    timezone. For this project, we use Asia/Nicosia for Limassol/Cyprus.
    """
    hour = timestamp.hour

    if DAY_START_HOUR <= hour < DAY_END_HOUR:
        return DAY_PRICE_EUR_PER_KWH

    return NIGHT_PRICE_EUR_PER_KWH


def is_day_rate(price_eur_per_kwh: float) -> bool:
    """
    Helper used later by dispatch.

    The dispatch policy will discharge during expensive/day-rate periods.
    Keeping this tiny function here avoids duplicating tariff thresholds inside
    dispatch logic.
    """
    return price_eur_per_kwh >= DAY_PRICE_EUR_PER_KWH