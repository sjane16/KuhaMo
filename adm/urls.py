from django.urls import path
from django.contrib.auth import views as auth_views
from user.decorators import admin_required
from . import views

urlpatterns = [
    path('dashboard/', admin_required(views.dashboard), name='dashboard'),
    path('base/', admin_required(views.base), name='base'),
    path('reports/', admin_required(views.reports), name='reports'),
    path('reports/<int:report_id>/', admin_required(views.report_detail), name='adm_report_detail'),
    path('reports/<int:report_id>/save/', admin_required(views.report_save), name='adm_report_save'),
    path('reports/<int:report_id>/status/', admin_required(views.report_status), name='adm_report_status'),
    path('logout/', auth_views.LogoutView.as_view(next_page='admin_login'), name='logoutadmin'),
    path('menu/', admin_required(views.ProfileMenu), name='ProfileMenu'),
    path('universitymap/', admin_required(views.universitymap), name='universitymap'),
    path('survey-analysis/', admin_required(views.survey_analysis), name='survey_analysis'),
    path('api/buildings/', admin_required(views.buildings_api), name='buildings_api'),
    path('api/floor-map/', admin_required(views.floor_map_api), name='floor_map_api'),
    path('calendar/', admin_required(views.calendar_view), name='calendar_view'),
]
