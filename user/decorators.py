from django.shortcuts import redirect
from functools  import wraps
from django.views.decorators.cache import never_cache

def user_required(view_func):
    @wraps(view_func)
    @never_cache
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect('login')
        if request.user.is_staff or request.user.is_superuser:
            return redirect('dashboard')
        return view_func(request, *args, **kwargs)
    return wrapper

def admin_required(view_func):
    @wraps(view_func)
    @never_cache
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect('login')
        if not (request.user.is_staff or request.user.is_superuser):
            return redirect('userDashboard')
        return view_func(request, *args, **kwargs)
    return wrapper