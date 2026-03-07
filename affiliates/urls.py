from django.urls import path
from affiliates import views

app_name = 'affiliates'

urlpatterns = [
    path('', views.dashboard, name='dashboard'),
    path('join/', views.join, name='join'),
    path('referrals/', views.referrals, name='referrals'),
    path('commissions/', views.commissions, name='commissions'),
    path('payouts/', views.payouts, name='payouts'),
    path('settings/', views.payout_settings, name='settings'),
]
