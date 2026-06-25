from django.urls import path
from . import views

urlpatterns = [
    path('dashboard/', views.dashboard, name='dashboard'),
    path('base/', views.base, name='base'),
    path('reports/', views.reports, name='reports'),
    path('reports/<int:report_id>/', views.report_detail, name='adm_report_detail'),
    path('reports/<int:report_id>/save/', views.report_save, name='adm_report_save'),
    path('reports/<int:report_id>/status/', views.report_status, name='adm_report_status'),
]