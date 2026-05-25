from __future__ import annotations

from pathlib import Path

from django.core.management.base import BaseCommand

from app.services.data_pipeline import bootstrap_demo_timeseries, run_and_persist_dispatch


class Command(BaseCommand):
    help = "Populate the database with one representative 15-minute demo week."

    def add_arguments(self, parser):
        parser.add_argument(
            "--force",
            action="store_true",
            help="Delete existing input and dispatch rows before bootstrapping.",
        )
        parser.add_argument(
            "--with-dispatch",
            action="store_true",
            help="Also run battery dispatch after bootstrapping input time series.",
        )
        parser.add_argument(
            "--solar-csv",
            type=str,
            default=None,
            help=(
                "Optional path to a renewables.ninja hourly CSV. "
                "Expected common columns: time,electricity."
            ),
        )

    def handle(self, *args, **options):
        solar_csv = options["solar_csv"]
        solar_csv_path = Path(solar_csv) if solar_csv else None

        bootstrap_result = bootstrap_demo_timeseries(
            force=options["force"],
            solar_csv_path=solar_csv_path,
        )

        self.stdout.write(self.style.SUCCESS("Demo time series bootstrap complete."))
        self.stdout.write(f"Rows: {bootstrap_result.time_series_points}")
        self.stdout.write(f"Solar source: {bootstrap_result.solar_source}")
        self.stdout.write(
            f"Solar range: "
            f"{bootstrap_result.min_solar_kw:.1f} to {bootstrap_result.max_solar_kw:.1f} kW"
        )
        self.stdout.write(
            f"Load range: "
            f"{bootstrap_result.min_load_kw:.1f} to {bootstrap_result.max_load_kw:.1f} kW"
        )

        if options["with_dispatch"]:
            dispatch_result = run_and_persist_dispatch()

            self.stdout.write(self.style.SUCCESS("Dispatch run complete."))
            self.stdout.write(f"Dispatch rows: {dispatch_result.dispatch_intervals}")
            self.stdout.write(
                f"Grid import: {dispatch_result.total_grid_import_kwh:.1f} kWh"
            )
            self.stdout.write(
                f"Battery charged: {dispatch_result.total_battery_charge_kwh:.1f} kWh"
            )
            self.stdout.write(
                f"Battery discharged: "
                f"{dispatch_result.total_battery_discharge_kwh:.1f} kWh"
            )
            self.stdout.write(f"Final SoC: {dispatch_result.final_soc_pct:.1f}%")