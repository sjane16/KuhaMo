import json
from datetime import timedelta
from unittest.mock import patch

from django.contrib.auth.models import User
from django.db import connection
from django.test import RequestFactory, TestCase
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from django.utils import timezone
from django.core.cache import cache

from user.models import Notification, Report, SurveyResponse
from user.views import dashboardStatsAjax, get_notifications_page_ajax, userSurveyAjax

from .views import (
    build_survey_analysis_context,
    build_survey_responses_list,
    get_notifications_page_ajax_admin,
    _build_dashboard_data,
    _build_resolution_buckets,
    _cached_dashboard_data,
    _reports_for_resolution_buckets,
    _build_pdf_priority_tables,
)


class SurveyAnalyticsPaginationTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        user = User.objects.create_user(username="survey-pagination-test")
        reports = []
        for index in range(26):
            started_at = timezone.now()
            report = Report.objects.create(
                user=user,
                job_order_id=f"TEST-SURVEY-{index}",
                category="electrical",
                location="Test Building, 1, 101",
                description="Test report",
                status="closed",
                priority="standard",
                assigned_personnel_data=[{"name": "Mr. Remigio"}],
                in_progress_at=started_at,
                accomplished_at=started_at + timedelta(hours=1),
            )
            reports.append(report)
            SurveyResponse.objects.create(
                report=report,
                quality=5,
                quantity=4,
                timeliness=3,
            )
        Notification.objects.bulk_create([
            Notification(user=user, report=report, message=f"Notification {index}")
            for index, report in enumerate(reports)
        ])
        cls.user = user

    def test_responses_are_filtered_and_paginated_in_the_database(self):
        with CaptureQueriesContext(connection) as queries:
            first_page, page = build_survey_responses_list(1)

        second_page, second_page_obj = build_survey_responses_list(2)
        self.assertEqual(len(first_page), 25)
        self.assertEqual(len(second_page), 1)
        self.assertEqual(page.paginator.count, 26)
        self.assertEqual(second_page_obj.number, 2)
        self.assertLessEqual(len(queries), 2)

    def test_analytics_aggregate_scores_and_do_not_issue_survey_n_plus_one(self):
        with CaptureQueriesContext(connection) as queries:
            context = build_survey_analysis_context()

        self.assertEqual(context["total_surveys"], 26)
        self.assertEqual(context["avg_rating"], 4.0)
        self.assertEqual(context["rating_counts"], {1: 0, 2: 0, 3: 26, 4: 26, 5: 26})
        self.assertEqual(context["responses_total_count"], 26)
        self.assertLessEqual(len(queries), 4)

    def test_user_survey_history_is_paginated(self):
        request = RequestFactory().get("/user/surveys/?page=2")
        request.user = self.user

        response = userSurveyAjax(request)
        payload = json.loads(response.content)

        self.assertIn("Page 2 of 2", payload["html"])

    def test_dashboard_greeting_includes_logged_in_user_on_both_layouts(self):
        self.user.first_name = "Jane"
        request = RequestFactory().get("/user/dashboard/stats/")
        request.user = self.user

        payload = json.loads(dashboardStatsAjax(request).content)

        self.assertIn("Hello, Jane!", payload["mobile_html"])
        self.assertIn("Hello, Jane!", payload["desktop_html"])

    def test_user_notifications_are_paginated(self):
        request = RequestFactory().get("/user/notifications/ajax/?page=2")
        request.user = self.user

        response = get_notifications_page_ajax(request)
        payload = json.loads(response.content)

        self.assertEqual(payload["current_page"], 2)
        self.assertEqual(payload["total_count"], 26)
        self.assertIn("Page 2 of 2", payload["html"])

    def test_admin_notifications_are_paginated(self):
        request = RequestFactory().get("/adm/notifications/ajax/?page=2")
        request.user = self.user

        response = get_notifications_page_ajax_admin(request)
        payload = json.loads(response.content)

        self.assertEqual(payload["current_page"], 2)
        self.assertEqual(payload["total_count"], 26)
        self.assertIn("Page 2 of 2", payload["html"])

    def test_dashboard_resolution_buckets_use_one_query(self):
        buckets = _build_resolution_buckets("7", timezone.now())
        with CaptureQueriesContext(connection) as queries:
            reports_by_bucket = _reports_for_resolution_buckets(buckets)

        self.assertEqual(len(reports_by_bucket), 7)
        self.assertEqual(sum(map(len, reports_by_bucket)), 26)
        self.assertEqual(len(queries), 1)

    def test_dashboard_aggregates_preserve_report_and_rating_totals(self):
        dashboard = _build_dashboard_data("7")

        self.assertEqual(dashboard["avg_satisfaction"], 4.0)
        self.assertEqual(dashboard["satisfaction_counts"], [26, 26, 26, 0, 0])
        self.assertEqual(sum(dashboard["status_data"]), 26)
        self.assertEqual(sum(dashboard["categories_counts"]), 26)

    def test_pdf_priority_tables_use_one_query_for_all_buckets(self):
        with CaptureQueriesContext(connection) as queries:
            today = timezone.localdate()
            tables = _build_pdf_priority_tables(today, today)

        self.assertEqual(len(tables), 3)
        standard_table = next(table for table in tables if table["code"] == "standard")
        self.assertEqual(standard_table["completed"], 26)
        self.assertEqual(len(queries), 1)

    def test_dashboard_analytics_cache_reuses_result_for_same_period(self):
        cache.clear()
        self.addCleanup(cache.clear)
        with patch("adm.views._build_dashboard_data", return_value={"cached": True}) as build:
            first = _cached_dashboard_data("cache-test")
            second = _cached_dashboard_data("cache-test")

        self.assertEqual(first, second)
        build.assert_called_once()


class PendingReportProgressionTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_user(username="progression-admin", is_staff=True)
        self.reporter = User.objects.create_user(username="progression-reporter")
        self.client.force_login(self.admin)
        self.report = Report.objects.create(
            user=self.reporter,
            job_order_id="PROGRESSION-TEST",
            category="electrical",
            location="Test Building, First Floor, Room 1",
            description="Test report",
        )

    def save_report(self, **overrides):
        data = {
            "category": "electrical",
            "priority": "standard",
            "personnel_names": ["remigio"],
            "pending_awaiting_personnel": "1",
            "findings": "Inspected and identified the issue.",
            "recommendation": "Replace the damaged part.",
        }
        data.update(overrides)
        return self.client.post(reverse("adm_report_save", args=[self.report.pk]), data)

    def test_pending_form_marks_full_width_and_conditional_requirements(self):
        response = self.client.get(reverse("adm_report_detail", args=[self.report.pk]))

        self.assertEqual(response.content.count(b'data-cdd-class="w-full"'), 2)
        self.assertContains(response, 'class="flex-1 min-w-0 p-6 space-y-8 margin-bottom-8"')
        self.assertNotContains(response, "lg:max-h-[80vh]")
        self.assertContains(response, "Materials Available")
        self.assertContains(response, "Required if Materials Available is unchecked")
        self.assertContains(response, "Findings")
        self.assertContains(response, "Recommendation")

    def test_materials_available_allows_progress_without_a_material_list(self):
        response = self.save_report(pending_awaiting_materials="1")

        self.assertEqual(response.status_code, 302)
        self.report.refresh_from_db()
        self.assertEqual(self.report.status, "in_progress")
        self.assertEqual(self.report.materials_required, [])

    def test_materials_unavailable_needs_one_complete_material_row(self):
        response = self.save_report(
            mat_qty=["1"],
            mat_unit=["pcs"],
            mat_desc=["Replacement cable"],
        )

        self.assertEqual(response.status_code, 302)
        self.report.refresh_from_db()
        self.assertEqual(self.report.status, "in_progress")
        self.assertEqual(self.report.materials_required, [{
            "qty": "1", "unit": "pcs", "description": "Replacement cable",
        }])

    def test_materials_unavailable_without_complete_row_stays_pending(self):
        self.save_report()

        self.report.refresh_from_db()
        self.assertEqual(self.report.status, "pending")


    def test_incomplete_material_row_stays_pending(self):
        self.save_report(
            mat_qty=["1"],
            mat_unit=[""],
            mat_desc=["Replacement cable"],
        )

        self.report.refresh_from_db()
        self.assertEqual(self.report.status, "pending")
        self.assertEqual(self.report.materials_required, [])

    def test_findings_and_recommendation_are_required_for_progression(self):
        self.save_report(pending_awaiting_materials="1", findings="")
        self.report.refresh_from_db()
        self.assertEqual(self.report.status, "pending")

        self.save_report(
            pending_awaiting_materials="1",
            findings="Inspection completed.",
            recommendation="",
        )
        self.report.refresh_from_db()
        self.assertEqual(self.report.status, "pending")

    def test_priority_and_with_assigned_personnel_are_required_for_progression(self):
        self.save_report(pending_awaiting_materials="1", priority="")
        self.report.refresh_from_db()
        self.assertEqual(self.report.status, "pending")

        self.save_report(pending_awaiting_materials="1", pending_awaiting_personnel="")
        self.report.refresh_from_db()
        self.assertEqual(self.report.status, "pending")


class AdminProfileMenuTests(TestCase):
    def test_profile_summary_omits_redundant_username_row(self):
        admin = User.objects.create_user(
            username="profile-admin",
            email="profile-admin@example.com",
            first_name="Profile",
            last_name="Admin",
            is_staff=True,
        )
        self.client.force_login(admin)

        response = self.client.get(reverse("adm_menu_ajax"))
        html = response.json()["html"]

        self.assertIn(admin.get_full_name(), html)
        self.assertIn(admin.email, html)
        self.assertNotIn(f">{admin.username}</span>", html)
