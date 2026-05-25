from __future__ import annotations

from app.services.load_profile import generate_representative_hotel_load
from app.services.tariff import tou_price


def preview_load_and_tariff() -> None:
    rows = generate_representative_hotel_load()

    loads = [load_kw for _, load_kw in rows]

    print(f"points: {len(rows)}")
    print(f"min load: {min(loads):.1f} kW")
    print(f"max load: {max(loads):.1f} kW")
    print(f"avg load: {sum(loads) / len(loads):.1f} kW")

    print("\nFirst 8 rows:")
    for timestamp, load_kw in rows[:8]:
        print(
            timestamp.isoformat(),
            f"load={load_kw:.1f} kW",
            f"price={tou_price(timestamp):.2f} EUR/kWh",
        )