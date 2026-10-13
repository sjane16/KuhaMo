from importlib import import_module
from types import SimpleNamespace
from unittest.mock import patch

from django.apps import apps
from django.contrib.auth.models import User
from django.test import RequestFactory, TestCase

from .forms import ProfilePasswordChangeForm
from .models import Report, UserProfile
from .views import menu
from adm.views import ProfileMenu, _filter_admin_reports, build_personnel_rows


class ProfilePasswordTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='profile-test', password='Original1!')
        UserProfile.objects.create(user=self.user, role='student')

    def test_invalid_password_requests_do_not_change_password(self):
        cases = [
            ('Wrong1!', 'Replacement2!', 'Replacement2!'),
            ('Original1!', 'Replacement2!', 'Different2!'),
            ('Original1!', 'Original1!', 'Original1!'),
            ('Original1!', 'weak', 'weak'),
            ('', '', ''),
        ]
        for old, new, confirm in cases:
            form = ProfilePasswordChangeForm(self.user, {
                'old_password': old, 'new_password1': new, 'new_password2': confirm,
            })
            self.assertFalse(form.is_valid())
            self.user.refresh_from_db()
            self.assertTrue(self.user.check_password('Original1!'))

    def test_both_views_preserve_device_invalidation_audit_and_session_update(self):
        for view, module in ((menu, 'user.views'), (ProfileMenu, 'adm.views')):
            self.user.set_password('Original1!')
            self.user.save()
            request = RequestFactory().post('/profile/', {
                'change_password': '1', 'old_password': 'Original1!',
                'new_password1': 'Replacement2!', 'new_password2': 'Replacement2!',
            })
            request.user = self.user
            with patch(module + '.messages'), patch(module + '.log_event') as audit, patch(
                module + '.invalidate_trusted_devices'
            ) as invalidate, patch(module + '.update_session_auth_hash') as update_session:
                response = view(request)
            self.assertEqual(response.status_code, 302)
            self.user.refresh_from_db()
            self.assertTrue(self.user.check_password('Replacement2!'))
            invalidate.assert_called_once_with(self.user)
            audit.assert_called_once_with(request, 'password_changed', user=self.user, where='Edit Profile')
            update_session.assert_called_once_with(request, self.user)
