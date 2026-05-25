from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

from django.test import TestCase

from app.models import DispatchInterval, TimeSeriesPoint
from app.services.reporting import ReportUnavailableError, get_weekly_report

CYPRUS_TZ = ZoneInfo("Asia/Nicosia")


class WeeklyReportingTests(TestCase):
    def test_report_unavailable_when_no_dispatch_rows_exist(self):
        with self.assertRaises(ReportUnavailableError):
            get_weekly_report()

    def test_weekly_report_calculates_financial_and_energy_metrics(self):
        first_point = TimeSeriesPoint.objects.create(
            timestamp=datetime(2025, 7, 7, 12, 0, tzinfo=CYPRUS_TZ),
            solar_kw=100.0,
            load_kw=80.0,
            grid_price_eur_per_kwh=0.30,
        )
        second_point = TimeSeriesPoint.objects.create(
            timestamp=datetime(2025, 7, 7, 12, 15, tzinfo=CYPRUS_TZ),
            solar_kw=0.0,
            load_kw=100.0,
            grid_price_eur_per_kwh=0.30,
        )

        DispatchInterval.objects.create(
            point=first_point,
            solar_to_load_kw=80.0,
            battery_charge_kw=20.0,
            battery_discharge_kw=0.0,
            grid_import_kw=0.0,
            curtailed_solar_kw=0.0,
            soc_kwh=205.0,
            soc_pct=51.25,
        )
        DispatchInterval.objects.create(
            point=second_point,
            solar_to_load_kw=0.0,
            battery_charge_kw=0.0,
            battery_discharge_kw=50.0,
            grid_import_kw=50.0,
            curtailed_solar_kw=0.0,
            soc_kwh=190.0,
            soc_pct=47.5,
        )

        report = get_weekly_report()

        # With battery:
        # interval 1 grid = 0 kWh
        # interval 2 grid = 50 kW * 0.25 h = 12.5 kWh
        # spend = 12.5 * 0.30 = 3.75 EUR
        self.assertEqual(report.grid_spend_with_battery_eur, 3.75)

        # Without battery:
        # interval 1: load 80 kW, solar 100 kW -> grid 0 kWh
        # interval 2: load 100 kW, solar 0 kW -> grid 25 kWh
        # spend = 25 * 0.30 = 7.50 EUR
        self.assertEqual(report.grid_spend_without_battery_eur, 7.50)

        self.assertEqual(report.savings_eur, 3.75)

        # Charged/discharged are AC-side kW values converted to kWh.
        self.assertEqual(report.total_battery_charged_kwh, 5.0)
        self.assertEqual(report.total_battery_discharged_kwh, 12.5)

        # Solar total:
        # 100 kW * 0.25 h = 25 kWh
        self.assertEqual(report.total_solar_kwh, 25.0)

        # No curtailment in this small fixture.
        self.assertEqual(report.curtailed_solar_kwh, 0.0)
        self.assertEqual(report.solar_self_consumption_pct, 100.0)

        self.assertEqual(len(report.labels), 2)
        self.assertEqual(len(report.soc_pct_series), 2)
        self.assertEqual(len(report.dispatch_rows), 2)