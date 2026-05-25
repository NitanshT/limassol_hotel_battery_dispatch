from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

from django.test import TestCase
from django.urls import reverse

from app.models import TimeSeriesPoint
from app.services.what_if import (
    WhatIfInputs,
    WhatIfUnavailableError,
    run_what_if_scenario,
)

CYPRUS_TZ = ZoneInfo("Asia/Nicosia")


class WhatIfServiceTests(TestCase):
    def test_what_if_requires_input_timeseries(self):
        with self.assertRaises(WhatIfUnavailableError):
            run_what_if_scenario(WhatIfInputs(pv_kwp=200.0, battery_kwh=400.0))

    def test_what_if_runs_against_stored_timeseries(self):
        TimeSeriesPoint.objects.create(
            timestamp=datetime(2025, 7, 7, 12, 0, tzinfo=CYPRUS_TZ),
            solar_kw=200.0,
            load_kw=50.0,
            grid_price_eur_per_kwh=0.30,
        )
        TimeSeriesPoint.objects.create(
            timestamp=datetime(2025, 7, 7, 12, 15, tzinfo=CYPRUS_TZ),
            solar_kw=0.0,
            load_kw=100.0,
            grid_price_eur_per_kwh=0.30,
        )

        result = run_what_if_scenario(
            WhatIfInputs(
                pv_kwp=200.0,
                battery_kwh=400.0,
            )
        )

        self.assertEqual(result.pv_kwp, 200.0)
        self.assertEqual(result.battery_kwh, 400.0)
        self.assertEqual(result.battery_power_kw, 200.0)
        self.assertGreaterEqual(result.savings_eur, 0.0)
        self.assertGreater(result.total_battery_charged_kwh, 0.0)


class WhatIfViewTests(TestCase):
    def test_what_if_view_returns_200_without_data(self):
        response = self.client.get(reverse("what-if-report"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "What-if analysis unavailable")