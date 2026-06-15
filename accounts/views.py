from django.shortcuts import render, redirect 
from .forms import StudentLogin, AdminLogin
from django.contrib.auth import authenticate, login
from django.contrib import messages
from django.contrib.messages import get_messages
from django_ratelimit.decorators import ratelimit
from axes.decorators import axes_dispatch
from axes.utils import reset_request
from django.core.exceptions import PermissionDenied


def splash_screen(request):
    return render(request, 'accounts/index.html')

@ratelimit(key='ip', rate='5/m', method='POST', block=False)
def student_login(request):

    if getattr(request, 'limited', False):
        messages.error(request, "Too many login attempts. Please try again later.")
        return render(request, 'accounts/student_login.html')
    
    if request.method == 'POST':
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

@ratelimit(key='ip', rate='5/m', method='POST', block=False)
def admin_login(request):

    if getattr(request, 'limited', False):
        messages.error(request, "Too many login attempts. Please try again later.")
        return render(request, 'accounts/admin_login.html')

    if request.method == 'POST':
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