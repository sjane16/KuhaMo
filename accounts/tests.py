# Run these tests from the project root (with the virtual environment activated):
# python manage.py test accounts.tests.LandingNavigationTests --verbosity 2
#
# Scope: landing-page links and signed-out redirects. These tests do not verify
# successful login, OTP delivery/verification, browser styling, or middleware.
#
# urlparse separates a redirect URL into its path and query string.
# parse_qs converts a query string into a dictionary of lists.
from urllib.parse import parse_qs, urlparse
from smtplib import SMTPException
from unittest.mock import patch

# AnonymousUser represents a visitor who has not logged in.
from django.contrib.auth.models import AnonymousUser, User
from django.http import HttpResponse
# RequestFactory builds requests without a browser or running development server.
# SimpleTestCase blocks database queries by default; these checks need no test data.
from django.test import RequestFactory, SimpleTestCase, TestCase, override_settings
# reverse: route name -> URL. resolve: URL -> registered view.
from django.urls import resolve, reverse

# Import the real landing view so its template and URL tags are rendered.
from accounts.forms import SignUpForm
from accounts.views import splash_screen
from user.models import UserProfile


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


@override_settings(PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'])
class SignupMergeTests(TestCase):
    def test_signup_roles_and_email_domains(self):
        self.assertEqual(
            [value for value, _ in SignUpForm.base_fields['role'].choices if value],
            ['student', 'faculty', 'staff'],
        )
        for role, email, valid in [
            ('staff', 'worker@gmail.com', True),
            ('staff', 'WORKER@GMAIL.COM', True),
            ('staff', 'worker@yahoo.com', False),
            ('staff', 'worker@udm.edu.ph', False),
            ('staff', 'worker@gmail.com.example.com', False),
            ('student', 'student@udm.edu.ph', True),
            ('faculty', 'faculty@udm.edu.ph', True),
            ('student', 'student@gmail.com', False),
            ('faculty', 'faculty@gmail.com', False),
        ]:
            with self.subTest(role=role, email=email):
                form = SignUpForm(data={'role': role, 'email': email})
                form.is_valid()
                self.assertEqual('email' not in form.errors, valid)
        for role in ('admin', 'med_personnel'):
            form = SignUpForm(data={'role': role, 'email': 'worker@gmail.com'})
            self.assertFalse(form.is_valid())
            self.assertIn('role', form.errors)

    def test_staff_signup_waits_for_head_admin_approval(self):
        session = self.client.session
        session['privacy_viewed'] = True
        session.save()
        with patch('accounts.views.SignUpForm') as form_class, \
             patch('accounts.views.is_ratelimited', return_value=False), \
             patch('accounts.views.send_mail'), \
             patch('accounts.views._render_signup', return_value=HttpResponse('signup')):
            form_class.return_value.is_valid.return_value = True
            form_class.return_value.cleaned_data = {
                'first_name': 'Staff', 'last_name': 'Applicant', 'email': 'staff-applicant@gmail.com',
                'password': 'new-password', 'role': 'staff',
                'department': '', 'phone': '09123456789',
            }
            self.client.post(reverse('signup'))

        user = User.objects.get(email='staff-applicant@gmail.com')
        profile = UserProfile.objects.get(user=user)
        self.assertEqual(profile.role, 'staff')
        self.assertEqual(profile.approval_status, UserProfile.APPROVAL_PENDING)
        self.assertFalse(user.is_active)
        with patch('accounts.views.is_ratelimited', return_value=False):
            response = self.client.post(reverse('verify_otp'), {'otp': profile.otp})
        self.assertRedirects(response, reverse('login'), fetch_redirect_response=False)
        user.refresh_from_db()
        self.assertTrue(user.is_active)
        self.assertFalse(user.is_staff)
        self.assertFalse(user.is_superuser)
        # Verified, but blocked until the Head Admin approves the account
        with patch('accounts.views.is_ratelimited', return_value=False):
            response = self.client.post(reverse('login'), {'email': user.email, 'password': 'new-password'})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "waiting for an administrator")
        self.assertNotIn('_auth_user_id', self.client.session)

        UserProfile.objects.filter(user=user).update(approval_status=UserProfile.APPROVAL_APPROVED)
        with patch('accounts.views.is_ratelimited', return_value=False):
            response = self.client.post(reverse('login'), {'email': user.email, 'password': 'new-password'})
        self.assertRedirects(response, reverse('userDashboard'), fetch_redirect_response=False)
        self.assertEqual(int(self.client.session['_auth_user_id']), user.pk)

    def test_staff_signup_reuse_and_email_failure_cleanup(self):
        for reuse, mail_fails in [(False, False), (False, True), (True, True)]:
            with self.subTest(reuse=reuse, mail_fails=mail_fails):
                email = f'staff-{reuse}-{mail_fails}@gmail.com'
                existing = None
                if reuse:
                    existing = User.objects.create_user(
                        username=email, email=email, password='old-password', is_active=False,
                    )
                    UserProfile.objects.update_or_create(user=existing, defaults={'role': 'staff'})

                session = self.client.session
                session['privacy_viewed'] = True
                session.save()
                with patch('accounts.views.SignUpForm') as form_class, \
                     patch('accounts.views.is_ratelimited', return_value=False), \
                     patch('accounts.views.send_mail', side_effect=SMTPException('offline') if mail_fails else None), \
                     patch('accounts.views._render_signup', return_value=HttpResponse('signup')):
                    form_class.return_value.is_valid.return_value = True
                    form_class.return_value.cleaned_data = {
                        'first_name': 'Test', 'last_name': 'Staff', 'email': email,
                        'password': 'new-password', 'role': 'staff',
                        'department': 'Facilities', 'phone': '09123456789',
                    }
                    response = self.client.post(reverse('signup'))

                saved = User.objects.filter(email=email).first()
                if mail_fails and not reuse:
                    self.assertIsNone(saved)
                else:
                    self.assertIsNotNone(saved)
                    self.assertEqual(UserProfile.objects.get(user=saved).approval_status, UserProfile.APPROVAL_PENDING)
                    if reuse:
                        self.assertEqual(saved.pk, existing.pk)
                    else:
                        self.assertRedirects(response, reverse('verify_otp'), fetch_redirect_response=False)
