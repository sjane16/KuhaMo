from django.shortcuts import render, redirect 
from .forms import StudentLogin, AdminLogin
from django.contrib.auth import authenticate, login
from django.contrib import messages
from django.views.decorators.cache import never_cache
from django.contrib.messages import get_messages
from axes.decorators import axes_dispatch
from axes.utils import reset_request
from django.core.exceptions import PermissionDenied
from django_ratelimit.core import is_ratelimited
from security.models import HoneypotHit
from security.utils import is_ip_flagged

@never_cache
def splash_screen(request):
    return render(request, 'accounts/index.html')


@never_cache
def student_login(request):

    if request.method == 'POST':
        ip = request.META.get('REMOTE_ADDR')

        if is_ip_flagged(ip):
            storage = get_messages(request)
            storage.used = True
            messages.error(request, "Invalid student ID or password")
            return render(request, 'accounts/student_login.html', {'form': StudentLogin()})

        if request.POST.get('website'):
            HoneypotHit.objects.create(
                trigger_type = 'form_field',
                path=request.path,
                ip_address=request.META.get('REMOTE_ADDR'),
                user_agent=request.META.get('HTTP_USER_AGENT', ''),
                extra_info=f"Bot filled honeypot field with: {request.POST.get('website')}"
            )
            storage = get_messages(request)
            storage.used = True
            messages.error(request, "Invalid student ID or password")
            return render(request, 'accounts/student_login.html', {'form': StudentLogin()})

        if is_ratelimited(request, key='ip', rate='5/m', method='POST', increment=True, fn=student_login):
            messages.error(request, "Too many login attempts. Please try again later")
            return render(request, 'accounts/student_login.html', {'form': StudentLogin()})
        form = StudentLogin(data = request.POST)
        if form.is_valid():
            student_id = form.cleaned_data.get('student_id')
            student_password = form.cleaned_data.get('student_password')

            try:
                user = authenticate(request, username=student_id, password=student_password)

                if user is not None:
                    login(request, user)
                    reset_request(request)
                    messages.success(request, "Welcome back! You have successfully logged in")
                    return redirect('/user/user_dashboard/')
                else:
                    storage = get_messages(request)
                    storage.used = True
                    messages.error(request, "Invalid student ID or password")
            
            except PermissionDenied:
                storage = get_messages(request)
                storage.used = True
                messages.error(request, "Access denied. Your account has been temporarily locked due to 5 failed login attempts. Please try again after 30 minutes")
            
            except Exception as e:
                storage =  get_messages(request)
                storage.used = True 
                messages.error(request, "An authentication gateway failure occured. Please contact system admin")
        else:
            storage = get_messages(request)
            storage.used = True
            messages.error(request, "Please fill up all required fields correctly")
    else:
        form = StudentLogin()

    return render(request, 'accounts/student_login.html', {'form': form})

@never_cache
def admin_login(request):

    if request.method == 'POST':
        ip = request.META.get('REMOTE_ADDR')

        if is_ip_flagged(ip):
            storage = get_messages(request)
            storage.used = True
            messages.error(request, "Invalid administrator credentials")
            return render(request, 'accounts/admin_login.html', {'form': AdminLogin()})


        if request.POST.get('website'):
            HoneypotHit.objects.create(
                trigger_type = 'form_field',
                path=request.path,
                ip_address=request.META.get('REMOTE_ADDR'),
                user_agent=request.META.get('HTTP_USER_AGENT', ''),
                extra_info=f"Bot filled honeypot field with: {request.POST.get('website')}"
            )
            storage = get_messages(request)
            storage.used = True
            messages.error(request, "Invalid administrator credentials")
            return render(request, 'accounts/admin_login.html', {'form': AdminLogin()})


        if is_ratelimited(request, key='ip', rate='5/m', method='POST', increment=True, fn=admin_login):
            messages.error(request, "Too many login attempts. Please try again later")
            return render(request, 'accounts/admin_login.html', {'form': AdminLogin()})

        form = AdminLogin(data=request.POST)
        if form.is_valid():
            admin_id = form.cleaned_data.get('admin_id')
            admin_password = form.cleaned_data.get('admin_password')

            try:
                user = authenticate(request, username=admin_id, password=admin_password)

                if user is not None:
                    if user.is_staff or user.is_superuser:
                        login(request, user)
                        reset_request(request)
                        messages.success(request, "Welcome back! You have successfully logged in")
                        return redirect('/adm/dashboard/')
                    else:
                        storage = get_messages(request)
                        storage.used = True 
                        messages.error(request, "Access denied. Your account does not have administrative privileges")
                else:
                    storage = get_messages(request)
                    storage.used = True
                    messages.error(request, "Invalid administrator credentials")
            
            except PermissionDenied:
                storage = get_messages(request)
                storage.used = True
                messages.error(request, "Access denied. Administrative access has been locked due to 5 failed verification attempts. Please try again after 30 minutes")

            except Exception as e:
                storage = get_messages(request) 
                storage.used = True
                messages.error(request, "An administrative authentication gateway failure occurred")
        else:
            storage = get_messages(request)
            storage.used = True
            messages.error(request, "Please fill up all required fields correctly")
            
    else:  
        form = AdminLogin()

    return render(request, 'accounts/admin_login.html', {'form': form})

def custom_lockout(request, credentials=None, *args, **kwargs):
    storage = get_messages(request)
    storage.used = True 

    messages.error(request, "Access denied. Your account has been temporarily locked due to 5 failed login attempts. Please try again after 30 minutes")

    if request.path and 'admin' in request.path:
        return redirect('admin_login')
    return redirect('student_login')
    
