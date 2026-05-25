from django.db import models


class TimeSeriesPoint(models.Model):
    """
    One 15-minute input interval for the representative hotel week.

    This stores the three required input series together:
    - solar_kw
    - load_kw
    - grid_price_eur_per_kwh

    A single table is pragmatic here because the dispatch and report always consume
    the three series together.
    """

    timestamp = models.DateTimeField(unique=True, db_index=True)
    solar_kw = models.FloatField()
    load_kw = models.FloatField()
    grid_price_eur_per_kwh = models.FloatField()

    class Meta:
        ordering = ["timestamp"]

    def __str__(self) -> str:
        return (
            f"{self.timestamp.isoformat()} | "
            f"solar={self.solar_kw:.1f} kW | "
            f"load={self.load_kw:.1f} kW | "
            f"price={self.grid_price_eur_per_kwh:.2f} EUR/kWh"
        )


class DispatchInterval(models.Model):
    """
    Battery dispatch result for one 15-minute interval.

    This is derived data. It can be deleted and regenerated from TimeSeriesPoint.
    Keeping it separate makes the input data auditable and avoids mixing measured /
    synthetic data with policy outputs.
    """

    point = models.OneToOneField(
        TimeSeriesPoint,
        on_delete=models.CASCADE,
        related_name="dispatch",
    )

    solar_to_load_kw = models.FloatField()
    battery_charge_kw = models.FloatField()
    battery_discharge_kw = models.FloatField()
    grid_import_kw = models.FloatField()
    curtailed_solar_kw = models.FloatField()

    soc_kwh = models.FloatField()
    soc_pct = models.FloatField()

    class Meta:
        ordering = ["point__timestamp"]

    def __str__(self) -> str:
        return (
            f"{self.point.timestamp.isoformat()} | "
            f"soc={self.soc_pct:.1f}% | "
            f"grid={self.grid_import_kw:.1f} kW"
        )