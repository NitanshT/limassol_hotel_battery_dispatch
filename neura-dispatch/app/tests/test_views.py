from __future__ import annotations

from django.test import TestCase
from django.urls import reverse


class WeeklyReportViewTests(TestCase):
    def test_weekly_report_view_returns_200_even_without_dispatch_data(self):
        response = self.client.get(reverse("weekly-report"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Report unavailable")