from __future__ import annotations

import json

from django.http import HttpRequest, HttpResponse
from django.shortcuts import render

from app.services.reporting import ReportUnavailableError, get_weekly_report


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