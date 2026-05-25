from django.contrib import admin

from .models import DispatchInterval, TimeSeriesPoint


@admin.register(TimeSeriesPoint)
class TimeSeriesPointAdmin(admin.ModelAdmin):
    list_display = (
        "timestamp",
        "solar_kw",
        "load_kw",
        "grid_price_eur_per_kwh",
    )
    list_filter = ("grid_price_eur_per_kwh",)
    search_fields = ("timestamp",)
    ordering = ("timestamp",)


@admin.register(DispatchInterval)
class DispatchIntervalAdmin(admin.ModelAdmin):
    list_display = (
        "point",
        "solar_to_load_kw",
        "battery_charge_kw",
        "battery_discharge_kw",
        "grid_import_kw",
        "curtailed_solar_kw",
        "soc_pct",
    )
    ordering = ("point__timestamp",)