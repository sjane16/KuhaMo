from django.shortcuts import redirect
from functools  import wraps
from django.views.decorators.cache import never_cache
from django.contrib.auth.views import redirect_to_login

def user_required(view_func):
    @wraps(view_func)
    @never_cache
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect_to_login(        #remembers the requested page in the URL (selected shortcut key)
                request.get_full_path(),
                login_url='login',
            )
        if request.user.is_staff or request.user.is_superuser:
            return redirect('dashboard')
        
        return view_func(request, *args, **kwargs)
    return wrapper

def admin_required(view_func):
    @wraps(view_func)
    @never_cache
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect_to_login(
                request.get_full_path(),
                login_url='login',
            )
        
        if not (request.user.is_staff or request.user.is_superuser):
            return redirect('userDashboard')
        
        return view_func(request, *args, **kwargs)
    return wrapper