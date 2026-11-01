import json
from datetime import datetime
from types import SimpleNamespace
from unittest.mock import patch
from zoneinfo import ZoneInfo

from django.contrib.auth.models import User
from django.core.cache import cache
from django.template.loader import render_to_string
from django.test import RequestFactory, TestCase, override_settings
from django.urls import reverse

from user.models import UserProfile
from . import views
from .views import _report_month_availability


MANILA = ZoneInfo('Asia/Manila')


@override_settings(PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'])
class MonthlyReportAvailabilityTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.head = User.objects.create_user(username='monthly-report-head', is_staff=True)
        UserProfile.objects.filter(user=cls.head).update(is_head_admin=True)

    def setUp(self):
        cache.clear()
        self.addCleanup(cache.clear)
        self.head.refresh_from_db()
        self.factory = RequestFactory()

    def get_view_response(self, view, route, data=None):
        request = self.factory.get(reverse(route), data or {})
        request.user = self.head
        request._messages = []
        return view(request)

    def post_view_response(self, view, route, data=None):
        request = self.factory.post(reverse(route), data or {})
        request.user = self.head
        return view(request)

    @staticmethod
    def at(year, month, day, hour, minute=0):
        return datetime(year, month, day, hour, minute, tzinfo=MANILA)

    def test_picker_and_ajax_unlock_current_month_at_10pm_manila(self):
        before_cutoff = self.at(2026, 11, 30, 21, 59)
        with patch('adm.views.timezone.now', return_value=before_cutoff):
            availability = _report_month_availability()
            page = render_to_string('dashboard.html', {
                'period': '30',
                'is_head_admin': True,
                **availability,
            })
            self.assertIn('value="2026-10"', page)
            self.assertIn('max="2026-10"', page)
            self.assertIn('scheduleReportMonthAvailabilityRefresh', page)

            data = json.loads(
                self.get_view_response(views.adm_dashboard_ajax, 'adm_dashboard_ajax').content
            )
            self.assertEqual(data['report_month_max'], '2026-10')
            self.assertEqual(data['report_month_unlock_after_ms'], 60_000)

        at_cutoff = self.at(2026, 11, 30, 22)
        with patch('adm.views.timezone.now', return_value=at_cutoff):
            availability = _report_month_availability()
            self.assertEqual(availability['report_month_max'], '2026-11')

    def test_current_and_future_month_are_rejected_before_cutoff(self):
        before_cutoff = self.at(2026, 11, 30, 21, 59)
        with patch('adm.views.timezone.now', return_value=before_cutoff):
            requests = (
                self.get_view_response(
                    views.adm_dashboard_ajax, 'adm_dashboard_ajax', {'report_month': '2026-11'}
                ),
                self.get_view_response(
                    views.dashboard_report_summary, 'dashboard_report_summary', {'report_month': '2026-11'}
                ),
                self.post_view_response(
                    views.export_dashboard_report_pdf,
                    'export_dashboard_report_pdf',
                    {'report_month': '2026-11'},
                ),
                self.get_view_response(
                    views.adm_dashboard_ajax, 'adm_dashboard_ajax', {'report_month': '2026-12'}
                ),
            )

        for response in requests:
            with self.subTest(status=response.status_code):
                self.assertEqual(response.status_code, 400)

    def test_current_month_is_allowed_at_cutoff_and_missing_month_defaults_to_it(self):
        at_cutoff = self.at(2026, 11, 30, 22)
        with patch('adm.views.timezone.now', return_value=at_cutoff):
            summary = self.get_view_response(
                views.dashboard_report_summary,
                'dashboard_report_summary',
                {'report_month': '2026-11'},
            )
            self.assertEqual(summary.status_code, 200)

            with patch('adm.views.pisa.CreatePDF', return_value=SimpleNamespace(err=0)):
                pdf = self.post_view_response(
                    views.export_dashboard_report_pdf, 'export_dashboard_report_pdf'
                )
            self.assertEqual(pdf.status_code, 200)
            self.assertIn('Dashboard_Report_2026-11.pdf', pdf['Content-Disposition'])

    def test_december_unlock_and_january_use_correct_year(self):
        december_cutoff = _report_month_availability(self.at(2026, 12, 31, 22))
        self.assertEqual(december_cutoff['report_month_max'], '2026-12')

        january = _report_month_availability(self.at(2027, 1, 1, 0))
        self.assertEqual(january['report_month_max'], '2026-12')
