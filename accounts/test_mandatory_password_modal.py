from django.contrib.auth.models import User
from django.http import HttpResponse
from django.template.loader import render_to_string
from django.test import Client, RequestFactory, TestCase
from django.urls import reverse

from accounts.middleware import ForcePasswordChangeMiddleware
from accounts.views import _post_login_redirect
from user.models import UserProfile


class ImportedAccountPasswordChangeTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='imported@example.com',
            email='imported@example.com',
            password='Temporary1!',
        )
        self.profile = UserProfile.objects.create(
            user=self.user,
            role='student',
            must_change_password=True,
        )
        self.client.force_login(self.user)

    def test_flagged_account_is_kept_on_dashboard_and_other_pages_redirect(self):
        middleware = ForcePasswordChangeMiddleware(lambda request: HttpResponse('allowed'))
        request = RequestFactory().get(reverse('userReports'))
        request.user = self.user

        response = middleware(request)

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response['Location'], reverse('userDashboard'))

        request = RequestFactory().get(reverse('userDashboard'))
        request.user = self.user
        response = middleware(request)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content, b'allowed')

    def test_ajax_password_change_clears_import_flag_and_keeps_session(self):
        response = self.client.post(
            reverse('force_password_change'),
            {
                'new_password': 'Campus1!',
                'confirm_new_password': 'Campus1!',
            },
            HTTP_X_REQUESTED_WITH='XMLHttpRequest',
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()['ok'])
        self.assertEqual(response.json()['redirect_url'], reverse('userDashboard'))
        self.profile.refresh_from_db()
        self.user.refresh_from_db()
        self.assertFalse(self.profile.must_change_password)
        self.assertTrue(self.user.check_password('Campus1!'))
        self.assertIn('_auth_user_id', self.client.session)

    def test_login_sends_flagged_account_to_dashboard_before_pending_next(self):
        request = RequestFactory().get(reverse('login'))
        request.user = self.user
        request.session = {'pending_login_next': reverse('userReports')}

        response = _post_login_redirect(request, self.user)

        self.assertEqual(response['Location'], reverse('userDashboard'))
        self.assertIn('pending_login_next', request.session)

    def test_modal_lists_the_signup_password_requirements(self):
        html = render_to_string('accounts/forced_password_modal.html', {'user': self.user})

        self.assertIn('At least 8 characters, maximum 16; no spaces', html)
        self.assertIn('1 uppercase letter', html)
        self.assertIn('1 number', html)
        self.assertIn('1 symbol', html)

    def test_normal_user_is_not_forced_into_the_password_change_flow(self):
        self.profile.must_change_password = False
        self.profile.save(update_fields=['must_change_password'])
        middleware = ForcePasswordChangeMiddleware(lambda request: HttpResponse('allowed'))
        request = RequestFactory().get(reverse('userReports'))
        request.user = self.user

        response = middleware(request)

        self.assertEqual(response.status_code, 200)
