from django.shortcuts import render

def student_login(request):
    return render(request, 'accounts/student_login.html')

def admin_login(request):
    return render(request, 'accounts/admin_login.html')

def splash_screen(request):
    return render(request, 'accounts/index.html')
