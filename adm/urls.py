from django.urls import path
from django.contrib.auth import views as auth_views
from user.decorators import admin_required
from . import views

urlpatterns = [
    path('dashboard/', admin_required(views.dashboard), name='dashboard'),
    path('base/', admin_required(views.base), name='base'),
    path('reports/', admin_required(views.reports), name='reports'),
    path('reports/<int:report_id>/', admin_required(views.report_detail), name='adm_report_detail'),
    path('reports/<int:report_id>/job-order/pdf/', admin_required(views.export_job_order_pdf_admin), name='exportJobOrderPDFAdmin'),
    path('reports/<int:report_id>/save/', admin_required(views.report_save), name='adm_report_save'),
    path('reports/<int:report_id>/status/', admin_required(views.report_status), name='adm_report_status'),
    path('logout/', auth_views.LogoutView.as_view(next_page='admin_login'), name='logoutadmin'),
    path('menu/', admin_required(views.ProfileMenu), name='ProfileMenu'),
    path('ajax/menu/', admin_required(views.adm_menu_ajax), name='adm_menu_ajax'),
    path('survey-analysis/', admin_required(views.survey_analysis), name='survey_analysis'),
    path('ajax/survey-analysis/', admin_required(views.adm_survey_analysis_ajax), name='adm_survey_analysis_ajax'),
    path('ajax/survey-analysis/responses/', admin_required(views.adm_survey_responses_ajax), name='adm_survey_responses_ajax'),
    path('notifications/', admin_required(views.adminNotifications), name='adminNotifications'),
    path('ajax/notifications/', admin_required(views.get_notifications_ajax_admin), name='get_notifications_ajax_admin'),
    path('ajax/notifications-page/', admin_required(views.get_notifications_page_ajax_admin), name='get_notifications_page_ajax_admin'),
    path('ajax/notifications/mark-all-read/', admin_required(views.mark_all_notifications_read_admin), name='mark_all_notifications_read_admin'),
    path('notifications/<int:notification_id>/view/', admin_required(views.view_notification_admin), name='view_notification_admin'),
    path('ajax/reports/', admin_required(views.adm_reports_ajax), name='adm_reports_ajax'),
    path('ajax/dashboard/', admin_required(views.adm_dashboard_ajax), name='adm_dashboard_ajax'),

    

]