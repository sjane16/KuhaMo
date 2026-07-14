from django.urls import path
from . import views

urlpatterns = [
    path('administrator/', views.decoy_admin, name='decoy_admin'),
]