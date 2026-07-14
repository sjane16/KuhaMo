from django.urls import path 
from . import views 

urlpatterns = [
    path('index/', views.splash_screen, name='index'),
    path('student_login/', views.student_login, name='student_login'),
    path('staff-portal-x6226/', views.admin_login, name='admin_login'),
]