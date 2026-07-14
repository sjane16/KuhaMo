from django.urls import path
from django.contrib.auth import views as auth_views
from .decorators import user_required
from . import views

urlpatterns = [
    path('user_dashboard/', user_required(views.userDashboard), name='userDashboard'),
    path('menu/', user_required(views.menu), name='menu'),
    path('base/', user_required(views.base), name='base'),
    path('survey/submit/<int:report_id>/', user_required(views.submitSurvey), name='submitSurvey'),
    path('survey/', user_required(views.userSurvey), name='userSurvey'),
    path('report_form/', user_required(views.reportForm), name='reportForm'),
    path('user_reports/', user_required(views.userReports), name='userReports'),
    path('reported_issue/<int:report_id>/', user_required(views.reportedIssue), name='reportedIssue'),
    path('logout/', auth_views.LogoutView.as_view(next_page='student_login'), name='logout'),
    path('chatbot/', user_required(views.chatbot), name='chatbot'),
    path('chatbot/response/', user_required(views.chatbot_response), name='chatbot_response'),
    path('ajax/load-floors/', user_required(views.load_floors), name='ajax_load_floors'),
    path('ajax/load-rooms/', user_required(views.load_rooms), name='ajax_load_rooms'),
    path('ajax/predict-category/', user_required(views.predictCategory), name='predictCategory'),
    path('notifications/', user_required(views.userNotifications), name='userNotifications'),
    path('ajax/notifications/', user_required(views.get_notifications_ajax), name='get_notifications_ajax'),
    path('notifications/<int:notification_id>/view/', user_required(views.view_notification), name='view_notification'),
]