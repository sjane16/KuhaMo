from django.urls import path
from django.contrib.auth import views as auth_views
from . import views

urlpatterns = [
    path('menu/', views.menu, name='menu'),
    path('base/', views.base, name='base'),
    path('user_dashboard/', views.userDashboard, name='userDashboard'),
    path('report_form/', views.reportForm, name='reportForm'),
    path('user_reports/', views.userReports, name='userReports'),
    path('reported_issue/<int:report_id>/', views.reportedIssue, name='reportedIssue'),
    path('logout/', auth_views.LogoutView.as_view(next_page='student_login'), name = 'logout'),
]