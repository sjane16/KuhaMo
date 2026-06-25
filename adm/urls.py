from django.urls import path
from . import views
from django.contrib.auth import views as auth_views


urlpatterns = [
    path('dashboard/', views.dashboard, name='dashboard'),
    path('base/', views.base, name='base'),
    path('reports/', views.reports, name='reports'),
    path('reports/<int:report_id>/', views.report_detail, name='adm_report_detail'),
    path('reports/<int:report_id>/save/', views.report_save, name='adm_report_save'),
    path('reports/<int:report_id>/status/', views.report_status, name='adm_report_status'),
    path('logout/', auth_views.LogoutView.as_view(next_page='admin_login'), name = 'logoutadmin'),
    path('menu/', views.ProfileMenu, name ='ProfileMenu'),
    path('universitymap/', views.universitymap, name ='universitymap'),
    path('api/buildings/', views.buildings_api, name = 'buildings_api'),
    path('api/floor-map/', views.floor_map_api, name= 'floor_map_api'),
]