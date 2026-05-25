from django.urls import path

from . import views

urlpatterns = [
    path("weekly/", views.weekly_report, name="weekly-report"),
    path("what-if/", views.what_if_report, name="what-if-report"),
]