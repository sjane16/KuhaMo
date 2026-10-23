from django.shortcuts import redirect
from django.urls import reverse


class ForcePasswordChangeMiddleware:
    """Accounts created by an admin (Excel import) log in with an emailed temporary
    password. Until they choose their own, every page sends them to the change page."""

    ALLOWED_PREFIXES = ('/static/', '/media/', '/user/logout/', '/adm/logout/')

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        user = getattr(request, 'user', None)
        if user is not None and user.is_authenticated:
            profile = getattr(user, 'profile', None)
            if profile is not None and profile.must_change_password:
                change_url = reverse('force_password_change')
                is_admin = user.is_staff or user.is_superuser
                dashboard_url = reverse('dashboard' if is_admin else 'userDashboard')
                dashboard_data_url = reverse('adm_dashboard_ajax' if is_admin else 'dashboardStatsAjax')
                allowed_paths = {change_url, dashboard_url, dashboard_data_url}
                if request.path not in allowed_paths and not request.path.startswith(self.ALLOWED_PREFIXES):
                    return redirect(dashboard_url)
        return self.get_response(request)
