from django.urls import path
from django.contrib.auth import views as auth_views
from . import views

urlpatterns = [
    path('user_dashboard/', views.userDashboard, name='userDashboard'),
    path('menu/', views.menu, name='menu'),
    path('base/', views.base, name='base'),
    path('survey/submit/<int:report_id>/', views.submitSurvey, name='submitSurvey'),
    path('survey/', views.userSurvey, name='userSurvey'),
    path('report_form/', views.reportForm, name='reportForm'),
    path('user_reports/', views.userReports, name='userReports'),
    path('reported_issue/<int:report_id>/', views.reportedIssue, name='reportedIssue'),
    path('logout/', auth_views.LogoutView.as_view(next_page='student_login'), name = 'logout'),
    path('chatbot/', views.chatbot, name='chatbot'),
    path('chatbot/response/', views.chatbot_response, name='chatbot_response'),
]