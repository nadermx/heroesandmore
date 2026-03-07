from django.urls import path
from . import views

app_name = 'affiliates_api'

urlpatterns = [
    path('join/', views.AffiliateJoinView.as_view(), name='join'),
    path('dashboard/', views.AffiliateDashboardView.as_view(), name='dashboard'),
    path('settings/', views.AffiliateSettingsView.as_view(), name='settings'),
    path('referrals/', views.ReferralListView.as_view(), name='referrals'),
    path('commissions/', views.CommissionListView.as_view(), name='commissions'),
    path('payouts/', views.PayoutListView.as_view(), name='payouts'),
]
