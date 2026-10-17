# Run these tests from the project root (with the virtual environment activated):
# python manage.py test accounts.tests.LandingNavigationTests --verbosity 2
#
# Scope: landing-page links and signed-out redirects. These tests do not verify
# successful login, OTP delivery/verification, browser styling, or middleware.
#
# urlparse separates a redirect URL into its path and query string.
# parse_qs converts a query string into a dictionary of lists.
from urllib.parse import parse_qs, urlparse

# AnonymousUser represents a visitor who has not logged in.
from django.contrib.auth.models import AnonymousUser
# RequestFactory builds requests without a browser or running development server.
# SimpleTestCase blocks database queries by default; these checks need no test data.
from django.test import RequestFactory, SimpleTestCase
# reverse: route name -> URL. resolve: URL -> registered view.
from django.urls import resolve, reverse

# Import the real landing view so its template and URL tags are rendered.
from accounts.views import splash_screen


# Regression tests protect existing navigation against future route changes.
# Django discovers methods whose names start with test_.
class LandingNavigationTests(SimpleTestCase):
    # Django runs setUp before EACH test, giving it a fresh request factory.
    def setUp(self):
        self.factory = RequestFactory()

    # Verify that the landing page renders and includes every expected destination.
    # A removed or misspelled URL name can raise NoReverseMatch here.
    def test_landing_page_renders_with_correct_links(self):
        # Simulate GET /auth/index/. RequestFactory skips middleware, so we
        # explicitly attach the signed-out user normally supplied by middleware.
        request = self.factory.get(reverse('index'))
        request.user = AnonymousUser()

        # Call the real view directly and inspect the HTML response it produces.
        response = splash_screen(request)

        # HTTP 200 means the page was returned successfully.
        self.assertEqual(response.status_code, 200)

        # These are the name= values in urls.py, not template filenames.
        # Include the navigation links and all five feature shortcuts.
        route_names = [
            'login',
            'signup',
            'reportForm',
            'userReports',
            'userSurvey',
            'reports',
            'dashboard',
        ]

        # subTest identifies the failing route and lets other routes be checked.
        for name in route_names:
            with self.subTest(route=name):
                # The rendered HTML must contain a link to this resolved URL.
                self.assertContains(
                    response,
                    f'href="{reverse(name)}"',
                )

    # Verify that protected shortcuts send visitors to the shared login page
    # and preserve the selected destination in the next query parameter.
    def test_signed_out_shortcuts_redirect_to_login(self):
        # Only protected feature pages belong here; login and signup are public.
        route_names = [
            'reportForm',
            'userReports',
            'userSurvey',
            'reports',
            'dashboard',
        ]

        for name in route_names:
            with self.subTest(route=name):
                # Resolve the route name so the test follows the URL configuration.
                destination = reverse(name)

                # Simulate a signed-out visitor opening this shortcut.
                request = self.factory.get(destination)
                request.user = AnonymousUser()

                # Call the URL-registered view, including its role decorator.
                # The decorator must redirect before the feature view runs.
                view = resolve(destination).func
                response = view(request)

                # HTTP 302 tells the browser to visit a different URL.
                self.assertEqual(response.status_code, 302)

                # Example: /auth/login/?next=/user/report_form/
                # Inspect the login path separately from the next parameter.
                redirect_url = urlparse(response.url)

                # Both user and admin shortcuts must use the shared login route.
                self.assertEqual(
                    redirect_url.path,
                    reverse('login'),
                )

                # next must retain the exact page the visitor selected.
                # parse_qs returns lists, so compare against [destination].
                # This checks the redirect value, not the later OTP return flow.
                self.assertEqual(
                    parse_qs(redirect_url.query).get('next'),
                    [destination],
                )