from __future__ import annotations

import os
from pathlib import Path

import requests
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = "Download renewables.ninja hourly PV CSV for the Limassol hotel scenario."

    def add_arguments(self, parser):
        parser.add_argument(
            "--output",
            type=str,
            default="data/renewables_ninja_limassol_hourly.csv",
            help="Output CSV path.",
        )
        parser.add_argument(
            "--date-from",
            type=str,
            default="2025-07-07",
            help="Start date for representative week.",
        )
        parser.add_argument(
            "--date-to",
            type=str,
            default="2025-07-13",
            help="End date for representative week.",
        )

    def handle(self, *args, **options):
        token = os.getenv("RENEWABLES_NINJA_TOKEN")

        if not token:
            raise CommandError(
                "Missing RENEWABLES_NINJA_TOKEN environment variable. "
                "Create an account at renewables.ninja, copy your API token, "
                "then set it before running this command."
            )

        output_path = Path(settings.BASE_DIR) / options["output"]

        session = requests.Session()
        session.headers.update({"Authorization": f"Token {token}"})

        url = "https://www.renewables.ninja/api/data/pv"

        params = {
            "lat": 34.707130,
            "lon": 33.022617,
            "date_from": options["date_from"],
            "date_to": options["date_to"],
            "dataset": "merra2",
            "capacity": 200,
            "system_loss": 0.1,
            "tracking": 0,
            "tilt": 30,
            "azim": 180,
            "format": "csv",
            "local_time": "true",
            "header": "true",
        }

        response = session.get(url, params=params, timeout=60)

        if response.status_code != 200:
            raise CommandError(
                f"renewables.ninja request failed with HTTP {response.status_code}:\n"
                f"{response.text[:1000]}"
            )

        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(response.text, encoding="utf-8")

        self.stdout.write(self.style.SUCCESS("Downloaded renewables.ninja PV CSV."))
        self.stdout.write(f"Saved to: {output_path}")