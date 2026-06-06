from django.urls import path
from . import views

urlpatterns = [
    path('menu/', views.menu, name='menu'),
    path('base/', views.base, name='base'),
    path('user_dashboard/', views.userDashboard, name='userDashboard'),
    path('report_form/', views.reportForm, name='reportForm'),
    path('user_reports/', views.userReports, name='userReports'),
    path('reported_issue/<int:report_id>/', views.reportedIssue, name='reportedIssue'),
]