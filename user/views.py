from django.shortcuts import render

def menu(request):
    return render(request, 'user/menu.html', {
        "active_page": "menu"
    })

def base(request):
    return render(request, 'user/layouts/base.html', {
        "active_page": "base"
    })



