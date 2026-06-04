from django.shortcuts import render, redirect 
from .forms import StudentLogin, AdminLogin
from django.contrib.auth import authenticate, login
from django.contrib import messages
from django.contrib.messages import get_messages

def splash_screen(request):
    return render(request, 'accounts/index.html')

def student_login(request):
    if request.method == 'POST':
        form = StudentLogin(data = request.POST)
        if form.is_valid():
            student_id = form.cleaned_data.get('student_id')
            student_password = form.cleaned_data.get('student_password')
            user = authenticate(username=student_id, password=student_password)

            if user is not None:
                login(request, user)
                messages.success(request,"Welcome back, student!")
                return redirect('/student_dashboard')
            else:
                storage = get_messages(request)
                storage.used = True
                messages.error(request, "Invalid student ID or password")
        else:
            storage = get_messages(request)
            storage.used = True
            messages.error(request, "Invalid student ID or password")
    else:
        form = StudentLogin()

    return render(request, 'accounts/student_login.html', {'form': form})

def admin_login(request):
    if request.method == 'POST':
        form = AdminLogin(data = request.POST)

        if form.is_valid():
            admin_id = form.cleaned_data.get('admin_id')
            admin_password = form.cleaned_data.get('admin_password')
            user = authenticate(username=admin_id, password=admin_password)

            if user is not None:

                if user.is_staff or user.is_superuser:
                    login(request, user)
                    messages.success(request,"Welcome back, admin!")
                    return redirect('/admin_dashboard')
                else:
                    storage = get_messages(request)
                    storage.used = True 
                    messages.error(request, "Invalid ID or password")
            else:
                storage = get_messages(request)
                storage.used = True 
                messages.error(request, "Invalid ID or password")
        else:
            storage = get_messages(request)
            storage.used = True
            messages.error(request, "Invalid ID or password")
    else:
        form = AdminLogin()

    return render(request, 'accounts/admin_login.html', {'form':form})

