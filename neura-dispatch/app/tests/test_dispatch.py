from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

from django.test import SimpleTestCase

from app.services.dispatch import BatteryConfig, DispatchInput, run_greedy_dispatch

CYPRUS_TZ = ZoneInfo("Asia/Nicosia")


class DispatchPolicyTests(SimpleTestCase):
    def test_soc_bounds_and_power_limits_are_respected(self):
        rows = [
            DispatchInput(
                timestamp=datetime(2025, 7, 7, 12, 0, tzinfo=CYPRUS_TZ),
                solar_kw=300.0,
                load_kw=20.0,
                price_eur_per_kwh=0.30,
            ),
            DispatchInput(
                timestamp=datetime(2025, 7, 7, 14, 0, tzinfo=CYPRUS_TZ),
                solar_kw=0.0,
                load_kw=300.0,
                price_eur_per_kwh=0.30,
            ),
        ]

        results = run_greedy_dispatch(rows)

        self.assertEqual(len(results), 2)

        for result in results:
            self.assertGreaterEqual(result.soc_pct, 10.0)
            self.assertLessEqual(result.soc_pct, 95.0)

            self.assertGreaterEqual(result.battery_charge_kw, 0.0)
            self.assertGreaterEqual(result.battery_discharge_kw, 0.0)
            self.assertGreaterEqual(result.grid_import_kw, 0.0)
            self.assertGreaterEqual(result.curtailed_solar_kw, 0.0)

            self.assertLessEqual(result.battery_charge_kw, 200.0)
            self.assertLessEqual(result.battery_discharge_kw, 200.0)

    def test_surplus_solar_charges_battery_before_curtailment(self):
        config = BatteryConfig(initial_soc_pct=10.0)

        rows = [
            DispatchInput(
                timestamp=datetime(2025, 7, 7, 12, 0, tzinfo=CYPRUS_TZ),
                solar_kw=220.0,
                load_kw=20.0,
                price_eur_per_kwh=0.30,
            )
        ]

        result = run_greedy_dispatch(rows, config=config)[0]

        self.assertEqual(result.solar_to_load_kw, 20.0)
        self.assertGreater(result.battery_charge_kw, 0.0)
        self.assertEqual(result.grid_import_kw, 0.0)
        self.assertGreater(result.soc_pct, config.initial_soc_pct)

    def test_battery_does_not_discharge_at_night_rate(self):
        config = BatteryConfig(initial_soc_pct=80.0)

        rows = [
            DispatchInput(
                timestamp=datetime(2025, 7, 7, 2, 0, tzinfo=CYPRUS_TZ),
                solar_kw=0.0,
                load_kw=100.0,
                price_eur_per_kwh=0.15,
            ),
            DispatchInput(
                timestamp=datetime(2025, 7, 7, 10, 0, tzinfo=CYPRUS_TZ),
                solar_kw=0.0,
                load_kw=100.0,
                price_eur_per_kwh=0.30,
            ),
        ]

        night_result, day_result = run_greedy_dispatch(rows, config=config)

        self.assertEqual(night_result.battery_discharge_kw, 0.0)
        self.assertEqual(night_result.grid_import_kw, 100.0)

        self.assertGreater(day_result.battery_discharge_kw, 0.0)
        self.assertLess(day_result.grid_import_kw, 100.0)

    def test_invalid_negative_inputs_are_rejected(self):
        rows = [
            DispatchInput(
                timestamp=datetime(2025, 7, 7, 12, 0, tzinfo=CYPRUS_TZ),
                solar_kw=-1.0,
                load_kw=100.0,
                price_eur_per_kwh=0.30,
            )
        ]

        with self.assertRaises(ValueError):
            run_greedy_dispatch(rows)