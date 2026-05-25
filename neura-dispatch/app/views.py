from __future__ import annotations

import json

from django.http import HttpRequest, HttpResponse
from django.shortcuts import render

from app.services.reporting import ReportUnavailableError, get_weekly_report
from app.services.what_if import (
    WhatIfInputs,
    WhatIfUnavailableError,
    run_default_comparison_scenarios,
    run_what_if_scenario,
)


def weekly_report(request: HttpRequest) -> HttpResponse:
    try:
        report = get_weekly_report()
    except ReportUnavailableError as error:
        return render(
            request,
            "reports/weekly.html",
            {
                "report": None,
                "error_message": str(error),
            },
        )

    return render(
        request,
        "reports/weekly.html",
        {
            "report": report,
            "chart_labels_json": json.dumps(report.labels),
            "soc_pct_series_json": json.dumps(report.soc_pct_series),
        },
    )

def what_if_report(request: HttpRequest) -> HttpResponse:
    error_message = None
    custom_result = None
    comparison_results = []

    pv_kwp = request.GET.get("pv_kwp", "200")
    battery_kwh = request.GET.get("battery_kwh", "400")

    try:
        inputs = WhatIfInputs(
            pv_kwp=float(pv_kwp),
            battery_kwh=float(battery_kwh),
        )
        custom_result = run_what_if_scenario(inputs)
        comparison_results = run_default_comparison_scenarios()
    except (ValueError, WhatIfUnavailableError) as error:
        error_message = str(error)

    return render(
        request,
        "reports/what_if.html",
        {
            "pv_kwp": pv_kwp,
            "battery_kwh": battery_kwh,
            "custom_result": custom_result,
            "comparison_results": comparison_results,
            "error_message": error_message,
        },
    )