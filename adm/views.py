from django.shortcuts import render

def dashboard(request):
    return render(request, 'dashboard.html', {
        "active_page": "dashboard"
    })

def base(request):
    return render(request, 'layouts/base.html', {
        "active_page": "base"
    })

