from django.urls import path
from . import views

app_name = 'accounts'

urlpatterns = [
    path('settings/', views.settings_view, name='settings'),
    path('dashboard/', views.dashboard_view, name='dashboard'),
    path('seller/', views.seller_dashboard, name='seller_dashboard'),
    path('<str:username>/', views.profile_view, name='profile'),
]
