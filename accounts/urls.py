from django.urls import path 
from . import views 

urlpatterns = [
    path('index/', views.splash_screen, name='index'),
    path('student_login/', views.student_login, name='student_login'),
    path('admin_login/', views.admin_login, name='admin_login'),
]