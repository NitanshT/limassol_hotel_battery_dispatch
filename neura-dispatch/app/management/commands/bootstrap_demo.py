from __future__ import annotations

from pathlib import Path

from django.core.management.base import BaseCommand

from app.services.data_import import bootstrap_demo_timeseries


class Command(BaseCommand):
    help = "Populate the database with one representative 15-minute demo week."

    def add_arguments(self, parser):
        parser.add_argument(
            "--force",
            action="store_true",
            help="Delete existing input and dispatch rows before bootstrapping.",
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

        result = bootstrap_demo_timeseries(
            force=options["force"],
            solar_csv_path=solar_csv_path,
        )

        self.stdout.write(self.style.SUCCESS("Demo time series bootstrap complete."))
        self.stdout.write(f"Rows: {result.time_series_points}")
        self.stdout.write(f"Solar source: {result.solar_source}")
        self.stdout.write(
            f"Solar range: {result.min_solar_kw:.1f} to {result.max_solar_kw:.1f} kW"
        )
        self.stdout.write(
            f"Load range: {result.min_load_kw:.1f} to {result.max_load_kw:.1f} kW"
        )