import json
from datetime import timedelta

from django.contrib.auth.models import User
from django.db import connection
from django.test import RequestFactory, TestCase
from django.test.utils import CaptureQueriesContext
from django.utils import timezone

from user.models import Notification, Report, SurveyResponse
from user.views import dashboardStatsAjax, get_notifications_page_ajax, userSurveyAjax

from .views import (
    build_survey_analysis_context,
    build_survey_responses_list,
    get_notifications_page_ajax_admin,
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

