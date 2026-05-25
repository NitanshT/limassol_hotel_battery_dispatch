from __future__ import annotations

from django.core.management.base import BaseCommand

from app.services.data_pipeline import run_and_persist_dispatch


class Command(BaseCommand):
    help = "Run greedy battery dispatch against stored time-series rows."

    def handle(self, *args, **options):
        result = run_and_persist_dispatch()

        self.stdout.write(self.style.SUCCESS("Dispatch run complete."))
        self.stdout.write(f"Rows: {result.dispatch_intervals}")
        self.stdout.write(f"Grid import: {result.total_grid_import_kwh:.1f} kWh")
        self.stdout.write(f"Battery charged: {result.total_battery_charge_kwh:.1f} kWh")
        self.stdout.write(
            f"Battery discharged: {result.total_battery_discharge_kwh:.1f} kWh"
        )
        self.stdout.write(f"Final SoC: {result.final_soc_pct:.1f}%")