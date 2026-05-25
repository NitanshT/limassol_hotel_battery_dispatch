from django.http import HttpRequest, HttpResponse


def weekly_report(request: HttpRequest) -> HttpResponse:
    return HttpResponse(
        "Weekly report endpoint is wired. Reporting implementation comes in a later commit."
    )